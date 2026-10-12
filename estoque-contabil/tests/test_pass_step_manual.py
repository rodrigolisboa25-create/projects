"""PASSO A PASSO: o que MB59, mês anterior e All Brazil não trouxeram pode ser preenchido manualmente na Base de estoque."""

from __future__ import annotations

import pytest

from ops_contabil import mb59
from ops_contabil.db import connect
from ops_contabil.mb59 import enrich_inventory_pass_step
from test_optimus_import import ADMIN, env  # noqa: F401 - fixture reaproveitada
from test_pass_step_audit import seed


@pytest.fixture(autouse=True)
def no_all_brazil(monkeypatch):
    monkeypatch.setattr(mb59, "pass_step_lookup_from_all_brazil", lambda *args, **kwargs: {"lookup": {}})


def test_manual_fill_is_the_last_step_and_survives_reprocessing(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, _sent, _replies = env
    seed(database)
    enrich_inventory_pass_step(settings, "2026-09")  # 2115MAT-C fica sem nada nas três fontes
    client, csrf = client_for(ADMIN)
    headers = {"X-CSRF-Token": csrf}

    pending = client.get("/api/inventory/pass-step/pending", params={"period": "2026-09"}).json()
    keys = {item["center_material_key"]: item for item in pending["items"]}
    assert "2115MAT-C" in keys and set(keys["2115MAT-C"]["missing"]) == {"product_offer_end_date", "season", "year"}

    bad = client.post("/api/inventory/pass-step/manual", headers=headers, json={
        "period": "2026-09", "items": [{"center_material_key": "2115MAT-C", "season": "XX"}]})
    assert bad.status_code == 422 and "Season inválida" in bad.json()["detail"]

    saved = client.post("/api/inventory/pass-step/manual", headers=headers, json={
        "period": "2026-09",
        "items": [{"center_material_key": "2115MAT-C", "season": "fa", "year": "2025", "product_offer_end_date": "2026-06-30"}],
    })
    assert saved.status_code == 200 and saved.json()["cells_filled"] == 3

    grid = client.get("/api/inventory", params={"period": "2026-09", "page_size": 10}).json()
    row = next(r for r in grid["rows"] if r["material"] == "MAT-C")
    assert row["season"] == "FA" and int(float(row["year"])) == 2025
    assert grid["pass_step_sources"][str(row["source_row"])]["season"].startswith("Manual (")

    # Refazer a busca: as fontes continuam sem o valor, então o manual (4º passo) é mantido.
    result = enrich_inventory_pass_step(settings, "2026-09")
    assert result["field_sources"]["season"]["manual"] == 1 and result["not_found"]["season"] == 0
    with connect(database) as connection:
        assert connection.execute(
            "select season, cast(year as integer) from inventory_rows where period='2026-09' and material='MAT-C'").fetchone() == ("FA", 2025)
    assert "2115MAT-C" not in {i["center_material_key"] for i in
                               client.get("/api/inventory/pass-step/pending", params={"period": "2026-09"}).json()["items"]}
