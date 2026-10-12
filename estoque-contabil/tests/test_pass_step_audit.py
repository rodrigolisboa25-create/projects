"""PASSO A PASSO: a origem de cada valor fica auditável na grade, sem nenhuma coluna nova na Base de Estoque."""

from __future__ import annotations

import pytest

from ops_contabil import mb59
from ops_contabil.db import connect
from ops_contabil.inventory import INVENTORY_COLUMNS
from ops_contabil.mb59 import enrich_inventory_pass_step, ensure_mb59_schema
from test_optimus_import import ADMIN, env  # noqa: F401 - fixture reaproveitada


@pytest.fixture(autouse=True)
def no_all_brazil(monkeypatch):
    """Sem All Brazil: o teste não lê os snapshots reais do Drive (o passo 3 fica vazio)."""
    monkeypatch.setattr(mb59, "pass_step_lookup_from_all_brazil", lambda *args, **kwargs: {"lookup": {}})


def seed(database) -> None:
    with connect(database) as connection:
        ensure_mb59_schema(connection)
        for period in ("2026-08", "2026-09"):
            for row, (plant, material) in enumerate([("1081", "MAT-A"), ("1081", "MAT-B"), ("2115", "MAT-C")], start=1):
                connection.execute(
                    """insert into inventory_rows(period,source_row,company,plant,material,center_material_key,unrestricted_quantity,fiscal_total_amount)
                       values (?,?,'7170',?,?,?,1,10)""",
                    [period, row, plant, material, plant + material],
                )
        # Agosto (mês anterior) já tem Season/Year para MAT-A; a MB59 de setembro traz MAT-B.
        connection.execute("update inventory_rows set season='SP', year=2026 where period='2026-08' and material='MAT-A'")
        connection.execute(
            """insert into mb59_rows(period,center_material_key,material,plant,product_offer_end_date,season,year,season_year,posting_date,source_row)
               values ('2026-09','1081MAT-B','MAT-B','1081','2026-12-31','HO',2026,'HO2026','2026-09-10',2)""")


def test_sources_follow_the_rule_and_need_no_new_column(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, _sent, _replies = env
    seed(database)
    client, _csrf = client_for(ADMIN)
    columns_before = [c["key"] for c in client.get("/api/inventory/columns").json()]
    result = enrich_inventory_pass_step(settings, "2026-09")  # 1º MB59, 2º mês anterior, 3º All Brazil (aqui ausente)
    assert result["field_sources"]["season"] == {"mb59": 1, "previous_inventory": 1, "all_brazil": 0, "manual": 0, "not_found": 1}
    grid = client.get("/api/inventory", params={"period": "2026-09", "page_size": 10}).json()
    sources = grid["pass_step_sources"]
    assert sources["2"] == {"product_offer_end_date": "MB59", "season": "MB59", "year": "MB59"}
    assert sources["1"]["season"] == "Mês anterior (2026-08)" and sources["1"]["year"] == "Mês anterior (2026-08)"
    assert sources["3"] == {"product_offer_end_date": "Não localizado", "season": "Não localizado", "year": "Não localizado"}
    # Nenhuma coluna nova: grade, exportação e tabela continuam iguais.
    assert [c["key"] for c in client.get("/api/inventory/columns").json()] == columns_before
    with connect(database) as connection:
        table_columns = {r[0] for r in connection.execute(
            "select column_name from information_schema.columns where table_name='inventory_rows'").fetchall()}
    assert table_columns == {"period", "source_row", *[name for name, _ in INVENTORY_COLUMNS]}
