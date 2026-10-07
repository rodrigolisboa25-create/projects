"""Semáforos do Health Center para a ponte do Drive compartilhado e o backup programado."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

import ops_contabil.drive_bridge as bridge
from ops_contabil.health_center import _bridge_indicators
from test_drive_bridge import T1, load_period, machine

ADMIN = {"email": "admin@gruposbf.com.br", "role": "admin", "pages": []}
USER = {"email": "user@gruposbf.com.br", "role": "user", "pages": ["overview", "agent"]}


def by_key(indicators: list[dict]) -> dict[str, dict]:
    return {item["key"]: item for item in indicators}


def backup_info(**overrides) -> dict:
    info = {"enabled": True, "frequency": "daily", "effective_folder": "G:/Estoque_Cont/backups/PC", "last_backup_at": None, "last_backup_error": None}
    info.update(overrides)
    return info


def test_connected_and_up_to_date(tmp_path: Path, monkeypatch) -> None:
    drive = tmp_path / "Drives compartilhados" / "Estoque_Cont"
    drive.mkdir(parents=True)
    monkeypatch.setenv("OPS_BRIDGE_ROOT", str(drive))
    admin = machine(tmp_path, "admin")
    load_period(admin, "2026-09", 3, T1)
    bridge.mark_local_change(admin, ["2026-09"])
    bridge.publish_pending(admin)
    bridge.sync_from_bridge(admin)

    result = by_key(_bridge_indicators(admin, ADMIN, backup_info(last_backup_at=datetime.now().isoformat())))

    assert result["bridge_folder"]["level"] == "healthy" and result["bridge_folder"]["status"] == "Conectado"
    assert result["bridge_sync"]["level"] == "healthy" and "1 de 1 competência(s) sincronizada(s)" in result["bridge_sync"]["details"]
    assert result["backup"]["level"] == "healthy" and result["backup"]["status"] == "Em dia"


def test_missing_folder_and_pending_publication_are_flagged(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPS_BRIDGE_ROOT", str(tmp_path / "Drives compartilhados" / "Estoque_Cont"))
    admin = machine(tmp_path, "admin")
    load_period(admin, "2026-09", 3, T1)
    bridge.mark_local_change(admin, ["2026-09"])
    bridge.publish_pending(admin)  # falha: pasta inexistente, fica pendente com erro

    result = by_key(_bridge_indicators(admin, ADMIN, backup_info(enabled=False)))

    assert result["bridge_folder"]["level"] == "critical" and result["bridge_folder"]["status"] == "Inacessível"
    assert result["bridge_sync"]["level"] == "critical" and result["bridge_sync"]["status"] == "Suspensa (sem Drive)"
    assert "aguardando envio ao Drive: 2026-09" in result["bridge_sync"]["details"]
    assert result["backup"]["level"] == "warning" and result["backup"]["status"] == "Desativado"


def test_recent_success_does_not_hide_a_disconnected_drive(tmp_path: Path, monkeypatch) -> None:
    drive = tmp_path / "Drives compartilhados" / "Estoque_Cont"
    drive.mkdir(parents=True)
    monkeypatch.setenv("OPS_BRIDGE_ROOT", str(drive))
    user = machine(tmp_path, "user")
    bridge.sync_from_bridge(user)  # verificação bem-sucedida agora há pouco
    assert by_key(_bridge_indicators(user, USER, None))["bridge_sync"]["status"] == "Em dia"

    drive.rename(drive.with_name("Estoque_Cont_fora"))  # Drive desconectado logo depois

    result = by_key(_bridge_indicators(user, USER, None))
    assert (result["bridge_folder"]["level"], result["bridge_folder"]["status"]) == ("critical", "Inacessível")
    assert (result["bridge_sync"]["level"], result["bridge_sync"]["status"]) == ("critical", "Suspensa (sem Drive)")


def test_stale_verification_warns_and_user_does_not_see_backup(tmp_path: Path, monkeypatch) -> None:
    drive = tmp_path / "Drives compartilhados" / "Estoque_Cont"
    drive.mkdir(parents=True)
    monkeypatch.setenv("OPS_BRIDGE_ROOT", str(drive))
    user = machine(tmp_path, "user")
    old = (datetime.now() - timedelta(hours=2)).replace(microsecond=0).isoformat()
    bridge._update_state(user, lambda state: state.update(last_sync_at=old))

    result = by_key(_bridge_indicators(user, USER, None))

    assert result["bridge_sync"]["level"] == "warning" and result["bridge_sync"]["status"] == "Sem verificação recente"
    assert "15 minutos" in result["bridge_sync"]["details"]
    assert "backup" not in result


@pytest.mark.parametrize(
    ("overrides", "level", "status"),
    [
        ({"last_backup_at": (datetime.now() - timedelta(days=3)).isoformat()}, "warning", "Atrasado"),
        ({"last_backup_at": datetime.now().isoformat(), "last_backup_error": "sem espaço"}, "critical", "Falha no último backup"),
        ({"frequency": "weekly", "last_backup_at": (datetime.now() - timedelta(days=5)).isoformat()}, "healthy", "Em dia"),
    ],
)
def test_backup_traffic_light(tmp_path: Path, monkeypatch, overrides: dict, level: str, status: str) -> None:
    drive = tmp_path / "Drives compartilhados" / "Estoque_Cont"
    drive.mkdir(parents=True)
    monkeypatch.setenv("OPS_BRIDGE_ROOT", str(drive))
    admin = machine(tmp_path, "admin")

    result = by_key(_bridge_indicators(admin, ADMIN, backup_info(**overrides)))

    assert (result["backup"]["level"], result["backup"]["status"]) == (level, status)
