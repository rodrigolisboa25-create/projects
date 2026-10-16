"""Inserir visuais (Visão e relatórios): o Optimus só descreve o gráfico; o sistema valida, calcula e evita duplicados."""

from __future__ import annotations

import json

import pytest

from ops_contabil import visuals
from ops_contabil.db import connect
from ops_contabil.inventory import overview_filter_options
from test_optimus_import import ADMIN, USER, env  # noqa: F401 - fixture reaproveitada
from test_overview_filters import seed


def test_local_interpreter_understands_simple_requests(env) -> None:  # noqa: F811
    settings, database, *_ = env
    seed(database)
    options = overview_filter_options(settings, "2026-09")
    pie = visuals.local_interpret("Pizza do valor fiscal por Season", options)["spec"]
    assert (pie["type"], pie["dimension"], pie["measure"]) == ("pizza", "season", "fiscal_value")
    matrix = visuals.local_interpret("matriz do valor por divisão e season", options)["spec"]
    assert (matrix["type"], matrix["dimension"], matrix["series"]) == ("matriz", "division", "season")
    top = visuals.local_interpret("top 3 centros por quantidade livre", options)["spec"]
    assert (top["type"], top["dimension"], top["measure"], top["top"]) == ("barras", "plant", "free_quantity", 3)
    cut = visuals.local_interpret("valor por centro só da divisão Calçados", options)["spec"]
    assert cut["dimension"] == "plant" and cut["filters"] == {"division": ["Calçados"]}


def test_spec_validation_and_duplicates() -> None:
    with pytest.raises(ValueError):
        visuals.clean_spec({"type": "matriz", "dimension": "division"})  # matriz precisa de duas dimensões
    with pytest.raises(ValueError):
        visuals.clean_spec({"type": "barras", "dimension": "inexistente"})
    plants = visuals.clean_spec({"type": "barras", "dimension": "plant"})
    assert visuals.find_duplicate(plants, [])["target"] == "chart-plants"  # igual ao "Valor por centro"
    assert visuals.find_duplicate({**plants, "filters": {"division": ["Calçados"]}}, []) is None  # recorte novo
    pie = visuals.clean_spec({"type": "pizza", "dimension": "division"})
    duplicate = visuals.find_duplicate(pie, [])
    assert duplicate["target"] == "chart-division" and duplicate["same_type"] is False  # mesmo dado, outro estilo
    assert visuals.find_duplicate(visuals.clean_spec({"type": "evolucao"}), [])["target"] == "chart-trend"
    assert visuals.find_duplicate(visuals.clean_spec({"type": "corrida"}), [])["target"] == "chart-material-race"
    mine = {"id": "abc", "spec": visuals.clean_spec({"type": "barras", "dimension": "plant", "measure": "free_quantity"})}
    assert visuals.find_duplicate(dict(mine["spec"]), [mine])["target"] == "visual-abc"


def test_lines_and_ranking_table_with_top_by_aging(env) -> None:  # noqa: F811
    settings, database, *_ = env
    seed(database)
    with connect(database) as connection:  # aging em dias e descrição dos materiais
        connection.execute("update inventory_rows set aging_days = source_row * 100, material_description = 'Produto ' || source_row")
    options = overview_filter_options(settings, "2026-09")
    table = visuals.local_interpret("tabela dos top 2 materiais com maior aging", options)["spec"]
    assert (table["type"], table["dimension"], table["rank_by"], table["top"]) == ("tabela", "material_name", "aging_days", 2)
    rows = visuals.dataset(settings, "2026-09", table)["rows"]
    assert [r["label"] for r in rows] == ["Produto 6", "Produto 5"] and rows[0]["aging_days"] == 600.0  # top pelo aging
    lines = visuals.clean_spec({"type": "linhas", "dimension": "season", "series": "material_name", "measure": "fiscal_value",
                                "rank_by": "aging_days", "top": 2})
    data = visuals.dataset(settings, "2026-09", lines)
    assert [s["label"] for s in data["series"]] == ["Produto 6", "Produto 5"] and data["x"] == ["FA", "SU"]
    assert data["series"][0]["values"] == [10.0, None]  # Produto 6 só tem FA (valor 10)
    single = visuals.dataset(settings, "2026-09", visuals.clean_spec({"type": "linhas", "dimension": "season"}))
    assert len(single["series"]) == 1 and sum(single["series"][0]["values"]) == 220.0


def test_visuals_travel_between_machines_by_the_drive(env, tmp_path, monkeypatch) -> None:  # noqa: F811
    settings, *_ = env
    root = tmp_path / "Estoque_Cont"
    root.mkdir()
    import ops_contabil.access_sync as access_sync
    monkeypatch.setattr(access_sync, "machine_file_name", lambda _s: "MAQUINA-A.json")
    item = visuals.add_visual(settings, "adm@gruposbf.com.br", visuals.clean_spec({"type": "pizza", "dimension": "season"}))
    assert visuals.sync_visuals(settings, root)["published"]
    journal = root / "visuais" / "alteracoes" / "MAQUINA-A.json"
    payload = json.loads(journal.read_text(encoding="utf-8"))
    payload["entries"][item["id"]].update(deleted=True, changed_at="2999-01-01T00:00:00")  # outra máquina removeu depois
    (root / "visuais" / "alteracoes" / "MAQUINA-B.json").write_text(json.dumps(payload), encoding="utf-8")
    assert visuals.sync_visuals(settings, root)["received"] == 1 and visuals.list_visuals(settings) == []


def test_lone_visual_gets_a_partner_suggestion() -> None:
    pie = visuals.clean_spec({"type": "pizza", "dimension": "season"})
    assert visuals.needs_partner(pie, False, [])  # sozinho e esticado de ponta a ponta
    assert not visuals.needs_partner(pie, False, [False])  # já tem par: fica lado a lado
    assert not visuals.needs_partner(visuals.clean_spec({"type": "evolucao"}), False, [])  # evolução fica bem larga
    partners = visuals.complements(pie, [])
    assert len(partners) == 2 and all(p["dimension"] == "season" and p["type"] != "pizza" for p in partners)
    plants = visuals.clean_spec({"type": "pizza", "dimension": "plant", "measure": "free_quantity"})
    assert all(visuals.find_duplicate(p, []) is None for p in visuals.complements(plants, []))  # nunca sugere um original


def test_dataset_uses_the_same_numbers_and_page_filters(env) -> None:  # noqa: F811
    settings, database, *_ = env
    seed(database)
    pie = visuals.dataset(settings, "2026-09", visuals.clean_spec({"type": "pizza", "dimension": "season"}))
    assert sum(item["value"] for item in pie["items"]) == 220.0
    columns = visuals.dataset(settings, "2026-09", visuals.clean_spec({"type": "colunas", "dimension": "division"}))
    variance = {v["label"]: v for v in columns["variance"]}
    assert columns["previous_period"] == "2026-08" and variance["Vestuário"]["previous_value"] == 40.0
    matrix = visuals.dataset(settings, "2026-09", visuals.clean_spec({"type": "matriz", "dimension": "division", "series": "season"}),
                             {"plant": ["1081"]})  # filtro da página vale também para o visual
    assert sum(map(sum, matrix["values"])) == 150.0
    trend = visuals.dataset(settings, "2026-09", visuals.clean_spec({"type": "evolucao", "filters": {"division": ["Vestuário"]}}))
    assert [item["fiscal_value"] for item in trend["items"]] == [40.0, 90.0]


def test_api_insert_list_remove_and_agent_reply(env) -> None:  # noqa: F811
    settings, database, _downloads, client_for, _sent, replies = env
    seed(database)
    client, csrf = client_for(ADMIN)
    headers = {"X-CSRF-Token": csrf}
    agent = {"action": "create", "reply": "Vou inserir a pizza.", "spec": {"type": "pizza", "dimension": "season", "title": "Valor por Season"}}
    replies[:] = [f"[[VISUAL]]{json.dumps(agent)}[[/VISUAL]]"]
    answer = client.post("/api/dashboard/visuals/interpret", headers=headers,
                         json={"period": "2026-09", "message": "pizza do valor por season"}).json()
    assert answer["action"] == "create" and answer["source"] == "optimus" and answer["spec"]["type"] == "pizza"
    assert len(answer["pairing"]["suggestions"]) == 2  # pizza sozinha ficaria esticada: o Optimus sugere um par
    link = client.get("/api/settings/bridge/link").json()
    assert link["url"].startswith("https://drive.google.com/drive/folders/") and link["default"] is True
    assert client.post("/api/settings/bridge/link", headers=headers, json={"url": "https://exemplo.com/pasta-qualquer"}).status_code == 422

    replies[:] = []  # n8n sem resposta válida: o sistema interpreta sozinho
    local = client.post("/api/dashboard/visuals/interpret", headers=headers,
                        json={"period": "2026-09", "message": "valor por centro"}).json()
    assert local["action"] == "exists" and local["duplicate"]["target"] == "chart-plants" and local["source"] == "sistema"

    saved = client.post("/api/dashboard/visuals", headers=headers, json={"period": "2026-09", "spec": answer["spec"]})
    assert saved.status_code == 200 and saved.json()["data"]["items"]
    again = client.post("/api/dashboard/visuals", headers=headers, json={"period": "2026-09", "spec": answer["spec"]})
    assert again.status_code == 409  # o mesmo visual não é inserido duas vezes
    blocked = client.post("/api/dashboard/visuals", headers=headers,
                          json={"period": "2026-09", "spec": {"type": "barras", "dimension": "plant"}})
    assert blocked.status_code == 409  # igual a um gráfico original
    forced = client.post("/api/dashboard/visuals", headers=headers,
                         json={"period": "2026-09", "spec": {"type": "pizza", "dimension": "division"}, "force": True})
    assert forced.status_code == 200  # mesmo dado de um original, mas em outro estilo (confirmado pelo usuário)

    listed = client.get("/api/dashboard/visuals?period=2026-09").json()["visuals"]
    assert [v["type"] for v in listed] == ["pizza", "pizza"] and all(v["span"] == 6 for v in listed)
    other, other_csrf = client_for(USER)
    assert [v["id"] for v in other.get("/api/dashboard/visuals?period=2026-09").json()["visuals"]] == [v["id"] for v in listed]  # da equipe toda
    assert other.delete(f"/api/dashboard/visuals/{listed[0]['id']}", headers={"X-CSRF-Token": other_csrf}).status_code == 403
    assert other.post("/api/dashboard/visuals/interpret", headers={"X-CSRF-Token": other_csrf},
                      json={"period": "2026-09", "message": "pizza por season"}).status_code == 403  # só administradores
    assert client.delete(f"/api/dashboard/visuals/{listed[0]['id']}", headers=headers).status_code == 200
    assert len(client.get("/api/dashboard/visuals?period=2026-09").json()["visuals"]) == 1
