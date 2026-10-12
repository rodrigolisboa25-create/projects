"""Base mestre: posição oficial usada só como "mês anterior" do PASSO A PASSO, sem virar competência."""

from __future__ import annotations

import pytest

from ops_contabil import mb59
from ops_contabil.db import connect
from ops_contabil.master_base import ensure_master_base_schema
from ops_contabil.mb59 import enrich_inventory_pass_step, ensure_mb59_schema
from test_optimus_import import ADMIN, env  # noqa: F401 - fixture reaproveitada


@pytest.fixture(autouse=True)
def no_all_brazil(monkeypatch):
    """Sem All Brazil: o teste não lê os snapshots reais do Drive (o passo 3 fica vazio)."""
    monkeypatch.setattr(mb59, "pass_step_lookup_from_all_brazil", lambda *args, **kwargs: {"lookup": {}})


def seed(database) -> None:
    with connect(database) as connection:
        ensure_mb59_schema(connection)
        ensure_master_base_schema(connection)
        for row, (plant, material) in enumerate([("1081", "MAT-A"), ("2115", "MAT-C")], start=1):
            connection.execute(
                """insert into inventory_rows(period,source_row,company,plant,material,center_material_key,unrestricted_quantity,fiscal_total_amount)
                   values ('2026-09',?,'7170',?,?,?,1,10)""",
                [row, plant, material, plant + material],
            )
        # Agosto existe só como base mestre (posição oficial), não como competência.
        connection.execute(
            """insert into master_base_rows values
               ('2026-08','1081MAT-A','2026-06-30','SP',2025), ('2026-08','2115MAT-C',null,'FA',2024)""")
        connection.execute(
            """insert into master_base_imports(period,source_path,source_sha256,source_sheet,header_row,row_count,fiscal_total,imported_by)
               values ('2026-08','C:/x/KPI Ago.26.xlsb','abc','BASE - CKMR',5,2,1234.5,'admin@x')""")


def test_master_base_feeds_previous_month_without_becoming_a_period(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, _sent, _replies = env
    seed(database)
    client, _csrf = client_for(ADMIN)

    result = enrich_inventory_pass_step(settings, "2026-09")
    assert result["previous_from_master_base"] is True
    assert result["field_sources"]["season"]["previous_inventory"] == 2
    grid = client.get("/api/inventory", params={"period": "2026-09", "page_size": 10}).json()
    assert grid["pass_step_sources"]["1"]["year"] == "Mês anterior (2026-08 · base mestre)"
    assert {row["material"]: row["year"] for row in grid["rows"]} in (
        {"MAT-A": 2025, "MAT-C": 2024}, {"MAT-A": "2025", "MAT-C": "2024"})

    # Não aparece como competência.
    periods = client.get("/api/inventory/periods").text
    assert "2026-08" not in periods

    # Fica como ponto de atenção em Controles e auditoria.
    controls = client.get("/api/governance/status", params={"period": "2026-09"}).json()["controls"]
    assert controls[0]["title"] == "Ponto de atenção: base mestre de 2026-08"
    assert controls[0]["badge"] == "Em uso" and "PASSO A PASSO de 2026-09" in controls[0]["detail"]


def test_newer_system_load_replaces_master_base(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, _sent, _replies = env
    seed(database)
    with connect(database) as connection:
        connection.execute(
            """insert into inventory_imports(period,source_path,source_sha256,source_sheet,header_row,row_count,schema_fingerprint,imported_at)
               values ('2026-08','zmm119.xlsx','def','Sheet1',1,0,'fp', current_timestamp + interval 1 hour)""")
    result = enrich_inventory_pass_step(settings, "2026-09")
    assert result["previous_from_master_base"] is False
    client, _csrf = client_for(ADMIN)
    controls = client.get("/api/governance/status", params={"period": "2026-09"}).json()["controls"]
    assert controls[0]["badge"] == "Substituída"
