from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import pyarrow as pa
from openpyxl import Workbook, load_workbook

from .db import connect
from .ingestion.schema_resolver import Resolution, SchemaContract, load_contracts, resolve_headers


INVENTORY_COLUMNS: tuple[tuple[str, str], ...] = (
    ("center_material_key", "CE & MAT"),
    ("operation_status", "STATUS OPERAÇÃO"),
    ("company", "Empresa"),
    ("plant", "Centro"),
    ("material", "Material"),
    ("material_description", "Texto breve material"),
    ("base_unit", "UM básica"),
    ("ncm", "NCM"),
    ("unrestricted_quantity", "Utilização livre"),
    ("blocked_quantity", "Bloqueado"),
    ("average_company_cost", "Custo Médio Empresa"),
    ("fiscal_cost", "Custo Fiscal"),
    ("total", "Total"),
    ("icms_st_amount", "Vlr ICMS ST"),
    ("ipi_amount", "Vlr IPI"),
    ("inventory_type", "Tipo"),
    ("company_total_amount", "Vlr Tot Emp"),
    ("fiscal_total_amount", "Vlr Tot Fisc"),
    ("average_commercial_cost", "Custo Médio Comercial"),
    ("commercial_total_amount", "Vlr Total CC"),
    ("company_unit_cost", "CE UNIT"),
    ("style_color", "Estilo-Cor"),
    ("style", "Estilo"),
    ("fiscal_unit_cost", "Custo Fiscal UNIT."),
    ("division_description", "Division Description"),
    ("material_origin", "Material Origin Des."),
    ("product_offer_end_date", "Product Offer End Dt"),
    ("aging_days", "Days"),
    ("aging_bucket", "AGING"),
    ("lifecycle", "Lifecycle"),
    ("lifecycle_description", "Lifecycle Descrip."),
    ("location_group", "Local"),
    ("fob_amount", "FOB"),
    ("import_tax_amount", "II"),
    ("other_costs_amount", "Outros Custos"),
    ("season_year", "Season/Coleção"),
    ("season", "Season"),
    ("year", "Year"),
    ("historical_year_bucket", "Tudo que for antes de 2022 deixar <2022"),
)

NUMERIC_COLUMNS = {
    "unrestricted_quantity", "blocked_quantity", "average_company_cost", "fiscal_cost",
    "total", "icms_st_amount", "ipi_amount", "company_total_amount", "fiscal_total_amount",
    "average_commercial_cost", "commercial_total_amount", "company_unit_cost", "fiscal_unit_cost",
    "aging_days", "fob_amount", "import_tax_amount", "other_costs_amount", "year",
}
DATE_COLUMNS = {"product_offer_end_date"}
HIDDEN_UI_COLUMNS = {"historical_year_bucket"}
INVENTORY_COMPANY = "7170"


# Contrato oficial da exportação bruta ZMM119 gerada pelo SAP GUI.
# O mapeamento é estritamente POSICIONAL (A:R). Os textos de cabeçalho
# abaixo servem somente como trava de segurança contra mudança de layout;
# eles nunca são usados para descobrir/reordenar colunas.
ZMM119_POSITIONAL_CONTRACT: tuple[tuple[str, str], ...] = (
    ("company", "Empresa"),                              # A
    ("plant", "Centro"),                                # B
    ("material", "Material"),                           # C
    ("material_description", "Texto breve material"),   # D
    ("base_unit", "UM básica"),                         # E
    ("ncm", "NCM"),                                     # F
    ("unrestricted_quantity", "Utilização livre"),      # G
    ("blocked_quantity", "Bloqueado"),                  # H
    ("average_company_cost", "Custo Médio Empresa"),    # I
    ("fiscal_cost", "Custo Fiscal"),                    # J
    ("total", "Total"),                                 # K
    ("icms_st_amount", "Vlr ICMS ST"),                  # L
    ("ipi_amount", "Vlr IPI"),                          # M
    ("inventory_type", "Tipo"),                         # N
    ("company_total_amount", "Vlr Tot Emp"),            # O
    ("fiscal_total_amount", "Vlr Tot Fisc"),            # P
    ("average_commercial_cost", "Custo Médio Comercial"), # Q
    ("commercial_total_amount", "Vlr Total CC"),        # R
)


def _header_signature(value: Any) -> str:
    """Normaliza só para detectar drift do layout; nunca para mapear a coluna."""
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _zmm119_positional_resolution(worksheet: Any) -> Resolution:
    """Valida e fixa o contrato A:R da exportação SAP ZMM119.

    A posição física é a fonte de verdade. O cabeçalho é apenas uma trava de
    segurança para impedir carga silenciosamente errada se o SAP mudar o layout.
    """
    expected_count = len(ZMM119_POSITIONAL_CONTRACT)
    actual_count = int(getattr(worksheet, "max_column", 0) or 0)
    if actual_count != expected_count:
        raise ValueError(
            "Estrutura da ZMM119 mudou: eram esperadas exatamente 18 colunas (A:R), "
            f"mas o arquivo possui {actual_count}. A carga foi bloqueada para evitar "
            "mapeamento incorreto."
        )

    header = next(
        worksheet.iter_rows(
            min_row=1, max_row=1, min_col=1, max_col=expected_count, values_only=True
        ),
        None,
    )
    if header is None:
        raise ValueError("A exportação ZMM119 não possui linha de cabeçalho.")

    mismatches: list[str] = []
    for index, (_, expected_header) in enumerate(ZMM119_POSITIONAL_CONTRACT):
        actual_header = "" if index >= len(header) or header[index] is None else str(header[index]).strip()
        if _header_signature(actual_header) != _header_signature(expected_header):
            column_letter = chr(ord("A") + index)
            mismatches.append(
                f"{column_letter}: esperado '{expected_header}', recebido '{actual_header or '<vazio>'}'"
            )

    if mismatches:
        raise ValueError(
            "A ordem/estrutura da exportação ZMM119 mudou. O sistema usa contrato posicional "
            "A:R e não remapeia colunas por nome. Divergências: " + "; ".join(mismatches)
        )

    positions = {name: index for index, (name, _) in enumerate(ZMM119_POSITIONAL_CONTRACT)}
    source_headers = {str(index): str(header[index] or "").strip() for index in range(expected_count)}
    return Resolution(
        header_row=1,
        positions=positions,
        source_headers=source_headers,
        optional_missing=[],
        suggestions={},
    )


def _project_root() -> Path:
    configured = os.getenv("OPS_PROJECT_ROOT")
    return Path(configured).resolve() if configured else Path.cwd().resolve()


def sample_workbook() -> Path:
    return _project_root() / "Posição de Estoque - FISIA.xlsb"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_inventory_schema(connection: Any) -> None:
    columns = ",\n".join(
        f'"{name}" {"date" if name in DATE_COLUMNS else "double" if name in NUMERIC_COLUMNS else "varchar"}'
        for name, _ in INVENTORY_COLUMNS
    )
    connection.execute(
        f"""
        create table if not exists inventory_rows (
            period varchar not null,
            source_row bigint not null,
            {columns}
        );
        create table if not exists inventory_imports (
            period varchar primary key,
            source_path varchar not null,
            source_sha256 varchar not null,
            source_sheet varchar not null,
            header_row integer not null,
            row_count bigint not null,
            schema_fingerprint varchar not null,
            imported_at timestamp not null default current_timestamp
        );
        """
    )


def _as_rows(value: Any) -> list[list[Any]]:
    if value is None:
        return []
    if not isinstance(value, tuple):
        return [[value]]
    if value and not isinstance(value[0], tuple):
        return [list(value)]
    return [list(row) for row in value]


def _clean_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        return None if math.isnan(result) else result
    text = str(value).strip().replace("R$", "").replace(" ", "")
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _clean_value(name: str, value: Any) -> Any:
    if value is None or value == "":
        return None
    if name in NUMERIC_COLUMNS:
        return _clean_number(value)
    if name in DATE_COLUMNS:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, (int, float)):
            return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _read_records_pyxlsb(path: Path, contract: SchemaContract, period: str) -> tuple[list[list[Any]], Any, str]:
    from pyxlsb import open_workbook

    workbook = open_workbook(str(path))
    try:
        source_sheet = next((name for name in contract.sheet_aliases if name in workbook.sheets), None)
        if source_sheet is None:
            raise ValueError(f"Aba Base Orig. não encontrada em {path.name}")
        worksheet = workbook.get_sheet(source_sheet)
        try:
            preview = [[cell.v for cell in row] for _, row in zip(range(contract.header_search_rows), worksheet.rows())]
        finally:
            worksheet.close()
        resolution = resolve_headers(preview, contract)
        worksheet = workbook.get_sheet(source_sheet)
        records: list[list[Any]] = []
        names = [name for name, _ in INVENTORY_COLUMNS]
        try:
            for source_row, cells in enumerate(worksheet.rows(), start=1):
                if source_row <= resolution.header_row:
                    continue
                row = [cell.v for cell in cells]
                material_position = resolution.positions["material"]
                if material_position >= len(row) or row[material_position] in (None, ""):
                    continue
                values = []
                for name in names:
                    position = resolution.positions.get(name)
                    raw = None if position is None or position >= len(row) else row[position]
                    values.append(_clean_value(name, raw))
                records.append([period, source_row, *values])
        finally:
            worksheet.close()
        return records, resolution, source_sheet
    finally:
        workbook.close()


def _store_inventory_records(
    settings: Any,
    period: str,
    path: Path,
    source_hash: str,
    source_sheet: str,
    resolution: Any,
    records: list[list[Any]],
) -> dict[str, Any]:
    names = [name for name, _ in INVENTORY_COLUMNS]
    batch_names = ["period", "source_row", *names]
    batch_types = [pa.string(), pa.int64(), *[
        pa.date32() if name in DATE_COLUMNS else pa.float64() if name in NUMERIC_COLUMNS else pa.string()
        for name in names
    ]]
    batch = pa.Table.from_arrays(
        [pa.array([row[index] for row in records], type=data_type) for index, data_type in enumerate(batch_types)],
        names=batch_names,
    )
    quoted = ",".join(f'"{name}"' for name, _ in INVENTORY_COLUMNS)
    with connect(settings.path("database")) as connection:
        ensure_inventory_schema(connection)
        connection.execute("begin")
        try:
            connection.execute("delete from inventory_rows where period=?", [period])
            connection.register("inventory_batch", batch)
            connection.execute(
                f"insert into inventory_rows(period, source_row, {quoted}) select * from inventory_batch"
            )
            connection.execute("delete from inventory_imports where period=?", [period])
            connection.execute(
                "insert into inventory_imports(period,source_path,source_sha256,source_sheet,header_row,row_count,schema_fingerprint) values (?,?,?,?,?,?,?)",
                [period, str(path), source_hash, source_sheet, resolution.header_row, len(records), resolution.fingerprint],
            )
            connection.execute("commit")
        except Exception:
            connection.execute("rollback")
            raise
    return {"status": "imported", "period": period, "rows": len(records), "path": str(path), "header_row": resolution.header_row}


def import_inventory_xlsb(settings: Any, period: str, path: Path | None = None, force: bool = False) -> dict[str, Any]:
    """Importa a aba Base Orig. por cabeçalho, independentemente da ordem física das colunas."""
    datetime.strptime(period, "%Y-%m")
    path = (path or sample_workbook()).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Planilha de posição não encontrada: {path}")
    source_hash = _sha256(path)
    with connect(settings.path("database")) as connection:
        ensure_inventory_schema(connection)
        current = connection.execute(
            "select source_sha256, row_count from inventory_imports where period=?", [period]
        ).fetchone()
        if current and current[0] == source_hash and not force:
            return {"status": "unchanged", "period": period, "rows": int(current[1]), "path": str(path)}

    contract: SchemaContract = load_contracts(settings.root / "config" / "schemas.yaml")["zmm119_base_orig"]
    staging = Path(os.path.expandvars("%LOCALAPPDATA%")) / "OpsContabil" / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    staged_path = staging / f"inventory_{source_hash[:16]}.xlsb"
    if not staged_path.exists() or staged_path.stat().st_size != path.stat().st_size:
        shutil.copy2(path, staged_path)
    records, resolution, source_sheet = _read_records_pyxlsb(staged_path, contract, period)
    return _store_inventory_records(settings, period, path, source_hash, source_sheet, resolution, records)


def import_zmm119_xlsx(
    settings: Any,
    period: str,
    path: Path,
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    """Ingere a ZMM119 por A:R e mantém exclusivamente registros da Empresa 7170."""
    datetime.strptime(period, "%Y-%m")
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Exportação ZMM119 não encontrada: {path}")

    source_hash = _sha256(path)
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if not workbook.worksheets:
            raise ValueError("A exportação ZMM119 não possui nenhuma aba.")

        # A exportação automática do SAP gera uma grade/aba. O mapeamento não usa
        # aliases nem resolve cabeçalhos: a fonte de verdade é a posição física A:R.
        worksheet = workbook.worksheets[0]
        resolution = _zmm119_positional_resolution(worksheet)

        names = [name for name, _ in INVENTORY_COLUMNS]
        source_names = [name for name, _ in ZMM119_POSITIONAL_CONTRACT]
        records: list[list[Any]] = []
        discarded_company_rows = 0
        total_source_rows = max(1, int(getattr(worksheet, "max_row", 1) or 1) - 1)
        if progress_callback is not None:
            progress_callback(0.0, f"Lendo {total_source_rows:,} linhas da ZMM119.")

        for source_row, row in enumerate(
            worksheet.iter_rows(
                min_row=2,
                min_col=1,
                max_col=len(ZMM119_POSITIONAL_CONTRACT),
                values_only=True,
            ),
            start=2,
        ):
            processed = source_row - 1
            if progress_callback is not None and (processed % 5000 == 0 or processed >= total_source_rows):
                progress_callback(
                    min(processed / total_source_rows, 0.88),
                    f"Lendo ZMM119: {processed:,} de {total_source_rows:,} linhas.",
                )

            # Material é sempre a coluna C. Linha sem material não é registro de estoque.
            if len(row) < 3 or row[2] in (None, ""):
                continue

            values: dict[str, Any] = {name: None for name in names}
            for position, name in enumerate(source_names):
                raw = None if position >= len(row) else row[position]
                values[name] = _clean_value(name, raw)

            # Regra oficial da Base de Estoque: somente a empresa FISIA 7170.
            # A ZMM119 pode eventualmente retornar registros de outras empresas
            # (por exemplo, 8000), que não devem participar de joins nem relatórios.
            if str(values.get("company") or "").strip() != INVENTORY_COMPANY:
                discarded_company_rows += 1
                continue

            material = str(values["material"])
            plant = "" if values["plant"] is None else str(values["plant"])
            quantity = values["unrestricted_quantity"] or 0
            fiscal_total = values["fiscal_total_amount"] or 0
            company_total = values["company_total_amount"] or 0

            values.update({
                "center_material_key": f"{plant}{material}",
                "style_color": material[:10],
                "style": material[:6],
                "company_unit_cost": company_total / quantity if quantity else None,
                "fiscal_unit_cost": fiscal_total / quantity if quantity else None,
                "fob_amount": fiscal_total * 0.50,
                "import_tax_amount": fiscal_total * 0.35,
                "other_costs_amount": fiscal_total * 0.15,
            })
            records.append([period, source_row, *[values[name] for name in names]])

        if not records:
            raise ValueError(
                "A exportação ZMM119 foi lida, mas não contém registros de estoque após o cabeçalho."
            )

        if progress_callback is not None:
            progress_callback(0.90, f"Preparando {len(records):,} registros da ZMM119 para gravação.")
        result = _store_inventory_records(
            settings,
            period,
            path,
            source_hash,
            str(worksheet.title),
            resolution,
            records,
        )
        result["company_filter"] = INVENTORY_COMPANY
        result["discarded_company_rows"] = discarded_company_rows
        if progress_callback is not None:
            progress_callback(
                1.0,
                f"ZMM119 gravada: {len(records):,} registros da Empresa {INVENTORY_COMPANY}; "
                f"{discarded_company_rows:,} linhas de outras empresas descartadas.",
            )
        return result
    finally:
        workbook.close()


def _worksheet_exists(workbook: Any, name: str) -> bool:
    try:
        workbook.Worksheets(name)
        return True
    except Exception:
        return False


def inventory_columns() -> list[dict[str, str]]:
    numeric = NUMERIC_COLUMNS
    return [
        {
            "key": name,
            "label": label,
            "type": "integer" if name == "year" else "date" if name in DATE_COLUMNS else "number" if name in numeric else "text",
        }
        for name, label in INVENTORY_COLUMNS
        if name not in HIDDEN_UI_COLUMNS
    ]


def _serialize(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _inventory_query_parts(
    period: str,
    query: str,
    sort: str,
    direction: str,
    column_filters: dict[str, str] | None = None,
    pending_joins: bool = False,
) -> tuple[str, list[Any], str, str]:
    """Monta a mesma consulta usada pela grade e pelo download filtrado."""
    allowed = {name for name, _ in INVENTORY_COLUMNS} | {"source_row"}
    safe_sort = sort if sort in allowed else "source_row"
    safe_direction = "desc" if direction.lower() == "desc" else "asc"
    where = "period=?"
    params: list[Any] = [period]
    if query.strip():
        searched = ["material", "material_description", "plant", "style_color", "ncm", "aging_bucket", "lifecycle_description"]
        where += " and (" + " or ".join(f'coalesce(cast("{name}" as varchar),\'\') ilike ?' for name in searched) + ")"
        params.extend([f"%{query.strip()}%"] * len(searched))
    if pending_joins:
        where += """ and (
            division_description is null or trim(coalesce(division_description,''))='' or
            material_origin is null or trim(coalesce(material_origin,''))='' or
            lifecycle is null or trim(coalesce(lifecycle,''))='' or
            lifecycle_description is null or trim(coalesce(lifecycle_description,''))='' or
            product_offer_end_date is null or
            aging_days is null or
            aging_bucket is null or trim(coalesce(aging_bucket,''))='' or
            season is null or trim(coalesce(season,''))='' or
            year is null or
            season_year is null or trim(coalesce(season_year,''))=''
        )"""
    for name, raw_value in (column_filters or {}).items():
        value = str(raw_value).strip()
        if name not in allowed or not value:
            continue
        where += f' and coalesce(cast("{name}" as varchar),\'\') ilike ?'
        params.append(f"%{value}%")
    return where, params, safe_sort, safe_direction


def list_inventory(
    settings: Any,
    period: str,
    page: int,
    page_size: int,
    query: str,
    sort: str,
    direction: str,
    column_filters: dict[str, str] | None = None,
    pending_joins: bool = False,
) -> dict[str, Any]:
    names = [name for name, _ in INVENTORY_COLUMNS]
    where, params, sort, direction = _inventory_query_parts(
        period, query, sort, direction, column_filters, pending_joins
    )
    select = ",".join(["source_row", *[f'"{name}"' for name in names]])
    with connect(settings.path("database")) as connection:
        ensure_inventory_schema(connection)
        total = int(connection.execute(f"select count(*) from inventory_rows where {where}", params).fetchone()[0])
        rows = connection.execute(
            f'select {select} from inventory_rows where {where} order by "{sort}" {direction} nulls last limit ? offset ?',
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
    keys = ["source_row", *names]
    return {
        "period": period,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": max(1, math.ceil(total / page_size)),
        "pending_joins": pending_joins,
        "rows": [{key: _serialize(value) for key, value in zip(keys, row, strict=True)} for row in rows],
    }


def export_inventory_xlsx(
    settings: Any,
    destination: Path,
    period: str,
    query: str,
    sort: str,
    direction: str,
    column_filters: dict[str, str] | None = None,
    pending_joins: bool = False,
) -> dict[str, Any]:
    """Exporta todas as linhas que atendem exatamente aos filtros ativos da grade."""
    visible_columns = [(name, label) for name, label in INVENTORY_COLUMNS if name not in HIDDEN_UI_COLUMNS]
    names = [name for name, _ in visible_columns]
    where, params, sort, direction = _inventory_query_parts(
        period, query, sort, direction, column_filters, pending_joins
    )
    select = ",".join(["source_row", *[f'"{name}"' for name in names]])

    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet("Base de Estoque")
    worksheet.freeze_panes = "A2"
    worksheet.append(["#", *[label for _, label in visible_columns]])
    row_count = 0
    try:
        with connect(settings.path("database")) as connection:
            ensure_inventory_schema(connection)
            cursor = connection.execute(
                f'select {select} from inventory_rows where {where} order by "{sort}" {direction} nulls last',
                params,
            )
            while True:
                chunk = cursor.fetchmany(5000)
                if not chunk:
                    break
                for row in chunk:
                    worksheet.append(list(row))
                    row_count += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(destination)
    finally:
        try:
            workbook.close()
        except Exception:
            pass
    return {"path": str(destination), "rows": row_count, "period": period}



def _natural_key(text: Any) -> tuple[tuple[int, Any], ...]:
    """Ordena rótulos mistos de forma natural: 2 vem antes de 10."""
    value = "" if text is None else str(text).strip()
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\\d+)", value)
        if part
    )


def _fiscal_matrix(
    connection: Any,
    period: str,
    row_col: str,
    col_col: str,
) -> dict[str, Any]:
    """Monta uma matriz de valor fiscal para dois agrupadores categóricos."""
    allowed = {
        "aging_bucket",
        "lifecycle_description",
        "season",
        "year",
        "historical_year_bucket",
        "division_description",
        "location_group",
    }
    if row_col not in allowed or col_col not in allowed:
        raise ValueError("Coluna inválida para matriz fiscal.")

    rows = connection.execute(
        f"""
        select
            coalesce(nullif(trim(cast("{row_col}" as varchar)), ''), 'Não informado') as row_label,
            coalesce(nullif(trim(cast("{col_col}" as varchar)), ''), 'Não informado') as col_label,
            coalesce(sum(fiscal_total_amount), 0) as fiscal_value
        from inventory_rows
        where period=?
        group by 1, 2
        """,
        [period],
    ).fetchall()

    row_labels = sorted({str(row[0]) for row in rows}, key=_natural_key)
    column_labels = sorted({str(row[1]) for row in rows}, key=_natural_key)
    lookup = {(str(row[0]), str(row[1])): float(row[2] or 0) for row in rows}
    values = [
        [lookup.get((row_label, column_label), 0.0) for column_label in column_labels]
        for row_label in row_labels
    ]
    return {
        "rows": row_labels,
        "columns": column_labels,
        "values": values,
        "series": [
            {"label": row_label, "values": values[index]}
            for index, row_label in enumerate(row_labels)
        ],
    }


def _location_bars(connection: Any, period: str, limit: int = 8) -> list[dict[str, Any]]:
    """Retorna local de estoque com quantidade livre e valor fiscal."""
    rows = connection.execute(
        """
        select
            coalesce(nullif(trim(cast(location_group as varchar)), ''), 'Não informado') as label,
            count(*) as rows,
            coalesce(sum(unrestricted_quantity), 0) as quantity,
            coalesce(sum(fiscal_total_amount), 0) as fiscal_value
        from inventory_rows
        where period=?
        group by 1
        order by fiscal_value desc
        limit ?
        """,
        [period, limit],
    ).fetchall()
    return [
        {
            "label": row[0],
            "rows": int(row[1]),
            "quantity": float(row[2] or 0),
            "value": float(row[3] or 0),
        }
        for row in rows
    ]



def _division_bars(connection: Any, period: str, limit: int = 12) -> list[dict[str, Any]]:
    """Retorna Division Description com quantidade livre e valor fiscal."""
    rows = connection.execute(
        """
        select
            coalesce(nullif(trim(cast(division_description as varchar)), ''), 'Não informado') as label,
            count(*) as rows,
            coalesce(sum(unrestricted_quantity), 0) as quantity,
            coalesce(sum(fiscal_total_amount), 0) as fiscal_value
        from inventory_rows
        where period=?
        group by 1
        order by fiscal_value desc
        limit ?
        """,
        [period, limit],
    ).fetchall()
    return [
        {
            "label": row[0],
            "rows": int(row[1]),
            "quantity": float(row[2] or 0),
            "value": float(row[3] or 0),
        }
        for row in rows
    ]


def _compiled_period_trend(connection: Any, period: str, limit: int = 18) -> list[dict[str, Any]]:
    """Série mensal somente das competências efetivamente compiladas."""
    rows = connection.execute(
        """
        select period,
               count(*) as rows,
               coalesce(sum(unrestricted_quantity), 0) as quantity,
               coalesce(sum(fiscal_total_amount), 0) as fiscal_value
        from inventory_rows
        where period <= ?
        group by period
        order by period desc
        limit ?
        """,
        [period, limit],
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in reversed(rows):
        quantity = float(row[2] or 0)
        fiscal_value = float(row[3] or 0)
        result.append(
            {
                "period": str(row[0]),
                "rows": int(row[1]),
                "quantity": quantity,
                "fiscal_value": fiscal_value,
                "pmm": fiscal_value / quantity if quantity else 0.0,
            }
        )
    return result


def _pmm_grouped(connection: Any, period: str, column: str) -> list[dict[str, Any]]:
    """PMM contábil por dimensão, sem média de médias."""
    allowed_columns = {"division_description", "plant", "location_group", "season"}
    if column not in allowed_columns:
        raise ValueError(f"Dimensão PMM não permitida: {column}")
    rows = connection.execute(
        f"""
        with grouped as (
            select coalesce(nullif(trim(cast("{column}" as varchar)), ''), 'Não informado') as label,
                   count(*) as rows,
                   coalesce(sum(unrestricted_quantity), 0) as quantity,
                   coalesce(sum(fiscal_total_amount), 0) as fiscal_value
              from inventory_rows
             where period=?
             group by 1
        )
        select label, rows, quantity, fiscal_value,
               case when quantity<>0 then fiscal_value/quantity else 0 end as pmm
          from grouped
         order by pmm desc, fiscal_value desc
        """,
        [period],
    ).fetchall()
    return [
        {
            "label": str(row[0]),
            "rows": int(row[1]),
            "quantity": float(row[2] or 0),
            "fiscal_value": float(row[3] or 0),
            "pmm": float(row[4] or 0),
        }
        for row in rows
    ]


def _division_variance(
    connection: Any,
    period: str,
    previous_period: str | None,
) -> list[dict[str, Any]]:
    """Compara categoria/divisão com a última competência compilada anterior."""
    if not previous_period:
        return []
    rows = connection.execute(
        """
        with current_period as (
            select coalesce(nullif(trim(cast(division_description as varchar)), ''), 'Não informado') as label,
                   coalesce(sum(unrestricted_quantity), 0) as quantity,
                   coalesce(sum(fiscal_total_amount), 0) as fiscal_value
            from inventory_rows
            where period=?
            group by 1
        ), previous_period as (
            select coalesce(nullif(trim(cast(division_description as varchar)), ''), 'Não informado') as label,
                   coalesce(sum(unrestricted_quantity), 0) as quantity,
                   coalesce(sum(fiscal_total_amount), 0) as fiscal_value
            from inventory_rows
            where period=?
            group by 1
        )
        select coalesce(c.label, p.label) as label,
               coalesce(c.quantity, 0) as current_quantity,
               coalesce(p.quantity, 0) as previous_quantity,
               coalesce(c.fiscal_value, 0) as current_value,
               coalesce(p.fiscal_value, 0) as previous_value
        from current_period c
        full outer join previous_period p on p.label=c.label
        order by abs(coalesce(c.fiscal_value, 0)-coalesce(p.fiscal_value, 0)) desc
        """,
        [period, previous_period],
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        current_value = float(row[3] or 0)
        previous_value = float(row[4] or 0)
        difference = current_value - previous_value
        result.append(
            {
                "label": str(row[0]),
                "current_quantity": float(row[1] or 0),
                "previous_quantity": float(row[2] or 0),
                "current_value": current_value,
                "previous_value": previous_value,
                "difference": difference,
                "variation_pct": (
                    (difference / previous_value) * 100
                    if previous_value
                    else None
                ),
            }
        )
    return result



def dashboard_summary(settings: Any, period: str) -> dict[str, Any]:
    with connect(settings.path("database")) as connection:
        ensure_inventory_schema(connection)
        core = connection.execute(
            """select count(*), count(distinct material), coalesce(sum(unrestricted_quantity),0),
                      coalesce(sum(fiscal_total_amount),0), count(distinct style_color)
               from inventory_rows where period=?""",
            [period],
        ).fetchone()

        def grouped(column: str, limit: int = 8) -> list[dict[str, Any]]:
            rows = connection.execute(
                f"""select coalesce(nullif(trim(cast("{column}" as varchar)),''),'Não informado'),
                           count(*), coalesce(sum(fiscal_total_amount),0)
                    from inventory_rows where period=? group by 1 order by 3 desc limit ?""",
                [period, limit],
            ).fetchall()
            return [
                {"label": row[0], "rows": int(row[1]), "value": float(row[2])}
                for row in rows
            ]

        import_info = connection.execute(
            "select source_path, header_row, imported_at from inventory_imports where period=?",
            [period],
        ).fetchone()
        enriched = connection.execute(
            """select count(distinct case when division_description is not null then style_color end),
                      count(distinct style_color)
               from inventory_rows where period=? and style_color is not null""",
            [period],
        ).fetchone()
        try:
            measured_coverage = connection.execute(
                "select coverage_pct from all_brazil_imports where period=?",
                [period],
            ).fetchone()
        except Exception:
            measured_coverage = None

        cost = connection.execute(
            """select coalesce(sum(fob_amount),0),
                      coalesce(sum(import_tax_amount),0),
                      coalesce(sum(other_costs_amount),0)
               from inventory_rows where period=?""",
            [period],
        ).fetchone()

        aging = grouped("aging_bucket")
        plants = grouped("plant")
        lifecycle = grouped("lifecycle_description")
        origins = grouped("material_origin")
        locations = _location_bars(connection, period)
        # Centros sem local no Mapping (aba "Planta e local"): explicam a barra "Não informado".
        locations_unmapped = [
            {"plant": str(row[0]), "rows": int(row[1]), "value": float(row[2] or 0)}
            for row in connection.execute(
                """select coalesce(nullif(trim(cast(plant as varchar)),''),'(sem centro)'),
                          count(*), coalesce(sum(fiscal_total_amount),0)
                   from inventory_rows
                   where period=? and coalesce(nullif(trim(cast(location_group as varchar)),''),'')=''
                   group by 1 order by 3 desc""",
                [period],
            ).fetchall()
        ]
        division = _division_bars(connection, period, 12)
        aging_for_season = _fiscal_matrix(
            connection,
            period,
            "historical_year_bucket",
            "season",
        )
        lifecycle_aging = _fiscal_matrix(
            connection,
            period,
            "lifecycle_description",
            "aging_bucket",
        )
        # Risco de obsolescência: composição do valor fiscal de cada Division por faixa de Aging.
        division_aging = _fiscal_matrix(
            connection,
            period,
            "division_description",
            "aging_bucket",
        )
        top_styles = grouped("style_color", 8)
        trend = _compiled_period_trend(connection, period)
        pmm_breakdowns = {
            "period": [
                {
                    "label": item["period"],
                    "rows": item["rows"],
                    "quantity": item["quantity"],
                    "fiscal_value": item["fiscal_value"],
                    "pmm": item["pmm"],
                }
                for item in trend
            ],
            "division": _pmm_grouped(connection, period, "division_description"),
            "plant": _pmm_grouped(connection, period, "plant"),
            "location": _pmm_grouped(connection, period, "location_group"),
            "season": _pmm_grouped(connection, period, "season"),
        }
        previous_row = connection.execute(
            "select max(period) from inventory_rows where period < ?",
            [period],
        ).fetchone()
        previous_period = str(previous_row[0]) if previous_row and previous_row[0] else None
        previous_core = None
        if previous_period:
            previous_core = connection.execute(
                """select coalesce(sum(unrestricted_quantity),0),
                          coalesce(sum(fiscal_total_amount),0)
                   from inventory_rows where period=?""",
                [previous_period],
            ).fetchone()
        division_variance = _division_variance(connection, period, previous_period)

    quantity = float(core[2] or 0)
    fiscal_value = float(core[3] or 0)
    coverage = (
        float(measured_coverage[0])
        if measured_coverage
        else ((100 * enriched[0] / enriched[1]) if enriched and enriched[1] else 0)
    )
    pmm = fiscal_value / quantity if quantity else 0.0
    previous_quantity = float(previous_core[0] or 0) if previous_core else 0.0
    previous_fiscal_value = float(previous_core[1] or 0) if previous_core else 0.0
    previous_pmm = previous_fiscal_value / previous_quantity if previous_quantity else 0.0
    pmm_variation_pct = (
        ((pmm - previous_pmm) / previous_pmm) * 100
        if previous_pmm
        else None
    )

    return {
        "period": period,
        "rows": int(core[0]),
        "materials": int(core[1]),
        "quantity": quantity,
        "fiscal_value": fiscal_value,
        "style_colors": int(core[4]),
        "all_brazil_coverage": round(coverage, 2),
        "pmm": pmm,
        "previous_period": previous_period,
        "pmm_comparison": {
            "current": pmm,
            "previous": previous_pmm,
            "variation_pct": pmm_variation_pct,
        },
        "trend": trend,
        "pmm_breakdowns": pmm_breakdowns,
        "division_variance": division_variance,
        "aging": aging,
        "plants": plants,
        "lifecycle": lifecycle,
        "origins": origins,
        "locations": locations,
        "locations_unmapped": locations_unmapped,
        "division": division,
        "aging_for_season": aging_for_season,
        "lifecycle_aging": lifecycle_aging,
        "division_aging": division_aging,
        "top_styles": top_styles,
        "cost_composition": {
            "fob": float(cost[0]),
            "ii": float(cost[1]),
            "others": float(cost[2]),
        },
        "source": None
        if import_info is None
        else {
            "path": import_info[0],
            "header_row": int(import_info[1]),
            "imported_at": _serialize(import_info[2]),
        },
    }
