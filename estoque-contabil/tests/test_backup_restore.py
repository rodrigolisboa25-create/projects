"""Restauração do banco a partir de um backup (.zip): conferência, troca segura e API."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
import time
import zipfile
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

import ops_contabil.backup_restore as backup_restore
import ops_contabil.web.app as web_app
from ops_contabil.backup import mirror_local_copy, run_backup
from ops_contabil.backup_restore import RestoreError, apply_restore, list_backups, prepare_restore
from ops_contabil.db import connect
from ops_contabil.inventory import ensure_inventory_schema
from test_bridge_api import ADMIN, USER, make_machine


class FakeSettings:
    def __init__(self, database: Path) -> None:
        self.database = database

    def path(self, key: str) -> Path:
        assert key == "database"
        return self.database


def add_rows(database: Path, period: str, amounts: list[float]) -> None:
    with connect(database) as connection:
        ensure_inventory_schema(connection)
        for index, amount in enumerate(amounts):
            connection.execute(
                """insert into inventory_rows(period, source_row, material, fiscal_total_amount, unrestricted_quantity)
                   values (?, (select coalesce(max(source_row), 0) + 1 from inventory_rows), ?, ?, 1)""",
                [period, f"MAT{index:06d}", amount],
            )


def machine(tmp_path: Path) -> Path:
    database = tmp_path / "OpsContabil" / "processed" / "ops_contabil.duckdb"
    add_rows(database, "2026-08", [10.0, 20.0])
    add_rows(database, "2026-09", [5.0])
    with connect(database) as connection:
        connection.execute("insert into allowed_users(email, role) values ('antigo@gruposbf.com.br','admin')")
        connection.execute("insert into system_settings(setting_key, setting_value) values ('backup_folder', '\"X:/antiga\"')")
    return database


def periods(database: Path) -> dict[str, int]:
    with connect(database) as connection:
        return dict(connection.execute("select period, count(*) from inventory_rows group by 1").fetchall())


def test_restore_brings_back_data_and_keeps_machine_access_and_settings(tmp_path: Path) -> None:
    database = machine(tmp_path)
    archive = run_backup(FakeSettings(database), tmp_path / "backups", now=datetime(2026, 9, 1, 8, 0, 0))

    # Depois do backup: a máquina ganhou uma competência, mudou 2026-08 e trocou acessos/configurações.
    add_rows(database, "2026-10", [1.0])
    with connect(database) as connection:
        connection.execute("delete from inventory_rows where period='2026-08'")
        connection.execute("delete from allowed_users")
        connection.execute("insert into allowed_users(email, role) values ('atual@gruposbf.com.br','admin')")
        connection.execute("update system_settings set setting_value='\"Y:/atual\"' where setting_key='backup_folder'")

    summary = prepare_restore(database, archive)
    assert periods(database) == {"2026-09": 1, "2026-10": 1}  # conferir não altera nada
    by_period = {item["period"]: item for item in summary["periods"]}
    assert by_period["2026-08"]["backup_rows"] == 2 and by_period["2026-08"]["local_rows"] is None
    assert by_period["2026-10"]["backup_rows"] is None and by_period["2026-10"]["local_rows"] == 1
    assert by_period["2026-08"]["backup_fiscal_value"] == pytest.approx(30.0)
    assert summary["created_at"] == "2026-09-01T08:00:00"

    result = apply_restore(database, summary["token"], restored_by=ADMIN, source_file=str(archive))

    assert result["status"] == "restored" and result["periods"] == ["2026-08", "2026-09"]
    assert periods(database) == {"2026-08": 2, "2026-09": 1}
    with duckdb.connect(str(database), read_only=True) as connection:
        assert connection.execute("select email from allowed_users").fetchall() == [("atual@gruposbf.com.br",)]
        assert connection.execute(
            "select setting_value from system_settings where setting_key='backup_folder'"
        ).fetchone() == ('"Y:/atual"',)
        state = json.loads(connection.execute(
            "select setting_value from system_settings where setting_key='bridge_state'"
        ).fetchone()[0])
    assert state["pending_publish"] == ["2026-08", "2026-09"]
    assert state["data_revision"] >= 1 and state["restored_by"] == ADMIN
    previous = Path(result["previous_copy"])
    assert periods(previous) == {"2026-09": 1, "2026-10": 1}  # o banco anterior ficou guardado
    assert not list(database.parent.glob(".restauracao-*"))


def test_invalid_archives_are_rejected_without_touching_the_database(tmp_path: Path) -> None:
    database = machine(tmp_path)
    before = periods(database)

    not_zip = tmp_path / "planilha.zip"
    not_zip.write_text("isto não é um zip", encoding="utf-8")
    with pytest.raises(RestoreError, match="não é um .zip"):
        prepare_restore(database, not_zip)

    other = tmp_path / "outro.zip"
    with zipfile.ZipFile(other, "w") as archive:
        archive.writestr("relatorio.csv", "a;b")
    with pytest.raises(RestoreError, match="não é um backup do Estoque Contábil"):
        prepare_restore(database, other)

    evil = tmp_path / "malicioso.zip"
    with zipfile.ZipFile(evil, "w") as archive:
        archive.writestr("schema.sql", "")
        archive.writestr("load.sql", "")
        archive.writestr("../../fora.txt", "x")
    with pytest.raises(RestoreError, match="caminhos inválidos"):
        prepare_restore(database, evil)

    with pytest.raises(RestoreError, match="não está mais disponível"):
        apply_restore(database, "0" * 32)
    assert periods(database) == before
    assert not list(database.parent.glob(".restauracao-*"))


def test_swap_waits_for_open_connections_and_blocks_new_ones(tmp_path: Path, monkeypatch) -> None:
    database = machine(tmp_path)
    archive = run_backup(FakeSettings(database), tmp_path / "backups")
    add_rows(database, "2026-10", [1.0])
    token = prepare_restore(database, archive)["token"]

    released = threading.Event()
    gate_closed = threading.Event()
    seen_during_swap: list[dict[str, int]] = []
    original_gate = backup_restore.database_maintenance

    @contextmanager
    def observed_gate():
        with original_gate():
            gate_closed.set()  # a partir daqui novas conexões ficam esperando
            yield

    monkeypatch.setattr(backup_restore, "database_maintenance", observed_gate)

    def long_query() -> None:
        with connect(database) as connection:
            connection.execute("select count(*) from inventory_rows").fetchone()
            gate_closed.wait(30)
            time.sleep(0.8)  # consulta demorada ainda aberta quando a troca começa
        released.set()

    def late_reader() -> None:
        gate_closed.wait(30)  # chega durante a troca: espera e lê o banco já restaurado
        time.sleep(0.1)
        with connect(database) as connection:
            seen_during_swap.append(dict(connection.execute(
                "select period, count(*) from inventory_rows group by 1"
            ).fetchall()))

    worker = threading.Thread(target=long_query)
    worker.start()
    time.sleep(0.2)
    reader = threading.Thread(target=late_reader)
    reader.start()
    result = apply_restore(database, token)
    worker.join()
    reader.join()

    assert released.is_set() and result["status"] == "restored"
    assert seen_during_swap == [{"2026-08": 2, "2026-09": 1}]


def test_restore_gives_up_cleanly_when_the_database_stays_busy(tmp_path: Path, monkeypatch) -> None:
    database = machine(tmp_path)
    archive = run_backup(FakeSettings(database), tmp_path / "backups")
    token = prepare_restore(database, archive)["token"]
    monkeypatch.setattr(backup_restore, "SWAP_WAIT_SECONDS", 0.5)

    holder = duckdb.connect(str(database))  # conexão que não fecha a tempo
    try:
        with pytest.raises(RestoreError, match="Nada foi alterado"):
            apply_restore(database, token)
    finally:
        holder.close()
    assert periods(database) == {"2026-08": 2, "2026-09": 1}
    with connect(database) as connection:  # o banco continua utilizável normalmente
        assert connection.execute("select count(*) from allowed_users").fetchone()[0] == 1


def test_local_copy_keeps_only_the_newest_and_listing_finds_backups(tmp_path: Path) -> None:
    database = machine(tmp_path)
    drive_folder = tmp_path / "drive" / "backups" / "MAQUINA"
    local = tmp_path / "OpsContabil" / "backup"
    created = []
    for day in (1, 2, 3):
        archive = run_backup(FakeSettings(database), drive_folder, now=datetime(2026, 9, day, 7, 0, 0))
        created.append(archive)
        mirror_local_copy(archive, local)
    assert sorted(path.name for path in local.iterdir()) == [created[2].name]

    found = list_backups([(drive_folder, "Drive — MAQUINA"), (local, "Este computador")])
    assert [item["name"] for item in found][:1] == [created[2].name]
    assert {item["location"] for item in found} == {"Drive — MAQUINA", "Este computador"}
    assert found[0]["created_at"] == "2026-09-03T07:00:00"


def test_restore_api_flow_and_permissions(tmp_path: Path, monkeypatch) -> None:
    settings, admin, csrf = make_machine(tmp_path, "admin", ADMIN, "admin", "[]")
    _, user, user_csrf = make_machine(tmp_path, "user", USER, "user", '["overview","agent"]')
    database = settings.path("database")
    add_rows(database, "2026-09", [7.0, 8.0])
    headers = {"X-CSRF-Token": csrf}

    ran = admin.post("/api/settings/backup/run", headers=headers)
    assert ran.status_code == 200, ran.text
    add_rows(database, "2026-09", [9.0])  # muda depois do backup

    listed = admin.get("/api/settings/backup/list").json()["backups"]
    assert listed and listed[0]["path"] == ran.json()["file"]

    inspected = admin.post("/api/settings/backup/inspect", json={"path": listed[0]["path"]}, headers=headers)
    assert inspected.status_code == 200, inspected.text
    token = inspected.json()["token"]
    assert inspected.json()["periods"] == [
        {"period": "2026-09", "backup_rows": 2, "backup_fiscal_value": 15.0, "local_rows": 3, "local_fiscal_value": 24.0}
    ]

    wrong = admin.post("/api/settings/backup/restore", json={"token": token, "confirmation": "sim"}, headers=headers)
    assert wrong.status_code == 422 and periods(database) == {"2026-09": 3}

    for path in ("/api/settings/backup/list",):
        assert user.get(path).status_code == 403
    assert user.post("/api/settings/backup/inspect", json={"path": listed[0]["path"]}, headers={"X-CSRF-Token": user_csrf}).status_code == 403
    assert user.post("/api/settings/backup/restore", json={"token": token, "confirmation": "RESTAURAR"}, headers={"X-CSRF-Token": user_csrf}).status_code == 403
    assert user.post("/api/settings/backup/pick-file", headers={"X-CSRF-Token": user_csrf}).status_code == 403

    restored = admin.post("/api/settings/backup/restore", json={"token": token, "confirmation": "restaurar"}, headers=headers)
    assert restored.status_code == 200, restored.text
    assert periods(database) == {"2026-09": 2}
    # A sessão do administrador continua válida depois da troca do banco.
    assert admin.get("/api/auth/session").json()["user"]["email"] == ADMIN
    summary = admin.get("/api/dashboard/summary?period=2026-09").json()
    assert summary["rows"] == 2

    again = admin.post("/api/settings/backup/restore", json={"token": token, "confirmation": "RESTAURAR"}, headers=headers)
    assert again.status_code == 422  # o mesmo backup conferido não é aplicado duas vezes


def test_backup_file_picker_returns_the_chosen_zip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(web_app, "pick_file", lambda title, initial=None: r"C:\backups\ops_contabil_backup_20260901_080000.zip")
    _, admin, csrf = make_machine(tmp_path, "admin", ADMIN, "admin", "[]")
    response = admin.post("/api/settings/backup/pick-file", headers={"X-CSRF-Token": csrf})
    assert response.json() == {"path": r"C:\backups\ops_contabil_backup_20260901_080000.zip", "cancelled": False}
