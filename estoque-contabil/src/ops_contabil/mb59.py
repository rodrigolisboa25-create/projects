from __future__ import annotations

import math
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import pyarrow as pa
from openpyxl import load_workbook

from .audit import sha256
from .db import connect
from .ingestion.schema_resolver import load_contracts, resolve_headers
from .master_base import master_base_in_use
from .sources.all_brazil import pass_step_lookup_from_all_brazil


def ensure_mb59_schema(connection: Any) -> None:
    connection.execute(
        """
        create table if not exists mb59_rows (
            period varchar not null,
            center_material_key varchar not null,
            material varchar not null,
            plant varchar not null,
            product_offer_end_date date,
            season varchar,
            year integer,
            season_year varchar,
            posting_date date,
            source_row bigint,
            primary key(period, center_material_key)
        );
        create table if not exists mb59_imports (
            period varchar primary key,
            source_path varchar not null,
            source_sha256 varchar not null,
            source_sheet varchar not null,
            header_row integer not null,
            source_rows bigint not null,
            lookup_rows bigint not null,
            schema_fingerprint varchar not null,
            imported_at timestamp not null default current_timestamp
        );
        -- Base GR do mês por SKU (regra do PASSO A PASSO validada com a área): a entrada mais recente
        -- de cada SKU (10 primeiros caracteres do material, todos os centros), sem pedidos intercompany.
        create table if not exists mb59_sku_entries (
            period varchar not null,
            sku varchar not null,
            posting_date date,
            material_document varchar,
            purchase_order varchar,
            purchase_order_item varchar,
            vendor varchar,
            material varchar,
            plant varchar,
            movement_type varchar,
            primary key(period, sku)
        );
        -- Pedidos de compra das entradas do mês (para a SQVI DOC_COMPRA e para conferir a Base GR importada).
        create table if not exists mb59_orders (
            period varchar not null,
            purchase_order varchar not null,
            vendor varchar,
            lines bigint not null,
            intercompany boolean not null,
            primary key(period, purchase_order)
        );
        -- Coleção (Season/Year) de cada pedido de compra, vinda da Base GR ou do export da SQVI DOC_COMPRA.
        create table if not exists gr_collection_rows (
            period varchar not null,
            purchase_order varchar not null,
            season varchar not null,
            year integer not null,
            primary key(period, purchase_order)
        );
        create table if not exists gr_collection_imports (
            period varchar primary key,
            source_kind varchar not null,
            file_name varchar not null,
            source_path varchar not null,
            source_sha256 varchar not null,
            orders bigint not null,
            lines bigint not null,
            summary_json varchar,
            imported_by varchar,
            imported_at timestamp not null default current_timestamp
        );
        """
    )


# Fornecedores das transferências entre empresas do grupo (intercompany): ficam fora da regra do
# PASSO A PASSO, como no fechamento manual (não têm coleção na SQVI DOC_COMPRA).
INTERCOMPANY_VENDORS = frozenset({"7008002", "7008004"})


def normalize_vendor(value: Any) -> str | None:
    text = _text(value)
    return text.lstrip("0") or text if text else None


def is_intercompany(vendor: Any) -> bool:
    return normalize_vendor(vendor) in INTERCOMPANY_VENDORS


def sku_of(material: Any) -> str | None:
    """SKU do fechamento: os 10 primeiros caracteres do material (modelo-cor, sem o tamanho)."""
    text = _text(material)
    return text.strip().upper()[:10] if text else None


def _text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip() or None


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not math.isnan(float(value)):
        return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
    return None


def _year(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def import_mb59_xlsx(settings: Any, period: str, path: Path) -> dict[str, Any]:
    datetime.strptime(period, "%Y-%m")
    path = path.resolve()
    contract = load_contracts(settings.root / "config" / "schemas.yaml")["mb59_base"]
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        best: tuple[Any, Any] | None = None
        for worksheet in workbook.worksheets:
            preview = [
                list(row)
                for row in worksheet.iter_rows(
                    min_row=1, max_row=contract.header_search_rows, values_only=True
                )
            ]
            try:
                candidate = resolve_headers(preview, contract)
            except Exception:
                continue
            if best is None or len(candidate.positions) > len(best[1].positions):
                best = (worksheet, candidate)
        if best is None:
            raise ValueError("Nenhuma aba da exportação MB59 atende ao contrato de colunas.")
        worksheet, resolution = best
        selected: dict[str, dict[str, Any]] = {}
        sku_entries: dict[str, dict[str, Any]] = {}
        orders: dict[str, dict[str, Any]] = {}
        source_rows = 0
        for source_row, row in enumerate(
            worksheet.iter_rows(min_row=resolution.header_row + 1, values_only=True),
            start=resolution.header_row + 1,
        ):
            def raw(field: str) -> Any:
                position = resolution.positions.get(field)
                return None if position is None or position >= len(row) else row[position]

            material = _text(raw("material"))
            plant = _text(raw("plant"))
            if not material or not plant:
                continue
            source_rows += 1
            posting_date = _date(raw("posting_date"))
            product_offer_end_date = _date(raw("product_offer_end_date"))
            season = _text(raw("season"))
            year = _year(raw("year"))
            season_year = _text(raw("season_year")) or (
                f"{season}{year}" if season is not None and year is not None else None
            )
            key = f"{plant}{material}"
            candidate = {
                "period": period,
                "center_material_key": key,
                "material": material,
                "plant": plant,
                "product_offer_end_date": product_offer_end_date,
                "season": season,
                "year": year,
                "season_year": season_year,
                "posting_date": posting_date,
                "source_row": source_row,
            }
            current = selected.get(key)
            if current is None or (posting_date or date.min) >= (current["posting_date"] or date.min):
                if current is not None:
                    for field in ("product_offer_end_date", "season", "year", "season_year"):
                        if candidate[field] is None:
                            candidate[field] = current[field]
                selected[key] = candidate

            # Pedidos e entrada mais recente por SKU (sem intercompany) para a regra por SKU.
            purchase_order = _text(raw("purchase_order"))
            vendor = normalize_vendor(raw("vendor"))
            intercompany = vendor in INTERCOMPANY_VENDORS
            if purchase_order:
                order = orders.setdefault(purchase_order, {"period": period, "purchase_order": purchase_order,
                                                            "vendor": vendor, "lines": 0, "intercompany": intercompany})
                order["lines"] += 1
            sku = sku_of(material)
            if sku and posting_date and not intercompany:
                entry = {
                    "period": period, "sku": sku, "posting_date": posting_date,
                    "material_document": _text(raw("material_document")), "purchase_order": purchase_order,
                    "purchase_order_item": _text(raw("purchase_order_item")), "vendor": vendor,
                    "material": material, "plant": plant, "movement_type": _text(raw("movement_type")),
                }
                rank = (posting_date, entry["material_document"] or "", entry["purchase_order_item"] or "")
                previous = sku_entries.get(sku)
                if previous is None or rank > previous["_rank"]:
                    sku_entries[sku] = {**entry, "_rank": rank}
        rows = list(selected.values())
        sku_rows = [{k: v for k, v in entry.items() if k != "_rank"} for entry in sku_entries.values()]
        order_rows = list(orders.values())
        batch = pa.Table.from_pylist(rows) if rows else None
        source_hash = sha256(path)
        with connect(settings.path("database")) as connection:
            ensure_mb59_schema(connection)
            connection.execute("begin")
            try:
                connection.execute("delete from mb59_rows where period=?", [period])
                if batch is not None:
                    connection.register("mb59_batch", batch)
                    connection.execute("insert into mb59_rows select * from mb59_batch")
                connection.execute("delete from mb59_sku_entries where period=?", [period])
                if sku_rows:
                    connection.register("mb59_sku_batch", pa.Table.from_pylist(sku_rows))
                    connection.execute(
                        """insert into mb59_sku_entries(period, sku, posting_date, material_document, purchase_order,
                               purchase_order_item, vendor, material, plant, movement_type)
                           select period, sku, posting_date, material_document, purchase_order,
                               purchase_order_item, vendor, material, plant, movement_type from mb59_sku_batch"""
                    )
                connection.execute("delete from mb59_orders where period=?", [period])
                if order_rows:
                    connection.register("mb59_orders_batch", pa.Table.from_pylist(order_rows))
                    connection.execute(
                        """insert into mb59_orders(period, purchase_order, vendor, lines, intercompany)
                           select period, purchase_order, vendor, lines, intercompany from mb59_orders_batch"""
                    )
                connection.execute("delete from mb59_imports where period=?", [period])
                connection.execute(
                    """insert into mb59_imports(period,source_path,source_sha256,source_sheet,
                       header_row,source_rows,lookup_rows,schema_fingerprint)
                       values (?,?,?,?,?,?,?,?)""",
                    [period, str(path), source_hash, worksheet.title, resolution.header_row,
                     source_rows, len(rows), resolution.fingerprint],
                )
                connection.execute("commit")
            except Exception:
                connection.execute("rollback")
                raise
        return {
            "status": "imported",
            "period": period,
            "source_rows": source_rows,
            "lookup_rows": len(rows),
            "sku_entries": len(sku_rows),
            "orders": len(order_rows),
            "intercompany_orders": sum(1 for order in order_rows if order["intercompany"]),
            "path": str(path),
            "header_row": resolution.header_row,
        }
    finally:
        workbook.close()


def ensure_pass_step_sources_schema(connection: Any) -> None:
    """Tabela de auditoria do PASSO A PASSO: origem de Product Offer End Dt, Season e Year por linha.

    Fica fora de inventory_rows (a Base de Estoque não ganha colunas); liga pela competência + source_row."""
    connection.execute(
        """create table if not exists pass_step_sources (
               period varchar not null,
               source_row bigint not null,
               product_offer_end_date varchar,
               season varchar,
               year varchar
           )"""
    )


def pass_step_sources(settings: Any, period: str, source_rows: list[int]) -> dict[int, dict[str, str | None]]:
    """Origem dos campos PASSO A PASSO das linhas pedidas (para o balão da grade)."""
    if not source_rows:
        return {}
    with connect(settings.path("database")) as connection:
        ensure_pass_step_sources_schema(connection)
        rows = connection.execute(
            f"""select source_row, product_offer_end_date, season, year from pass_step_sources
                where period=? and source_row in ({','.join('?' * len(source_rows))})""",
            [period, *source_rows],
        ).fetchall()
    return {int(r[0]): {"product_offer_end_date": r[1], "season": r[2], "year": r[3]} for r in rows}


PASS_STEP_FIELDS = ("product_offer_end_date", "season", "year")
SEASONS = ("FA", "HO", "SP", "SU")


def ensure_pass_step_manual_schema(connection: Any) -> None:
    """Preenchimento manual do PASSO A PASSO (último recurso): só vale quando MB59, mês anterior e All Brazil
    não trouxeram o valor. Fica por competência + CE & MAT + campo, com quem preencheu e quando."""
    connection.execute(
        """create table if not exists pass_step_manual (
               period varchar not null,
               center_material_key varchar not null,
               field varchar not null,
               value varchar not null,
               filled_by varchar,
               filled_at timestamp not null default current_timestamp
           )"""
    )


def _manual_label(filled_by: str | None, filled_at: Any) -> str:
    when = filled_at.strftime("%d/%m/%Y") if hasattr(filled_at, "strftime") else str(filled_at or "")[:10]
    who = (filled_by or "").split("@")[0]
    return f"Manual ({', '.join(item for item in (who, when) if item)})"


def _manual_value(field: str, value: Any) -> Any:
    """Valida e converte um valor digitado. Levanta ValueError com a mensagem para o usuário."""
    text = str(value or "").strip()
    if not text:
        return None
    if field == "season":
        text = text.upper()
        if text not in SEASONS:
            raise ValueError(f"Season inválida: {text}. Use {', '.join(SEASONS)}.")
        return text
    if field == "year":
        if not text.isdigit() or not 2000 <= int(text) <= 2100:
            raise ValueError(f"Year inválido: {text}. Informe o ano com 4 dígitos (2000 a 2100).")
        return int(text)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Product Offer End Dt inválida: {text}.") from exc


def pass_step_pending(settings: Any, period: str, limit: int = 500) -> dict[str, Any]:
    """CE & MAT da competência com Product Offer End Dt, Season ou Year ainda vazios (Não localizado)."""
    with connect(settings.path("database")) as connection:
        rows = connection.execute(
            """select center_material_key, any_value(material), any_value(plant), any_value(material_description),
                      count(*), sum(coalesce(fiscal_total_amount,0)),
                      any_value(product_offer_end_date), any_value(season), any_value(cast(year as integer)),
                      bool_or(product_offer_end_date is null), bool_or(season is null), bool_or(year is null)
                 from inventory_rows
                where period=? and (product_offer_end_date is null or season is null or year is null)
                group by center_material_key
                order by 6 desc""",
            [period],
        ).fetchall()
    items = [
        {
            "center_material_key": r[0], "material": r[1], "plant": r[2], "description": r[3],
            "rows": int(r[4]), "fiscal_value": float(r[5] or 0),
            "product_offer_end_date": None if r[9] else (r[6].isoformat() if r[6] else None),
            "season": None if r[10] else r[7],
            "year": None if r[11] else r[8],
            "missing": [field for field, missing in zip(PASS_STEP_FIELDS, r[9:12]) if missing],
        }
        for r in rows
    ]
    return {"period": period, "keys": len(items), "rows": sum(item["rows"] for item in items), "items": items[:limit]}


def save_pass_step_manual(settings: Any, period: str, items: list[dict[str, Any]], filled_by: str) -> dict[str, Any]:
    """Grava o preenchimento manual e aplica na hora nas linhas que continuam vazias (fonte = Manual)."""
    entries: list[tuple[str, str, Any]] = []
    for item in items:
        key = str(item.get("center_material_key") or "").strip()
        if not key:
            raise ValueError("Linha sem CE & MAT.")
        for field in PASS_STEP_FIELDS:
            value = _manual_value(field, item.get(field))
            if value is not None:
                entries.append((key, field, value))
    if not entries:
        raise ValueError("Preencha ao menos um campo.")
    applied = 0
    with connect(settings.path("database")) as connection:
        ensure_pass_step_manual_schema(connection)
        ensure_pass_step_sources_schema(connection)
        connection.execute("begin")
        try:
            for key, field, value in entries:
                connection.execute(
                    "delete from pass_step_manual where period=? and center_material_key=? and field=?", [period, key, field]
                )
                connection.execute(
                    "insert into pass_step_manual(period, center_material_key, field, value, filled_by) values (?,?,?,?,?)",
                    [period, key, field, str(value), filled_by],
                )
                filled_at = connection.execute(
                    "select filled_at from pass_step_manual where period=? and center_material_key=? and field=?",
                    [period, key, field],
                ).fetchone()[0]
                targets = [r[0] for r in connection.execute(
                    f"select source_row from inventory_rows where period=? and center_material_key=? and {field} is null",
                    [period, key],
                ).fetchall()]
                if not targets:
                    continue
                connection.execute(
                    f"update inventory_rows set {field}=? where period=? and center_material_key=? and {field} is null",
                    [value, period, key],
                )
                label = _manual_label(filled_by, filled_at)
                marks = ",".join("?" * len(targets))
                existing = {r[0] for r in connection.execute(
                    f"select source_row from pass_step_sources where period=? and source_row in ({marks})", [period, *targets]
                ).fetchall()}
                if existing:
                    connection.execute(
                        f"update pass_step_sources set {field}=? where period=? and source_row in ({','.join('?' * len(existing))})",
                        [label, period, *existing],
                    )
                for source_row in set(targets) - existing:
                    connection.execute(
                        f"insert into pass_step_sources(period, source_row, {field}) values (?,?,?)", [period, source_row, label]
                    )
                applied += len(targets)
            connection.execute("commit")
        except Exception:
            connection.execute("rollback")
            raise
    return {"period": period, "values": len(entries), "cells_filled": applied}


def _previous_period(period: str) -> str:
    year_number, month_number = map(int, period.split("-"))
    first_day = date(year_number, month_number, 1)
    return (first_day - timedelta(days=1)).strftime("%Y-%m")


def enrich_inventory_pass_step(
    settings: Any,
    period: str,
    as_of: date | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    """Preenche campos PASSO A PASSO com prioridade operacional homologada.

    Prioridade por campo:
    1. Base GR / MB59 da competência, usando CE & MAT (Centro + Material).
    2. Posição de Estoque do mês anterior, usando CE & MAT.
    3. All Brazil sem Centro: primeiro Material completo; se ele não existir no
       cadastro, fallback pelo Estilo-Cor de 10 caracteres.

    Se nenhuma das três fontes trouxer valor, o campo permanece NULL e deve ser
    apresentado ao usuário como "Não localizado". Nenhum valor é inferido ou inventado.
    """
    datetime.strptime(period, "%Y-%m")
    if as_of is None:
        year_number, month_number = map(int, period.split("-"))
        as_of = date(year_number, month_number, monthrange(year_number, month_number)[1])
    previous_period = _previous_period(period)

    with connect(settings.path("database")) as connection:
        ensure_mb59_schema(connection)
        inventory_exists = bool(
            connection.execute(
                """select count(*) > 0 from information_schema.tables
                   where lower(table_name)='inventory_rows'"""
            ).fetchone()[0]
        )
        if not inventory_exists:
            return {
                "status": "inventory_missing",
                "period": period,
                "previous_period": previous_period,
                "rows": 0,
                "message": "A Base de Estoque ainda não foi carregada.",
            }

        current_rows = connection.execute(
            """select source_row, center_material_key,
                      upper(trim(material)) as material_key,
                      product_offer_end_date, season, year
               from inventory_rows
               where period=?
               order by source_row""",
            [period],
        ).fetchall()
        if not current_rows:
            return {
                "status": "inventory_missing",
                "period": period,
                "previous_period": previous_period,
                "rows": 0,
                "message": f"A competência {period} não possui linhas na Base de Estoque.",
            }

        mb_rows = connection.execute(
            """select center_material_key, product_offer_end_date, season, year
               from mb59_rows where period=?""",
            [period],
        ).fetchall()
        mb_lookup = {
            str(row[0]): {
                "product_offer_end_date": row[1],
                "season": row[2],
                "year": int(row[3]) if row[3] is not None else None,
            }
            for row in mb_rows
            if row[0] not in (None, "")
        }

        # Regra por SKU (validada com o fechamento manual): entrada mais recente do SKU no mês, sem intercompany;
        # Product Offer End Dt = Data de lançamento e Season/Year = coleção do pedido (Base GR / SQVI DOC_COMPRA).
        # Competências importadas antes desta regra não têm mb59_sku_entries e seguem a regra antiga (CE & MAT).
        sku_lookup = {
            str(row[0]): {
                "product_offer_end_date": row[1],
                "season": row[3],
                "year": int(row[4]) if row[4] is not None else None,
                "purchase_order": row[2],
            }
            for row in connection.execute(
                """select entries.sku, entries.posting_date, entries.purchase_order, collection.season, collection.year
                     from mb59_sku_entries entries
                     left join gr_collection_rows collection
                       on collection.period = entries.period and collection.purchase_order = entries.purchase_order
                    where entries.period=?""",
                [period],
            ).fetchall()
        }
        use_sku_rule = bool(sku_lookup)
        collection_imported = bool(
            connection.execute("select count(*) > 0 from gr_collection_imports where period=?", [period]).fetchone()[0]
        )

        # Passo 2: posição do mês anterior. Se houver base mestre (posição oficial carregada só para isso)
        # mais nova que a carga daquele mês no sistema, ela é a posição do mês anterior.
        previous_from_master = master_base_in_use(connection, previous_period)
        previous_rows = connection.execute(
            f"""select center_material_key, product_offer_end_date, season, year
               from {'master_base_rows' if previous_from_master else 'inventory_rows'} where period=?""",
            [previous_period],
        ).fetchall()
        previous_lookup = {
            str(row[0]): {
                "product_offer_end_date": row[1],
                "season": row[2],
                "year": int(row[3]) if row[3] is not None else None,
            }
            for row in previous_rows
            if row[0] not in (None, "")
        }

        # 4º (último recurso): preenchimento manual feito na Base de estoque para o que as três fontes não trouxeram.
        ensure_pass_step_manual_schema(connection)
        manual_lookup: dict[str, dict[str, tuple[Any, str]]] = {}
        for key, field, value, filled_by, filled_at in connection.execute(
            "select center_material_key, field, value, filled_by, filled_at from pass_step_manual where period=?", [period]
        ).fetchall():
            manual_lookup.setdefault(str(key), {})[field] = (_manual_value(field, value), _manual_label(filled_by, filled_at))

    material_keys = {
        str(row[2]).strip()
        for row in current_rows
        if row[2] not in (None, "")
    }
    try:
        all_brazil = pass_step_lookup_from_all_brazil(
            settings,
            as_of,
            material_keys,
            progress_callback=(
                (lambda fraction, message: progress_callback(fraction * 0.42, message))
                if progress_callback is not None
                else None
            ),
        )
    except (FileNotFoundError, ValueError, OSError):
        all_brazil = {"lookup": {}, "snapshot": None, "snapshot_date": None, "conflict_keys": 0}
    all_brazil_lookup = all_brazil["lookup"]

    field_sources = {
        field: {"mb59": 0, "previous_inventory": 0, "all_brazil": 0, "manual": 0, "not_found": 0}
        for field in PASS_STEP_FIELDS
    }
    updates: list[dict[str, Any]] = []

    # Origem gravada na Base de Estoque para auditoria (colunas "Origem ...").
    source_labels = {
        "mb59": "MB59",
        "previous_inventory": f"Mês anterior ({previous_period}{' · base mestre' if previous_from_master else ''})",
        "all_brazil": "All Brazil",
        "not_found": "Não localizado",
    }

    def choose(field: str, center_material_key: str, material_key: str) -> tuple[Any, str]:
        month_entry = (sku_lookup.get(material_key[:10], {}) if use_sku_rule
                       else mb_lookup.get(center_material_key, {}))
        candidates = (
            ("mb59", month_entry.get(field)),
            ("previous_inventory", previous_lookup.get(center_material_key, {}).get(field)),
            ("all_brazil", all_brazil_lookup.get(material_key, {}).get(field)),
        )
        for source, value in candidates:
            if value not in (None, ""):
                field_sources[field][source] += 1
                return value, source_labels[source]
        manual = manual_lookup.get(center_material_key, {}).get(field)
        if manual is not None:
            field_sources[field]["manual"] += 1
            return manual
        field_sources[field]["not_found"] += 1
        return None, source_labels["not_found"]

    total_current_rows = max(1, len(current_rows))
    if progress_callback is not None:
        progress_callback(0.44, f"Aplicando prioridades do PASSO A PASSO em {len(current_rows):,} linhas.")
    for processed, (source_row, center_material_key, material_key, existing_offer, existing_season, existing_year) in enumerate(current_rows, start=1):
        if progress_callback is not None and (processed % 5000 == 0 or processed >= total_current_rows):
            progress_callback(
                0.44 + (processed / total_current_rows) * 0.46,
                f"PASSO A PASSO: {processed:,} de {total_current_rows:,} linhas processadas.",
            )
        center_key = "" if center_material_key is None else str(center_material_key)
        material_only_key = "" if material_key is None else str(material_key).strip().upper()
        offer_end, offer_source = choose("product_offer_end_date", center_key, material_only_key)
        season, season_source = choose("season", center_key, material_only_key)
        year_value, year_source = choose("year", center_key, material_only_key)
        year_number = int(year_value) if year_value is not None else None
        updates.append({
            "source_row": int(source_row),
            "product_offer_end_date": offer_end,
            "season": None if season is None else str(season).strip(),
            "year": year_number,
            "product_offer_end_date_source": offer_source,
            "season_source": season_source,
            "year_source": year_source,
        })

    if progress_callback is not None:
        progress_callback(0.92, "Gravando resultado do PASSO A PASSO na Base de Estoque.")
    batch = pa.Table.from_pylist(updates)
    with connect(settings.path("database")) as connection:
        connection.register("pass_step_batch", batch)
        connection.execute("begin")
        try:
            connection.execute(
                """update inventory_rows as inventory set
                     product_offer_end_date=step.product_offer_end_date,
                     season=step.season,
                     year=step.year
                   from pass_step_batch as step
                   where inventory.period=? and inventory.source_row=step.source_row""",
                [period],
            )
            # Auditoria (sem coluna nova na Base de Estoque): de onde veio cada valor do PASSO A PASSO.
            ensure_pass_step_sources_schema(connection)
            connection.execute("delete from pass_step_sources where period=?", [period])
            connection.execute(
                """insert into pass_step_sources(period, source_row, product_offer_end_date, season, year)
                   select ?, source_row, product_offer_end_date_source, season_source, year_source from pass_step_batch""",
                [period],
            )
            connection.execute("commit")
        except Exception:
            connection.execute("rollback")
            raise

    rows = len(current_rows)
    if progress_callback is not None:
        progress_callback(1.0, f"PASSO A PASSO concluído em {rows:,} linhas.")
    return {
        "status": "enriched",
        "period": period,
        "previous_period": previous_period,
        "as_of": as_of.isoformat(),
        "rows": rows,
        "mb59_ce_mat_matches": sum(1 for row in current_rows if str(row[1]) in mb_lookup),
        "pass_step_rule": "sku" if use_sku_rule else "ce_mat",
        "gr_collection_imported": collection_imported,
        "mb59_sku_matches": sum(
            1 for row in current_rows if use_sku_rule and str(row[2] or "").strip().upper()[:10] in sku_lookup
        ),
        "previous_ce_mat_matches": sum(1 for row in current_rows if str(row[1]) in previous_lookup),
        "previous_from_master_base": previous_from_master,
        "all_brazil_material_matches": sum(1 for row in current_rows if str(row[2]).strip() in all_brazil_lookup),
        "all_brazil_snapshot": all_brazil.get("snapshot"),
        "all_brazil_snapshots_available": all_brazil.get("snapshots_available", 0),
        "all_brazil_snapshots_scanned": all_brazil.get("snapshots_scanned", 0),
        "all_brazil_conflict_keys": all_brazil.get("conflict_keys", 0),
        "field_sources": field_sources,
        "not_found": {
            field: counts["not_found"]
            for field, counts in field_sources.items()
        },
        "message": (
            (
                "PASSO A PASSO aplicado com a Base GR do mês por SKU (entrada mais recente, sem intercompany; "
                "Product Offer End Dt = Data de lançamento; Season/Year = coleção do pedido"
                + ("" if collection_imported else " — coleção dos pedidos ainda não importada")
                + "), "
                if use_sku_rule
                else "PASSO A PASSO aplicado com prioridade MB59 por CE & MAT, "
            )
            + f"posição {previous_period}{' (base mestre)' if previous_from_master else ''} por CE & MAT e All Brazil por Material. "
            "Campos sem correspondência foram marcados como Não localizado."
        ),
    }


def enrich_inventory_from_mb59(
    settings: Any,
    period: str,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Compatibilidade: usa a rotina PASSO A PASSO sem inferir valores ausentes."""
    return enrich_inventory_pass_step(settings, period, as_of)

def has_mb59_period(settings: Any, period: str) -> bool:
    with connect(settings.path("database")) as connection:
        ensure_mb59_schema(connection)
        return connection.execute(
            "select count(*)>0 from mb59_imports where period=?", [period]
        ).fetchone()[0]


def mb59_status(settings: Any, period: str) -> dict[str, Any]:
    with connect(settings.path("database")) as connection:
        ensure_mb59_schema(connection)
        row = connection.execute(
            """select imports.source_path, imports.lookup_rows, imports.imported_at,
                      count(rows.center_material_key) as indexed_rows,
                      count(rows.product_offer_end_date) as offer_rows,
                      count(rows.season) as season_rows,
                      count(rows.year) as year_rows
                 from mb59_imports imports
                 left join mb59_rows rows on rows.period=imports.period
                where imports.period=?
                group by imports.source_path, imports.lookup_rows, imports.imported_at""",
            [period],
        ).fetchone()
    if row is None:
        return {
            "period": period,
            "updated": False,
            "message": "MB59 pendente para esta competência",
        }
    return {
        "period": period,
        "updated": True,
        "source_path": row[0],
        "file_name": Path(row[0]).name,
        "lookup_rows": int(row[1]),
        "imported_at": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
        "indexed_rows": int(row[3]),
        "offer_rows": int(row[4]),
        "season_rows": int(row[5]),
        "year_rows": int(row[6]),
        "pass_step_value_rows": max(int(row[4]), int(row[5]), int(row[6])),
        "message": "MB59 atualizada para esta competência",
    }
