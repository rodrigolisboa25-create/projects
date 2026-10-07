"""Restauração do banco local a partir de um backup (.zip) do Estoque Contábil.

Fluxo em duas etapas, sem tocar no banco em uso até o último instante:

1. ``prepare_restore``: confere o .zip (integridade, conteúdo esperado, espaço em
   disco), importa o backup num banco provisório e compara as competências dele com
   as desta máquina. Nada muda no banco em uso.
2. ``apply_restore``: leva para o banco provisório os acessos e as configurações
   desta máquina (a restauração é de dados), prepara a ponte para receber/enviar o
   que for mais recente e troca os arquivos com as conexões bloqueadas. O banco
   anterior é guardado como cópia e volta ao lugar se a troca falhar.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

import duckdb

from .backup import BACKUP_PATTERN
from .db import AUTH_MIGRATIONS, SCHEMA_SQL, connect, database_maintenance

REQUIRED_ENTRIES = ("schema.sql", "load.sql")
PREPARED_PREFIX = ".restauracao-"
PREVIOUS_PREFIX = "ops_contabil.antes-da-restauracao-"
KEEP_PREVIOUS_COPIES = 2
SWAP_WAIT_SECONDS = 60.0
BRIDGE_STATE_KEY = "bridge_state"
TOKEN_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class RestoreError(ValueError):
    """Backup inválido ou restauração impossível; a mensagem é mostrada ao usuário."""


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def backup_created_at(path: Path) -> datetime | None:
    match = BACKUP_PATTERN.match(path.name)
    if match:
        return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
    return None


def list_backups(folders: list[tuple[Path, str]], limit: int = 40) -> list[dict[str, Any]]:
    """Backups encontrados nas pastas conhecidas, do mais recente para o mais antigo."""
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for folder, location in folders:
        try:
            candidates = list(folder.iterdir()) if folder.is_dir() else []
        except OSError:
            continue
        for path in candidates:
            created = backup_created_at(path)
            if created is None or not path.is_file():
                continue
            key = os.path.normcase(str(path.resolve()))
            if key in seen:
                continue
            seen.add(key)
            try:
                size = path.stat().st_size
            except OSError:
                continue
            items.append({
                "path": str(path),
                "name": path.name,
                "created_at": created.isoformat(),
                "size_bytes": size,
                "location": location,
            })
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items[:limit]


def _check_archive(archive: zipfile.ZipFile) -> int:
    names = archive.namelist()
    for name in names:
        pure = PurePosixPath(name.replace("\\", "/"))
        if pure.is_absolute() or ".." in pure.parts or ":" in name:
            raise RestoreError("O arquivo contém caminhos inválidos e não será usado.")
    for required in REQUIRED_ENTRIES:
        if required not in names:
            raise RestoreError(
                "Este arquivo não é um backup do Estoque Contábil (faltam as definições do banco). "
                "Escolha um arquivo ops_contabil_backup_AAAAMMDD_HHMMSS.zip."
            )
    broken = archive.testzip()
    if broken is not None:
        raise RestoreError(f"O backup está corrompido ({broken}). Escolha outro arquivo.")
    return sum(info.file_size for info in archive.infolist())


def _periods(connection: Any) -> dict[str, dict[str, float]]:
    exists = connection.execute(
        "select 1 from information_schema.tables where table_schema='main' and table_name='inventory_rows'"
    ).fetchone()
    if not exists:
        return {}
    rows = connection.execute(
        "select period, count(*), coalesce(sum(fiscal_total_amount),0) from inventory_rows group by period"
    ).fetchall()
    return {str(period): {"rows": int(count), "fiscal_value": float(fiscal or 0)} for period, count, fiscal in rows}


def prepared_path(database: Path, token: str) -> Path:
    if not TOKEN_PATTERN.match(token):
        raise RestoreError("Identificador de restauração inválido. Confira o backup novamente.")
    return database.parent / f"{PREPARED_PREFIX}{token}.duckdb"


def discard_prepared(database: Path, token: str | None = None) -> None:
    """Remove bancos provisórios (um específico ou todos os que sobraram)."""
    pattern = f"{PREPARED_PREFIX}{token}.duckdb*" if token else f"{PREPARED_PREFIX}*.duckdb*"
    for path in database.parent.glob(pattern):
        try:
            path.unlink()
        except OSError:
            continue


def prepare_restore(database: Path, archive_path: Path) -> dict[str, Any]:
    """Confere o backup e importa-o num banco provisório. Não altera o banco em uso."""
    if not archive_path.is_file():
        raise RestoreError(f"Arquivo não encontrado: {archive_path}")
    if not zipfile.is_zipfile(archive_path):
        raise RestoreError("O arquivo escolhido não é um .zip válido.")
    discard_prepared(database)
    token = uuid.uuid4().hex
    target = prepared_path(database, token)
    with zipfile.ZipFile(archive_path) as archive:
        uncompressed = _check_archive(archive)
        # Precisa caber: extração temporária + banco provisório + cópia do banco atual.
        current_size = database.stat().st_size if database.exists() else 0
        needed = uncompressed * 2 + current_size
        free = shutil.disk_usage(database.parent).free
        if free < needed:
            raise RestoreError(
                f"Espaço insuficiente no disco para restaurar: livres {free / 1024**2:.0f} MB, "
                f"necessários cerca de {needed / 1024**2:.0f} MB."
            )
        with tempfile.TemporaryDirectory(prefix="ops-restauracao-") as temporary:
            folder = Path(temporary) / "banco"
            archive.extractall(folder)
            try:
                with duckdb.connect(str(target)) as connection:
                    connection.execute(f"import database '{_sql_path(folder)}'")
            except duckdb.Error as exc:
                discard_prepared(database, token)
                raise RestoreError(f"Não foi possível ler o conteúdo do backup: {exc}") from exc
    try:
        with duckdb.connect(str(target)) as connection:
            connection.execute(SCHEMA_SQL)
            for statement in AUTH_MIGRATIONS:
                connection.execute(statement)
            backup_periods = _periods(connection)
            has_inventory = connection.execute(
                "select 1 from information_schema.tables where table_schema='main' and table_name='inventory_rows'"
            ).fetchone()
            tables = int(connection.execute(
                "select count(*) from information_schema.tables where table_schema='main'"
            ).fetchone()[0])
    except Exception:
        discard_prepared(database, token)
        raise
    if not has_inventory:
        discard_prepared(database, token)
        raise RestoreError("O backup não contém a Base de Estoque do Estoque Contábil.")

    local_periods: dict[str, dict[str, float]] = {}
    local_readable = True
    try:
        with connect(database) as connection:
            local_periods = _periods(connection)
    except Exception:  # noqa: BLE001 - banco atual danificado: a restauração é justamente a saída
        local_readable = False

    periods = []
    for period in sorted(set(backup_periods) | set(local_periods), reverse=True):
        backup_info = backup_periods.get(period)
        local_info = local_periods.get(period)
        periods.append({
            "period": period,
            "backup_rows": backup_info["rows"] if backup_info else None,
            "backup_fiscal_value": backup_info["fiscal_value"] if backup_info else None,
            "local_rows": local_info["rows"] if local_info else None,
            "local_fiscal_value": local_info["fiscal_value"] if local_info else None,
        })
    created = backup_created_at(archive_path)
    return {
        "token": token,
        "file": str(archive_path),
        "created_at": created.isoformat() if created else None,
        "tables": tables,
        "periods": periods,
        "local_readable": local_readable,
    }


def _read_machine_config(database: Path) -> tuple[list[tuple[str, str]], list[str], list[tuple[Any, ...]], int] | None:
    """Configurações, acessos e revisão de dados desta máquina (None se o banco atual não abrir)."""
    try:
        with connect(database) as connection:
            settings_rows = connection.execute(
                "select setting_key, setting_value from system_settings where setting_key <> ?", [BRIDGE_STATE_KEY]
            ).fetchall()
            cursor = connection.execute("select * from allowed_users")
            columns = [str(item[0]) for item in cursor.description]
            users = cursor.fetchall()
            state_row = connection.execute(
                "select setting_value from system_settings where setting_key=?", [BRIDGE_STATE_KEY]
            ).fetchone()
    except Exception:  # noqa: BLE001 - banco atual danificado: usa o que veio no backup
        return None
    revision = 0
    try:
        revision = int((json.loads(state_row[0]) if state_row else {}).get("data_revision", 0))
    except (TypeError, ValueError, AttributeError):
        revision = 0
    return [(str(key), str(value)) for key, value in settings_rows], columns, users, revision


def _file_in_use(path: Path) -> bool:
    """True se algum processo/conexão ainda mantém o arquivo aberto.

    No Windows o DuckDB abre o banco permitindo renomear; por isso a troca não pode
    confiar num erro do os.replace. Uma abertura exclusiva (sem compartilhamento)
    só funciona quando não resta nenhum outro identificador aberto.
    """
    if os.name != "nt" or not path.exists():
        return False
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    generic_read, open_existing, file_attribute_normal = 0x80000000, 3, 0x80
    handle = kernel32.CreateFileW(str(path), generic_read, 0, None, open_existing, file_attribute_normal, None)
    if handle in (None, wintypes.HANDLE(-1).value):
        return True
    kernel32.CloseHandle(handle)
    return False


def _wait_until_free(paths: list[Path], deadline: float) -> None:
    delay = 0.1
    while any(_file_in_use(path) for path in paths):
        if time.monotonic() >= deadline:
            raise PermissionError("banco ainda em uso")
        time.sleep(delay)
        delay = min(delay * 2, 1.0)


def _move_with_retry(source: Path, target: Path, deadline: float) -> None:
    delay = 0.1
    while True:
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 1.0)


def _cleanup_previous_copies(folder: Path) -> None:
    copies = sorted(folder.glob(f"{PREVIOUS_PREFIX}*.duckdb"), key=lambda item: item.name, reverse=True)
    for old in copies[KEEP_PREVIOUS_COPIES:]:
        for path in (old, Path(f"{old}.wal")):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue


def apply_restore(database: Path, token: str, *, restored_by: str = "", source_file: str = "") -> dict[str, Any]:
    """Substitui o banco local pelo backup conferido em ``prepare_restore``."""
    prepared = prepared_path(database, token)
    if not prepared.is_file():
        raise RestoreError("O backup conferido não está mais disponível. Clique em Conferir novamente.")

    machine = _read_machine_config(database)
    now = datetime.now().replace(microsecond=0)
    with duckdb.connect(str(prepared)) as connection:
        connection.execute("begin transaction")
        try:
            state_row = connection.execute(
                "select setting_value from system_settings where setting_key=?", [BRIDGE_STATE_KEY]
            ).fetchone()
            try:
                state = json.loads(state_row[0]) if state_row else {}
            except (TypeError, ValueError):
                state = {}
            if not isinstance(state, dict):
                state = {}
            restored_periods = sorted(_periods(connection))
            if machine is not None:
                settings_rows, columns, users, revision = machine
                # Configurações e acessos são desta máquina; do backup vêm só os dados.
                connection.execute("delete from system_settings")
                for key, value in settings_rows:
                    connection.execute(
                        "insert into system_settings(setting_key, setting_value, updated_at) values (?,?,current_timestamp)",
                        [key, value],
                    )
                target_columns = {
                    str(row[0]) for row in connection.execute(
                        "select column_name from information_schema.columns where table_schema='main' and table_name='allowed_users'"
                    ).fetchall()
                }
                keep = [index for index, column in enumerate(columns) if column in target_columns]
                if users and keep:
                    connection.execute("delete from allowed_users")
                    names = ", ".join(f'"{columns[index]}"' for index in keep)
                    marks = ", ".join("?" for _ in keep)
                    connection.executemany(
                        f"insert into allowed_users ({names}) values ({marks})",
                        [[row[index] for index in keep] for row in users],
                    )
            else:
                revision = 0
            # A ponte recebe do Drive o que lá for mais recente e reenvia o restante
            # (a publicação nunca sobrescreve uma versão mais nova no Drive).
            state.setdefault("periods", {})
            state["pending_publish"] = restored_periods
            state["data_revision"] = max(revision, int(state.get("data_revision", 0) or 0)) + 1
            state["last_sync_error"] = None
            state["last_publish_error"] = None
            state["restored_at"] = now.isoformat()
            state["restored_from"] = source_file
            state["restored_by"] = restored_by
            connection.execute(
                """insert into system_settings(setting_key,setting_value,updated_at) values (?,?,current_timestamp)
                   on conflict(setting_key) do update set setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
                [BRIDGE_STATE_KEY, json.dumps(state, ensure_ascii=False, default=str)],
            )
            connection.execute("commit")
        except Exception:
            connection.execute("rollback")
            raise
        connection.execute("checkpoint")

    previous = database.parent / f"{PREVIOUS_PREFIX}{now:%Y%m%d_%H%M%S}.duckdb"
    database_wal = Path(f"{database}.wal")
    moved_current = False
    with database_maintenance():
        deadline = time.monotonic() + SWAP_WAIT_SECONDS
        try:
            # Espera as conexões já abertas terminarem (as novas estão bloqueadas).
            _wait_until_free([database, database_wal], deadline)
            if database.exists():
                _move_with_retry(database, previous, deadline)
                moved_current = True
                if database_wal.exists():
                    _move_with_retry(database_wal, Path(f"{previous}.wal"), deadline)
            _move_with_retry(prepared, database, deadline)
        except PermissionError as exc:
            if moved_current and not database.exists():
                os.replace(previous, database)
                if Path(f"{previous}.wal").exists():
                    os.replace(Path(f"{previous}.wal"), database_wal)
            raise RestoreError(
                "O banco local continuou em uso (uma consulta ou atualização demorada). "
                "Nada foi alterado; aguarde alguns instantes e tente novamente."
            ) from exc
    discard_prepared(database)
    _cleanup_previous_copies(database.parent)
    return {
        "status": "restored",
        "periods": restored_periods,
        "previous_copy": str(previous) if moved_current else None,
        "restored_at": now.isoformat(),
        "kept_machine_settings": machine is not None,
    }
