from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .db import connect

PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
DIRECT_PERIOD_TABLES = (
    "inventory_rows",
    "inventory_imports",
    "mb59_rows",
    "mb59_imports",
    "all_brazil_imports",
)
RUN_CHILD_TABLES = ("source_files", "control_results", "accounting_insights")


def _table_exists(connection: Any, table: str) -> bool:
    return bool(
        connection.execute(
            "select 1 from information_schema.tables where table_schema='main' and table_name=?",
            [table],
        ).fetchone()
    )


def _period_counts(connection: Any, period: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in DIRECT_PERIOD_TABLES:
        if _table_exists(connection, table):
            counts[table] = int(
                connection.execute(f"select count(*) from {table} where period=?", [period]).fetchone()[0]
            )
    if _table_exists(connection, "pipeline_runs"):
        counts["pipeline_runs"] = int(
            connection.execute("select count(*) from pipeline_runs where period=?", [period]).fetchone()[0]
        )
        for table in RUN_CHILD_TABLES:
            if _table_exists(connection, table):
                counts[table] = int(
                    connection.execute(
                        f"select count(*) from {table} where run_id in "
                        "(select run_id from pipeline_runs where period=?)",
                        [period],
                    ).fetchone()[0]
                )
    return counts


def delete_compiled_period(settings: Any, period: str, deleted_by: str) -> dict[str, object]:
    if not PERIOD_PATTERN.fullmatch(period):
        raise ValueError("Competência inválida. Use o formato AAAA-MM.")

    database = Path(settings.path("database"))
    if not database.is_file():
        raise ValueError("O banco compilado ainda não existe.")

    with connect(database) as connection:
        counts = _period_counts(connection, period)
        if counts.get("inventory_rows", 0) == 0:
            raise ValueError(f"A competência {period} não possui Base de Estoque compilada.")
        connection.execute("checkpoint")

    backup_folder = Path(settings.path("processed")) / "backups" / "period_delete"
    backup_folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = backup_folder / f"ops_contabil_before_delete_{period}_{stamp}_{uuid.uuid4().hex[:6]}.duckdb"
    shutil.copy2(database, backup)

    with connect(database) as connection:
        connection.execute("begin transaction")
        try:
            if _table_exists(connection, "pipeline_runs"):
                for table in RUN_CHILD_TABLES:
                    if _table_exists(connection, table):
                        connection.execute(
                            f"delete from {table} where run_id in "
                            "(select run_id from pipeline_runs where period=?)",
                            [period],
                        )
            for table in DIRECT_PERIOD_TABLES:
                if _table_exists(connection, table):
                    connection.execute(f"delete from {table} where period=?", [period])
            if _table_exists(connection, "pipeline_runs"):
                connection.execute("delete from pipeline_runs where period=?", [period])
            connection.execute(
                """create table if not exists period_deletion_audit (
                       deletion_id varchar primary key,
                       period varchar not null,
                       deleted_by varchar not null,
                       deleted_at timestamp not null default current_timestamp,
                       deleted_counts_json json not null,
                       backup_path varchar not null
                   )"""
            )
            connection.execute(
                """insert into period_deletion_audit(
                       deletion_id,period,deleted_by,deleted_counts_json,backup_path
                   ) values (?,?,?,?,?)""",
                [str(uuid.uuid4()), period, deleted_by, json.dumps(counts), str(backup)],
            )
            connection.execute("commit")
        except Exception:
            connection.execute("rollback")
            raise

    return {
        "period": period,
        "deleted_by": deleted_by,
        "deleted_counts": counts,
        "backup_path": str(backup),
        "recoverable": True,
    }
