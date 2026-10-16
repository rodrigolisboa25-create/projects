"""Base mestre: posição oficial usada só como "mês anterior" do PASSO A PASSO, sem virar competência."""

from __future__ import annotations

from datetime import date

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


def test_year_before_2022_text_travels_as_before_2022(env) -> None:  # noqa: F811
    """Na posição oficial o Year de itens antigos é o texto "<2022": ele não pode virar "sem Year"."""
    from ops_contabil.inventory import YEAR_BEFORE_2022, _clean_value
    from ops_contabil.mappings import apply_mapping_rules
    from ops_contabil.mb59 import _manual_value

    assert _clean_value("year", "<2022") == YEAR_BEFORE_2022
    assert _clean_value("year", " <2022 ") == YEAR_BEFORE_2022 and _clean_value("year", "2025") == 2025
    assert _manual_value("year", "<2022") == YEAR_BEFORE_2022

    settings, database, _downloads, client_for, _sent, _replies = env
    seed(database)
    with connect(database) as connection:
        connection.execute("update master_base_rows set year=? where center_material_key='2115MAT-C'", [YEAR_BEFORE_2022])
    result = enrich_inventory_pass_step(settings, "2026-09")
    assert result["field_sources"]["year"]["previous_inventory"] == 2 and result["not_found"]["year"] == 0
    apply_mapping_rules(settings, "2026-09")
    with connect(database) as connection:
        assert connection.execute(
            """select historical_year_bucket, season_year from inventory_rows
               where period='2026-09' and material='MAT-C'""").fetchone() == ("<2022", "FA<2022")

    client, _csrf = client_for(ADMIN)
    grid = client.get("/api/inventory", params={"period": "2026-09", "page_size": 10, "filters": '{"year":"<2022"}'}).json()
    assert [row["material"] for row in grid["rows"]] == ["MAT-C"]


def test_year_follows_material_like_the_closing(env) -> None:  # noqa: F811
    """Year: Base GR do mês pelo Material (entrada mais recente com coleção) e mês anterior pelo Material, sem Centro."""
    settings, database, _downloads, _client_for, _sent, _replies = env
    seed(database)
    with connect(database) as connection:
        connection.execute(
            """insert into inventory_rows(period,source_row,company,plant,material,center_material_key,unrestricted_quantity,fiscal_total_amount)
               values ('2026-09',3,'7170','1081','MAT-D','1081MAT-D',1,10)""")
        # Agosto: MAT-D só existia em outro centro, como "<2022"; MAT-E veio com 2015, que também vira "<2022".
        connection.execute("insert into master_base_rows values ('2026-08','3000MAT-D',null,'SP',0), ('2026-08','3000MAT-E',null,'FA',2015)")
        connection.execute(
            """insert into inventory_rows(period,source_row,company,plant,material,center_material_key,unrestricted_quantity,fiscal_total_amount)
               values ('2026-09',4,'7170','1081','MAT-E','1081MAT-E',1,10)""")
        # Setembro: vale a primeira linha de MAT-A (ordem do arquivo) entre os pedidos de importação (48…) com coleção.
        # O pedido nacional (47…) vem antes, mas fica fora; 4800000009 não tem coleção.
        connection.execute(
            """insert into mb59_material_entries(period, material, purchase_order, posting_date, source_row) values
               ('2026-09','MAT-A','4700000004','2026-09-01',4), ('2026-09','MAT-A','4800000001','2026-09-10',5),
               ('2026-09','MAT-A','4800000002','2026-09-20',6), ('2026-09','MAT-A','4800000009','2026-09-25',7)""")
        connection.execute("""insert into gr_collection_rows values ('2026-09','4700000004','HO',2027),
                              ('2026-09','4800000001','FA',2025), ('2026-09','4800000002','SP',2026)""")

    result = enrich_inventory_pass_step(settings, "2026-09")
    assert result["year_rule"] == "material"
    with connect(database) as connection:
        years = dict(connection.execute(
            "select material, cast(year as integer) from inventory_rows where period='2026-09'").fetchall())
    assert years == {"MAT-A": 2025, "MAT-C": 2024, "MAT-D": 0, "MAT-E": 0}
    # Product Offer End Dt e Season: primeira entrada do Material no arquivo (qualquer pedido, inclusive nacional).
    assert result["offer_season_rule"] == "material"
    with connect(database) as connection:
        assert connection.execute(
            "select product_offer_end_date, season from inventory_rows where period='2026-09' and material='MAT-A'"
        ).fetchone() == (date(2026, 9, 1), "HO")


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
