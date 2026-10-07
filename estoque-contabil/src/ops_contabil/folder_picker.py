"""Seleção de pasta pela janela nativa do Windows.

O navegador não informa o caminho completo de uma pasta escolhida; como o servidor
do Estoque Contábil roda no próprio computador do usuário, ele abre a janela de
seleção do Windows e devolve o caminho escolhido. A janela roda em um processo
separado (nunca trava o servidor) e fica sempre à frente do navegador.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PICK_TIMEOUT_SECONDS = 600

_TK_SCRIPT = r"""
import json, sys, tkinter
from tkinter import filedialog
title, initial = sys.argv[1], sys.argv[2]
root = tkinter.Tk()
root.withdraw()
root.attributes("-topmost", True)
root.update()
chosen = filedialog.askdirectory(parent=root, title=title, initialdir=initial or None, mustexist=True)
root.destroy()
print(json.dumps({"path": chosen or None}))
"""

_POWERSHELL_SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form -Property @{TopMost=$true; ShowInTaskbar=$false; WindowState='Minimized'}
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = $env:OPS_PICK_TITLE
$dialog.ShowNewFolderButton = $true
if ($env:OPS_PICK_INITIAL -and (Test-Path -LiteralPath $env:OPS_PICK_INITIAL)) { $dialog.SelectedPath = $env:OPS_PICK_INITIAL }
if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { $dialog.SelectedPath }
"""


_TK_FILE_SCRIPT = r"""
import json, sys, tkinter
from tkinter import filedialog
title, initial, label, pattern = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
root = tkinter.Tk()
root.withdraw()
root.attributes("-topmost", True)
root.update()
chosen = filedialog.askopenfilename(parent=root, title=title, initialdir=initial or None,
                                    filetypes=[(label, pattern)])
root.destroy()
print(json.dumps({"path": chosen or None}))
"""

_POWERSHELL_FILE_SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form -Property @{TopMost=$true; ShowInTaskbar=$false; WindowState='Minimized'}
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = $env:OPS_PICK_TITLE
$dialog.Filter = $env:OPS_PICK_FILTER
if ($env:OPS_PICK_INITIAL -and (Test-Path -LiteralPath $env:OPS_PICK_INITIAL)) { $dialog.InitialDirectory = $env:OPS_PICK_INITIAL }
if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { $dialog.FileName }
"""


def _normalize(path: str | None) -> str | None:
    if not path:
        return None
    return str(Path(path))  # barras do Windows, como no Explorer


def pick_folder(title: str, initial: str | None = None) -> str | None:
    """Abre a janela de seleção de pasta e devolve o caminho escolhido (None se cancelar)."""
    initial_dir = initial if initial and Path(initial).is_dir() else ""
    try:
        result = subprocess.run(
            [sys.executable, "-c", _TK_SCRIPT, title, initial_dir],
            capture_output=True,
            text=True,
            timeout=PICK_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and result.stdout.strip():
            return _normalize(json.loads(result.stdout.strip().splitlines()[-1]).get("path"))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    # Contingência sem Tk: janela de pastas do próprio Windows (Windows Forms).
    import os

    environment = {**os.environ, "OPS_PICK_TITLE": title, "OPS_PICK_INITIAL": initial_dir}
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", _POWERSHELL_SCRIPT],
        capture_output=True,
        text=True,
        timeout=PICK_TIMEOUT_SECONDS,
        env=environment,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return _normalize(result.stdout.strip() or None)


def pick_file(title: str, initial: str | None = None, label: str = "Backup do Estoque Contábil", pattern: str = "*.zip") -> str | None:
    """Abre a janela de seleção de arquivo e devolve o caminho escolhido (None se cancelar)."""
    import os

    initial_dir = initial if initial and Path(initial).is_dir() else ""
    try:
        result = subprocess.run(
            [sys.executable, "-c", _TK_FILE_SCRIPT, title, initial_dir, label, pattern],
            capture_output=True,
            text=True,
            timeout=PICK_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and result.stdout.strip():
            return _normalize(json.loads(result.stdout.strip().splitlines()[-1]).get("path"))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    environment = {**os.environ, "OPS_PICK_TITLE": title, "OPS_PICK_INITIAL": initial_dir, "OPS_PICK_FILTER": f"{label}|{pattern}"}
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", _POWERSHELL_FILE_SCRIPT],
        capture_output=True,
        text=True,
        timeout=PICK_TIMEOUT_SECONDS,
        env=environment,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return _normalize(result.stdout.strip() or None)
