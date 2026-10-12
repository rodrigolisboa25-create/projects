"""Visão e relatórios: Evolução do Aging por Material — série histórica mês a mês desde o Product Offer End Dt."""

from __future__ import annotations

from ops_contabil.db import connect
from test_optimus_import import ADMIN, env  # noqa: F401 - fixture reaproveitada


def seed(database) -> None:
    rows = [
        # linha, descrição, quantidade, valor, Product Offer End Dt
        (1, "TENIS A", 10, 1000.0, "2026-07-15"),
        (2, "TENIS A", 30, 3000.0, "2026-09-01"),
        (3, "TENIS B", 5, 500.0, "2026-08-31"),
        (4, "TENIS B", 5, 999.0, "2026-12-31"),  # Futures: ainda não está em aging na data-base
        (5, "CAMISETA C", 1, 10.0, None),        # sem Product Offer End Dt: fora da série
    ]
    with connect(database) as connection:
        for row, name, quantity, value, offer_end in rows:
            connection.execute(
                """insert into inventory_rows(period,source_row,company,plant,material,material_description,unrestricted_quantity,
                   fiscal_total_amount,product_offer_end_date) values ('2026-09',?,'7170','1081',?,?,?,?,?)""",
                [row, f"MAT-{row}", name, quantity, value, offer_end],
            )


def test_aging_grows_month_by_month_until_the_base_date(env) -> None:  # noqa: F811
    _settings, database, _downloads, client_for, _sent, _replies = env
    seed(database)
    client, _csrf = client_for(ADMIN)
    data = client.get("/api/dashboard/aging-race", params={"period": "2026-09"}).json()
    assert data["as_of"] == "2026-09-30" and data["months"] == ["2026-07", "2026-08", "2026-09"]
    series = {item["name"]: item["series"] for item in data["materials"]}
    assert set(series) == {"TENIS A", "TENIS B"}
    # TENIS A: em jul só o lote de 15/07 (16 dias até 31/07); em set os dois lotes, dias ponderados pela quantidade.
    assert series["TENIS A"][0] == {"value": 1000.0, "quantity": 10.0, "days": 16.0}
    assert series["TENIS A"][2] == {"value": 4000.0, "quantity": 40.0, "days": round((10 * 77 + 30 * 29) / 40, 1)}
    # TENIS B entra em agosto; o lote Futures (dez/2026) não conta.
    assert series["TENIS B"][0] == {"value": 0.0, "quantity": 0.0, "days": None}
    assert series["TENIS B"][2] == {"value": 500.0, "quantity": 5.0, "days": 30.0}
    other = client.get("/api/dashboard/aging-race", params={"period": "2026-09", "filters": '{"plant": ["9999"]}'}).json()
    assert other["months"] == [] and other["materials"] == []
