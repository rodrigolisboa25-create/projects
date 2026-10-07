"""Proteções comuns a todos os testes."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _never_touch_the_real_drive(tmp_path: Path, monkeypatch) -> None:
    # Sem esta variável, a ponte detectaria sozinha o drive compartilhado REAL
    # (G:\Drives compartilhados\Estoque_Cont). Por padrão, cada teste aponta para
    # uma pasta inexistente; os testes da ponte definem a sua pasta temporária.
    monkeypatch.setenv("OPS_BRIDGE_ROOT", str(tmp_path / "sem-drive-nos-testes"))
    # Nenhum teste dispara notificações reais do Windows nem grava o registro do app.
    monkeypatch.setattr("ops_contabil.notifications.windows_toast", lambda xml, tag: None)
