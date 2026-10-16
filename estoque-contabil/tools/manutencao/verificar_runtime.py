"""Confere se as duas cópias instaladas do sistema estão iguais ao código do projeto (src/ops_contabil), arquivo a arquivo.

Uso:  python tools/manutencao/verificar_runtime.py
Cópias conferidas (as duas que o sistema usa nesta máquina):
  %LOCALAPPDATA%/OpsContabil/runtime/app/src/ops_contabil
  %LOCALAPPDATA%/OpsContabil/runtime/.venv/Lib/site-packages/ops_contabil
Saída "igual" nas duas = a máquina roda exatamente o código do projeto. Se listar arquivos, rode publicar_no_runtime.ps1.
"""
import hashlib
import os
import sys
from pathlib import Path

PROJECT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
SOURCE = PROJECT / "src" / "ops_contabil"
RUNTIME = Path(os.environ["LOCALAPPDATA"]) / "OpsContabil" / "runtime"
TARGETS = (RUNTIME / "app" / "src" / "ops_contabil", RUNTIME / ".venv" / "Lib" / "site-packages" / "ops_contabil")


def digest(path: Path) -> bytes:
    return hashlib.sha256(path.read_bytes()).digest()


problems = 0
for target in TARGETS:
    different = []
    for file in SOURCE.rglob("*"):
        if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc" and ".bak" not in file.name:
            copy = target / file.relative_to(SOURCE)
            if not copy.exists() or digest(copy) != digest(file):
                different.append(file.relative_to(SOURCE).as_posix())
    problems += len(different)
    print(f"{target} -> {'igual' if not different else 'DIFERENTE: ' + ', '.join(different)}")
sys.exit(1 if problems else 0)
