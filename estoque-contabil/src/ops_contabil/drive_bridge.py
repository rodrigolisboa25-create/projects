"""Ponte de dados entre máquinas por uma pasta compartilhada do Google Drive.

O Drive é somente transporte: cada máquina continua dona do seu banco local.

- Publicar: depois de uma atualização local, a competência é exportada em Parquet
  para ``<raiz>/periodos/<AAAA-MM>/<versão>/``; só depois que todos os arquivos
  estão gravados o ponteiro ``atual.json`` passa a indicar a nova versão.
- Receber: uma competência do Drive só é aplicada se for mais recente que a local e
  se todos os arquivos estiverem completos (tamanho e SHA-256 conferidos). Enquanto
  o Google Drive ainda estiver baixando, a máquina simplesmente aguarda.
- Nada é apagado localmente por ausência no Drive. Usuários, permissões,
  preferências, Mapping e auditoria nunca passam pela ponte.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import tempfile
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .db import connect
from .inventory import ensure_inventory_schema
from .mb59 import ensure_mb59_schema

BRIDGE_TABLES = ("inventory_rows", "inventory_imports", "mb59_rows", "mb59_imports", "all_brazil_imports")
FRESHNESS_TABLES = ("inventory_imports", "mb59_imports", "all_brazil_imports")
ROOT_SETTING = "bridge_root"
STATE_SETTING = "bridge_state"
DEFAULT_FOLDER_NAMES = ("Estoque_Cont",)
SHARED_DRIVE_PARENTS = ("Drives compartilhados", "Shared drives")
REDIRECT_FILE = "pasta_movida.json"
POINTER_FILE = "atual.json"
MANIFEST_FILE = "manifest.json"
KEEP_VERSIONS = 3
FORMAT_VERSION = 1

_STATE_LOCK = threading.Lock()


class BridgeUnavailable(RuntimeError):
    """A pasta compartilhada não está acessível nesta máquina."""


# --------------------------------------------------------------------------- util


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.replace(microsecond=0).isoformat()


def _parse(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None, microsecond=0)
    try:
        return datetime.fromisoformat(str(value)).replace(tzinfo=None, microsecond=0)
    except ValueError:
        return None


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temporary, path)


def bridge_enabled(settings: Any) -> bool:
    return bool((settings.raw.get("bridge") or {}).get("enabled"))


def _folder_names(settings: Any) -> tuple[str, ...]:
    names = (settings.raw.get("bridge") or {}).get("drive_folder_names") or DEFAULT_FOLDER_NAMES
    return tuple(str(name) for name in names)


def _drive_letters() -> list[str]:
    return [f"{chr(code)}:/" for code in range(ord("C"), ord("Z") + 1)]


# ------------------------------------------------------------------ settings/state


def _get_setting(settings: Any, key: str) -> Any:
    with connect(settings.path("database")) as connection:
        row = connection.execute("select setting_value from system_settings where setting_key=?", [key]).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except (TypeError, ValueError):
        return row[0]


def _set_setting(settings: Any, key: str, value: Any) -> None:
    with connect(settings.path("database")) as connection:
        connection.execute(
            """insert into system_settings(setting_key,setting_value,updated_at) values (?,?,current_timestamp)
               on conflict(setting_key) do update set setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
            [key, json.dumps(value, ensure_ascii=False, default=str)],
        )


def load_state(settings: Any) -> dict[str, Any]:
    state = _get_setting(settings, STATE_SETTING)
    if not isinstance(state, dict):
        state = {}
    state.setdefault("periods", {})
    state.setdefault("pending_publish", [])
    state.setdefault("data_revision", 0)
    return state


def _update_state(settings: Any, mutate) -> dict[str, Any]:
    with _STATE_LOCK:
        state = load_state(settings)
        mutate(state)
        _set_setting(settings, STATE_SETTING, state)
        return state


# --------------------------------------------------------------------- pasta raiz


def _relative_to_shared_drive(path: Path) -> str | None:
    parts = list(path.parts)
    for index, part in enumerate(parts):
        if part in SHARED_DRIVE_PARENTS:
            return "/".join(parts[index:])
    return None


def _resolve_relative(relative: str | None) -> Path | None:
    if not relative:
        return None
    for letter in _drive_letters():
        candidate = Path(letter) / relative
        if candidate.is_dir():
            return candidate
    return None


def _follow_redirect(root: Path) -> Path:
    redirect = _read_json(root / REDIRECT_FILE)
    if not redirect:
        return root
    target = Path(str(redirect.get("path") or ""))
    if str(redirect.get("path") or "") and target.is_dir():
        return target
    return _resolve_relative(redirect.get("relative")) or root


def resolve_root(settings: Any) -> dict[str, Any]:
    """Localiza a pasta da ponte: configurada > variável de ambiente > detecção pelo nome."""
    configured = _get_setting(settings, ROOT_SETTING)
    if isinstance(configured, dict) and configured.get("path"):
        path = Path(str(configured["path"]))
        if not path.is_dir():
            path = _resolve_relative(configured.get("relative")) or path
        return _describe(_follow_redirect(path) if path.is_dir() else path, "configured")
    environment = os.getenv("OPS_BRIDGE_ROOT", "").strip()
    if environment:
        path = Path(os.path.expandvars(environment))
        return _describe(_follow_redirect(path) if path.is_dir() else path, "environment")
    for name in _folder_names(settings):
        for parent in SHARED_DRIVE_PARENTS:
            found = _resolve_relative(f"{parent}/{name}")
            if found is not None:
                return _describe(_follow_redirect(found), "detected")
    return {"path": None, "source": "none", "available": False}


def _describe(path: Path, source: str) -> dict[str, Any]:
    return {"path": str(path), "source": source, "available": path.is_dir()}


def bridge_root(settings: Any) -> Path:
    info = resolve_root(settings)
    if not info["available"]:
        raise BridgeUnavailable(
            "A pasta compartilhada do Drive não está acessível nesta máquina "
            f"({info['path'] or 'não localizada'}). Verifique o Google Drive para computador."
        )
    return Path(str(info["path"]))


def validate_folder(path: Path) -> None:
    if not path.is_dir():
        raise ValueError(f"A pasta não existe ou não está acessível: {path}")
    probe = path / f".teste_escrita_{uuid.uuid4().hex[:8]}"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise ValueError(f"Sem permissão de escrita na pasta: {path} ({exc})") from exc


def set_root(settings: Any, new_path: str | None, *, leave_redirect: bool = True, changed_by: str = "") -> dict[str, Any]:
    """Troca a pasta da ponte (contingência). None volta para a detecção automática."""
    previous = resolve_root(settings)
    if new_path is None or not str(new_path).strip():
        with connect(settings.path("database")) as connection:
            connection.execute("delete from system_settings where setting_key=?", [ROOT_SETTING])
        return resolve_root(settings)
    path = Path(os.path.expandvars(str(new_path).strip()))
    validate_folder(path)
    _set_setting(settings, ROOT_SETTING, {"path": str(path), "relative": _relative_to_shared_drive(path)})
    if leave_redirect and previous.get("available") and Path(str(previous["path"])).resolve() != path.resolve():
        # As outras máquinas seguem a nova pasta ao encontrar este aviso na antiga.
        _write_json_atomic(
            Path(str(previous["path"])) / REDIRECT_FILE,
            {"path": str(path), "relative": _relative_to_shared_drive(path), "changed_at": _iso(_now()), "changed_by": changed_by},
        )
    return resolve_root(settings)


# ------------------------------------------------------------------ dados locais


def _ensure_tables(connection: Any) -> None:
    ensure_inventory_schema(connection)
    ensure_mb59_schema(connection)
    connection.execute(
        """create table if not exists all_brazil_imports (
            period varchar primary key, snapshot_date date, source_path varchar, source_sha256 varchar,
            inventory_keys bigint, matched_keys bigint, coverage_pct double, duplicate_keys bigint,
            conflict_keys bigint, schema_fingerprint varchar, imported_at timestamp default current_timestamp
        )"""
    )


def local_periods(settings: Any) -> dict[str, dict[str, Any]]:
    """Competências locais com linhas, valor fiscal e momento da última carga."""
    with connect(settings.path("database")) as connection:
        _ensure_tables(connection)
        rows = connection.execute(
            """select period, count(*), coalesce(sum(fiscal_total_amount),0)
               from inventory_rows group by period"""
        ).fetchall()
        union = " union all ".join(f"select period, imported_at from {table}" for table in FRESHNESS_TABLES)
        loaded = connection.execute(
            f"select period, max(imported_at) from ({union}) group by period"
        ).fetchall()
    loaded_at = {str(period): _parse(value) for period, value in loaded}
    return {
        str(period): {"rows": int(count), "fiscal_value": float(fiscal), "loaded_at": loaded_at.get(str(period))}
        for period, count, fiscal in rows
    }


def _local_changed_at(state: dict[str, Any], period: str, local: dict[str, dict[str, Any]]) -> datetime | None:
    entry = state["periods"].get(period) or {}
    changed = _parse(entry.get("changed_at"))
    if changed is not None:
        return changed
    info = local.get(period)
    return None if info is None else info.get("loaded_at")


def mark_local_change(settings: Any, periods: list[str], reason: str = "") -> None:
    """Registra que os dados destas competências mudaram nesta máquina e devem ser publicados."""
    changed_at = _iso(_now())

    def mutate(state: dict[str, Any]) -> None:
        for period in periods:
            state["periods"][period] = {"changed_at": changed_at, "origin": "local", "version": None, "reason": reason}
            if period not in state["pending_publish"]:
                state["pending_publish"].append(period)

    _update_state(settings, mutate)


def mark_local_deletion(settings: Any, period: str) -> None:
    """A exclusão é local: impede que a ponte traga de volta a mesma versão excluída."""
    deleted_at = _iso(_now())

    def mutate(state: dict[str, Any]) -> None:
        state["periods"][period] = {"deleted_at": deleted_at, "origin": "local", "version": None}
        state["pending_publish"] = [item for item in state["pending_publish"] if item != period]

    _update_state(settings, mutate)


# ----------------------------------------------------------------------- publicar


def _pointer(root: Path, period: str) -> dict[str, Any] | None:
    return _read_json(root / "periodos" / period / POINTER_FILE)


def publish_period(settings: Any, period: str, *, published_by: str = "", force: bool = False) -> dict[str, Any]:
    root = bridge_root(settings)
    state = load_state(settings)
    local = local_periods(settings)
    if period not in local:
        return {"period": period, "status": "skipped", "reason": "competência sem Base de Estoque nesta máquina"}
    changed_at = _local_changed_at(state, period, local) or _now()
    entry = state["periods"].get(period) or {}
    remote = _pointer(root, period)
    remote_changed = _parse((remote or {}).get("changed_at"))
    if not force and remote is not None:
        if entry.get("version") and entry.get("version") == remote.get("version"):
            return {"period": period, "status": "skipped", "reason": "o Drive já tem esta versão"}
        if remote_changed is not None and remote_changed > changed_at:
            return {"period": period, "status": "skipped", "reason": "o Drive tem uma versão mais recente"}
        if not entry.get("changed_at") and remote_changed is not None and remote_changed >= changed_at:
            return {"period": period, "status": "skipped", "reason": "o Drive já tem esta carga"}

    # Nome ordenável pelo momento da publicação (microssegundos): a versão mais nova
    # é sempre a última em ordem alfabética.
    version = f"{datetime.now():%Y%m%dT%H%M%S%f}-{uuid.uuid4().hex[:8]}"
    period_folder = root / "periodos" / period
    staging = period_folder / f".enviando-{version}"
    final = period_folder / version
    files: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="ops-ponte-") as temporary:
        export = Path(temporary)
        with connect(settings.path("database")) as connection:
            _ensure_tables(connection)
            for table in BRIDGE_TABLES:
                target = export / f"{table}.parquet"
                connection.execute(
                    f"copy (select * from {table} where period = ?) to '{_sql_path(target)}' (format parquet, compression zstd)",
                    [period],
                )
        staging.mkdir(parents=True, exist_ok=True)
        try:
            for table in BRIDGE_TABLES:
                source = export / f"{table}.parquet"
                shutil.copy2(source, staging / source.name)
                files[source.name] = {"size": source.stat().st_size, "sha256": _sha256(source)}
            manifest = {
                "format": FORMAT_VERSION,
                "period": period,
                "version": version,
                "changed_at": _iso(changed_at),
                "published_at": _iso(_now()),
                "published_by": published_by,
                "machine": socket.gethostname(),
                "rows": local[period]["rows"],
                "fiscal_value": round(local[period]["fiscal_value"], 2),
                "files": files,
            }
            _write_json_atomic(staging / MANIFEST_FILE, manifest)
            os.replace(staging, final)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    # O ponteiro só muda depois que a versão inteira está gravada.
    _write_json_atomic(period_folder / POINTER_FILE, manifest)
    _prune_versions(period_folder, keep=version)

    def mutate(current: dict[str, Any]) -> None:
        current["periods"][period] = {"changed_at": _iso(changed_at), "origin": "local", "version": version,
                                      "published_at": manifest["published_at"]}
        current["pending_publish"] = [item for item in current["pending_publish"] if item != period]
        current["last_publish_at"] = manifest["published_at"]
        current["last_publish_error"] = None

    _update_state(settings, mutate)
    return {"period": period, "status": "published", "version": version, "rows": manifest["rows"]}


def _prune_versions(period_folder: Path, keep: str) -> None:
    versions = sorted(
        (item for item in period_folder.iterdir() if item.is_dir() and not item.name.startswith(".")),
        key=lambda item: item.name,
        reverse=True,
    )
    for old in versions[KEEP_VERSIONS:]:
        if old.name != keep:
            shutil.rmtree(old, ignore_errors=True)
    for stale in period_folder.glob(".enviando-*"):
        try:
            if datetime.fromtimestamp(stale.stat().st_mtime) < datetime.now() - timedelta(days=1):
                shutil.rmtree(stale, ignore_errors=True)
        except OSError:
            continue


def publish_pending(settings: Any, *, published_by: str = "") -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for period in list(load_state(settings)["pending_publish"]):
        try:
            results.append(publish_period(settings, period, published_by=published_by))
        except Exception as exc:  # noqa: BLE001 - fica pendente e é tentado de novo
            _update_state(settings, lambda state, exc=exc: state.update(last_publish_error=str(exc)))
            results.append({"period": period, "status": "failed", "error": str(exc)})
            if isinstance(exc, BridgeUnavailable):
                break
    return results


def publish_all(settings: Any, *, published_by: str = "") -> list[dict[str, Any]]:
    """Publica todas as competências locais que o Drive ainda não tem em versão igual ou mais nova."""
    periods = sorted(local_periods(settings))
    _update_state(settings, lambda state: state.update(
        pending_publish=sorted(set(state["pending_publish"]) | set(periods))
    ))
    return publish_pending(settings, published_by=published_by)


# ------------------------------------------------------------------------ receber


def _verify_files(folder: Path, pointer: dict[str, Any]) -> str | None:
    """Confere a versão no Drive. Devolve o motivo se ainda não estiver completa."""
    manifest = _read_json(folder / MANIFEST_FILE)
    if manifest is None or manifest.get("version") != pointer.get("version"):
        return "o manifesto da versão ainda não chegou pelo Google Drive"
    files = pointer.get("files") or {}
    for name, meta in files.items():
        path = folder / name
        try:
            if path.stat().st_size != int(meta.get("size", -1)):
                return f"{name} ainda está sendo baixado pelo Google Drive"
        except OSError:
            return f"{name} ainda não chegou pelo Google Drive"
        if _sha256(path) != meta.get("sha256"):
            return f"{name} está incompleto ou foi alterado"
    return None


def _parquet_columns(connection: Any, path: Path) -> dict[str, str]:
    rows = connection.execute(f"describe select * from read_parquet('{_sql_path(path)}')").fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def _table_columns(connection: Any, table: str) -> set[str]:
    rows = connection.execute(
        "select column_name from information_schema.columns where table_schema='main' and table_name=?", [table]
    ).fetchall()
    return {str(row[0]) for row in rows}


def _apply_version(settings: Any, folder: Path, period: str, files: dict[str, Any]) -> None:
    with connect(settings.path("database")) as connection:
        _ensure_tables(connection)
        connection.execute("begin transaction")
        try:
            for table in BRIDGE_TABLES:
                name = f"{table}.parquet"
                if name not in files:
                    continue
                source = folder / name
                existing = _table_columns(connection, table)
                for column, data_type in _parquet_columns(connection, source).items():
                    if column not in existing:
                        connection.execute(f'alter table {table} add column "{column}" {data_type}')
                connection.execute(f"delete from {table} where period = ?", [period])
                connection.execute(
                    f"insert into {table} by name select * from read_parquet('{_sql_path(source)}') where period = ?",
                    [period],
                )
            connection.execute("commit")
        except Exception:
            connection.execute("rollback")
            raise


def sync_from_bridge(settings: Any, *, apply_lock: threading.Lock | None = None) -> dict[str, Any]:
    """Traz do Drive as competências mais recentes que as locais. Nunca apaga dados locais."""
    root = bridge_root(settings)
    periods_folder = root / "periodos"
    applied: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    if periods_folder.is_dir():
        for period_folder in sorted(item for item in periods_folder.iterdir() if item.is_dir()):
            period = period_folder.name
            pointer = _read_json(period_folder / POINTER_FILE)
            if not pointer or pointer.get("period") != period or int(pointer.get("format", 0)) > FORMAT_VERSION:
                continue
            state = load_state(settings)
            entry = state["periods"].get(period) or {}
            remote_changed = _parse(pointer.get("changed_at"))
            if entry.get("version") == pointer.get("version"):
                continue
            deleted_at = _parse(entry.get("deleted_at"))
            if deleted_at is not None and remote_changed is not None and remote_changed <= deleted_at:
                skipped.append({"period": period, "reason": "competência excluída nesta máquina depois desta versão"})
                continue
            local_changed = _local_changed_at(state, period, local_periods(settings))
            if local_changed is not None and (remote_changed is None or remote_changed <= local_changed):
                skipped.append({"period": period, "reason": "a versão desta máquina é igual ou mais recente"})
                continue
            folder = period_folder / str(pointer.get("version"))
            problem = _verify_files(folder, pointer)
            if problem:
                waiting.append({"period": period, "reason": problem})
                continue
            if apply_lock is not None:
                with apply_lock:
                    _apply_version(settings, folder, period, pointer.get("files") or {})
            else:
                _apply_version(settings, folder, period, pointer.get("files") or {})

            def mutate(current: dict[str, Any], pointer=pointer, period=period) -> None:
                current["periods"][period] = {
                    "changed_at": pointer.get("changed_at"),
                    "origin": "bridge",
                    "version": pointer.get("version"),
                    "published_by": pointer.get("published_by"),
                    "received_at": _iso(_now()),
                }
                current["data_revision"] = int(current.get("data_revision", 0)) + 1

            _update_state(settings, mutate)
            applied.append({"period": period, "version": pointer.get("version"), "rows": pointer.get("rows")})
    result = {"applied": applied, "waiting": waiting, "skipped": skipped, "synced_at": _iso(_now())}
    _update_state(settings, lambda state: state.update(last_sync_at=result["synced_at"], last_sync_result={
        "applied": [item["period"] for item in applied],
        "waiting": waiting,
    }, last_sync_error=None))
    return result


def record_sync_error(settings: Any, error: str) -> None:
    _update_state(settings, lambda state: state.update(last_sync_error=error, last_sync_attempt_at=_iso(_now())))


# ------------------------------------------------------------------------- status


def bridge_status(settings: Any) -> dict[str, Any]:
    root = resolve_root(settings)
    state = load_state(settings)
    local = local_periods(settings)
    remote: dict[str, dict[str, Any]] = {}
    if root["available"]:
        folder = Path(str(root["path"])) / "periodos"
        if folder.is_dir():
            for period_folder in folder.iterdir():
                pointer = _read_json(period_folder / POINTER_FILE) if period_folder.is_dir() else None
                if pointer:
                    remote[period_folder.name] = pointer
    periods = []
    for period in sorted(set(local) | set(remote), reverse=True):
        entry = state["periods"].get(period) or {}
        pointer = remote.get(period)
        if period in state["pending_publish"]:
            situation = "Aguardando envio ao Drive"
        elif pointer and entry.get("version") == pointer.get("version"):
            situation = "Sincronizada"
        elif pointer and period not in local:
            situation = "Disponível no Drive (será recebida)"
        elif pointer:
            remote_changed = _parse(pointer.get("changed_at"))
            local_changed = _local_changed_at(state, period, local)
            situation = (
                "Mais recente no Drive (será recebida)"
                if local_changed is None or (remote_changed and remote_changed > local_changed)
                else "Mais recente nesta máquina"
            )
        else:
            situation = "Somente nesta máquina"
        periods.append({
            "period": period,
            "local_rows": (local.get(period) or {}).get("rows"),
            "local_changed_at": _iso(_local_changed_at(state, period, local)),
            "drive_version": (pointer or {}).get("version"),
            "drive_changed_at": (pointer or {}).get("changed_at"),
            "drive_published_by": (pointer or {}).get("published_by"),
            "drive_rows": (pointer or {}).get("rows"),
            "situation": situation,
        })
    return {
        "enabled": bridge_enabled(settings),
        "root": root,
        "periods": periods,
        "pending_publish": state["pending_publish"],
        "last_publish_at": state.get("last_publish_at"),
        "last_publish_error": state.get("last_publish_error"),
        "last_sync_at": state.get("last_sync_at"),
        "last_sync_error": state.get("last_sync_error"),
        "last_sync_result": state.get("last_sync_result"),
        "data_revision": int(state.get("data_revision", 0)),
    }
