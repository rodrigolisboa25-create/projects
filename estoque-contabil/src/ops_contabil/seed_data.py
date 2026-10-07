from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

SNAPSHOT_VERSION_KEY = "embedded_snapshot_version"
SNAPSHOT_BUILT_AT_KEY = "embedded_snapshot_built_at"
PREFERENCE_KEYS = {
    "density",
    "default_page_size",
    "animations_enabled",
    "chart_animations_enabled",
    "card_animations_enabled",
    "backup_enabled",
    "backup_folder",
    "backup_frequency",
    "backup_retention_days",
}


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _setting(connection: duckdb.DuckDBPyConnection, key: str) -> str:
    try:
        row = connection.execute(
            "select setting_value from system_settings where setting_key=?",
            [key],
        ).fetchone()
    except duckdb.Error:
        return ""
    if not row:
        return ""
    raw = str(row[0])
    try:
        value = json.loads(raw)
        return str(value) if value is not None else ""
    except (json.JSONDecodeError, TypeError):
        return raw.strip('"')


def _set_setting(connection: duckdb.DuckDBPyConnection, key: str, value: object) -> None:
    connection.execute(
        """insert into system_settings(setting_key,setting_value,updated_at)
           values (?,?,now())
           on conflict(setting_key) do update set
             setting_value=excluded.setting_value,
             updated_at=now()""",
        [key, json.dumps(value, ensure_ascii=False)],
    )


def _inventory_freshness(connection: duckdb.DuckDBPyConnection) -> datetime | None:
    try:
        row = connection.execute("select max(imported_at) from inventory_imports").fetchone()
        return row[0] if row and isinstance(row[0], datetime) else None
    except duckdb.Error:
        return None


def _version_key(value: object) -> tuple[int, ...]:
    parts = tuple(int(item) for item in re.findall(r"\d+", str(value or "")))
    return parts or (0,)


def snapshot_summary(database: Path) -> dict[str, Any]:
    with duckdb.connect(str(database), read_only=True) as connection:
        periods = connection.execute(
            """select period,count(*) as rows,
                      coalesce(sum(unrestricted_quantity),0) as quantity,
                      coalesce(sum(fiscal_total_amount),0) as fiscal_value
                 from inventory_rows group by period order by period"""
        ).fetchall()
        users = connection.execute(
            "select email,role,is_active from allowed_users order by email"
        ).fetchall()
        mapping_rows = connection.execute("select count(*) from mapping_rules").fetchone()[0]
        return {
            "version": _setting(connection, SNAPSHOT_VERSION_KEY),
            "built_at": _setting(connection, SNAPSHOT_BUILT_AT_KEY),
            "periods": [
                {
                    "period": str(row[0]),
                    "rows": int(row[1]),
                    "quantity": float(row[2] or 0),
                    "fiscal_value": float(row[3] or 0),
                }
                for row in periods
            ],
            "allowed_users": [
                {"email": str(row[0]), "role": str(row[1]), "active": bool(row[2])}
                for row in users
            ],
            "mapping_rows": int(mapping_rows),
            "size_bytes": database.stat().st_size,
        }


def create_snapshot(
    source: Path,
    target: Path,
    version: str,
    built_at: str | None = None,
) -> dict[str, Any]:
    """Create a consistent, sanitized DuckDB snapshot for first-use installations."""
    source = source.resolve()
    target = target.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Banco operacional não localizado: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    built_at = built_at or datetime.now(UTC).isoformat()
    building = target.with_name(f".{target.stem}.building-{os.getpid()}{target.suffix}")
    if building.exists():
        building.unlink()

    with tempfile.TemporaryDirectory(prefix="ops-seed-export-") as temporary:
        export_folder = Path(temporary) / "database"
        export_folder.mkdir()
        with duckdb.connect(str(source), read_only=True) as source_connection:
            source_connection.execute(f"export database '{_sql_path(export_folder)}' (format parquet)")
        with duckdb.connect(str(building)) as snapshot:
            snapshot.execute(f"import database '{_sql_path(export_folder)}'")
            snapshot.execute(
                "update allowed_users set identity_subject=null,last_login_at=null,google_sub=null"
            )
            snapshot.execute("delete from system_settings where setting_key='shared_version'")
            # Estado da ponte e dos backups pertence a cada máquina; a pasta da ponte
            # configurada (bridge_root) segue no pacote para novas instalações.
            # access_state (verificação da lista central de acessos) também é desta máquina:
            # a instalação nova começa o próprio prazo e recebe a lista pelo Drive.
            snapshot.execute(
                "delete from system_settings where setting_key in ('bridge_state','backup_state','access_state','notification_preferences')"
            )
            # O histórico do sino é desta máquina e não vai para as instalações novas.
            snapshot.execute("drop table if exists notification_log")
            snapshot.execute("drop sequence if exists notification_seq")
            _set_setting(snapshot, SNAPSHOT_VERSION_KEY, version)
            _set_setting(snapshot, SNAPSHOT_BUILT_AT_KEY, built_at)
            snapshot.execute("checkpoint")

    os.replace(building, target)
    summary = snapshot_summary(target)
    if not summary["periods"]:
        raise RuntimeError("O snapshot foi criado sem nenhuma competência compilada.")
    manifest = {
        **summary,
        "database": target.name,
        "sha256": _sha256(target),
    }
    target.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def _sha256(path: Path) -> str:
    import hashlib

    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _local_state(database: Path) -> dict[str, Any]:
    if not database.is_file():
        return {"version": "", "freshness": None, "identities": {}, "preferences": {}}
    with duckdb.connect(str(database), read_only=True) as connection:
        identities: dict[str, tuple[str | None, datetime | None]] = {}
        try:
            rows = connection.execute(
                "select email,identity_subject,last_login_at from allowed_users"
            ).fetchall()
            identities = {str(row[0]): (row[1], row[2]) for row in rows}
        except duckdb.Error:
            pass
        preferences: dict[str, str] = {}
        try:
            rows = connection.execute(
                "select setting_key,setting_value from system_settings"
            ).fetchall()
            preferences = {str(row[0]): str(row[1]) for row in rows if str(row[0]) in PREFERENCE_KEYS}
        except duckdb.Error:
            pass
        return {
            "version": _setting(connection, SNAPSHOT_VERSION_KEY),
            "freshness": _inventory_freshness(connection),
            "identities": identities,
            "preferences": preferences,
        }


# Tabelas com dados de uma competência. Numa atualização, cada competência do
# pacote substitui a local somente se for nova ou mais recente; o resto do banco
# (usuários, identidades, preferências, Mapping, auditoria) nunca é tocado.
PERIOD_TABLES = ("inventory_rows", "inventory_imports", "mb59_rows", "mb59_imports", "all_brazil_imports")
FRESHNESS_TABLES = ("inventory_imports", "mb59_imports", "all_brazil_imports")
UPDATE_BACKUP_NAME = "ops_contabil.antes-da-atualizacao.duckdb"


def _catalog_tables(connection: duckdb.DuckDBPyConnection, catalog: str) -> set[str]:
    rows = connection.execute(
        "select table_name from information_schema.tables where table_catalog=? and table_schema='main'",
        [catalog],
    ).fetchall()
    return {str(row[0]) for row in rows}


def _catalog_columns(connection: duckdb.DuckDBPyConnection, catalog: str, table: str) -> dict[str, str]:
    rows = connection.execute(
        """select column_name, data_type from information_schema.columns
           where table_catalog=? and table_schema='main' and table_name=? order by ordinal_position""",
        [catalog, table],
    ).fetchall()
    return {str(name): str(data_type) for name, data_type in rows}


def _loaded_periods(connection: duckdb.DuckDBPyConnection, catalog: str, tables: set[str]) -> set[str]:
    if "inventory_rows" not in tables:
        return set()
    rows = connection.execute(f'select distinct period from "{catalog}".main.inventory_rows').fetchall()
    return {str(row[0]) for row in rows}


def _period_freshness(connection: duckdb.DuckDBPyConnection, catalog: str, tables: set[str]) -> dict[str, datetime]:
    """Momento da carga mais recente (ZMM119, MB59 ou All Brazil) de cada competência."""
    parts = [
        f'select period, imported_at as loaded_at from "{catalog}".main."{table}"'
        for table in FRESHNESS_TABLES
        if table in tables
    ]
    if not parts:
        return {}
    rows = connection.execute(
        f"select period, max(loaded_at) from ({' union all '.join(parts)}) group by period"
    ).fetchall()
    return {str(period): loaded_at for period, loaded_at in rows if loaded_at is not None}


def _plan_update(seed: Path, target: Path) -> tuple[list[tuple[str, str]], list[dict[str, str]]]:
    """Decide, sem alterar nada, quais competências do pacote entram nesta máquina."""
    to_apply: list[tuple[str, str]] = []
    kept: list[dict[str, str]] = []
    with duckdb.connect(str(target), read_only=True) as connection:
        local = str(connection.execute("select current_database()").fetchone()[0])
        connection.execute(f"attach '{_sql_path(seed)}' as pkg (read_only)")
        try:
            package_tables = _catalog_tables(connection, "pkg")
            local_tables = _catalog_tables(connection, local)
            local_periods = _loaded_periods(connection, local, local_tables)
            package_fresh = _period_freshness(connection, "pkg", package_tables)
            local_fresh = _period_freshness(connection, local, local_tables)
            for period in sorted(_loaded_periods(connection, "pkg", package_tables)):
                incoming, current = package_fresh.get(period), local_fresh.get(period)
                if period not in local_periods:
                    to_apply.append((period, "competência nova nesta máquina"))
                elif incoming is not None and (current is None or incoming > current):
                    to_apply.append((period, "carga do pacote mais recente que a local"))
                else:
                    kept.append({"period": period, "reason": "carga local igual ou mais recente que a do pacote"})
        finally:
            connection.execute("detach pkg")
    return to_apply, kept


def _update_periods(seed: Path, target: Path, incoming_version: str) -> dict[str, Any]:
    to_apply, kept = _plan_update(seed, target)
    if not to_apply:
        return {"applied": [], "kept": kept, "backup": None}

    # Cópia de segurança do banco inteiro antes de qualquer alteração. O arquivo
    # precisa estar fechado: no Windows o DuckDB bloqueia o arquivo aberto.
    backup = target.with_name(UPDATE_BACKUP_NAME)
    shutil.copy2(target, backup)
    wal = target.with_name(target.name + ".wal")
    backup_wal = backup.with_name(backup.name + ".wal")
    if wal.exists():
        shutil.copy2(wal, backup_wal)
    elif backup_wal.exists():
        backup_wal.unlink()

    with duckdb.connect(str(target)) as connection:
        local = str(connection.execute("select current_database()").fetchone()[0])
        connection.execute(f"attach '{_sql_path(seed)}' as pkg (read_only)")
        try:
            package_tables = _catalog_tables(connection, "pkg")
            local_tables = _catalog_tables(connection, local)
            connection.execute("begin transaction")
            try:
                for table in PERIOD_TABLES:
                    if table not in package_tables:
                        continue
                    package_columns = _catalog_columns(connection, "pkg", table)
                    if table not in local_tables:
                        connection.execute(
                            f'create table "{local}".main."{table}" as select * from pkg.main."{table}" where false'
                        )
                        local_tables.add(table)
                    else:
                        # Pacote gerado por uma versão mais nova pode trazer colunas que o
                        # banco local ainda não tem; são acrescentadas antes da cópia.
                        local_columns = _catalog_columns(connection, local, table)
                        for column, data_type in package_columns.items():
                            if column not in local_columns:
                                connection.execute(
                                    f'alter table "{local}".main."{table}" add column "{column}" {data_type}'
                                )
                    for period, _ in to_apply:
                        connection.execute(f'delete from "{local}".main."{table}" where period=?', [period])
                        connection.execute(
                            f'insert into "{local}".main."{table}" by name '
                            f'select * from pkg.main."{table}" where period=?',
                            [period],
                        )
                _set_setting(connection, SNAPSHOT_VERSION_KEY, incoming_version)
                connection.execute("commit")
            except Exception:
                connection.execute("rollback")
                raise
            applied = [{"period": period, "reason": reason} for period, reason in to_apply]
            return {"applied": applied, "kept": kept, "backup": str(backup)}
        finally:
            connection.execute("detach pkg")


def apply_snapshot(seed: Path, target: Path) -> dict[str, Any]:
    """Install or refresh the bundled compiled periods.

    Without a local database, the snapshot is installed as is. On an existing
    installation, only compiled periods are refreshed: each period in the package
    replaces the local one when it is missing locally or its latest load is newer.
    Users, identity bindings, preferences, Mapping, audit history and periods that
    exist only on this computer are never touched.
    """
    seed = seed.resolve()
    target = target.resolve()
    if not seed.is_file():
        raise FileNotFoundError(f"Snapshot embutido não localizado: {seed}")
    incoming = snapshot_summary(seed)
    target.parent.mkdir(parents=True, exist_ok=True)

    if not target.is_file():
        temporary = target.with_name(f".{target.stem}.installing-{os.getpid()}{target.suffix}")
        shutil.copy2(seed, temporary)
        os.replace(temporary, target)
        return {"status": "installed", **snapshot_summary(target)}

    update = _update_periods(seed, target, str(incoming["version"]))
    return {
        "status": "updated_periods" if update["applied"] else "kept_local_database",
        "incoming_snapshot_version": incoming["version"],
        "applied_periods": update["applied"],
        "kept_periods": update["kept"],
        "backup": update["backup"],
        **snapshot_summary(target),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gerencia o snapshot embutido do Estoque Contábil.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--source", type=Path, required=True)
    create.add_argument("--target", type=Path, required=True)
    create.add_argument("--version", required=True)
    create.add_argument("--built-at")
    apply = subparsers.add_parser("apply")
    apply.add_argument("--seed", type=Path, required=True)
    apply.add_argument("--target", type=Path, required=True)
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "create":
        result = create_snapshot(args.source, args.target, args.version, args.built_at)
    elif args.command == "apply":
        result = apply_snapshot(args.seed, args.target)
    else:
        result = snapshot_summary(args.database)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
