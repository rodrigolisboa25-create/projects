"""Lista central de acessos: cadastro, desativação e exclusão valem em todas as máquinas."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import ops_contabil.web.app as web_app
from ops_contabil.access_sync import _update_state, local_view, read_merged, sync_access, verification
from ops_contabil.auth import BOOTSTRAP_ADMINS, SESSION_COOKIE, create_session_token
from ops_contabil.db import connect
from ops_contabil.health_center import _access_indicator
from ops_contabil.inventory import ensure_inventory_schema
from ops_contabil.settings import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADMIN_A = "admin.a@gruposbf.com.br"
ADMIN_B = "admin.b@gruposbf.com.br"
USER = "usuario.novo@gruposbf.com.br"


@pytest.fixture()
def drive(tmp_path: Path, monkeypatch) -> Path:
    folder = tmp_path / "Drives compartilhados" / "Estoque_Cont"
    folder.mkdir(parents=True)
    monkeypatch.setenv("OPS_BRIDGE_ROOT", str(folder))
    return folder


def machine(tmp_path: Path, name: str, users: list[tuple[str, str]]) -> tuple[Settings, TestClient]:
    root = tmp_path / name
    (root / "config").mkdir(parents=True)
    shutil.copy(PROJECT_ROOT / "config" / "schemas.yaml", root / "config" / "schemas.yaml")
    database = root / "processed" / "ops.duckdb"
    settings = Settings(
        root=root,
        raw={
            "project": {"database": str(database), "processed": str(database.parent), "landing": str(root / "landing"), "output": str(root / "output")},
            "sources": {"all_brazil_materials": {}},
            "runtime": {"machine_name": name},
            "bridge": {"enabled": True},
        },
    )
    with connect(database) as connection:
        ensure_inventory_schema(connection)
        for email, role in users:
            connection.execute(
                "insert into allowed_users(email,is_active,role,allowed_pages,identity_subject) values (?,true,?,?,?)",
                [email, role, "[]" if role == "admin" else '["overview"]', f"windows:{email}"],
            )
    return settings, TestClient(web_app.create_app(settings))


def login(client: TestClient, settings: Settings, email: str) -> str:
    client.cookies.set(SESSION_COOKIE, create_session_token(settings, email, f"windows:{email}"))
    return client.get("/api/auth/session").json().get("csrf_token", "")


def bind_identity(settings: Settings, email: str) -> None:
    """Equivale ao primeiro login no Windows do usuário naquela máquina."""
    with connect(settings.path("database")) as connection:
        connection.execute("update allowed_users set identity_subject=?, updated_at=current_timestamp where email=?", [f"windows:{email}", email])


def row(settings: Settings, email: str):
    with connect(settings.path("database")) as connection:
        return connection.execute("select is_active, role, allowed_pages from allowed_users where email=?", [email]).fetchone()


def test_user_registered_on_one_admin_machine_reaches_every_machine(tmp_path: Path, drive: Path) -> None:
    a, admin_a = machine(tmp_path, "PC-ADMIN-A", [(ADMIN_A, "admin")])
    b, admin_b = machine(tmp_path, "PC-ADMIN-B", [(ADMIN_B, "admin")])
    u, user_pc = machine(tmp_path, "PC-USUARIO", [])
    csrf_a = login(admin_a, a, ADMIN_A)
    login(admin_b, b, ADMIN_B)

    created = admin_a.post("/api/settings/access", json={"email": USER, "role": "user", "pages": ["overview", "docs"]},
                           headers={"X-CSRF-Token": csrf_a})
    assert created.status_code == 200, created.text
    sync_access(a, drive)
    assert (drive / "acesso" / "alteracoes" / "PC-ADMIN-A.json").is_file()

    # Outra máquina de administrador passa a ver o novo usuário em Configurações.
    sync_access(b, drive)
    listed = {item["email"]: item for item in admin_b.get("/api/settings").json()["allowed_users"]}
    assert listed[USER]["is_active"] and listed[USER]["access_changed_by"] == ADMIN_A
    assert ADMIN_A in listed  # o cadastro de um administrador também aparece para o outro

    # A máquina do usuário recebe a liberação sem reinstalar e ele consegue entrar.
    assert row(u, USER) is None
    sync_access(u, drive)
    assert row(u, USER)[0] is True and json.loads(row(u, USER)[2]) == ["overview", "docs"]
    bind_identity(u, USER)
    login(user_pc, u, USER)
    assert user_pc.get("/api/docs/info").status_code in (200, 404)  # página Documentação liberada
    assert user_pc.get("/api/inventory?period=2026-09").status_code == 403  # Base de estoque não liberada


def test_deactivation_and_deletion_reach_the_user_machine(tmp_path: Path, drive: Path) -> None:
    a, admin_a = machine(tmp_path, "PC-ADMIN-A", [(ADMIN_A, "admin")])
    b, _ = machine(tmp_path, "PC-ADMIN-B", [(ADMIN_B, "admin"), (USER, "user")])  # cópia antiga com o usuário ativo
    u, user_pc = machine(tmp_path, "PC-USUARIO", [(USER, "user")])
    csrf_a = login(admin_a, a, ADMIN_A)
    _update_state(b, lambda state: state.update(publisher=True))  # B é máquina de administrador

    admin_a.post("/api/settings/access", json={"email": USER, "role": "user", "pages": ["overview"]}, headers={"X-CSRF-Token": csrf_a})
    sync_access(a, drive)
    sync_access(u, drive)
    login(user_pc, u, USER)
    assert user_pc.get("/api/dashboard/summary?period=2026-09").status_code == 200

    # Desativado na máquina A: a sessão do usuário cai na máquina dele.
    assert admin_a.post(f"/api/settings/access/{USER}/disable", headers={"X-CSRF-Token": csrf_a}).status_code == 200
    sync_access(a, drive)
    bind_identity(b, USER)  # um login antigo na máquina B não pode "ganhar" da desativação
    sync_access(b, drive)
    sync_access(u, drive)
    assert row(u, USER)[0] is False and row(b, USER)[0] is False
    assert user_pc.get("/api/dashboard/summary?period=2026-09").status_code == 401

    # Excluído: some de todas as máquinas e a lista antiga de B não o traz de volta.
    assert admin_a.delete(f"/api/settings/access/{USER}", headers={"X-CSRF-Token": csrf_a}).status_code == 200
    sync_access(a, drive)
    for _ in range(2):
        sync_access(b, drive)
        sync_access(u, drive)
    assert row(u, USER) is None and row(b, USER) is None
    merged, _ = read_merged(drive)
    assert merged[USER]["deleted"] is True

    # Recadastrado depois: volta a valer em todas as máquinas.
    admin_a.post("/api/settings/access", json={"email": USER, "role": "user", "pages": ["overview"]}, headers={"X-CSRF-Token": csrf_a})
    sync_access(a, drive)
    sync_access(u, drive)
    assert row(u, USER)[0] is True


def test_bootstrap_admins_are_never_removed_by_the_list(tmp_path: Path, drive: Path) -> None:
    protected = BOOTSTRAP_ADMINS[0]
    folder = drive / "acesso" / "alteracoes"
    folder.mkdir(parents=True)
    (folder / "INVASOR.json").write_text(json.dumps({"format": 1, "users": {
        protected: {"deleted": True, "active": False, "changed_at": "2099-01-01T00:00:00.000000Z", "changed_by": "x"}
    }}), encoding="utf-8")
    u, _ = machine(tmp_path, "PC-USUARIO", [])
    sync_access(u, drive)
    assert row(u, protected)[0] is True and row(u, protected)[1] == "admin"


def test_seven_days_without_verification_blocks_users_but_not_admins(tmp_path: Path, drive: Path) -> None:
    u, user_pc = machine(tmp_path, "PC-USUARIO", [(USER, "user"), (ADMIN_A, "admin")])
    sync_access(u, drive)
    login(user_pc, u, USER)
    assert user_pc.get("/api/dashboard/summary?period=2026-09").status_code == 200
    assert _access_indicator(u, {"role": "user"})["level"] == "healthy"

    # Máquina há 8 dias sem conseguir consultar o Drive (a pasta some nesta etapa).
    offline = drive.with_name("Estoque_Cont_offline")
    drive.rename(offline)
    eight_days_ago = (datetime.now(timezone.utc) - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    _update_state(u, lambda state: state.update(last_verified_at=eight_days_ago, last_sync_at=eight_days_ago))
    assert verification(u)["expired"] is True
    blocked = TestClient(web_app.create_app(u))  # servidor reiniciado: tenta sincronizar e não consegue
    login(blocked, u, USER)
    response = blocked.get("/api/dashboard/summary?period=2026-09")
    assert response.status_code == 401 and "7 dias" in response.json()["detail"]
    login(blocked, u, ADMIN_A)
    assert blocked.get("/api/dashboard/summary?period=2026-09").status_code == 200
    indicator = _access_indicator(u, {"role": "user"})
    assert indicator["level"] == "critical" and indicator["status"] == "Bloqueado (sem verificação)"

    offline.rename(drive)
    sync_access(u, drive)  # o Drive voltou: libera de novo
    assert verification(u)["expired"] is False
    login(blocked, u, USER)
    blocked_again = TestClient(web_app.create_app(u))
    login(blocked_again, u, USER)
    assert blocked_again.get("/api/dashboard/summary?period=2026-09").status_code == 200


def test_health_center_and_settings_show_the_real_access_list_status(tmp_path: Path, drive: Path) -> None:
    a, admin_a = machine(tmp_path, "PC-ADMIN-A", [(ADMIN_A, "admin")])
    login(admin_a, a, ADMIN_A)
    indicator = _access_indicator(a, {"role": "admin"})
    assert indicator["status"] in {"Ainda não verificada", "Em dia"}

    _update_state(a, lambda state: state.update(publisher=True))
    sync_access(a, drive)
    settings_payload = admin_a.get("/api/settings").json()
    assert settings_payload["access_sync"]["last_sync_at"]
    assert any(item["machine"] == "PC-ADMIN-A" for item in settings_payload["access_sync"]["machines"])
    health = admin_a.get("/api/health-center?period=2026-09").json()
    access = next(item for item in health["indicators"] if item["key"] == "access_sync")
    assert access["level"] == "healthy" and access["status"] == "Em dia"

    shutil.rmtree(drive)  # Drive inacessível: o erro aparece de verdade
    web_app_result = admin_a.post("/api/settings/access", json={"email": USER, "role": "user", "pages": ["overview"]},
                                  headers={"X-CSRF-Token": admin_a.get("/api/auth/session").json()["csrf_token"]})
    assert web_app_result.status_code == 200
    with pytest.raises(OSError):
        sync_access(a, drive)
    assert local_view(a)[USER]["changed_by"] == ADMIN_A
