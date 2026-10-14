"""Apresentações do Optimus (html-ppt): o agente monta o roteiro, o sistema desenha com os números reais."""

from __future__ import annotations

import io
import json
import time
import zipfile

import ops_contabil.web.app as web_app
from ops_contabil import presentations as decks
from ops_contabil.optimus_watch import presentation_offer_event, report_insights
from test_optimus_import import ADMIN, action, ask, env  # noqa: F401 - fixture reaproveitada
from test_optimus_proactive import SESSION, poll, proactive, seed_base  # noqa: F401 - fixture reaproveitada


def deck_reply(title: str = "Estoque em setembro", theme: str = "corporate-clean") -> str:
    spec = {
        "title": title, "subtitle": "Diretoria", "theme": theme,
        "slides": [
            {"layout": "cover", "kicker": "POSIÇÃO CONTÁBIL", "title": "Estoque <Fisia>", "subtitle": "Setembro", "tags": ["Aging"]},
            {"layout": "kpis", "kicker": "01 / VISÃO", "title": "Valor fiscal cresce", "kpis": ["fiscal_value", "pmm", "inexistente"]},
            {"layout": "chart", "kicker": "02 / AGING", "title": "Aging concentrado", "chart": "lifecycle_aging", "insight": "Recente."},
            {"layout": "chart", "kicker": "03 / X", "title": "Gráfico que não existe", "chart": "nao_existe"},
            {"layout": "slides_do_google", "title": "Layout inválido"},
            {"layout": "columns", "kicker": "04 / PRÓXIMOS", "title": "Próximos passos",
             "columns": [{"label": "A", "title": "Mapping", "text": "Cadastrar o centro 2115."}]},
            {"layout": "closing", "title": "Obrigado."},
        ],
    }
    return f"[[DECK]]{json.dumps(spec, ensure_ascii=False)}[[/DECK]]"


def wait_job(client, deck_id: str, seconds: float = 30) -> dict:
    deadline = time.time() + seconds
    while time.time() < deadline:
        data = client.get(f"/api/presentations/{deck_id}").json()
        if (data.get("job") or {}).get("status") in {"COMPLETED", "FAILED"}:
            return data
        time.sleep(0.2)
    raise AssertionError("a apresentação não terminou")


def test_spec_is_validated_and_rendered_with_system_numbers(env) -> None:  # noqa: F811
    settings, database, *_ = env
    seed_base(database)
    facts = report_insights(settings, "2026-09")
    spec = decks.normalize_spec(json.loads(deck_reply().split("[[DECK]]")[1].split("[[/DECK]]")[0]), facts)
    layouts = [slide["layout"] for slide in spec["slides"]]
    assert layouts == ["cover", "kpis", "chart", "columns", "closing"]  # gráfico e layout inválidos saem
    assert spec["slides"][1]["kpis"] == ["fiscal_value", "pmm"]
    html_text = decks.render_html(spec, facts)
    assert "Estoque &lt;Fisia&gt;" in html_text and "<Fisia>" not in html_text  # texto do agente é escapado
    assert decks.brl(facts["kpis"]["fiscal_value"]) in html_text  # número do KPI vem do sistema
    assert html_text.count('class="slide hp-slide') == 5
    assert 'src="http' not in html_text and 'href="http' not in html_text  # autocontido, sem rede
    assert "MIT" in html_text or "html-ppt-skill" in html_text


def wrap(payload: dict) -> str:
    return f"[[DECK]]{json.dumps(payload, ensure_ascii=False)}[[/DECK]]"


OUTLINE = {
    "title": "Estoque em setembro", "subtitle": "Diretoria", "theme": "estoque-contabil",
    "slides": [
        {"l": "cover", "t": "Estoque em setembro", "k": "POSIÇÃO"},
        {"l": "kpis", "t": "Valor fiscal cresce", "k": "VISÃO", "kpis": ["fiscal_value", "pmm"]},
        {"l": "section", "t": "Aging e lifecycle", "k": "AGING"},
        {"l": "flow", "t": "Pouco estoque passou de 12 meses", "k": "AGING", "id": "aging_flow"},
        {"l": "chart", "t": "Aging concentrado no recente", "k": "AGING", "id": "lifecycle_aging"},
        {"l": "closing", "t": "Obrigado."},
    ],
}


def agent_protocol(message: dict) -> str:
    """Agente falso que segue as etapas: estrutura, textos (por número do slide) e revisão por operações."""
    prompt = message["chatInput"]
    if "etapa 1/2" in prompt:
        return wrap(OUTLINE)
    if "etapa 2/2" in prompt:
        block = prompt.split("[SLIDES]\n")[1].split("\n[/SLIDES]")[0]
        numbers = [line.split(":")[0] for line in block.splitlines()]
        return wrap({n: {"insight": f"Texto do agente {n}.", "lede": f"Abertura {n}.", "subtitle": "Diretoria financeira"} for n in numbers})
    if "REVISÃO" in prompt:
        return wrap({"theme": "tokyo-night", "ops": [
            {"op": "edit", "n": 2, "set": {"title": "Valor fiscal revisado"}},
            {"op": "del", "n": 5},
            {"op": "add", "after": 2, "slide": {"layout": "chart", "kicker": "99 / RISCO", "title": "Risco por divisão", "chart": "risk"}},
        ]})
    return "ok"


def test_agent_builds_the_deck_user_revises_and_downloads(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, sent, replies = env
    seed_base(database)
    client, csrf = client_for(ADMIN)
    replies[:] = [agent_protocol for _ in range(10)]
    started = client.post("/api/presentations", headers={"X-CSRF-Token": csrf}, json={"period": "2026-09"}).json()
    data = wait_job(client, started["deck_id"])
    assert data["job"]["status"] == "COMPLETED" and data["source"] == "agent" and data["version"] == 1
    assert not data["job"].get("warning")  # todos os textos vieram do agente
    prompts = [m["chatInput"] for m in sent]
    assert any("etapa 1/2" in p for p in prompts) and sum("etapa 2/2" in p for p in prompts) >= 2  # textos em lotes
    assert all(m["sessionId"].startswith(f"apresentacao-{started['deck_id']}-") for m in sent)  # sessão nova por chamada
    assert all(len(p) < 6000 for p in prompts)  # prompts curtos: o gateway do n8n corta em ~20 s
    _version, spec, html_text = decks.load_version(settings, started["deck_id"])
    assert [s["layout"] for s in spec["slides"]] == ["cover", "kpis", "section", "flow", "chart", "closing"]
    assert [s["kicker"] for s in spec["slides"][1:-1]] == ["02 / VISÃO", "03 / AGING", "04 / AGING", "05 / AGING"]  # = posição (rodapé N / total)
    assert spec["slides"][4]["insight"] == "Texto do agente 5." and spec["slides"][2]["lede"] == "Abertura 3."
    assert 'class="hp-flow hp-pickable"' in html_text and 'data-count=' in html_text and "hp-section-num" in html_text
    assert 'data-fx="constellation"' in html_text and 'class="notes"' in html_text  # efeito e roteiro de fala
    view = client.get(f"/api/presentations/{started['deck_id']}/view")
    assert view.status_code == 200 and "Estoque em setembro" in view.text

    # Sugestão do usuário: o agente devolve só as operações; o sistema aplica no roteiro atual.
    client.post(f"/api/presentations/{started['deck_id']}/revise", headers={"X-CSRF-Token": csrf},
                json={"message": "use um tema escuro, troque o título dos KPIs e inclua o risco"})
    revised = wait_job(client, started["deck_id"])
    assert revised["job"]["status"] == "COMPLETED" and revised["version"] == 2
    assert "[ROTEIRO_ATUAL]" in sent[-1]["chatInput"] and "use um tema escuro" in sent[-1]["chatInput"]
    _version, spec, html_text = decks.load_version(settings, started["deck_id"])
    assert spec["theme"] == "tokyo-night" and 'data-theme="tokyo-night"' in html_text
    assert [s["layout"] for s in spec["slides"]] == ["cover", "kpis", "chart", "section", "flow", "closing"]
    assert spec["slides"][1]["title"] == "Valor fiscal revisado" and spec["slides"][2]["chart"] == "risk"
    assert spec["slides"][2]["kicker"] == "03 / RISCO" and spec["slides"][2]["insight"]  # texto completado pelo sistema

    # Revisão em que o agente devolve o roteiro inteiro (formato antigo) também vale.
    replies[:] = [deck_reply(title="Estoque em setembro — revisado", theme="corporate-clean")]
    client.post(f"/api/presentations/{started['deck_id']}/revise", headers={"X-CSRF-Token": csrf}, json={"message": "refaça"})
    again = wait_job(client, started["deck_id"])
    assert again["version"] == 3 and again["title"] == "Estoque em setembro — revisado"

    html_download = client.get(f"/api/presentations/{started['deck_id']}/download", params={"format": "html"})
    assert html_download.headers["content-type"].startswith("text/html") and "attachment" in html_download.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(client.get(f"/api/presentations/{started['deck_id']}/download", params={"format": "zip"}).content))
    assert any(name.endswith(".html") for name in archive.namelist()) and "LICENSE-html-ppt-skill.txt" in archive.namelist()


def test_texts_that_do_not_arrive_are_completed_by_the_system(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, _sent, replies = env
    seed_base(database)
    client, csrf = client_for(ADMIN)
    # Estrutura chega; os lotes de textos não (gateway): o sistema completa com os fatos, sem falhar.
    replies[:] = [wrap(OUTLINE)]
    started = client.post("/api/presentations", headers={"X-CSRF-Token": csrf}, json={"period": "2026-09"}).json()
    data = wait_job(client, started["deck_id"])
    assert data["job"]["status"] == "COMPLETED" and data["source"] == "agent"
    assert "textos do sistema" in data["job"]["warning"]
    _version, spec, _html = decks.load_version(settings, started["deck_id"])
    assert spec["slides"][4]["insight"] and spec["slides"][4]["points"]  # chart com texto tirado dos fatos
    assert spec["slides"][3]["insight"].startswith("Futures somam")


def test_request_that_changes_nothing_is_not_reported_as_applied(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, _sent, replies = env
    seed_base(database)
    client, csrf = client_for(ADMIN)
    replies[:] = [agent_protocol for _ in range(10)]
    deck_id = client.post("/api/presentations", headers={"X-CSRF-Token": csrf}, json={"period": "2026-09"}).json()["deck_id"]
    wait_job(client, deck_id)
    # Pedido de cor de um número: não é editável pelo roteiro; o agente devolve ops vazio com um recado.
    replies[:] = [wrap({"ops": [], "note": "A cor de um número específico não é editável; posso trocar o tema."})]
    client.post(f"/api/presentations/{deck_id}/revise", headers={"X-CSRF-Token": csrf}, json={"message": "deixe o FA 2026 mais escuro"})
    data = wait_job(client, deck_id)
    assert data["job"]["status"] == "COMPLETED" and data["job"]["unchanged"] is True and data["version"] == 1
    assert "Nada foi alterado" in data["job"]["message"] and "cor de um número" in data["job"]["message"]
    assert not (decks.deck_dir(settings, deck_id) / "v2.html").exists()


def test_changes_summary_brand_and_matrix_contrast(env) -> None:  # noqa: F811
    settings, database, *_ = env
    seed_base(database)
    facts = report_insights(settings, "2026-09")
    old = decks.default_spec(facts)
    assert decks.describe_changes(old, json.loads(json.dumps(old))) == []
    new = decks.apply_patch(old, {"theme": "tokyo-night", "ops": [{"op": "edit", "n": 3, "set": {"title": "Outro título"}}]})
    changes = decks.describe_changes(old, new)
    assert changes[0] == "tema: estoque-contabil → tokyo-night" and changes[1].startswith("slide 3 (")
    closing = decks.normalize_spec({"slides": [{"layout": "kpis", "title": "Estoque do Grupo SBF"},
                                              {"layout": "closing", "title": "Estoque Contábil — Grupo SBF"}]}, facts)
    assert closing["slides"][1]["title"] == "Estoque da Fisia"
    assert closing["slides"][-1]["title"] == "Fisia - 09/2026"  # último slide sempre "Fisia - MM/AAAA" da competência
    html_text = decks.render_html(decks.normalize_spec(old, facts), facts)
    assert "hp-hot" in html_text and ".hp-matrix td.hp-hot{color:var(--bg)" in html_text  # célula clara com número escuro


def test_agent_changes_the_form_but_never_the_values(env) -> None:  # noqa: F811
    settings, database, *_ = env
    seed_base(database)
    facts = report_insights(settings, "2026-09")
    spec = decks.normalize_spec(decks.default_spec(facts), facts)
    decks.number_kickers(spec)
    n_kpis = next(i for i, s in enumerate(spec["slides"], 1) if s["layout"] == "kpis")
    n_season = next(i for i, s in enumerate(spec["slides"], 1) if s.get("chart") == "aging_season")
    n_location = next(i for i, s in enumerate(spec["slides"], 1) if s.get("chart") == "location")
    new = decks.apply_patch(spec, {"ops": [
        {"op": "style", "n": n_season, "target": "cell:2026|FA", "set": {"color": "#0B2545", "bold": True}},
        {"op": "style", "n": n_season, "target": "title", "set": {"color": "url(javascript:x)", "size": 9}},  # cor inválida; tamanho limitado
        {"op": "style", "n": n_season, "target": "x\"><script>", "set": {"color": "laranja"}},  # endereço inválido
        {"op": "number", "n": n_kpis, "set": {"format": "full", "decimals": 7}},
        {"op": "chart", "n": n_location, "set": {"type": "donut", "top": 2, "highlight": ["extrema"], "colors": {"x": "javascript"}}},
        {"op": "style", "n": 0, "target": "values", "set": {"bold": True}},
        {"op": "edit", "n": n_kpis, "set": {"fiscal_value": 1}},  # tentar "mudar valor": campo ignorado
    ]})
    new = decks.normalize_spec(new, facts)
    decks.number_kickers(new)
    season = new["slides"][n_season - 1]
    assert season["styles"] == {"cell:2026|fa": {"color": "#0b2545", "bold": True}, "title": {"size": 2.5}}
    assert new["slides"][n_kpis - 1]["number_opts"] == {"format": "full", "decimals": 2}
    assert new["slides"][n_location - 1]["chart_opts"] == {"type": "donut", "top": 2, "highlight": ["extrema"]}
    assert new["styles"] == {"values": {"bold": True}}
    html_text = decks.render_html(new, facts)
    assert '[data-ref="cell:2026|fa"]' in html_text and "javascript" not in html_text and "<script>\"" not in html_text
    full = decks._num(facts["kpis"]["fiscal_value"], 2)
    assert f"R$ {full}" in html_text and 'data-full="1"' in html_text  # mesmo valor do sistema, escrito por extenso
    location = facts["charts"]["Local de estoque"]
    assert decks.pct(location[0]["share_pct"]) in html_text  # rosca mostra a participação real no valor fiscal
    assert any("formato dos números" in c for c in decks.describe_changes(spec, new))


def test_missing_choice_becomes_buttons_applied_without_the_agent(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, sent, replies = env
    seed_base(database)
    client, csrf = client_for(ADMIN)
    replies[:] = [agent_protocol for _ in range(10)]
    deck_id = client.post("/api/presentations", headers={"X-CSRF-Token": csrf}, json={"period": "2026-09"}).json()["deck_id"]
    wait_job(client, deck_id)
    # "Mude a cor da barra" sem dizer a cor: o agente pergunta; o painel mostra a paleta (só nesse caso).
    replies[:] = [wrap({"ops": [], "ask": {"question": "Qual cor para as barras do slide 5?", "pick": "color",
                                           "op": {"op": "chart", "n": 5, "set": {"series": {"Active": "$VALUE"}}}}})]
    client.post(f"/api/presentations/{deck_id}/revise", headers={"X-CSRF-Token": csrf}, json={"message": "mude a cor da barra do aging"})
    data = wait_job(client, deck_id)
    choices = data["job"]["choices"]
    assert data["job"]["unchanged"] is True and data["version"] == 1 and data["job"]["message"] == "Qual cor para as barras do slide 5?"
    green = next(option for option in choices["options"] if option["label"] == "Verde claro")
    assert green["color"] == "#86efac" and green["patch"]["ops"][0]["set"]["series"]["Active"] == "#86efac"

    calls = len(sent)
    client.post(f"/api/presentations/{deck_id}/apply", headers={"X-CSRF-Token": csrf}, json={"patch": green["patch"], "label": "Verde claro"})
    data = wait_job(client, deck_id)
    assert data["job"]["status"] == "COMPLETED" and data["version"] == 2 and len(sent) == calls  # sem chamar o agente
    _version, spec, html_text = decks.load_version(settings, deck_id)
    assert spec["slides"][4]["chart_opts"] == {"series": {"Active": "#86efac"}} and 'fill="#86efac"' in html_text

    # Cor que o sistema não conhece: em vez de "nada foi alterado", a paleta para escolher.
    replies[:] = [wrap({"ops": [{"op": "chart", "n": 5, "set": {"color": "verde-musgo"}}], "note": "Alterei a cor."})]
    client.post(f"/api/presentations/{deck_id}/revise", headers={"X-CSRF-Token": csrf}, json={"message": "barra verde musgo"})
    data = wait_job(client, deck_id)
    assert data["job"]["unchanged"] is True and "verde-musgo" in data["job"]["choices"]["title"]
    assert data["job"]["choices"]["options"][0]["patch"]["ops"][0]["set"]["color"].startswith("#")
    assert decks._color("verde claro") == "#86efac" and decks._color("Azul Escuro") == "#0b2545"


def test_open_slide_same_type_and_offer_per_base_update(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, sent, replies = env
    seed_base(database)
    client, csrf = client_for(ADMIN)
    replies[:] = [agent_protocol for _ in range(10)]
    deck_id = client.post("/api/presentations", headers={"X-CSRF-Token": csrf}, json={"period": "2026-09"}).json()["deck_id"]
    wait_job(client, deck_id)
    # O painel manda o slide aberto: o agente sabe que "esse slide" é o 5 e não precisa perguntar.
    replies[:] = [wrap({"ops": [{"op": "chart", "n": 5, "set": {"type": "bars"}}], "note": "Troquei para barras."})]
    client.post(f"/api/presentations/{deck_id}/revise", headers={"X-CSRF-Token": csrf},
                json={"message": "troque o tipo do gráfico desse slide", "slide": 5})
    data = wait_job(client, deck_id)
    assert "[SLIDE_ABERTO]\n5 · " in sent[-1]["chatInput"]
    # "Trocar" para o tipo que o gráfico já tem (barras) não é mudança: sem versão nova e sem "aplicada".
    assert data["job"]["unchanged"] is True and data["version"] == 1
    _version, spec, _html = decks.load_version(settings, deck_id)
    choices = decks.ask_choices({"question": "Qual tipo?", "pick": "chart_type",
                                 "op": {"op": "chart", "n": 5, "set": {"type": "$VALUE"}}}, spec)
    assert [o["label"] for o in choices["options"]] == ["Colunas", "Rosca", "Tabela"]  # sem o tipo atual

    # Oferta de apresentação a cada atualização da base: acompanha a versão do resumo entregue.
    from ops_contabil.optimus_watch import mark_delivered
    mark_delivered(settings, "report_insights:2026-09", "resumo-v1")
    first = presentation_offer_event(settings, "2026-09")["fingerprint"]
    mark_delivered(settings, "report_insights:2026-09", "resumo-v2")  # base atualizada: números novos
    assert presentation_offer_event(settings, "2026-09")["fingerprint"] != first


def test_over_12_months_card_matches_the_obsolescence_chart(env) -> None:  # noqa: F811
    settings, database, *_ = env
    seed_base(database)
    from ops_contabil.inventory import dashboard_summary
    summary = dashboard_summary(settings, "2026-09")
    risk = report_insights(settings, "2026-09")["charts"]["Risco de obsolescência"]["all_divisions_total"]
    over = summary["over_12_months"]
    assert round(over["value"], 2) == round(risk["over_12_months_value"], 2)  # card = total do gráfico de risco
    assert round(over["pct_of_received"], 1) == round(risk["over_12_months_pct_of_received"], 1)


def test_coverage_card_becomes_over_12_months_like_the_report_page(env) -> None:  # noqa: F811
    settings, database, *_ = env
    seed_base(database)
    facts = report_insights(settings, "2026-09")
    spec = decks.normalize_spec({"slides": [
        {"layout": "highlight", "kicker": "DESTAQUE", "title": "Cobertura All Brazil de 100%", "kpi": "coverage",
         "caption": "registros com Division"},
        {"layout": "kpis", "title": "Visão geral", "kpis": ["fiscal_value", "coverage"], "insight": "Cobertura All Brazil de 100%."},
    ]}, facts)
    highlight, kpis = spec["slides"][1], spec["slides"][2]
    assert highlight["kpi"] == "over_12_months" and "Cobertura" not in highlight["title"] + highlight["caption"]
    assert kpis["kpis"] == ["fiscal_value", "over_12_months"] and not kpis["insight"]
    html_text = decks.render_html(spec, facts)
    assert "Cobertura All Brazil" not in html_text and "Estoque com mais de 12 meses" in html_text
    assert "coverage" not in decks.KPIS and "cobertura" not in decks.facts_brief(facts).lower()


def test_free_charts_cover_any_cut_of_the_base_including_projection(env) -> None:  # noqa: F811
    from ops_contabil.presentation_data import dataset

    settings, database, *_ = env
    seed_base(database)  # agosto R$ 1.000; setembro R$ 1.350 (1081 R$ 1.050 + 2115 R$ 300)
    facts = report_insights(settings, "2026-09")
    facts["_loader"] = lambda query: dataset(settings, "2026-09", query)
    spec = {"slides": [
        {"layout": "chart", "kicker": "PROJEÇÃO", "chart": "custom",
         "data": {"dimension": "period", "measure": "fiscal_value", "projection": 3}},
        {"layout": "chart", "kicker": "CENTROS", "chart": "custom",
         "data": {"dimension": "plant", "measure": "fiscal_value", "compare": True, "filters": {"division": ["Calçados"]}}},
        {"layout": "chart", "title": "Dimensão inventada", "chart": "custom", "data": {"dimension": "cor_da_caixa"}},
    ]}
    decks.auto_texts(spec, facts)  # como no app: textos do sistema antes da validação
    spec = decks.normalize_spec(spec, facts)
    projection, plants = spec["slides"][1], spec["slides"][2]
    assert len(spec["slides"]) == 4  # capa, 2 gráficos livres, encerramento (dimensão desconhecida sai)
    assert projection["data"] == {"dimension": "period", "measure": "fiscal_value", "periods": 6, "projection": 3}
    # Tendência linear: +R$ 350 por mês → out R$ 1.700, nov R$ 2.050, dez R$ 2.400 (marcados como projeção).
    assert projection["title"] == f"Valor fiscal projetado em {decks.brl(2400)} em dezembro/2026"
    assert "tendência linear das 2 competências" in projection["insight"]
    html_text = decks.render_html(spec, facts)
    assert "out/26 proj." in html_text and "dez/26 proj." in html_text and decks.brl(1700) in html_text
    assert "Projeção" in html_text and "Realizado" in html_text
    model = decks.chart_model("custom", facts, plants["data"])
    assert [(item["label"], item["share"], item["variation"]) for item in model["items"]] == [("1081", 77.8, 5.0), ("2115", 22.2, None)]
    assert plants["title"].startswith("1081 lidera em valor fiscal")
    prompt = decks.patch_prompt(facts, spec, "inclua uma projeção para os próximos 3 meses")
    assert '"projection":1-6' in prompt and "Nunca diga que não consegue" in prompt and len(prompt) < 9000


def test_patch_operations_follow_the_current_numbering() -> None:
    current = {"title": "T", "subtitle": "S", "theme": "estoque-contabil",
               "slides": [{"layout": "cover", "title": "1"}, {"layout": "bullets", "title": "2"}, {"layout": "bullets", "title": "3"},
                          {"layout": "bullets", "title": "4"}, {"layout": "closing", "title": "5"}]}
    result = decks.apply_patch(current, {"ops": [
        {"op": "move", "n": 4, "after": 1}, {"op": "del", "n": 2}, {"op": "add", "after": 3, "slide": {"layout": "bullets", "title": "novo"}},
        {"op": "edit", "n": 3, "set": {"title": "3 editado", "layout": "inexistente"}}, {"op": "del", "n": 99},
    ]})
    assert [s["title"] for s in result["slides"]] == ["1", "4", "3 editado", "novo", "5"]
    assert result["slides"][2]["layout"] == "bullets" and current["slides"][2]["title"] == "3"  # original intacto


def test_without_the_agent_the_system_builds_the_default_deck(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, _sent, replies = env
    seed_base(database)
    client, csrf = client_for(ADMIN)
    replies[:] = ["não sei montar", "continuo sem JSON"]
    started = client.post("/api/presentations", headers={"X-CSRF-Token": csrf}, json={"period": "2026-09"}).json()
    data = wait_job(client, started["deck_id"])
    assert data["job"]["status"] == "COMPLETED" and data["source"] == "system" and data["job"]["warning"]
    assert data["slides"] >= 8


def test_agent_starts_a_presentation_from_the_chat(env) -> None:  # noqa: F811
    _settings, database, _downloads, client_for, sent, replies = env
    seed_base(database)
    client, csrf = client_for(ADMIN)
    # O mesmo n8n atende a conversa e o pedido de roteiro: responde conforme o que recebeu.
    first = [True]

    def reply(message: dict) -> str:
        if "[TAREFA_APRESENTACAO]" in message["chatInput"]:
            return deck_reply()
        if first[0]:
            first[0] = False
            return action({"type": "create_presentation", "request": "só divisões e aging"})
        return "Estou montando a apresentação."

    replies[:] = [reply for _ in range(6)]
    answer = ask(client, csrf, "gere uma apresentação com divisões e aging")
    deck_id = answer["presentation"]["deck_id"]
    data = wait_job(client, deck_id)
    assert data["job"]["status"] == "COMPLETED"
    request_prompt = next(m["chatInput"] for m in sent if "[TAREFA_APRESENTACAO]" in m["chatInput"])
    assert "só divisões e aging" in request_prompt


def test_offer_comes_after_the_report_and_respects_the_setting(proactive) -> None:  # noqa: F811
    settings, database, client_for, _sent, _replies = proactive
    client, csrf = client_for(ADMIN)
    assert presentation_offer_event(settings, "2026-09") is None  # o resumo ainda não chegou
    from ops_contabil.optimus_watch import mark_delivered
    mark_delivered(settings, "report_insights:2026-09", "x")
    offer = presentation_offer_event(settings, "2026-09")
    assert offer and offer["low_priority"] and offer["key"] == "presentation_offer:2026-09"

    # Entregue no chat como pergunta fixa com botões (sem chamar o agente) e uma vez só.
    web_app.OPTIMUS_OFFERS.clear()
    state = client.app.state
    state.optimus_watch["low_priority_gap"] = 0.0
    poll(client)
    web_app.OPTIMUS_OFFERS.clear()
    web_app.OPTIMUS_OFFERS.append({"offer_id": "oferta", "key": offer["key"], "created_at": "2026-10-10T10:00:00",
                                   "created_ts": time.time(), "event": offer["event"], "parameters": None, "summary": None,
                                   "notified": False, "system": False, "low_priority": True, "fingerprint": offer["fingerprint"],
                                   "status": "queued"})
    state.optimus_watch["last_delivery"].clear()
    message = poll(client)[0]
    assert message["kind"] == "presentation_offer" and "apresentação" in message["text"] and message["period"] == "2026-09"
    assert message["notify"] is True and message["notify_title"]  # o chat dispara a notificação do Windows
    assert presentation_offer_event(settings, "2026-09") is not None  # o vigia ainda detecta…
    from ops_contabil.optimus_watch import new_events
    assert new_events(settings, [offer]) == []  # …mas já foi entregue: não repete

    # Configurações > Interface e experiência > Geração de apresentações desligada: sem oferta.
    saved = client.put("/api/preferences/interface", headers={"X-CSRF-Token": csrf}, json={"presentations_enabled": False})
    assert saved.json()["presentations_enabled"] is False
    assert presentation_offer_event(settings, "2026-09") is None


def test_typed_yes_after_the_offer_starts_the_presentation(proactive) -> None:  # noqa: F811
    """Responder "sim" digitando (com ou sem "Responder a este aviso") também inicia a montagem."""
    settings, _db, client_for, sent, replies = proactive
    client, csrf = client_for(ADMIN)
    from ops_contabil.optimus_watch import mark_delivered
    mark_delivered(settings, "report_insights:2026-09", "x")
    offer = presentation_offer_event(settings, "2026-09")
    state = client.app.state
    state.optimus_watch["low_priority_gap"] = 0.0
    poll(client)
    web_app.OPTIMUS_OFFERS.clear()
    web_app.OPTIMUS_OFFERS.append({"offer_id": "oferta-sim", "key": offer["key"], "created_at": "2026-10-10T10:00:00",
                                   "created_ts": time.time(), "event": offer["event"], "parameters": None, "summary": None,
                                   "notified": False, "system": False, "low_priority": True, "fingerprint": offer["fingerprint"],
                                   "status": "queued"})
    state.optimus_watch["last_delivery"].clear()
    assert poll(client)[0]["kind"] == "presentation_offer"

    def agent(message: dict) -> str:
        if "[TAREFA_APRESENTACAO]" in message["chatInput"]:
            return deck_reply()
        if "[RESULTADO_FERRAMENTA_LOCAL]" in message["chatInput"]:
            return "Estou montando a apresentação."
        context = message["chatInput"]
        assert "recent_presentation_offer" in context and "presentation_offer" in context
        return action({"type": "create_presentation", "request": ""})

    replies[:] = [agent for _ in range(6)]
    answer = client.post("/api/optimus/chat", headers={"X-CSRF-Token": csrf},
                         json={"message": "sim", "session_id": SESSION, "period": "2026-09", "reply_to": "oferta-sim"}).json()
    assert answer["presentation"]["deck_id"]
    assert wait_job(client, answer["presentation"]["deck_id"])["job"]["status"] == "COMPLETED"
