"""O contexto enviado ao Optimus precisa listar todas as competências carregadas."""

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

import ops_contabil.web.app as web_app
from ops_contabil.auth import SESSION_COOKIE, create_session_token
from ops_contabil.db import connect
from ops_contabil.inventory import ensure_inventory_schema
from ops_contabil.settings import Settings


def test_optimus_context_lists_every_loaded_period_with_kpis(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "processed" / "ops.duckdb"
    settings = Settings(
        root=Path(__file__).resolve().parents[1],
        raw={
            "project": {
                "database": str(database),
                "processed": str(database.parent),
                "landing": str(tmp_path / "landing"),
                "output": str(tmp_path / "output"),
            },
            "sources": {"all_brazil_materials": {}},
        },
    )
    email = "felipe.teste@gruposbf.com.br"
    subject = f"windows:{email}"
    with connect(database) as connection:
        ensure_inventory_schema(connection)
        rows = [
            ("2026-07", 1, "MAT-1", 10, 1000.0),
            ("2026-07", 2, "MAT-2", 10, 1000.0),   # julho: 2.000 / 20 = PMM 100
            ("2026-08", 1, "MAT-1", 20, 2400.0),
            ("2026-08", 2, "MAT-3", 20, 2400.0),   # agosto: 4.800 / 40 = PMM 120 (+20%)
        ]
        for period, source_row, material, quantity, fiscal in rows:
            connection.execute(
                "insert into inventory_rows(period,source_row,material,unrestricted_quantity,fiscal_total_amount) values (?,?,?,?,?)",
                [period, source_row, material, quantity, fiscal],
            )
        connection.execute(
            "insert into allowed_users(email,is_active,role,allowed_pages,identity_subject) values (?,true,'user','[\"overview\",\"agent\"]',?)",
            [email, subject],
        )

    sent: list[dict] = []

    class FakeResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"output": "ok"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            sent.append(json)
            return FakeResponse()

    monkeypatch.setenv("N8N_CHAT_URL", "http://n8n.invalid/webhook")
    monkeypatch.setattr(web_app.httpx, "AsyncClient", FakeClient)
    client = TestClient(web_app.create_app(settings))
    client.cookies.set(SESSION_COOKIE, create_session_token(settings, email, subject))
    csrf = client.get("/api/auth/session").json()["csrf_token"]

    response = client.post(
        "/api/optimus/chat",
        json={"message": "Qual a variação de PMM nos dois períodos?", "session_id": "sessao-teste-123", "period": "2026-07"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text

    chat_input = sent[0]["chatInput"]
    context = json.loads(re.search(r"\[CONTEXTO_OPS_CONTABIL\]\n(.*)\n\[/CONTEXTO_OPS_CONTABIL\]", chat_input, re.S).group(1))
    assert context["period"] == "2026-07"
    periods = {item["period"]: item for item in context["available_periods"]}
    assert set(periods) == {"2026-07", "2026-08"}
    assert periods["2026-07"]["is_selected"] is True and periods["2026-08"]["is_selected"] is False
    assert periods["2026-07"]["pmm"] == 100.0 and periods["2026-08"]["pmm"] == 120.0
    assert periods["2026-08"]["previous_period"] == "2026-07"
    assert periods["2026-08"]["pmm_variation_pct"] == 20.0
    assert periods["2026-08"]["fiscal_value_variation_pct"] == 140.0
    assert periods["2026-08"]["materials"] == 2
    assert "2026-07, 2026-08" in context["period_guidance"]
    assert "Nunca afirme que uma competência presente nessa lista não foi importada" in context["period_guidance"]
