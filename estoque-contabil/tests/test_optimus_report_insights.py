"""Optimus: resumo proativo dos principais gráficos da Visão e relatórios, sem passar na frente dos outros avisos."""

from __future__ import annotations

import ops_contabil.web.app as web_app
from ops_contabil import optimus_watch
from ops_contabil.db import connect
from ops_contabil.inventory import dashboard_summary
from test_optimus_import import ADMIN, action, ask, env, tool_result  # noqa: F401 - fixture reaproveitada
from test_optimus_proactive import SESSION, event_of, poll, proactive  # noqa: F401 - fixture reaproveitada


def test_report_facts_are_the_same_numbers_of_the_overview_page(proactive) -> None:  # noqa: F811
    settings, database, _client_for, _sent, _replies = proactive
    item = optimus_watch.report_insights_event(settings, "2026-09")
    event = item["event"]
    page = dashboard_summary(settings, "2026-09")
    assert item["key"] == "report_insights:2026-09" and item["low_priority"] is True
    assert event["type"] == "report_insights" and event["previous_period"] == "2026-08"
    assert event["kpis"]["fiscal_value"] == round(page["fiscal_value"], 2) == 1350.0
    assert event["kpis"]["variation_pct_vs_previous"]["fiscal_value"] == 35.0  # 1.000 → 1.350
    assert {"Aging for Season", "Lifecycle × Aging", "Division Description", "Risco de obsolescência", "Local de estoque",
            "Origem do material", "Evolução da posição de estoque", "Composição do custo fiscal"} <= set(event["charts"])
    assert event["charts"]["Centros sem local no Mapping"][0]["plant"] == "2115"
    assert sum(cell["value"] for cell in event["charts"]["Aging for Season"]["by_year"]) == 1350.0

    # Só volta a ser enviado quando os números da competência mudam.
    assert optimus_watch.report_insights_event(settings, "2026-09")["fingerprint"] == item["fingerprint"]
    with connect(database) as connection:
        connection.execute("update inventory_rows set fiscal_total_amount=fiscal_total_amount+5000 where period='2026-09' and source_row=1")
    assert optimus_watch.report_insights_event(settings, "2026-09")["fingerprint"] != item["fingerprint"]


def test_report_never_overtakes_other_warnings_or_a_pending_decision(proactive) -> None:  # noqa: F811
    _settings, _db, client_for, sent, replies = proactive
    client, _csrf = client_for(ADMIN)
    state = client.app.state
    state.optimus_watch["low_priority_gap"] = 0.0
    poll(client)
    fresh = state.optimus_watch_once()
    assert "report_insights" in {item["event"]["type"] for item in fresh}

    replies[:] = [lambda message: f"Texto do agente: {event_of(message)['type']}" for _ in range(12)]
    delivered = []
    for _ in range(12):
        batch = poll(client)
        if not batch:
            break
        delivered.extend(batch)
    types = [item["text"].removeprefix("Texto do agente: ") for item in delivered]
    # Os avisos saem primeiro; a oferta da All Brazil deixou uma decisão (sim/não) pendente no chat,
    # então o resumo espera — não aparece no meio de uma decisão.
    assert "all_brazil_newer" in types and "report_insights" not in types

    web_app.SAP_CONFIRMATIONS.pop(SESSION, None)  # o administrador respondeu à oferta
    report = poll(client)
    assert len(report) == 1 and report[0]["text"] == "Texto do agente: report_insights"
    assert report[0]["notify_title"] == "Optimus: resumo da Visão e relatórios"
    prompt = sent[-1]["chatInput"]
    assert "[INSTRUCAO_RESUMO_RELATORIOS]" in prompt and "### 📊 Visão e relatórios" in prompt
    assert event_of(sent[-1])["charts"]["Local de estoque"]  # o agente recebe os números dos gráficos
    assert all(item["key"] != "report_insights:2026-09" for item in state.optimus_watch_once())  # entregue: não repete


def test_report_waits_a_longer_gap_after_the_last_warning(proactive) -> None:  # noqa: F811
    _settings, _db, client_for, _sent, replies = proactive
    client, _csrf = client_for(ADMIN)
    state = client.app.state
    poll(client)
    web_app.OPTIMUS_OFFERS.clear()
    state.optimus_watch["last_delivery"][SESSION] = __import__("time").time()  # acabou de chegar um aviso
    web_app.OPTIMUS_OFFERS.append({  # só o resumo na fila
        "offer_id": "resumo", "key": "report:2026-09", "created_at": "2026-10-09T10:00:00",
        "created_ts": __import__("time").time(), "event": optimus_watch.report_insights_event(_settings, "2026-09")["event"],
        "parameters": None, "summary": None, "notified": False, "system": False, "low_priority": True, "status": "queued",
    })
    replies[:] = ["Resumo dos relatórios"]
    assert poll(client) == []  # menos de 3 minutos desde o último aviso: espera
    state.optimus_watch["last_delivery"].clear()
    assert poll(client)[0]["text"] == "Resumo dos relatórios"


def queue_report(settings) -> None:
    import time
    web_app.OPTIMUS_OFFERS.append({
        "offer_id": f"resumo-{time.time()}", "key": "report:2026-09", "created_at": "2026-10-09T10:00:00",
        "created_ts": time.time(), "event": optimus_watch.report_insights_event(settings, "2026-09")["event"],
        "parameters": None, "summary": None, "notified": False, "system": False, "low_priority": True, "status": "queued",
    })


def test_user_chooses_in_the_chat_whether_to_keep_receiving_the_report(proactive) -> None:  # noqa: F811
    settings, _db, client_for, sent, replies = proactive
    client, csrf = client_for(ADMIN)
    state = client.app.state
    state.optimus_watch["low_priority_gap"] = 0.0
    poll(client)
    web_app.OPTIMUS_OFFERS.clear()

    # 1º resumo: a pessoa ainda não escolheu — o agente recebe choice = null e pergunta no fim da mensagem.
    queue_report(settings)
    replies[:] = ["### 📊 Visão e relatórios — setembro/2026\n...\n_Quer receber este resumo sempre aqui no chat? Responda sim ou não._"]
    first = poll(client)
    assert first and event_of(sent[-1])["delivery_preference"] == {"choice": None}
    assert "set_report_insights" in sent[-1]["chatInput"]  # a ferramenta está descrita para o agente

    # A pessoa responde "não" no chat: o agente grava a escolha na hora (sem confirmação extra).
    replies[:] = [action({"type": "set_report_insights", "enabled": False}), "Combinado, não envio mais o resumo."]
    ask(client, csrf, "não precisa")
    saved = tool_result(sent[-1])
    assert saved["ok"] and saved["status"] == "SAVED" and saved["enabled"] is False
    queue_report(settings)
    calls = len(sent)
    assert poll(client) == [] and len(sent) == calls  # resumo descartado sem chamar o agente
    assert web_app.OPTIMUS_OFFERS[-1]["status"] == "declined"

    # Pede para voltar a receber: os próximos resumos chegam e terminam com "é só me pedir".
    replies[:] = [action({"type": "set_report_insights", "enabled": True}), "Pronto, volto a enviar o resumo."]
    ask(client, csrf, "pode voltar a me mandar o resumo dos relatórios")
    assert tool_result(sent[-1])["enabled"] is True
    queue_report(settings)
    replies[:] = ["Resumo de novo"]
    delivered = poll(client)[0]
    assert delivered["text"] == "Resumo de novo"
    # Gráficos anexados pelo sistema (o agente não desenha): mesmos números do evento.
    titles = [chart["title"] for chart in delivered["charts"]]
    assert titles == ["Lifecycle × Aging", "PMM analítico por divisão", "Division Description", "Evolução da posição de estoque"]
    aging = delivered["charts"][0]
    assert [entry["label"] for entry in aging["legend"]] == ["Active"] and aging["items"][0]["label"] == "0-3 meses"
    assert delivered["charts"][1]["subtitle"].startswith("PMM da competência R$")
    assert event_of(sent[-1])["delivery_preference"] == {"choice": True}
    context = __import__("json").loads(__import__("re").search(
        r"\[CONTEXTO_OPS_CONTABIL\]\n(.*)\n\[/CONTEXTO_OPS_CONTABIL\]", sent[-1]["chatInput"], __import__("re").S).group(1))
    assert context["report_insights_preference"] is True


def test_report_survives_a_server_restart_until_it_reaches_the_chat(proactive) -> None:  # noqa: F811
    _settings, _db, client_for, _sent, replies = proactive
    client, _csrf = client_for(ADMIN)
    state = client.app.state
    state.optimus_watch["low_priority_gap"] = 0.0
    poll(client)
    assert any(item["key"] == "report_insights:2026-09" for item in state.optimus_watch_once())
    # Na fila (ou sendo escrito) não entra de novo.
    state.optimus_watch_once()
    assert sum(1 for offer in web_app.OPTIMUS_OFFERS if offer.get("key") == "report_insights:2026-09") == 1
    web_app.OPTIMUS_OFFERS.clear()  # o servidor reiniciou: a fila em memória se perdeu
    assert any(item["key"] == "report_insights:2026-09" for item in state.optimus_watch_once())  # volta a ser detectado
    web_app.OPTIMUS_OFFERS[:] = [offer for offer in web_app.OPTIMUS_OFFERS if offer.get("key") == "report_insights:2026-09"]
    replies[:] = ["Resumo entregue"]
    assert poll(client)[0]["text"] == "Resumo entregue"
    assert all(item["key"] != "report_insights:2026-09" for item in state.optimus_watch_once())  # entregue: não repete
