"""Backup programado do banco local do Estoque Contábil.

Cada backup é uma exportação completa e consistente do DuckDB (EXPORT DATABASE em
Parquet), empacotada num único .zip com instruções de restauração. A gravação é
feita primeiro numa pasta temporária local e só depois copiada para o destino
(que pode ser o Drive compartilhado), sob um nome provisório renomeado ao final.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .db import connect

BACKUP_PREFIX = "ops_contabil_backup_"
# ops_contabil_backup_AAAAMMDD_HHMMSS_<COMPUTADOR>.zip (nomes antigos não têm o computador).
BACKUP_PATTERN = re.compile(r"^ops_contabil_backup_(\d{8}_\d{6})(?:_([A-Za-z0-9-]+))?\.zip$")
FREQUENCY_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}
LOCAL_COPIES = 1
RESTORE_INSTRUCTIONS = """Backup do Estoque Contábil
===========================

Conteúdo: exportação completa do banco local (EXPORT DATABASE do DuckDB, em Parquet).

Como restaurar (recomendado):
1. Abra o Estoque Contábil com um usuário administrador.
2. Configurações > Backup programado > Restaurar a partir de um backup.
3. Escolha este arquivo (ou um da lista), clique em Conferir, confira as competências
   e confirme digitando RESTAURAR. O banco anterior fica guardado como cópia.

Somente se o sistema não abrir (com o sistema fechado):
1. Extraia este .zip para uma pasta, por exemplo C:\\restauracao.
2. Renomeie o banco atual %LOCALAPPDATA%\\OpsContabil\\processed\\ops_contabil.duckdb (guarde-o).
3. Execute, com o Python do runtime:
   python -c "import duckdb; duckdb.connect(r'%LOCALAPPDATA%\\OpsContabil\\processed\\ops_contabil.duckdb').execute(\\"import database 'C:/restauracao'\\")"
4. Abra o sistema normalmente.
"""


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def machine_tag() -> str:
    """Nome do computador seguro para nome de arquivo."""
    return re.sub(r"[^A-Za-z0-9-]+", "-", socket.gethostname()).strip("-").upper() or "MAQUINA"


def is_own_backup(path: Path, machine: str | None = None) -> bool:
    """Backup gerado por este computador (ou no formato antigo, sem o nome do computador)."""
    match = BACKUP_PATTERN.match(path.name)
    if not match:
        return False
    return match.group(2) is None or match.group(2).upper() == (machine or machine_tag())


def verify_backup(path: Path) -> None:
    """Confere o .zip gravado no destino antes de apagar o anterior."""
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if not {"schema.sql", "load.sql"} <= names:
                raise ValueError("o arquivo gravado não contém o banco completo")
            broken = archive.testzip()
            if broken is not None:
                raise ValueError(f"o arquivo gravado está corrompido ({broken})")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"o arquivo gravado não é um .zip válido: {exc}") from exc


def replace_previous_backups(folder: Path, keep: Path, machine: str | None = None) -> list[Path]:
    """Apaga os backups anteriores DESTE computador na pasta, mantendo só ``keep``.

    Chamado somente depois que ``keep`` foi gravado e conferido. Backups de outros
    computadores na mesma pasta nunca são apagados.
    """
    removed: list[Path] = []
    if not folder.is_dir():
        return removed
    keep_key = os.path.normcase(str(keep.resolve()))
    for path in folder.iterdir():
        if not path.is_file():
            continue
        partial = path.name.startswith(".ops_contabil_backup_") and path.name.endswith(".parcial")
        if partial:
            # Sobra de uma gravação interrompida deste computador.
            if not is_own_backup(Path(path.name[1:-len(".parcial")]), machine):
                continue
        elif not is_own_backup(path, machine) or os.path.normcase(str(path.resolve())) == keep_key:
            continue
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            continue
    return removed


def backup_is_due(last_backup_at: datetime | None, frequency: str, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    if last_backup_at is None:
        return True
    return now - last_backup_at >= timedelta(days=FREQUENCY_DAYS.get(frequency, 1)) - timedelta(minutes=5)


def local_backup_folder(database: Path) -> Path:
    """Pasta de backups neste computador, ao lado da pasta do banco.

    Na instalação: %LOCALAPPDATA%\\OpsContabil\\processed\\ops_contabil.duckdb -> %LOCALAPPDATA%\\OpsContabil\\backup.
    """
    return database.parent.parent / "backup"


def default_backup_folder(bridge_root: Path | None, database: Path) -> Path:
    if bridge_root is not None:
        return bridge_root / "backups" / socket.gethostname()
    return local_backup_folder(database)


def mirror_local_copy(backup: Path, local_folder: Path) -> Path | None:
    """Guarda também neste computador uma cópia do backup mais recente.

    Se a pasta de destino (ex.: Drive) se perder, o backup não vai junto com ela.
    A cópia local anterior só é apagada depois que a nova foi gravada e conferida.
    """
    try:
        if os.path.normcase(str(backup.parent.resolve())) == os.path.normcase(str(local_folder.resolve())):
            return None
        local_folder.mkdir(parents=True, exist_ok=True)
        partial = local_folder / f".{backup.name}.parcial"
        shutil.copy2(backup, partial)
        destination = local_folder / backup.name
        os.replace(partial, destination)
        verify_backup(destination)
    except (OSError, ValueError):
        return None
    replace_previous_backups(local_folder, destination)
    return destination


def run_backup(settings: Any, folder: Path, now: datetime | None = None) -> Path:
    """Gera o backup completo, grava no destino e confere o arquivo gravado.

    Não apaga nada: quem chama usa ``replace_previous_backups`` depois do sucesso.
    """
    now = (now or datetime.now()).replace(microsecond=0)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{BACKUP_PREFIX}{now:%Y%m%d_%H%M%S}_{machine_tag()}.zip"
    with tempfile.TemporaryDirectory(prefix="ops-backup-") as temporary:
        export = Path(temporary) / "banco"
        with connect(settings.path("database")) as connection:
            connection.execute(f"export database '{_sql_path(export)}' (format parquet, compression zstd)")
        package = Path(temporary) / name
        with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(export.rglob("*")):
                if file.is_file():
                    archive.write(file, file.relative_to(export).as_posix())
            archive.writestr("COMO_RESTAURAR.txt", RESTORE_INSTRUCTIONS)
        partial = folder / f".{name}.parcial"
        shutil.copy2(package, partial)
        destination = folder / name
        os.replace(partial, destination)
    try:
        verify_backup(destination)
    except ValueError:
        destination.unlink(missing_ok=True)  # o backup anterior continua intacto
        raise
    return destination