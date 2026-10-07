"""Seleção de pasta pela janela do Windows (rota da página Configurações)."""

from __future__ import annotations

from pathlib import Path

import ops_contabil.web.app as web_app
from test_bridge_api import ADMIN, USER, make_machine


def test_admin_gets_the_folder_chosen_in_the_windows_dialog(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_picker(title: str, initial: str | None = None) -> str | None:
        calls.append((title, initial))
        return r"G:\Drives compartilhados\Estoque_Cont\backups"

    monkeypatch.setattr(web_app, "pick_folder", fake_picker)
    _, admin, csrf = make_machine(tmp_path, "admin", ADMIN, "admin", "[]")

    response = admin.post(
        "/api/settings/pick-folder",
        json={"purpose": "backup", "initial": r"C:\Temp"},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 200
    assert response.json() == {"path": r"G:\Drives compartilhados\Estoque_Cont\backups", "cancelled": False}
    assert calls == [("Selecione a pasta de backup do Estoque Contábil", r"C:\Temp")]


def test_cancelling_the_dialog_changes_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(web_app, "pick_folder", lambda title, initial=None: None)
    _, admin, csrf = make_machine(tmp_path, "admin", ADMIN, "admin", "[]")

    response = admin.post("/api/settings/pick-folder", json={"purpose": "bridge"}, headers={"X-CSRF-Token": csrf})

    assert response.json() == {"path": None, "cancelled": True}


def test_only_admins_can_open_the_dialog(tmp_path: Path, monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(web_app, "pick_folder", lambda title, initial=None: opened.append(title))
    _, user, csrf = make_machine(tmp_path, "user", USER, "user", '["overview","agent"]')

    assert user.post("/api/settings/pick-folder", json={"purpose": "backup"}, headers={"X-CSRF-Token": csrf}).status_code == 403
    assert user.post("/api/settings/pick-folder", json={"purpose": "qualquer"}, headers={"X-CSRF-Token": csrf}).status_code in {403, 422}
    assert opened == []
