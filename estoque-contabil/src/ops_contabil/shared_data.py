from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .auth import BOOTSTRAP_ADMINS
from .db import connect
from .inventory import ensure_inventory_schema
from .mappings import ensure_mapping_schema
from .mb59 import ensure_mb59_schema


def shared_root(settings: Any) -> Path:
    configured = os.getenv("OPS_SHARED_DATA_ROOT", "").strip()
    if configured:
        return Path(os.path.expandvars(configured)).resolve()
    project_root = Path(os.getenv("OPS_PROJECT_ROOT", str(settings.root))).resolve()
    return project_root / "shared_data"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def publication_status(settings: Any) -> dict[str, Any]:
    pointer = _read_json(shared_root(settings) / "current.json")
    local_version = ""
    with connect(settings.path("database")) as connection:
        row = connection.execute(
            "select setting_value from system_settings where setting_key='shared_version'"
        ).fetchone()
        if row:
            local_version = str(row[0]).strip('"')
    return {
        "available": pointer is not None,
        "shared_root": str(shared_root(settings)),
        "published": pointer,
        "local_version": local_version,
        "synchronized": bool(pointer and pointer.get("version") == local_version),
    }


def publish_period(settings: Any, period: str, published_by: str) -> dict[str, Any]:
    root = shared_root(settings)
    version = datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    final_folder = root / "versions" / period / version
    staging = root / "versions" / period / ("." + version + ".staging")
    staging.mkdir(parents=True, exist_ok=False)
    counts: dict[str, int] = {}
    tables = {
        "inventory_rows": "period = ?",
        "inventory_imports": "period = ?",
        "mb59_rows": "period = ?",
        "mb59_imports": "period = ?",
        "mapping_rules": "true",
    }
    try:
        with connect(settings.path("database")) as connection:
            ensure_inventory_schema(connection)
            ensure_mb59_schema(connection)
            ensure_mapping_schema(connection)
            for table, where in tables.items():
                parameters = [] if where == "true" else [period]
                counts[table] = int(connection.execute(
                    f"select count(*) from {table} where {where}", parameters
                ).fetchone()[0])
                target = (staging / f"{table}.parquet").as_posix().replace("'", "''")
                connection.execute(
                    f"copy (select * from {table} where {where}) to '{target}' (format parquet, compression zstd)",
                    parameters,
                )
        if not counts.get("inventory_rows"):
            raise ValueError(f"A competência {period} ainda não possui Base de Estoque para publicar.")
        manifest = {
            "schema_version": 1,
            "version": version,
            "period": period,
            "published_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "published_by": published_by,
            "counts": counts,
            "relative_path": f"versions/{period}/{version}",
        }
        _write_json_atomic(staging / "manifest.json", manifest)
        staging.rename(final_folder)
        _write_json_atomic(root / "current.json", manifest)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def sync_latest_publication(settings: Any, force: bool = False) -> dict[str, Any]:
    pointer = _read_json(shared_root(settings) / "current.json")
    if pointer is None:
        return {"status": "not_available", **publication_status(settings)}
    status = publication_status(settings)
    if status["synchronized"] and not force:
        return {"status": "already_current", **status}
    folder = shared_root(settings) / str(pointer["relative_path"])
    manifest = _read_json(folder / "manifest.json")
    if manifest is None or manifest.get("version") != pointer.get("version"):
        raise RuntimeError("A publicação compartilhada está incompleta. O snapshot anterior foi preservado.")
    period = str(manifest["period"])
    with connect(settings.path("database")) as connection:
        ensure_inventory_schema(connection)
        ensure_mb59_schema(connection)
        ensure_mapping_schema(connection)
        connection.execute("begin transaction")
        try:
            for table in ("inventory_rows", "inventory_imports", "mb59_rows", "mb59_imports"):
                source = (folder / f"{table}.parquet").as_posix().replace("'", "''")
                connection.execute(f"delete from {table} where period=?", [period])
                connection.execute(f"insert into {table} by name select * from read_parquet('{source}')")
            mapping_source = (folder / "mapping_rules.parquet").as_posix().replace("'", "''")
            connection.execute("delete from mapping_rules")
            connection.execute(f"insert into mapping_rules by name select * from read_parquet('{mapping_source}')")
            connection.execute(
                """insert into system_settings values ('shared_version', ?, current_timestamp)
                   on conflict(setting_key) do update set setting_value=excluded.setting_value, updated_at=current_timestamp""",
                [str(manifest["version"])],
            )
            connection.execute("commit")
        except Exception:
            connection.execute("rollback")
            raise
    return {"status": "synchronized", **publication_status(settings)}


def publish_access_manifest(settings: Any) -> None:
    with connect(settings.path("database")) as connection:
        rows = connection.execute(
            "select email, is_active, role, allowed_pages from allowed_users order by email"
        ).fetchall()
    _write_json_atomic(shared_root(settings) / "access" / "users.json", {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "users": [
            {"email": row[0], "active": bool(row[1]), "role": row[2], "pages": json.loads(row[3] or "[]")}
            for row in rows
        ],
    })


def sync_access_manifest(settings: Any) -> None:
    payload = _read_json(shared_root(settings) / "access" / "users.json")
    if not payload or not isinstance(payload.get("users"), list):
        return
    with connect(settings.path("database")) as connection:
        for item in payload["users"]:
            email = str(item.get("email", "")).strip().lower()
            if not email:
                continue
            role = "admin" if email in BOOTSTRAP_ADMINS or item.get("role") == "admin" else "user"
            pages = [] if role == "admin" else list(item.get("pages") or [])
            connection.execute(
                """insert into allowed_users(email,is_active,role,allowed_pages,updated_at)
                   values (?,?,?,?,current_timestamp) on conflict(email) do update set
                   is_active=excluded.is_active,role=excluded.role,allowed_pages=excluded.allowed_pages,
                   updated_at=current_timestamp""",
                [email, True if email in BOOTSTRAP_ADMINS else bool(item.get("active")), role, json.dumps(pages)],
            )
