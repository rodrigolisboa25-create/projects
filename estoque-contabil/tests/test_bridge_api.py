"""Duas máquinas pela API: carga na máquina A chega à máquina B pelo Drive, sem reinstalar."""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import ops_contabil.web.app as web_app
from ops_contabil.auth import SESSION_COOKIE, create_session_token
from ops_contabil.db import connect
from ops_contabil.inventory import ensure_inventory_schema
from ops_contabil.settings import Settings
from test_sap_upload import upload, wait_job, zmm119_workbook

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADMIN = "bridge.admin@gruposbf.com.br"
USER = "bridge.user@gruposbf.com.br"


def make_machine(tmp_path: Path, name: str, email: str, role: str, pages: str) -> tuple[Settings, TestClient, str]:
    root = tmp_path / name
    (root / "config").mkdir(parents=True)
    shutil.copy(PROJECT_ROOT / "config" / "schemas.yaml", root / "config" / "schemas.yaml")
    database = root / "processed" / "ops.duckdb"
    settings = Settings(
        root=root,
        raw={
            "project": {"database": str(database), "processed": str(database.parent), "landing": str(root / "landing"), "output": str(root / "output")},
            "sources": {"all_brazil_materials": {}},
            "runtime": {"sap_timeout_seconds": 300},
            "bridge": {"enabled": True},
        },
    )
    with connect(database) as connection:
        ensure_inventory_schema(connection)
        connection.execute(
            "insert into allowed_users(email,is_active,role,allowed_pages,identity_subject) values (?,true,?,?,?)",
            [email, role, pages, f"windows:{email}"],
        )
    client = TestClient(web_app.create_app(settings))
    client.cookies.set(SESSION_COOKIE, create_session_token(settings, email, f"windows:{email}"))
    return settings, client, client.get("/api/auth/session").json()["csrf_token"]


@pytest.fixture()
def drive(tmp_path: Path, monkeypatch) -> Path:
    folder = tmp_path / "Drives compartilhados" / "Estoque_Cont"
    folder.mkdir(parents=True)
    monkeypatch.setenv("OPS_BRIDGE_ROOT", str(folder))
    monkeypatch.setattr(web_app, "enrich_inventory_from_all_brazil", lambda *_a, **_k: {"coverage_pct": 100.0})
    monkeypatch.setattr(web_app, "enrich_inventory_pass_step", lambda *_a, **_k: {"status": "enriched", "message": "ok"})
    monkeypatch.setattr(web_app, "apply_mapping_rules", lambda *_a, **_k: None)
    web_app.SAP_JOBS.clear()
    return folder


def test_upload_on_admin_machine_reaches_user_machine_without_reinstall(drive: Path, tmp_path: Path) -> None:
    _, admin, admin_csrf = make_machine(tmp_path, "admin", ADMIN, "admin", "[]")
    _, user, user_csrf = make_machine(tmp_path, "user", USER, "user", '["overview","agent"]')
    source = zmm119_workbook(tmp_path / "zmm119.xlsx", [("7170", "1081", "MAT000000001", 10), ("7170", "1080", "MAT000000002", 4)])

    job = wait_job(admin, upload(admin, admin_csrf, "ZMM119", "2026-09", source).json()["job_id"])
    assert job["status"] == "COMPLETED"
    pointer = drive / "periodos" / "2026-09" / "atual.json"
    for _ in range(120):  # a publicação roda em segundo plano logo após a carga
        if pointer.is_file():
            break
        time.sleep(0.25)
    assert json.loads(pointer.read_text(encoding="utf-8"))["rows"] == 2

    assert user.get("/api/bridge/revision").json()["data_revision"] == 0
    synced = user.post("/api/bridge/sync", headers={"X-CSRF-Token": user_csrf})
    assert synced.status_code == 200, synced.text
    assert [item["period"] for item in synced.json()["result"]["applied"]] == ["2026-09"]
    assert user.get("/api/bridge/revision").json()["data_revision"] == 1

    admin_summary = admin.get("/api/dashboard/summary?period=2026-09").json()
    user_summary = user.get("/api/dashboard/summary?period=2026-09").json()
    for key in ("rows", "fiscal_value", "quantity", "materials", "pmm"):
        assert user_summary[key] == admin_summary[key]
    assert any(item["period"] == "2026-09" for item in user.get("/api/inventory/periods").json()["periods"])
    status = {item["period"]: item["situation"] for item in user.get("/api/bridge/status").json()["periods"]}
    assert status["2026-09"] == "Sincronizada"


def test_optimus_on_user_machine_sees_periods_received_from_the_drive(drive: Path, tmp_path: Path, monkeypatch) -> None:
    _, admin, admin_csrf = make_machine(tmp_path, "admin", ADMIN, "admin", "[]")
    _, user, user_csrf = make_machine(tmp_path, "user", USER, "user", '["overview","agent"]')
    source = zmm119_workbook(tmp_path / "zmm119.xlsx", [("7170", "1081", "MAT000000001", 10)])
    assert wait_job(admin, upload(admin, admin_csrf, "ZMM119", "2026-09", source).json()["job_id"])["status"] == "COMPLETED"
    for _ in range(120):
        if (drive / "periodos" / "2026-09" / "atual.json").is_file():
            break
        time.sleep(0.25)
    user.post("/api/bridge/sync", headers={"X-CSRF-Token": user_csrf})

    sent: list[dict] = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            sent.append(json)

            class Response:
                status_code = 200
                text = ""

                @staticmethod
                def json():
                    return {"output": "ok"}

            return Response()

    monkeypatch.setenv("N8N_CHAT_URL", "http://n8n.invalid/webhook")
    monkeypatch.setattr(web_app.httpx, "AsyncClient", FakeClient)
    response = user.post(
        "/api/optimus/chat",
        json={"message": "Quais competências existem?", "session_id": "sessao-ponte-1", "period": "2026-09"},
        headers={"X-CSRF-Token": user_csrf},
    )
    assert response.status_code == 200, response.text
    context = json.loads(re.search(r"\[CONTEXTO_OPS_CONTABIL\]\n(.*)\n\[/CONTEXTO_OPS_CONTABIL\]", sent[0]["chatInput"], re.S).group(1))
    assert [item["period"] for item in context["available_periods"]] == ["2026-09"]
    assert context["summary"]["rows"] == 1


def test_permissions_folder_change_and_backup(drive: Path, tmp_path: Path) -> None:
    _, admin, admin_csrf = make_machine(tmp_path, "admin", ADMIN, "admin", "[]")
    _, user, user_csrf = make_machine(tmp_path, "user", USER, "user", '["overview","agent"]')
    headers = {"X-CSRF-Token": admin_csrf, "Content-Type": "application/json"}

    assert user.post("/api/bridge/publish", headers={"X-CSRF-Token": user_csrf}).status_code == 403
    assert user.put("/api/settings/bridge-root", json={"path": str(tmp_path)}, headers={"X-CSRF-Token": user_csrf}).status_code == 403
    assert user.post("/api/settings/backup/run", headers={"X-CSRF-Token": user_csrf}).status_code == 403

    bad = admin.put("/api/settings/bridge-root", json={"path": str(tmp_path / "nao_existe")}, headers=headers)
    assert bad.status_code == 422
    new_folder = tmp_path / "Drives compartilhados" / "Estoque_Cont_Contingencia"
    new_folder.mkdir()
    changed = admin.put("/api/settings/bridge-root", json={"path": str(new_folder), "leave_redirect": True}, headers=headers)
    assert changed.status_code == 200 and Path(changed.json()["root"]["path"]) == new_folder
    assert Path(user.get("/api/bridge/status").json()["root"]["path"]) == new_folder  # segue o aviso na pasta antiga

    backups = tmp_path / "meus_backups"
    preferences = admin.get("/api/settings").json()["preferences"]
    preferences.update(backup_enabled=True, backup_folder=str(backups))
    assert admin.put("/api/settings", json=preferences, headers=headers).status_code == 200
    ran = admin.post("/api/settings/backup/run", headers={"X-CSRF-Token": admin_csrf})
    assert ran.status_code == 200, ran.text
    assert ran.json()["status"] == "created" and Path(ran.json()["file"]).parent == backups
    assert admin.get("/api/settings").json()["backup"]["last_backup_file"] == ran.json()["file"]
