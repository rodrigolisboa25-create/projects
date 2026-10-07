"""Optimus proativo: o sistema detecta fatos, o AGENTE escreve o aviso e só age após o "sim" do administrador."""

from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path

import pytest

import ops_contabil.sources.all_brazil as all_brazil
import ops_contabil.web.app as web_app
from ops_contabil import optimus_watch
from ops_contabil.db import connect
from ops_contabil.mappings import ensure_mapping_schema
from ops_contabil.sources.all_brazil import AllBrazilSnapshot
from test_optimus_import import ADMIN, USER, action, ask, env, tool_result  # noqa: F401 - fixture reaproveitada

SESSION = "sessao-importacao"


def seed_base(database: Path) -> None:
    with connect(database) as connection:
        ensure_mapping_schema(connection)
        connection.execute(
            """create table if not exists all_brazil_imports(period varchar primary key, snapshot_date date, source_path varchar,
               source_sha256 varchar, inventory_keys integer, matched_keys integer, coverage_pct double, duplicate_keys integer,
               conflict_keys integer, schema_fingerprint varchar, imported_at timestamp)"""
        )
        connection.execute(
            """insert into all_brazil_imports(period,snapshot_date,source_path,inventory_keys,matched_keys,coverage_pct,duplicate_keys,conflict_keys)
               values ('2026-09','2026-09-28','G:/AB/2026/09. Setembro/ALL_BRAZIL_28_09.xlsx',10,10,100,0,0)"""
        )
        for period, value in (("2026-08", 1000.0), ("2026-09", 1050.0)):
            connection.execute(
                """insert into inventory_rows(period,source_row,material,plant,unrestricted_quantity,fiscal_total_amount,
                   division_description,material_origin,lifecycle_description,lifecycle,season,year,product_offer_end_date,
                   aging_bucket,location_group,operation_status)
                   values (?,1,'MAT-1','1081',10,?,'Calçados','Nacional','Active','F1','FA',2026,'2026-01-01','1) 0-3 meses','2_CD - EXTREMA','ATIVO')""",
                [period, value],
            )
        # Centro sem regra no Mapping (local e status vazios), como o 2115 da base real.
        connection.execute(
            """insert into inventory_rows(period,source_row,material,plant,unrestricted_quantity,fiscal_total_amount,
               division_description,material_origin,lifecycle_description,lifecycle,season,year,product_offer_end_date,aging_bucket)
               values ('2026-09',2,'MAT-2','2115',5,300.0,'Calçados','Nacional','Active','F1','FA',2026,'2026-01-01','1) 0-3 meses')"""
        )


@pytest.fixture()
def proactive(env, monkeypatch):
    settings, database, downloads, client_for, sent, replies = env
    seed_base(database)
    monkeypatch.setattr(all_brazil, "resolve_all_brazil",
                        lambda _s, _d: AllBrazilSnapshot(path=Path("ALL_BRAZIL_30_09.xlsx"), snapshot_date=date(2026, 9, 30), period="2026-09"))
    monkeypatch.setattr(web_app, "system_health", lambda *args, **kwargs: {"indicators": [
        {"key": "backup", "title": "Backup programado", "level": "warning", "status": "Atrasado", "summary": "Cópia de segurança",
         "details": "Último backup há 3 dias.", "fix": "Confira a pasta de backup e clique em Fazer backup agora.",
         "support_email": "suporte@exemplo"},
        {"key": "slides", "title": "Google Slides", "level": "warning", "status": "Verificação parcial"},
    ]})
    web_app.OPTIMUS_OFFERS.clear()
    client, _ = client_for(ADMIN)
    client.app.state.optimus_watch["min_gap"] = 0.0  # os testes buscam vários avisos seguidos
    return settings, database, client_for, sent, replies


def poll(client) -> list[dict]:
    return client.get("/api/optimus/proactive", params={"session_id": SESSION}).json()["messages"]


def event_of(message: dict) -> dict:
    return json.loads(re.search(r"\[EVENTO_PROATIVO\]\n(.*)\n\[/EVENTO_PROATIVO\]", message["chatInput"], re.S).group(1))


def test_watch_detects_facts_and_the_agent_writes_each_warning(proactive) -> None:
    settings, database, client_for, sent, replies = proactive
    client, csrf = client_for(ADMIN)
    assert poll(client) == []  # o sistema abriu: o administrador passa a ser "presente"

    fresh = client.app.state.optimus_watch_once()
    types = {item["event"]["type"] for item in fresh}
    assert {"all_brazil_newer", "mapping_gaps", "health_center"} <= types
    assert "new_period_available" not in types and "documentation_updated" not in types  # silenciosos na 1ª vez
    assert all(item["event"].get("indicator", {}).get("key") != "slides" for item in fresh)
    assert client.app.state.optimus_watch_once() == []  # nada mudou: não repete

    replies[:] = [lambda message: f"Aviso do agente sobre {event_of(message)['type']}" for _ in range(10)]
    delivered = []
    for _ in range(10):
        batch = poll(client)
        if not batch:
            break
        delivered.extend(batch)
    texts = [item["text"] for item in delivered]
    assert texts[0] == "Aviso do agente sobre all_brazil_newer"  # cada aviso é escrito pelo agente
    assert {"Aviso do agente sobre mapping_gaps", "Aviso do agente sobre health_center"} <= set(texts)
    assert all(item["notify"] is True for item in delivered)  # a notificação sai pela tela aberta
    mapping_event = next(event_of(m) for m in sent if "[EVENTO_PROATIVO]" in m["chatInput"] and event_of(m)["type"] == "mapping_gaps")
    assert mapping_event["plants_without_location"][0]["plant"] == "2115"
    assert "5_NVS - LOJAS" in mapping_event["known_locations"]

    # A oferta da All Brazil ficou pendente; o "sim" reprocessa os joins pelo mesmo caminho da página.
    def confirm(message: dict) -> str:
        pending = json.loads(re.search(r"\[CONTEXTO_OPS_CONTABIL\]\n(.*)\n\[/CONTEXTO_OPS_CONTABIL\]", message["chatInput"], re.S).group(1))["pending_sap_confirmation"]
        assert pending["origin"] == "optimus_proactive" and pending["parameters"] == {"kind": "reprocess", "period": "2026-09"}
        assert pending["proactive_event"]["new_file"] == "ALL_BRAZIL_30_09.xlsx"
        return action({"type": "confirm_sap", "confirmation_id": pending["confirmation_id"]})

    replies[:] = [confirm, "Reprocessamento iniciado."]
    ask(client, csrf, "sim, pode reprocessar")
    started = tool_result(sent[-1])
    assert started["ok"] and started["status"] == "STARTED" and started["result"]["job_type"] == "ENRICHMENT_ONLY"


def test_reply_to_a_specific_warning_restores_its_own_pending_decision(proactive) -> None:
    _settings, _db, client_for, sent, replies = proactive
    client, csrf = client_for(ADMIN)
    poll(client)
    client.app.state.optimus_watch_once()
    replies[:] = [lambda message: f"Aviso: {event_of(message)['type']}" for _ in range(10)]
    delivered = []
    for _ in range(10):
        batch = poll(client)
        if not batch:
            break
        delivered.extend(batch)
    all_brazil_offer = next(item for item in delivered if item["text"] == "Aviso: all_brazil_newer")

    # Outra pendência entra na frente (regra de Mapping preparada na conversa)...
    replies[:] = [action({"type": "save_mapping_rule", "group": "location", "key_value": "2115", "value_2": "5_NVS - LOJAS"}), "Confirma?"]
    ask(client, csrf, "o 2115 é 5_NVS - LOJAS")
    assert tool_result(sent[-1])["parameters"]["kind"] == "mapping"

    # ...mas a resposta pelo botão "Responder" vale para o aviso da All Brazil.
    def check_reply(message: dict) -> str:
        context = json.loads(re.search(r"\[CONTEXTO_OPS_CONTABIL\]\n(.*)\n\[/CONTEXTO_OPS_CONTABIL\]", message["chatInput"], re.S).group(1))
        assert context["replying_to_warning"]["offer_id"] == all_brazil_offer["id"]
        assert context["replying_to_warning"]["message"] == "Aviso: all_brazil_newer"
        pending = context["pending_sap_confirmation"]
        assert pending["parameters"]["kind"] == "reprocess"
        return action({"type": "confirm_sap", "confirmation_id": pending["confirmation_id"]})

    replies[:] = [check_reply, "Reprocessando."]
    response = client.post("/api/optimus/chat", json={"message": "sim", "session_id": SESSION, "period": "2026-09",
                                                      "reply_to": all_brazil_offer["id"]}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.text
    assert tool_result(sent[-1])["status"] == "STARTED"

    # Aviso já decidido: responder de novo não recria a pendência.
    replies[:] = ["Esse aviso já foi resolvido."]
    client.post("/api/optimus/chat", json={"message": "sim", "session_id": SESSION, "period": "2026-09",
                                           "reply_to": all_brazil_offer["id"]}, headers={"X-CSRF-Token": csrf})
    context = json.loads(re.search(r"\[CONTEXTO_OPS_CONTABIL\]\n(.*)\n\[/CONTEXTO_OPS_CONTABIL\]", sent[-1]["chatInput"], re.S).group(1))
    assert context["pending_sap_confirmation"] is None


def test_backup_schedule_is_enabled_only_after_yes(proactive) -> None:
    _settings, _db, client_for, sent, replies = proactive
    client, csrf = client_for(ADMIN)
    replies[:] = [action({"type": "set_backup_schedule", "enabled": True, "frequency": "weekly"}), "Confirma?"]
    ask(client, csrf, "ative o backup semanal")
    prepared = tool_result(sent[-1])
    assert prepared["status"] == "CONFIRMATION_REQUIRED" and "semanal" in prepared["summary"]
    assert client.get("/api/bridge/status").json()["backup"]["enabled"] is False
    replies[:] = [action({"type": "confirm_sap", "confirmation_id": prepared["confirmation_id"]}), "Ativado."]
    ask(client, csrf, "sim")
    assert tool_result(sent[-1])["status"] == "DONE"
    backup = client.get("/api/bridge/status").json()["backup"]
    assert backup["enabled"] is True and backup["frequency"] == "weekly"


def test_event_returns_to_the_queue_when_the_agent_is_unavailable(proactive) -> None:
    _settings, _db, client_for, sent, replies = proactive
    client, _csrf = client_for(ADMIN)
    poll(client)
    client.app.state.optimus_watch_once()

    def offline(_message):
        raise RuntimeError("n8n fora do ar")

    replies[:] = [offline]
    assert poll(client) == []
    replies[:] = ["Aviso escrito depois que o agente voltou"]
    assert poll(client)[0]["text"] == "Aviso escrito depois que o agente voltou"


def test_chat_receives_at_most_one_agent_warning_per_minute(proactive) -> None:
    _settings, _db, client_for, sent, replies = proactive
    client, _csrf = client_for(ADMIN)
    client.app.state.optimus_watch["min_gap"] = 60.0
    poll(client)
    client.app.state.optimus_watch_once()
    replies[:] = [lambda message: f"Aviso: {event_of(message)['type']}" for _ in range(10)]
    assert len(poll(client)) == 1
    calls = len(sent)
    assert poll(client) == [] and len(sent) == calls  # o próximo espera 1 minuto, sem chamar o agente
    client.app.state.optimus_watch["last_delivery"].clear()
    assert len(poll(client)) == 1


def connectivity(network: str, n8n: str) -> list[dict]:
    return [
        {"key": "network", "title": "VPN / rede", "level": network, "status": "Conectada" if network == "healthy" else "Não detectada",
         "summary": "Túnel VPN", "details": "Nenhuma conexão VPN ativa foi detectada no Windows.", "fix": "Conecte a VPN corporativa."},
        {"key": "n8n", "title": "n8n / Optimus", "level": n8n, "status": "Online" if n8n == "healthy" else "Indisponível",
         "summary": "Webhook", "details": "HTTP 403.", "fix": "Verifique o workflow."},
    ]


def test_vpn_down_the_system_warns_and_the_agent_explains_when_it_returns(proactive, monkeypatch) -> None:
    _settings, _db, client_for, sent, replies = proactive
    client, _csrf = client_for(ADMIN)
    state = client.app.state
    poll(client)
    state.optimus_watch_once()  # avisos do agente já na fila
    monkeypatch.setattr(web_app, "connectivity_indicators", lambda _url: connectivity("critical", "critical"))
    outage = state.optimus_connectivity_check()
    assert outage["indicator"]["key"] == "network"  # a VPN é a causa, não o n8n
    toast = state.notifier.sent[-1]
    assert toast["category"] == "connectivity" and toast["view"] == "health" and "VPN / rede" in toast["title"]

    calls = len(sent)
    response = client.get("/api/optimus/proactive", params={"session_id": SESSION}).json()
    assert response["offline"] is True
    [notice] = response["messages"]
    assert notice["kind"] == "system" and "VPN / rede: Não detectada" in notice["text"] and "Conecte a VPN" in notice["text"]
    assert client.get("/api/optimus/proactive", params={"session_id": SESSION}).json()["messages"] == []
    assert len(sent) == calls  # sem conexão o agente nem é chamado
    state.optimus_connectivity_check()  # continua fora: não repete o aviso
    assert sum(1 for item in state.notifier.sent if item["category"] == "connectivity") == 1

    monkeypatch.setattr(web_app, "connectivity_indicators", lambda _url: connectivity("healthy", "healthy"))
    assert state.optimus_connectivity_check() is None
    replies[:] = [lambda message: f"Aviso: {event_of(message)['type']}" for _ in range(10)]
    first = poll(client)[0]
    assert first["text"] == "Aviso: connectivity_restored"  # o agente explica o retorno antes dos demais
    restored = event_of(sent[-1])
    assert restored["cause"]["key"] == "network" and restored["minutes_offline"] >= 1 and restored["queued_warnings"] >= 1
    assert poll(client)[0]["text"] != "Aviso: connectivity_restored"  # em seguida, os avisos que esperavam


def test_vpn_down_with_the_agent_reachable_is_written_by_the_agent_once(proactive, monkeypatch) -> None:
    _settings, _db, client_for, sent, replies = proactive
    client, _csrf = client_for(ADMIN)
    state = client.app.state
    poll(client)
    monkeypatch.setattr(web_app, "connectivity_indicators", lambda _url: connectivity("critical", "healthy"))
    assert state.optimus_connectivity_check() is None
    state.optimus_connectivity_check()
    queued = [item for item in web_app.OPTIMUS_OFFERS if item.get("status") == "queued"]
    assert [item["key"] for item in queued] == ["health:network"]
    replies[:] = ["A VPN caiu; conecte de novo para extrair do SAP."]
    assert poll(client)[0]["text"].startswith("A VPN caiu")
    assert not any(item["category"] == "connectivity" for item in state.notifier.sent)


def test_optimus_prepares_mapping_rule_and_saves_only_after_yes(proactive) -> None:
    settings, database, client_for, sent, replies = proactive
    client, csrf = client_for(ADMIN)
    replies[:] = [action({"type": "save_mapping_rule", "group": "location", "key_value": "2115", "value_2": "5_NVS - LOJAS"}), "Confirma?"]
    ask(client, csrf, "o 2115 é 5_NVS - LOJAS")
    prepared = tool_result(sent[-1])
    assert prepared["status"] == "CONFIRMATION_REQUIRED" and "2115" in prepared["summary"] and "nova regra" in prepared["summary"]
    with connect(database) as connection:
        assert connection.execute("select count(*) from mapping_rules where group_key='location' and key_value='2115'").fetchone()[0] == 0

    replies[:] = [action({"type": "confirm_sap", "confirmation_id": prepared["confirmation_id"]}), "Regra salva."]
    ask(client, csrf, "sim")
    done = tool_result(sent[-1])
    assert done["status"] == "DONE", done
    with connect(database) as connection:
        assert connection.execute(
            "select value_2 from mapping_rules where group_key='location' and key_value='2115'").fetchone()[0] == "5_NVS - LOJAS"


def test_common_user_gets_no_warnings_and_only_self_service_actions(proactive) -> None:
    _settings, _db, client_for, sent, replies = proactive
    admin_client, _ = client_for(ADMIN)
    poll(admin_client)
    admin_client.app.state.optimus_watch_once()
    client, csrf = client_for(USER)
    assert poll(client) == []  # avisos proativos são só para administradores

    replies[:] = [action({"type": "save_user_access", "email": "novo@gruposbf.com.br", "role": "admin"}), "Sem permissão."]
    ask(client, csrf, "me dê acesso de administrador")
    assert tool_result(sent[-1])["status"] == "FORBIDDEN"

    replies[:] = [action({"type": "set_interface_preferences", "density": "compact"}), "Confirma?"]
    ask(client, csrf, "deixe a tela compacta")
    prepared = tool_result(sent[-1])
    assert prepared["status"] == "CONFIRMATION_REQUIRED"
    replies[:] = [action({"type": "confirm_sap", "confirmation_id": prepared["confirmation_id"]}), "Pronto."]
    ask(client, csrf, "sim")
    assert tool_result(sent[-1])["status"] == "DONE"
    assert client.get("/api/preferences/interface").json()["density"] == "compact"


def test_business_checks(env) -> None:
    settings, database, *_ = env
    seed_base(database)
    # Fechamento: em outubro, a competência de setembro existe; em novembro, falta outubro.
    assert optimus_watch.closing_event(settings, today=date(2026, 10, 5)) is None
    assert optimus_watch.closing_event(settings, today=date(2026, 11, 3))["event"]["missing_period"] == "2026-10"
    # Variação: +35% no valor fiscal total chama a atenção.
    variation = optimus_watch.variation_event(settings, "2026-09")
    assert variation and any(item["kind"] == "total_fiscal_value" for item in variation["event"]["findings"])
    # Execução SAP parada há mais de 40 minutos.
    stuck = optimus_watch.stuck_job_events([{"job_id": "j1", "status": "EXPORTING_FILE", "started_at": "2026-10-05T10:00:00",
                                             "transaction": "ZMM119", "period": "2026-09"}], now=time.mktime((2026, 10, 5, 11, 0, 0, 0, 0, -1)))
    assert stuck and stuck[0]["event"]["running_minutes"] == 60
    # Eventos informativos viram referência na 1ª vez e só avisam quando mudam.
    first = optimus_watch.latest_period_event(settings, "2026-09")
    assert optimus_watch.new_events(settings, [first]) == []
    assert optimus_watch.new_events(settings, [optimus_watch.latest_period_event(settings, "2026-08")])[0]["event"]["period"] == "2026-08"
