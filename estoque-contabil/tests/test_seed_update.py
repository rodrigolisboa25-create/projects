"""Reinstalação: o instalador atualiza competências sem tocar em usuários, preferências e Mapping."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb
import pytest

import ops_contabil.seed_data as seed_data
from ops_contabil.db import connect
from ops_contabil.inventory import ensure_inventory_schema
from ops_contabil.mappings import ensure_mapping_schema
from ops_contabil.mb59 import ensure_mb59_schema

T0 = datetime(2026, 9, 21, 21, 0)
T1 = datetime(2026, 9, 25, 21, 50)
T2 = datetime(2026, 9, 29, 10, 0)


def build_db(path: Path, periods: dict[str, tuple[int, datetime]], *, users: list[tuple[str, str | None]], prefs: dict[str, str],
             mapping_value: str) -> Path:
    """periods: competência -> (quantidade de linhas, momento da carga)."""
    with connect(path) as c:
        ensure_inventory_schema(c)
        ensure_mb59_schema(c)
        ensure_mapping_schema(c)
        c.execute(
            """create table if not exists all_brazil_imports (
                period varchar primary key, snapshot_date date, source_path varchar, source_sha256 varchar,
                inventory_keys bigint, matched_keys bigint, coverage_pct double, duplicate_keys bigint,
                conflict_keys bigint, schema_fingerprint varchar, imported_at timestamp default current_timestamp)"""
        )
        for period, (rows, loaded_at) in periods.items():
            for index in range(rows):
                c.execute(
                    "insert into inventory_rows(period,source_row,material,unrestricted_quantity,fiscal_total_amount) values (?,?,?,?,?)",
                    [period, index + 1, f"MAT-{period}-{index}", 1, 10.0],
                )
            c.execute(
                """insert into inventory_imports(period,source_path,source_sha256,source_sheet,header_row,row_count,
                   schema_fingerprint,imported_at) values (?,?,?,?,?,?,?,?)""",
                [period, f"C:/landing/{period}.xlsx", "sha", "Sheet1", 1, rows, "fp", loaded_at],
            )
            c.execute("insert into all_brazil_imports(period,coverage_pct,imported_at) values (?,?,?)", [period, 100.0, loaded_at])
        for email, subject in users:
            c.execute(
                "insert into allowed_users(email,is_active,role,allowed_pages,identity_subject) values (?,true,'user','[\"overview\"]',?)",
                [email, subject],
            )
        for key, value in prefs.items():
            c.execute("insert into system_settings(setting_key,setting_value) values (?,?)", [key, value])
        c.execute("delete from mapping_rules")
        c.execute(
            "insert into mapping_rules(group_key,key_value,value_1,position) values ('status','TESTE',?,1)",
            [mapping_value],
        )
    return path


def rows_by_period(path: Path) -> dict[str, int]:
    with duckdb.connect(str(path), read_only=True) as c:
        return {str(p): int(n) for p, n in c.execute("select period, count(*) from inventory_rows group by period").fetchall()}


@pytest.fixture()
def local_machine(tmp_path: Path) -> Path:
    # Máquina do usuário: instalada com Julho e Agosto, login feito, preferência alterada.
    return build_db(
        tmp_path / "local" / "ops_contabil.duckdb",
        {"2026-07": (2, T0), "2026-08": (3, T0)},
        users=[("felipe.teste@gruposbf.com.br", "windows:FELIPE")],
        prefs={"density": '"comfortable"'},
        mapping_value="LOCAL",
    )


def test_reinstall_adds_new_period_and_keeps_everything_else(local_machine: Path, tmp_path: Path) -> None:
    package = build_db(
        tmp_path / "pkg" / "seed.duckdb",
        {"2026-07": (2, T0), "2026-08": (3, T0), "2026-09": (4, T2)},
        users=[("felipe.teste@gruposbf.com.br", None), ("outro@gruposbf.com.br", None)],
        prefs={"density": '"compact"'},
        mapping_value="PACOTE",
    )

    result = seed_data.apply_snapshot(package, local_machine)

    assert result["status"] == "updated_periods"
    assert [item["period"] for item in result["applied_periods"]] == ["2026-09"]
    assert {item["period"] for item in result["kept_periods"]} == {"2026-07", "2026-08"}
    assert rows_by_period(local_machine) == {"2026-07": 2, "2026-08": 3, "2026-09": 4}
    with duckdb.connect(str(local_machine), read_only=True) as c:
        assert c.execute("select email, identity_subject from allowed_users").fetchall() == [("felipe.teste@gruposbf.com.br", "windows:FELIPE")]
        assert c.execute("select setting_value from system_settings where setting_key='density'").fetchone()[0] == '"comfortable"'
        assert c.execute("select value_1 from mapping_rules").fetchall() == [("LOCAL",)]
        assert c.execute("select coverage_pct from all_brazil_imports where period='2026-09'").fetchone()[0] == 100.0
    assert Path(result["backup"]).is_file()


def test_newer_package_load_replaces_the_local_period(local_machine: Path, tmp_path: Path) -> None:
    package = build_db(tmp_path / "pkg" / "seed.duckdb", {"2026-08": (7, T1)}, users=[], prefs={}, mapping_value="PACOTE")

    result = seed_data.apply_snapshot(package, local_machine)

    assert [item["period"] for item in result["applied_periods"]] == ["2026-08"]
    assert rows_by_period(local_machine) == {"2026-07": 2, "2026-08": 7}  # julho só existe na máquina: preservado


def test_newer_local_load_is_never_overwritten(tmp_path: Path) -> None:
    admin = build_db(tmp_path / "admin" / "ops_contabil.duckdb", {"2026-09": (9, T2)}, users=[], prefs={}, mapping_value="LOCAL")
    package = build_db(tmp_path / "pkg" / "seed.duckdb", {"2026-09": (4, T1)}, users=[], prefs={}, mapping_value="PACOTE")

    result = seed_data.apply_snapshot(package, admin)

    assert result["status"] == "kept_local_database"
    assert result["applied_periods"] == [] and result["backup"] is None
    assert rows_by_period(admin) == {"2026-09": 9}


def test_package_columns_missing_locally_are_added(local_machine: Path, tmp_path: Path) -> None:
    package = build_db(tmp_path / "pkg" / "seed.duckdb", {"2026-09": (1, T2)}, users=[], prefs={}, mapping_value="PACOTE")
    with duckdb.connect(str(package)) as c:
        c.execute("alter table inventory_rows add column nova_coluna varchar")
        c.execute("update inventory_rows set nova_coluna='valor novo'")

    seed_data.apply_snapshot(package, local_machine)

    with duckdb.connect(str(local_machine), read_only=True) as c:
        assert c.execute("select nova_coluna from inventory_rows where period='2026-09'").fetchone()[0] == "valor novo"
        assert c.execute("select count(*) from inventory_rows where period='2026-07' and nova_coluna is null").fetchone()[0] == 2


def test_failure_in_the_middle_rolls_everything_back(local_machine: Path, tmp_path: Path, monkeypatch) -> None:
    package = build_db(tmp_path / "pkg" / "seed.duckdb", {"2026-08": (7, T1), "2026-09": (4, T2)}, users=[], prefs={}, mapping_value="PACOTE")
    # Falha ao chegar na última tabela, depois de inventory_rows já ter sido alterada.
    monkeypatch.setattr(seed_data, "PERIOD_TABLES", (*seed_data.PERIOD_TABLES, "tabela_inexistente_no_pacote"))
    real_catalog_tables = seed_data._catalog_tables

    def catalog_with_ghost(connection, catalog):
        tables = real_catalog_tables(connection, catalog)
        return tables | {"tabela_inexistente_no_pacote"} if catalog == "pkg" else tables

    monkeypatch.setattr(seed_data, "_catalog_tables", catalog_with_ghost)

    with pytest.raises(duckdb.Error):
        seed_data.apply_snapshot(package, local_machine)

    assert rows_by_period(local_machine) == {"2026-07": 2, "2026-08": 3}
