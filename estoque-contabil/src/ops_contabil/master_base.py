"""Base mestre: Posição de Estoque oficial de um mês, usada só como "mês anterior" do PASSO A PASSO.

Não é uma competência: fica fora da Base de Estoque, dos relatórios e da lista de competências.
Guarda apenas o necessário para o passo 2 (CE & MAT, Product Offer End Dt, Season e Year) e aparece
somente como ponto de atenção em Controles e auditoria. Se depois a posição daquele mês for carregada
de novo no sistema (ZMM119 ou .xlsb), a carga mais recente passa a valer e a base mestre deixa de ser usada.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa

from .db import connect
from .ingestion.schema_resolver import SchemaContract, load_contracts, resolve_headers
from .inventory import INVENTORY_COMPANY, _clean_value, _sha256

MASTER_FIELDS = ("center_material_key", "product_offer_end_date", "season", "year")


def ensure_master_base_schema(connection: Any) -> None:
    connection.execute(
        """
        create table if not exists master_base_rows (
            period varchar not null,
            center_material_key varchar,
            product_offer_end_date date,
            season varchar,
            year integer
        );
        create table if not exists master_base_imports (
            period varchar primary key,
            source_path varchar not null,
            source_sha256 varchar not null,
            source_sheet varchar not null,
            header_row integer not null,
            row_count bigint not null,
            fiscal_total double,
            imported_by varchar,
            imported_at timestamp not null default current_timestamp
        );
        """
    )


def _read_master_rows(path: Path, contract: SchemaContract, period: str) -> tuple[list[tuple[Any, ...]], int, float, str]:
    """Lê da aba só as colunas do PASSO A PASSO (e o Vlr Tot Fisc para conferência), linha a linha."""
    from pyxlsb import open_workbook

    with open_workbook(str(path)) as workbook:
        source_sheet = next((name for name in contract.sheet_aliases if name in workbook.sheets), None)
        if source_sheet is None:
            raise ValueError(f"Aba Base Orig. / BASE - CKMR não encontrada em {path.name}")
        with workbook.get_sheet(source_sheet) as worksheet:
            preview = [[cell.v for cell in row] for _, row in zip(range(contract.header_search_rows), worksheet.rows())]
        resolution = resolve_headers(preview, contract)
        positions = resolution.positions
        wanted = ("center_material_key", "company", "plant", "material", "product_offer_end_date", "season", "year", "fiscal_total_amount")

        def cell(row: list[Any], name: str) -> Any:
            position = positions.get(name)
            return None if position is None or position >= len(row) else _clean_value(name, row[position])

        rows: list[tuple[Any, ...]] = []
        fiscal_total = 0.0
        with workbook.get_sheet(source_sheet) as worksheet:
            for source_row, cells in enumerate(worksheet.rows(), start=1):
                if source_row <= resolution.header_row:
                    continue
                row = [item.v for item in cells]
                values = {name: cell(row, name) for name in wanted}
                if values["material"] in (None, ""):
                    continue
                if values["company"] not in (None, "") and str(values["company"]).strip() != INVENTORY_COMPANY:
                    continue
                key = values["center_material_key"] or f"{values['plant'] or ''}{values['material']}"
                year = values["year"]
                try:
                    year = None if year in (None, "") else int(float(year))
                except (TypeError, ValueError):
                    year = None
                season = None if values["season"] in (None, "") else str(values["season"]).strip()
                rows.append((period, str(key), values["product_offer_end_date"], season, year))
                fiscal_total += float(values["fiscal_total_amount"] or 0)
    return rows, resolution.header_row, fiscal_total, source_sheet


def import_master_base(settings: Any, period: str, path: Path, imported_by: str = "") -> dict[str, Any]:
    """Carrega a Posição de Estoque oficial (.xlsb) de `period` como base mestre (não cria competência)."""
    datetime.strptime(period, "%Y-%m")
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Planilha de posição não encontrada: {path}")
    source_hash = _sha256(path)
    contract: SchemaContract = load_contracts(settings.root / "config" / "schemas.yaml")["zmm119_base_orig"]
    staging = Path(os.path.expandvars("%LOCALAPPDATA%")) / "OpsContabil" / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    staged_path = staging / f"master_{source_hash[:16]}.xlsb"
    try:
        if not staged_path.exists() or staged_path.stat().st_size != path.stat().st_size:
            shutil.copy2(path, staged_path)
        rows, header_row, fiscal_total, source_sheet = _read_master_rows(staged_path, contract, period)
    finally:
        staged_path.unlink(missing_ok=True)
    if not rows:
        raise ValueError("A planilha foi lida, mas não tem linhas de estoque depois do cabeçalho.")
    batch = pa.Table.from_arrays(
        [
            pa.array([row[0] for row in rows], type=pa.string()),
            pa.array([row[1] for row in rows], type=pa.string()),
            pa.array([row[2] for row in rows], type=pa.date32()),
            pa.array([row[3] for row in rows], type=pa.string()),
            pa.array([row[4] for row in rows], type=pa.int32()),
        ],
        names=["period", *MASTER_FIELDS],
    )
    with connect(settings.path("database")) as connection:
        ensure_master_base_schema(connection)
        connection.execute("begin")
        try:
            connection.execute("delete from master_base_rows where period=?", [period])
            connection.register("master_batch", batch)
            connection.execute(
                "insert into master_base_rows(period, center_material_key, product_offer_end_date, season, year) select * from master_batch"
            )
            connection.execute("delete from master_base_imports where period=?", [period])
            connection.execute(
                """insert into master_base_imports(period, source_path, source_sha256, source_sheet, header_row, row_count, fiscal_total, imported_by)
                   values (?,?,?,?,?,?,?,?)""",
                [period, str(path), source_hash, source_sheet, header_row, len(rows), round(fiscal_total, 2), imported_by],
            )
            connection.execute("commit")
        except Exception:
            connection.execute("rollback")
            raise
    return {
        "status": "imported",
        "period": period,
        "rows": len(rows),
        "fiscal_total": round(fiscal_total, 2),
        "source_sheet": source_sheet,
        "header_row": header_row,
        "path": str(path),
    }


def master_base_in_use(connection: Any, period: str) -> bool:
    """A base mestre vale enquanto for mais nova que a última carga da posição daquele mês no sistema."""
    ensure_master_base_schema(connection)
    master = connection.execute("select imported_at from master_base_imports where period=?", [period]).fetchone()
    if master is None:
        return False
    try:
        loaded = connection.execute("select max(imported_at) from inventory_imports where period=?", [period]).fetchone()
    except Exception:  # noqa: BLE001 - tabela ainda não criada
        loaded = None
    return loaded is None or loaded[0] is None or master[0] > loaded[0]


def master_base_status(settings: Any) -> list[dict[str, Any]]:
    """Bases mestre registradas, para o ponto de atenção em Controles e auditoria."""
    with connect(settings.path("database")) as connection:
        ensure_master_base_schema(connection)
        rows = connection.execute(
            """select period, source_path, source_sheet, row_count, fiscal_total, imported_by, imported_at
               from master_base_imports order by period"""
        ).fetchall()
        items = []
        for period, source_path, source_sheet, row_count, fiscal_total, imported_by, imported_at in rows:
            items.append({
                "period": str(period),
                "file_name": Path(str(source_path)).name,
                "source_sheet": str(source_sheet),
                "rows": int(row_count),
                "fiscal_total": float(fiscal_total or 0),
                "imported_by": imported_by or "",
                "imported_at": imported_at.isoformat() if hasattr(imported_at, "isoformat") else str(imported_at),
                "in_use": master_base_in_use(connection, str(period)),
            })
    return items
