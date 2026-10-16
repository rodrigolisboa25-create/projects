"""Agente de conferência, Fase 3: regras ajustáveis do PASSO A PASSO aprovadas e restauradas por um administrador."""

from __future__ import annotations

import pytest

from ops_contabil import mb59
from ops_contabil.conference import save_run
from ops_contabil.db import connect
from ops_contabil.mb59 import enrich_inventory_pass_step
from ops_contabil.pass_step_rules import DEFAULT_RULES, load_rules, save_rules
from test_master_base import seed
from test_optimus_import import ADMIN, env  # noqa: F401 - fixture reaproveitada


@pytest.fixture(autouse=True)
def no_all_brazil(monkeypatch):
    monkeypatch.setattr(mb59, "pass_step_lookup_from_all_brazil", lambda *args, **kwargs: {"lookup": {}})


def test_rules_change_the_pass_step_and_can_be_restored(env) -> None:  # noqa: F811
    settings, database, *_ = env
    seed(database)
    with connect(database) as connection:
        connection.execute(
            """insert into inventory_rows(period,source_row,company,plant,material,center_material_key,unrestricted_quantity,fiscal_total_amount)
               values ('2026-09',3,'7170','1081','MAT-D','1081MAT-D',1,10)""")
        connection.execute("insert into master_base_rows values ('2026-08','3000MAT-D',null,'SP',2023)")
    # Padrão: Year pelo Material (MAT-D só existia em outro centro no mês anterior).
    enrich_inventory_pass_step(settings, "2026-09")
    with connect(database) as connection:
        assert connection.execute("select cast(year as integer) from inventory_rows where material='MAT-D'").fetchone()[0] == 2023
        rules = load_rules(connection)
        assert rules == DEFAULT_RULES
        rules["year"] = {"step1": "gr_import_first", "step2": "ce_mat"}
        saved = save_rules(connection, rules, action="aprovada", changed_by=ADMIN, reason="teste")
        assert saved["version"] == 1
    # Year pelo CE & MAT: o centro 1081 não tinha MAT-D no mês anterior, então o Year fica vazio.
    result = enrich_inventory_pass_step(settings, "2026-09")
    assert result["rules"]["year"]["step2"] == "ce_mat"
    with connect(database) as connection:
        assert connection.execute("select year from inventory_rows where material='MAT-D'").fetchone()[0] is None


def test_admin_approves_suggestion_and_restores_default(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, *_ = env
    seed(database)
    save_run(settings, "conf-teste", period="2026-09", file_name="Posição.xlsb", sha="x", status="COMPLETED",
             message="ok", created_by=ADMIN, summary={"fields": {}}, diagnosis={"fields": {}}, finished=True)
    client, csrf = client_for(ADMIN)
    headers = {"X-CSRF-Token": csrf}

    bad = client.post("/api/governance/rules/apply", headers=headers,
                      json={"conference_id": "conf-teste", "field": "season", "step1": "inventada", "step2": "ce_mat"})
    assert bad.status_code == 422
    applied = client.post("/api/governance/rules/apply", headers=headers,
                          json={"conference_id": "conf-teste", "field": "season", "step1": "gr_all_latest", "step2": "material",
                                "reason": "Sugestão da conferência"})
    assert applied.status_code == 200 and applied.json()["version"] == 1
    rules = client.get("/api/governance/rules").json()
    assert rules["rules"]["season"] == {"step1": "gr_all_latest", "step2": "material"}
    assert rules["history"][0]["action"] == "aprovada" and rules["history"][0]["conference_id"] == "conf-teste"

    restored = client.post("/api/governance/rules/restore", headers=headers, json={"version": 0, "period": "2026-09"})
    assert restored.status_code == 200
    rules = client.get("/api/governance/rules").json()
    assert rules["rules"] == DEFAULT_RULES and rules["history"][0]["action"] == "restaurada" and rules["version"] == 2

    status = client.get("/api/governance/conference", params={"period": "2026-09"}).json()
    assert status["run"]["conference_id"] == "conf-teste" and status["run"]["status"] == "COMPLETED"
