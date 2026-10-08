"""Visão e relatórios: filtros de Division, Centro, Local de estoque e Season valem para todos os indicadores."""

from __future__ import annotations

import json

from ops_contabil.db import connect
from ops_contabil.inventory import dashboard_summary, overview_filter_options, overview_filter_sql
from test_optimus_import import ADMIN, env  # noqa: F401 - fixture reaproveitada

ROWS = [
    # período, centro, divisão, local, season, qtd, valor fiscal
    ("2026-08", "1081", "Calçados", "2_CD - EXTREMA", "FA", 10, 100.0),
    ("2026-08", "2115", "Vestuário", None, "SU", 5, 40.0),
    ("2026-09", "1081", "Calçados", "2_CD - EXTREMA", "FA", 10, 120.0),
    ("2026-09", "1081", "Vestuário", "2_CD - EXTREMA", "SP", 4, 30.0),
    ("2026-09", "2115", "Vestuário", None, "SU", 6, 60.0),
    ("2026-09", "2030", "Calçados", "5_NVS - LOJAS", "FA", 2, 10.0),
]


def seed(database) -> None:
    with connect(database) as connection:
        for index, (period, plant, division, location, season, qty, value) in enumerate(ROWS, start=1):
            connection.execute(
                """insert into inventory_rows(period,source_row,material,plant,division_description,location_group,season,
                   historical_year_bucket,aging_bucket,unrestricted_quantity,fiscal_total_amount)
                   values (?,?,?,?,?,?,?,'2026','1) 0-3 meses',?,?)""",
                [period, index, f"MAT-{index}", plant, division, location, season, qty, value],
            )


def test_filter_clause_ignores_unknown_dimensions_and_uses_parameters() -> None:
    assert overview_filter_sql({}) == ("", [])
    assert overview_filter_sql({"plant": [], "hack": ["x"], "division": "texto"}) == ("", [])
    clause, params = overview_filter_sql({"plant": ["2115", "2115", " "], "location": ["Não informado"]})
    assert params == ["2115", "Não informado"] and "?" in clause and "2115" not in clause  # valores sempre como parâmetro


def test_summary_and_every_chart_follow_the_filters(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, _sent, _replies = env
    seed(database)
    whole = dashboard_summary(settings, "2026-09")
    assert whole["fiscal_value"] == 220.0 and whole["filters"] == {}

    only_vestuario = dashboard_summary(settings, "2026-09", {"division": ["Vestuário"]})
    assert only_vestuario["fiscal_value"] == 90.0 and only_vestuario["quantity"] == 10
    assert {item["label"] for item in only_vestuario["plants"]} == {"1081", "2115"}
    assert only_vestuario["aging_for_season"]["columns"] == ["SP", "SU"]
    assert [item["fiscal_value"] for item in only_vestuario["trend"]] == [40.0, 90.0]  # Evolução com o mesmo filtro
    assert only_vestuario["pmm_comparison"]["previous"] == 8.0  # 40 / 5 na competência anterior
    assert {item["label"] for item in only_vestuario["pmm_breakdowns"]["division"]} == {"Vestuário"}
    assert only_vestuario["filters"] == {"division": ["Vestuário"]}

    # Vários filtros juntos (E entre dimensões, OU entre valores) e "Não informado" = campo vazio.
    combined = dashboard_summary(settings, "2026-09", {"location": ["Não informado", "5_NVS - LOJAS"], "season": ["SU"]})
    assert combined["fiscal_value"] == 60.0 and combined["rows"] == 1
    assert combined["locations_unmapped"] == [{"plant": "2115", "rows": 1, "value": 60.0}]
    # Centros de cada local (detalhamento do Mapa mental), com os mesmos filtros.
    assert [p["plant"] for p in whole["location_plants"]["2_CD - EXTREMA"]] == ["1081"]
    assert whole["location_plants"]["2_CD - EXTREMA"][0]["value"] == 150.0
    assert only_vestuario["location_plants"] == {
        "2_CD - EXTREMA": [{"plant": "1081", "rows": 1, "quantity": 4.0, "value": 30.0}],
        "Não informado": [{"plant": "2115", "rows": 1, "quantity": 6.0, "value": 60.0}],
    }

    options = {d["key"]: d for d in overview_filter_options(settings, "2026-09")["dimensions"]}
    assert [item["value"] for item in options["plant"]["values"]] == ["1081", "2115", "2030"]  # maior valor fiscal primeiro
    assert "Não informado" in [item["value"] for item in options["location"]["values"]]

    client, _csrf = client_for(ADMIN)
    response = client.get("/api/dashboard/summary", params={"period": "2026-09", "filters": json.dumps({"plant": ["2030"]})})
    assert response.status_code == 200 and response.json()["fiscal_value"] == 10.0
    assert client.get("/api/dashboard/summary", params={"period": "2026-09", "filters": "[1]"}).status_code == 422
    assert client.get("/api/dashboard/filter-options", params={"period": "2026-09"}).json()["dimensions"][0]["key"] == "division"
