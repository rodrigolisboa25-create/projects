"""Base de Estoque: soma das colunas de quantidade e valor sobre TODAS as linhas filtradas (não só a página)."""

from __future__ import annotations

import json

from ops_contabil.db import connect
from ops_contabil.inventory import SUM_COLUMNS, inventory_columns, list_inventory
from test_optimus_import import ADMIN, env  # noqa: F401 - fixture reaproveitada


def seed(database) -> None:
    with connect(database) as connection:
        for row, (plant, qty, blocked, fiscal) in enumerate(
            [("1081", 10, 1, 100.0), ("1081", 5, 0, 50.5), ("2115", 2, 3, 20.25), ("2115", 1, 0, 10.0)], start=1
        ):
            connection.execute(
                """insert into inventory_rows(period,source_row,material,plant,unrestricted_quantity,blocked_quantity,
                   fiscal_cost,fiscal_total_amount,company_total_amount,fob_amount,year)
                   values ('2026-09',?,?,?,?,?,7.5,?,?,?,2026)""",
                [row, f"MAT-{row}", plant, qty, blocked, fiscal, fiscal * 2, fiscal * 0.5],
            )


def test_only_quantity_and_value_columns_are_summed() -> None:
    flagged = {item["key"] for item in inventory_columns() if item["sum"]}
    assert flagged == set(SUM_COLUMNS)
    assert {"unrestricted_quantity", "blocked_quantity", "fiscal_total_amount", "fob_amount"} <= flagged
    # custos unitários, dias e ano não fazem sentido somados
    assert not flagged & {"fiscal_cost", "average_company_cost", "fiscal_unit_cost", "company_unit_cost", "aging_days", "year"}


def test_totals_cover_every_filtered_row_not_only_the_page(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, _sent, _replies = env
    seed(database)
    everything = list_inventory(settings, "2026-09", 1, 10, "", "source_row", "asc")
    assert everything["totals"]["unrestricted_quantity"] == 18 and everything["totals"]["blocked_quantity"] == 4
    assert everything["totals"]["fiscal_total_amount"] == 180.75
    assert everything["totals"]["ipi_amount"] == 0  # coluna sem valores soma zero

    # Filtro por coluna: só o centro 2115, com página de 1 linha — a soma continua sendo das 2 linhas filtradas.
    filtered = list_inventory(settings, "2026-09", 1, 1, "", "source_row", "asc", {"plant": "2115"})
    assert len(filtered["rows"]) == 1 and filtered["total"] == 2
    assert filtered["totals"]["unrestricted_quantity"] == 3
    assert filtered["totals"]["fiscal_total_amount"] == 30.25
    assert filtered["totals"]["company_total_amount"] == 60.5

    # A rota das colunas devolve o indicador de soma (booleano) sem erro de validação.
    client, _csrf = client_for(ADMIN)
    columns = client.get("/api/inventory/columns")
    assert columns.status_code == 200, columns.text
    assert {item["key"] for item in columns.json() if item["sum"] is True} == set(SUM_COLUMNS)

    # Pela rota da grade, com busca geral.
    response = client.get("/api/inventory", params={"period": "2026-09", "page_size": 10, "q": "MAT-1",
                                                    "filters": json.dumps({})})
    assert response.status_code == 200, response.text
    assert response.json()["totals"]["unrestricted_quantity"] == 10
