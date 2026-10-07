"""Ponte de dados pelo Drive compartilhado: o Drive só transporta, cada máquina decide."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

import ops_contabil.drive_bridge as bridge
import ops_contabil.backup as backup_module
from ops_contabil.backup import backup_is_due, machine_tag, mirror_local_copy, replace_previous_backups, run_backup
from ops_contabil.db import connect
from ops_contabil.inventory import ensure_inventory_schema
from ops_contabil.mb59 import ensure_mb59_schema
from ops_contabil.settings import Settings

T0 = datetime(2026, 9, 25, 21, 50)
T1 = datetime(2026, 9, 29, 10, 0)


def machine(tmp_path: Path, name: str) -> Settings:
    database = tmp_path / name / "processed" / "ops_contabil.duckdb"
    settings = Settings(
        root=tmp_path / name,
        raw={
            "project": {"database": str(database), "processed": str(database.parent), "landing": str(tmp_path / name / "landing")},
            "sources": {},
            "bridge": {"enabled": True},
        },
    )
    with connect(database) as c:
        ensure_inventory_schema(c)
        ensure_mb59_schema(c)
    return settings


def load_period(settings: Settings, period: str, rows: int, loaded_at: datetime, prefix: str = "MAT") -> None:
    with connect(settings.path("database")) as c:
        bridge._ensure_tables(c)
        c.execute("delete from inventory_rows where period=?", [period])
        c.execute("delete from inventory_imports where period=?", [period])
        c.execute("delete from all_brazil_imports where period=?", [period])
        for index in range(rows):
            c.execute(
                "insert into inventory_rows(period,source_row,material,unrestricted_quantity,fiscal_total_amount) values (?,?,?,?,?)",
                [period, index + 1, f"{prefix}-{index}", 2, 50.0],
            )
        c.execute(
            """insert into inventory_imports(period,source_path,source_sha256,source_sheet,header_row,row_count,schema_fingerprint,imported_at)
               values (?,?,?,?,?,?,?,?)""",
            [period, "C:/landing/x.xlsx", "sha", "Sheet1", 1, rows, "fp", loaded_at],
        )
        c.execute("insert into all_brazil_imports(period,coverage_pct,imported_at) values (?,?,?)", [period, 99.5, loaded_at])


def summary(settings: Settings, period: str) -> tuple[int, float, list[str]]:
    with connect(settings.path("database")) as c:
        count, fiscal = c.execute(
            "select count(*), coalesce(sum(fiscal_total_amount),0) from inventory_rows where period=?", [period]
        ).fetchone()
        materials = [row[0] for row in c.execute("select material from inventory_rows where period=? order by source_row", [period]).fetchall()]
    return int(count), float(fiscal), materials


@pytest.fixture()
def drive(tmp_path: Path, monkeypatch) -> Path:
    folder = tmp_path / "Drives compartilhados" / "Estoque_Cont"
    folder.mkdir(parents=True)
    monkeypatch.setenv("OPS_BRIDGE_ROOT", str(folder))
    return folder


def test_update_on_one_machine_reaches_the_other(drive: Path, tmp_path: Path) -> None:
    admin, user = machine(tmp_path, "admin"), machine(tmp_path, "user")
    load_period(admin, "2026-09", 5, T1)
    bridge.mark_local_change(admin, ["2026-09"], "Upload ZMM119")

    published = bridge.publish_pending(admin, published_by="admin@gruposbf.com.br")
    assert published[0]["status"] == "published"
    pointer = json.loads((drive / "periodos" / "2026-09" / "atual.json").read_text(encoding="utf-8"))
    assert pointer["published_by"] == "admin@gruposbf.com.br" and pointer["rows"] == 5
    assert bridge.load_state(admin)["pending_publish"] == []

    result = bridge.sync_from_bridge(user)
    assert [item["period"] for item in result["applied"]] == ["2026-09"]
    assert summary(user, "2026-09") == summary(admin, "2026-09")
    assert bridge.load_state(user)["data_revision"] == 1
    # Uma segunda verificação não reaplica a mesma versão.
    assert bridge.sync_from_bridge(user)["applied"] == []


def test_newer_local_data_is_never_overwritten_by_the_drive(drive: Path, tmp_path: Path) -> None:
    first, second = machine(tmp_path, "a"), machine(tmp_path, "b")
    load_period(first, "2026-09", 3, T0, prefix="ANTIGO")
    bridge.mark_local_change(first, ["2026-09"])
    bridge.publish_pending(first)
    load_period(second, "2026-09", 7, T1, prefix="NOVO")
    bridge.mark_local_change(second, ["2026-09"])

    result = bridge.sync_from_bridge(second)

    assert result["applied"] == []
    assert summary(second, "2026-09")[0] == 7


def test_incomplete_drive_download_waits_and_changes_nothing(drive: Path, tmp_path: Path) -> None:
    admin, user = machine(tmp_path, "admin"), machine(tmp_path, "user")
    load_period(user, "2026-09", 2, T0, prefix="ATUAL")
    load_period(admin, "2026-09", 6, T1)
    bridge.mark_local_change(admin, ["2026-09"])
    bridge.publish_pending(admin)
    pointer = json.loads((drive / "periodos" / "2026-09" / "atual.json").read_text(encoding="utf-8"))
    parquet = drive / "periodos" / "2026-09" / pointer["version"] / "inventory_rows.parquet"
    complete = parquet.read_bytes()
    parquet.write_bytes(complete[: len(complete) // 2])  # Google Drive ainda baixando

    result = bridge.sync_from_bridge(user)
    assert result["applied"] == [] and result["waiting"][0]["period"] == "2026-09"
    assert summary(user, "2026-09")[0] == 2

    parquet.write_bytes(complete)
    assert [item["period"] for item in bridge.sync_from_bridge(user)["applied"]] == ["2026-09"]
    assert summary(user, "2026-09")[0] == 6


def test_empty_or_broken_drive_never_deletes_local_data(drive: Path, tmp_path: Path) -> None:
    user = machine(tmp_path, "user")
    load_period(user, "2026-08", 4, T0)
    assert bridge.sync_from_bridge(user)["applied"] == []
    (drive / "periodos" / "2026-08").mkdir(parents=True)
    (drive / "periodos" / "2026-08" / "atual.json").write_text("{ corrompido", encoding="utf-8")
    assert bridge.sync_from_bridge(user)["applied"] == []
    assert summary(user, "2026-08")[0] == 4


def test_local_deletion_is_not_undone_by_the_same_drive_version(drive: Path, tmp_path: Path) -> None:
    admin, other = machine(tmp_path, "admin"), machine(tmp_path, "other")
    load_period(other, "2026-07", 3, T0)
    bridge.mark_local_change(other, ["2026-07"])
    bridge.publish_pending(other)
    bridge.sync_from_bridge(admin)
    assert summary(admin, "2026-07")[0] == 3
    with connect(admin.path("database")) as c:
        c.execute("delete from inventory_rows where period='2026-07'")
    bridge.mark_local_deletion(admin, "2026-07")
    assert bridge.sync_from_bridge(admin)["applied"] == []
    assert summary(admin, "2026-07")[0] == 0


def test_publish_skips_when_drive_is_current_and_keeps_three_versions(drive: Path, tmp_path: Path) -> None:
    admin = machine(tmp_path, "admin")
    load_period(admin, "2026-09", 2, T0)
    for _ in range(5):
        bridge.mark_local_change(admin, ["2026-09"])
        assert bridge.publish_pending(admin)[0]["status"] == "published"
    versions = [p for p in (drive / "periodos" / "2026-09").iterdir() if p.is_dir()]
    assert len(versions) == bridge.KEEP_VERSIONS
    assert bridge.publish_period(admin, "2026-09")["status"] == "skipped"


def test_unavailable_drive_keeps_publication_pending(tmp_path: Path, monkeypatch) -> None:
    admin = machine(tmp_path, "admin")
    missing = tmp_path / "Drives compartilhados" / "Estoque_Cont"
    monkeypatch.setenv("OPS_BRIDGE_ROOT", str(missing))
    load_period(admin, "2026-09", 2, T0)
    bridge.mark_local_change(admin, ["2026-09"])

    result = bridge.publish_pending(admin)
    assert result[0]["status"] == "failed"
    state = bridge.load_state(admin)
    assert state["pending_publish"] == ["2026-09"] and "não está acessível" in state["last_publish_error"]

    missing.mkdir(parents=True)
    assert bridge.publish_pending(admin)[0]["status"] == "published"
    assert bridge.load_state(admin)["pending_publish"] == []


def test_changing_the_folder_leaves_a_redirect_for_other_machines(drive: Path, tmp_path: Path, monkeypatch) -> None:
    admin, user = machine(tmp_path, "admin"), machine(tmp_path, "user")
    with pytest.raises(ValueError):
        bridge.set_root(admin, str(tmp_path / "nao_existe"))
    new_folder = tmp_path / "Drives compartilhados" / "Estoque_Cont_2"
    new_folder.mkdir(parents=True)

    info = bridge.set_root(admin, str(new_folder), changed_by="admin@gruposbf.com.br")
    assert info["source"] == "configured" and Path(info["path"]) == new_folder
    assert json.loads((drive / bridge.REDIRECT_FILE).read_text(encoding="utf-8"))["path"] == str(new_folder)
    # A outra máquina continua apontando para a pasta antiga e segue o aviso.
    assert Path(bridge.resolve_root(user)["path"]) == new_folder

    load_period(admin, "2026-09", 3, T1)
    bridge.mark_local_change(admin, ["2026-09"])
    bridge.publish_pending(admin)
    assert (new_folder / "periodos" / "2026-09" / "atual.json").is_file()
    assert [item["period"] for item in bridge.sync_from_bridge(user)["applied"]] == ["2026-09"]

    assert bridge.set_root(admin, None)["source"] == "environment"


def test_new_columns_from_a_newer_version_are_added(drive: Path, tmp_path: Path) -> None:
    admin, user = machine(tmp_path, "admin"), machine(tmp_path, "user")
    load_period(admin, "2026-09", 2, T1)
    with connect(admin.path("database")) as c:
        c.execute("alter table inventory_rows add column coluna_nova varchar")
        c.execute("update inventory_rows set coluna_nova='x'")
    bridge.mark_local_change(admin, ["2026-09"])
    bridge.publish_pending(admin)

    bridge.sync_from_bridge(user)
    with connect(user.path("database")) as c:
        assert c.execute("select count(*) from inventory_rows where coluna_nova='x'").fetchone()[0] == 2


def test_bridge_status_describes_each_period(drive: Path, tmp_path: Path) -> None:
    admin, user = machine(tmp_path, "admin"), machine(tmp_path, "user")
    load_period(admin, "2026-09", 2, T1)
    load_period(user, "2026-06", 1, T0)
    bridge.mark_local_change(admin, ["2026-09"])
    bridge.publish_pending(admin)

    status = {item["period"]: item["situation"] for item in bridge.bridge_status(user)["periods"]}
    assert status == {"2026-09": "Disponível no Drive (será recebida)", "2026-06": "Somente nesta máquina"}
    bridge.sync_from_bridge(user)
    status = {item["period"]: item["situation"] for item in bridge.bridge_status(user)["periods"]}
    assert status["2026-09"] == "Sincronizada"


# ------------------------------------------------------------------ backup


def test_backup_is_complete_restorable_and_replaces_the_previous_one(tmp_path: Path, monkeypatch) -> None:
    admin = machine(tmp_path, "admin")
    load_period(admin, "2026-09", 4, T1)
    folder = tmp_path / "backups"

    backup = run_backup(admin, folder, now=datetime(2026, 9, 29, 12, 0, 0))
    assert backup.name == f"ops_contabil_backup_20260929_120000_{machine_tag()}.zip"
    restore = tmp_path / "restore"
    with zipfile.ZipFile(backup) as archive:
        names = archive.namelist()
        assert "COMO_RESTAURAR.txt" in names and "schema.sql" in names and "load.sql" in names
        archive.extractall(restore)
    restored = tmp_path / "restaurado.duckdb"
    with duckdb.connect(str(restored)) as c:
        c.execute(f"import database '{restore.as_posix()}'")
        assert c.execute("select count(*) from inventory_rows where period='2026-09'").fetchone()[0] == 4

    # Arquivos já existentes na pasta: um antigo deste computador (formato sem nome),
    # um deste computador e um de OUTRO computador que usa a mesma pasta.
    legacy = folder / "ops_contabil_backup_20260901_080000.zip"
    mine = folder / f"ops_contabil_backup_20260920_080000_{machine_tag()}.zip"
    other = folder / "ops_contabil_backup_20260925_080000_OUTRA-MAQUINA.zip"
    for path in (legacy, mine, other):
        path.write_bytes(b"x")

    # Um backup novo com falha na conferência não apaga nada.
    def broken(path):
        raise ValueError("o arquivo gravado está corrompido")
    monkeypatch.setattr(backup_module, "verify_backup", broken)
    with pytest.raises(ValueError):
        run_backup(admin, folder, now=datetime(2026, 9, 30, 12, 0, 0))
    monkeypatch.undo()
    assert legacy.is_file() and mine.is_file() and other.is_file() and backup.is_file()
    assert not list(folder.glob("*20260930*"))

    # Backup novo conferido: os anteriores deste computador são apagados; o da outra máquina fica.
    newest = run_backup(admin, folder, now=datetime(2026, 10, 1, 12, 0, 0))
    removed = replace_previous_backups(folder, newest)
    assert sorted(p.name for p in removed) == sorted([legacy.name, mine.name, backup.name])
    assert sorted(p.name for p in folder.iterdir()) == sorted([newest.name, other.name])

    # A cópia local também guarda só a mais recente.
    local = tmp_path / "local_backup"
    first_copy = mirror_local_copy(newest, local)
    again = run_backup(admin, folder, now=datetime(2026, 10, 2, 12, 0, 0))
    replace_previous_backups(folder, again)
    mirror_local_copy(again, local)
    assert [p.name for p in local.iterdir()] == [again.name] and first_copy.name != again.name
    assert sorted(p.name for p in folder.iterdir()) == sorted([again.name, other.name])

def test_backup_schedule() -> None:
    now = datetime(2026, 9, 29, 12, 0)
    assert backup_is_due(None, "daily", now)
    assert not backup_is_due(now - timedelta(hours=10), "daily", now)
    assert backup_is_due(now - timedelta(days=1), "daily", now)
    assert not backup_is_due(now - timedelta(days=3), "weekly", now)
    assert backup_is_due(now - timedelta(days=7), "weekly", now)
    assert backup_is_due(now - timedelta(days=30), "monthly", now)
