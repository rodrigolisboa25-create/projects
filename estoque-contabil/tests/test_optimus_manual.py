"""Manual do sistema no Optimus: seções certas por pergunta, ferramenta local e cobertura das páginas."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import ops_contabil.web.app as web_app
from ops_contabil.auth import SESSION_COOKIE, create_session_token, page_catalog
from ops_contabil.db import connect
from ops_contabil.inventory import ensure_inventory_schema
from ops_contabil.settings import Settings
from ops_contabil.system_manual import load_sections, manual_for_question, manual_lookup

EMAIL = "manual.teste@gruposbf.com.br"


def test_manual_covers_every_page_and_every_section_has_keywords() -> None:
    sections = load_sections()
    titles = " | ".join(section.title for section in sections)
    for page in [*page_catalog(), {"label": "Configurações"}]:
        assert page["label"].casefold() in titles.casefold(), f"sem seção para a página {page['label']}"
    for section in sections:
        assert section.keywords, f"seção sem palavras-chave: {section.title}"
        assert len(section.body) > 200, f"seção vazia demais: {section.title}"


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("O que a página Base de estoque faz?", "Página Base de estoque"),
        ("Como é calculado o aging?", "Regras de cálculo"),
        ("Onde faço backup e como restauro a base?", "Restaurar a partir de um backup"),
        ("Quais bases o sistema utiliza?", "Fontes de dados"),
        ("Quais parâmetros preciso preencher para extrair a MB59?", "Página Extrações SAP"),
        ("O que significa a seta vermelha no Aging for Season?", "Página Visão e relatórios"),
        ("A extração da ZMM119 falhou, o que faço?", "Upload manual de planilha SAP (contingência)"),
        ("Como outro usuário recebe a base atualizada?", "Ponte de dados (Drive compartilhado Estoque_Cont)"),
        ("Como libero o acesso de um novo usuário ao Optimus?", "Perfis de acesso e permissões"),
    ],
)
def test_system_questions_get_the_right_sections(question: str, expected: str) -> None:
    sections = manual_for_question(question)
    assert expected in [section.title for section in sections]
    assert sum(len(section.text) for section in sections) <= 9000


@pytest.mark.parametrize(
    "question",
    ["Qual o valor fiscal de setembro?", "Quais os 10 materiais com maior valor em 2026-09?", "Compare o PMM de agosto e setembro", "oi"],
)
def test_data_questions_do_not_carry_the_manual(question: str) -> None:
    assert manual_for_question(question) == []


def test_manual_lookup_by_title_and_query() -> None:
    by_title = manual_lookup(["Página Mapping"])
    assert by_title["ok"] and by_title["sections"][0]["title"] == "Página Mapping"
    by_query = manual_lookup(None, "como restaurar um backup")
    assert "Restaurar a partir de um backup" in [item["title"] for item in by_query["sections"]]
    missing = manual_lookup(["assunto inexistente xyz"])
    assert missing["ok"] is False and missing["index"]


def make_client(tmp_path: Path, monkeypatch, replies: list[str]) -> tuple[TestClient, str, list[dict]]:
    database = tmp_path / "processed" / "ops.duckdb"
    settings = Settings(
        root=Path(__file__).resolve().parents[1],
        raw={
            "project": {"database": str(database), "processed": str(database.parent), "landing": str(tmp_path / "landing"), "output": str(tmp_path / "output")},
            "sources": {"all_brazil_materials": {}},
        },
    )
    with connect(database) as connection:
        ensure_inventory_schema(connection)
        connection.execute(
            "insert into inventory_rows(period,source_row,material,unrestricted_quantity,fiscal_total_amount) values ('2026-09',1,'MAT-1',10,1000.0)"
        )
        connection.execute(
            "insert into allowed_users(email,is_active,role,allowed_pages,identity_subject) values (?,true,'user','[\"overview\",\"agent\"]',?)",
            [EMAIL, f"windows:{EMAIL}"],
        )
    sent: list[dict] = []
    pending = list(replies)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            sent.append(json)
            text = pending.pop(0) if pending else "ok"

            class Response:
                status_code = 200

                @staticmethod
                def json():
                    return {"output": text}

            return Response()

    monkeypatch.setenv("N8N_CHAT_URL", "http://n8n.invalid/webhook")
    monkeypatch.setattr(web_app.httpx, "AsyncClient", FakeClient)
    client = TestClient(web_app.create_app(settings))
    client.cookies.set(SESSION_COOKIE, create_session_token(settings, EMAIL, f"windows:{EMAIL}"))
    return client, client.get("/api/auth/session").json()["csrf_token"], sent


def ask(client: TestClient, csrf: str, message: str) -> dict:
    response = client.post(
        "/api/optimus/chat",
        json={"message": message, "session_id": "sessao-manual-1", "period": "2026-09"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_chat_sends_manual_only_for_system_questions(tmp_path: Path, monkeypatch) -> None:
    client, csrf, sent = make_client(tmp_path, monkeypatch, ["resposta 1", "resposta 2"])

    ask(client, csrf, "Para que serve o Health Center?")
    system_input = sent[0]["chatInput"]
    manual = re.search(r"\[MANUAL_DO_SISTEMA\]\n(.*)\n\[/MANUAL_DO_SISTEMA\]", system_input, re.S)
    assert manual and "## Página Health Center" in manual.group(1)
    context = json.loads(re.search(r"\[CONTEXTO_OPS_CONTABIL\]\n(.*)\n\[/CONTEXTO_OPS_CONTABIL\]", system_input, re.S).group(1))
    assert "Página Health Center" in context["system_manual_index"]
    assert "system_manual" in context["local_tools"]
    assert system_input.index("[/MANUAL_DO_SISTEMA]") < system_input.index("[PERGUNTA_USUARIO]")

    ask(client, csrf, "Qual o valor fiscal de setembro?")
    assert "[MANUAL_DO_SISTEMA]" not in sent[1]["chatInput"]


def test_optimus_can_request_more_manual_sections_through_the_local_tool(tmp_path: Path, monkeypatch) -> None:
    request = '[[OPS_ACTION]]\n{"type":"system_manual","topics":["Página Mapping"],"query":"status da operação"}\n[[/OPS_ACTION]]'
    client, csrf, sent = make_client(tmp_path, monkeypatch, [request, "Resposta final sobre o Mapping"])

    result = ask(client, csrf, "Me explique o Mapping")

    assert result["response"] == {"output": "Resposta final sobre o Mapping"}
    tool = json.loads(re.search(r"\[RESULTADO_FERRAMENTA_LOCAL\]\n(.*)\n\[/RESULTADO_FERRAMENTA_LOCAL\]", sent[1]["chatInput"], re.S).group(1))
    assert tool["type"] == "system_manual" and tool["ok"] is True
    assert tool["sections"][0]["title"] == "Página Mapping"
    assert "BAIXADOS" in tool["sections"][0]["content"]
