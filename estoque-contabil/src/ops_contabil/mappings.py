from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any

from .db import connect


MAPPING_GROUPS: dict[str, dict[str, Any]] = {
    "aging": {
        "title": "Faixas de aging",
        "source": "MAPPING!A:C",
        "columns": ["Dias iniciais", "Faixa AGING", "Meses de referência"],
    },
    "location": {
        "title": "Planta e local",
        "source": "MAPPING!F:H",
        "columns": ["Planta", "Local anterior", "Local atual"],
    },
    "lifecycle": {
        "title": "Lifecycle",
        "source": "MAPPING!L:M",
        "columns": ["Lifecycle Descrip.", "Lifecycle", "Observação"],
    },
    "operation_status": {
        "title": "Status da operação",
        "source": "MAPPING!O:P",
        "columns": ["Planta", "STATUS OPERAÇÃO", "Observação"],
    },
}


AGING_LABEL_ALIASES: dict[str, str] = {
    "1)  0 - 3 Months": "1) 0-3 meses",
    "1) 0 - 3 Months": "1) 0-3 meses",
    "1) 0-3 Months": "1) 0-3 meses",
    "2) 3 - 6 Months": "2) 3-6 meses",
    "2) 3-6 Months": "2) 3-6 meses",
    "3) 6 - 9 Months": "3) 6-9 meses",
    "3) 6-9 Months": "3) 6-9 meses",
    "4) 9 - 12 Months": "4) 9-12 meses",
    "4) 9-12 Months": "4) 9-12 meses",
    "5) 12 - 18 Months": "5) 12-18 meses",
    "5) 12-18 Months": "5) 12-18 meses",
    "6) 18 - 24 Months": "6) 18-24 meses",
    "6) 18-24 Months": "6) 18-24 meses",
    "7) >2<5 Years": "7) 2-5 anos",
    "7) 2-5 Years": "7) 2-5 anos",
    "8) >5 Years": "8) >5 anos",
}


def _normalize_aging_labels(connection: Any) -> None:
    for legacy_label, normalized_label in AGING_LABEL_ALIASES.items():
        connection.execute(
            """update mapping_rules
               set value_1=?, updated_at=current_timestamp
               where group_key='aging' and lower(trim(coalesce(value_1,'')))=lower(trim(?))""",
            [normalized_label, legacy_label],
        )
        try:
            connection.execute(
                """update inventory_rows
                   set aging_bucket=?
                   where lower(trim(coalesce(aging_bucket,'')))=lower(trim(?))""",
                [normalized_label, legacy_label],
            )
        except Exception:
            # A tabela de estoque pode ainda não existir durante a inicialização do schema.
            pass


LOCATION_ROWS = [
    ("1080", "1_DHL - CENTRO DISTR.", "1_CD - DHL"),
    ("1081", "1_DHL - CENTRO DISTR.", "2_CD - EXTREMA"),
    ("1082", "1_DHL - CENTRO DISTR.", "3_CD - JARINU"),
    ("2029", "5_NFS - LOJAS", "4_NDIS - LOJAS"),
    ("2030", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2032", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2033", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2034", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2035", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2036", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2050", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2052", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2054", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2055", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2056", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2057", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2058", "5_NFS - LOJAS", "4_NDIS - LOJAS"),
    ("2070", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2071", "5_NFS - LOJAS", "4_NDIS - LOJAS"),
    ("2072", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2073", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2074", "4_NDDC 3.0_IFC", "6_DGT - 3_0 - IFC"),
    ("2075", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2076", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2077", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2078", "5_NFS - LOJAS", "4_NDIS - LOJAS"),
    ("2079", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2081", "2_LAPA - OFFICE", "7_LAPA - OFFICE"),
    ("2083", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2084", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2085", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2086", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2087", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2088", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2089", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2090", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2091", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2092", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2093", "5_NFS - LOJAS", "4_NDIS - LOJAS"),
    ("2094", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2095", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2096", "3_NDDC 2.0_EMBU", "2_CD - EXTREMA"),
    ("2097", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2098", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2099", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2100", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2101", "5_NFS - LOJAS", "4_NDIS - LOJAS"),
    ("2102", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2103", "4_NDDC 4.0_EXTREMA", "6_DGT - 4_0 - EXTREMA"),
    ("2104", "5_NFS - LOJAS", "4_NDIS - LOJAS"),
    ("2107", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2110", "5_NFS - LOJAS", "4_NDIS - LOJAS"),
    ("2105", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2108", "5_NFS - LOJAS", "4_NDIS - LOJAS"),
    ("1079", "7_MATRIZ - OFFICE", "8_MATRIZ - OFFICE"),
    ("1083", "9_CD - Rio de Janeiro", "9_CD - Rio de Janeiro"),
    ("2109", "5_NFS - LOJAS", "5_NVS - LOJAS"),
    ("2111", None, "4_NDIS - LOJAS"),
    ("2106", None, "5_NVS - LOJAS"),
    ("2112", None, "4_NDIS - LOJAS"),
    ("2113", None, "4_NDIS - LOJAS"),
    ("2114", None, "4_NDIS - LOJAS"),
]


def ensure_mapping_schema(connection: Any) -> None:
    connection.execute("create sequence if not exists mapping_seq start 1")
    connection.execute(
        """
        create table if not exists mapping_rules (
            mapping_id bigint primary key default nextval('mapping_seq'),
            group_key varchar not null,
            key_value varchar not null,
            value_1 varchar,
            value_2 varchar,
            position integer not null,
            updated_at timestamp not null default current_timestamp,
            unique(group_key, key_value)
        )
        """
    )
    seeds: dict[str, list[tuple[str, str | None, str | None]]] = {
        "aging": [
            ("0", "1) 0-3 meses", "0"),
            ("105", "2) 3-6 meses", "3.5"),
            ("195", "3) 6-9 meses", "6.5"),
            ("285", "4) 9-12 meses", "9.5"),
            ("375", "5) 12-18 meses", "12.5"),
            ("555", "6) 18-24 meses", "18.5"),
            ("735", "7) 2-5 anos", "24.5"),
            ("1815", "8) >5 anos", "60.5"),
        ],
        "location": LOCATION_ROWS,
        "lifecycle": [("Inactive", "F4", None), ("Active", "F1", None)],
        "operation_status": [
            (plant, "BAIXADOS" if plant in {"2031", "2096", "2073"} else "ATIVO", None)
            for plant in ["2031", *[row[0] for row in LOCATION_ROWS]]
        ],
    }
    for group_key, rows in seeds.items():
        count = connection.execute(
            "select count(*) from mapping_rules where group_key=?", [group_key]
        ).fetchone()[0]
        if count:
            continue
        connection.executemany(
            """insert into mapping_rules(group_key,key_value,value_1,value_2,position)
               values (?,?,?,?,?)""",
            [(group_key, key, value_1, value_2, position) for position, (key, value_1, value_2) in enumerate(rows, 1)],
        )


def list_mapping_groups(settings: Any) -> list[dict[str, Any]]:
    with connect(settings.path("database")) as connection:
        ensure_mapping_schema(connection)
        counts = dict(connection.execute(
            "select group_key,count(*) from mapping_rules group by group_key"
        ).fetchall())
    return [
        {"key": key, **metadata, "rows": int(counts.get(key, 0))}
        for key, metadata in MAPPING_GROUPS.items()
    ]


def list_mapping_rows(settings: Any, group_key: str) -> dict[str, Any]:
    if group_key not in MAPPING_GROUPS:
        raise ValueError("Grupo MAPPING inválido.")
    with connect(settings.path("database")) as connection:
        ensure_mapping_schema(connection)
        rows = connection.execute(
            """select mapping_id,key_value,value_1,value_2,position,updated_at
               from mapping_rules where group_key=? order by position,mapping_id""",
            [group_key],
        ).fetchall()
    keys = ["mapping_id", "key_value", "value_1", "value_2", "position", "updated_at"]
    return {
        "group": {"key": group_key, **MAPPING_GROUPS[group_key]},
        "rows": [dict(zip(keys, row, strict=True)) for row in rows],
    }


def save_mapping_row(
    settings: Any,
    group_key: str,
    key_value: str,
    value_1: str | None,
    value_2: str | None,
    mapping_id: int | None = None,
) -> dict[str, Any]:
    if group_key not in MAPPING_GROUPS:
        raise ValueError("Grupo MAPPING inválido.")
    key_value = str(key_value).strip()
    if not key_value:
        raise ValueError("A chave da regra é obrigatória.")
    with connect(settings.path("database")) as connection:
        ensure_mapping_schema(connection)
        if mapping_id is None:
            position = connection.execute(
                "select coalesce(max(position),0)+1 from mapping_rules where group_key=?", [group_key]
            ).fetchone()[0]
            row = connection.execute(
                """insert into mapping_rules(group_key,key_value,value_1,value_2,position)
                   values (?,?,?,?,?) returning mapping_id""",
                [group_key, key_value, value_1, value_2, position],
            ).fetchone()
            mapping_id = int(row[0])
        else:
            connection.execute(
                """update mapping_rules set key_value=?,value_1=?,value_2=?,updated_at=current_timestamp
                   where mapping_id=? and group_key=?""",
                [key_value, value_1, value_2, mapping_id, group_key],
            )
    return {"status": "saved", "mapping_id": mapping_id, "group_key": group_key}


def delete_mapping_row(settings: Any, group_key: str, mapping_id: int) -> None:
    if group_key not in MAPPING_GROUPS:
        raise ValueError("Grupo MAPPING inválido.")
    with connect(settings.path("database")) as connection:
        ensure_mapping_schema(connection)
        connection.execute(
            "delete from mapping_rules where group_key=? and mapping_id=?", [group_key, mapping_id]
        )


def apply_mapping_rules(settings: Any, period: str, as_of: date | None = None) -> None:
    year, month = map(int, period.split("-"))
    as_of = as_of or date(year, month, monthrange(year, month)[1])
    with connect(settings.path("database")) as connection:
        ensure_mapping_schema(connection)
        _normalize_aging_labels(connection)
        # Mapping fields are derived values. Clear them before reapplying the
        # current rules so an edited/deleted key cannot leave stale values in
        # any previously compiled period.
        connection.execute(
            """update inventory_rows set
                 operation_status=null,
                 location_group=null,
                 lifecycle=null,
                 aging_bucket=null
               where period=?""",
            [period],
        )
        connection.execute(
            """update inventory_rows as inventory set operation_status=rules.value_1
               from mapping_rules rules where inventory.period=?
               and rules.group_key='operation_status' and rules.key_value=inventory.plant""",
            [period],
        )
        connection.execute(
            """update inventory_rows as inventory set location_group=rules.value_2
               from mapping_rules rules where inventory.period=?
               and rules.group_key='location' and rules.key_value=inventory.plant""",
            [period],
        )
        connection.execute(
            """update inventory_rows set
                 center_material_key=coalesce(plant,'') || coalesce(material,''),
                 company_unit_cost=case when unrestricted_quantity<>0 then company_total_amount/unrestricted_quantity end,
                 style_color=substr(material,1,10), style=substr(material,1,6),
                 fiscal_unit_cost=case when unrestricted_quantity<>0 then fiscal_total_amount/unrestricted_quantity end,
                 aging_days=case when product_offer_end_date is not null then date_diff('day',product_offer_end_date,?::date) end,
                 aging_bucket=null,
                 fob_amount=fiscal_total_amount*0.50, import_tax_amount=fiscal_total_amount*0.35,
                 other_costs_amount=fiscal_total_amount*0.15,
                 season_year=case when season is not null and year is not null then season || cast(cast(year as integer) as varchar) end,
                 historical_year_bucket=case when year is null then null when year<2022 then '<2022' else cast(cast(year as integer) as varchar) end
               where period=?""",
            [as_of, period],
        )
        connection.execute(
            """update inventory_rows as inventory set aging_bucket=aging.value_1
               from mapping_rules aging
               where inventory.period=? and aging.group_key='aging'
                 and inventory.aging_days>=try_cast(aging.key_value as integer)
                 and try_cast(aging.key_value as integer)=(
                   select max(try_cast(candidate.key_value as integer)) from mapping_rules candidate
                   where candidate.group_key='aging' and try_cast(candidate.key_value as integer)<=inventory.aging_days
                 )""",
            [period],
        )
        connection.execute(
            "update inventory_rows set aging_bucket='0) Futures' where period=? and aging_days<0",
            [period],
        )
        connection.execute(
            """update inventory_rows as inventory set lifecycle=rules.value_1
               from mapping_rules rules where inventory.period=? and rules.group_key='lifecycle'
               and lower(trim(rules.key_value))=lower(trim(inventory.lifecycle_description))""",
            [period],
        )
