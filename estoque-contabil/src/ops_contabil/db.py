from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import duckdb

_OPEN_LOCK = threading.Lock()
# Liberado (set) em operação normal. A restauração de backup o fecha enquanto troca o
# arquivo do banco: novas conexões esperam, as já abertas terminam e fecham.
_DATABASE_AVAILABLE = threading.Event()
_DATABASE_AVAILABLE.set()
_MAINTENANCE_LOCK = threading.Lock()
MAINTENANCE_WAIT_SECONDS = 300.0


@contextmanager
def database_maintenance() -> Iterator[None]:
    """Bloqueia novas conexões enquanto o arquivo do banco é substituído."""
    with _MAINTENANCE_LOCK:
        # Fecha a passagem dentro da mesma trava das aberturas: nenhuma abertura fica
        # "no meio do caminho" depois deste ponto.
        with _OPEN_LOCK:
            _DATABASE_AVAILABLE.clear()
        try:
            yield
        finally:
            _DATABASE_AVAILABLE.set()


SCHEMA_SQL = """
create sequence if not exists run_seq start 1;
create table if not exists pipeline_runs (
    run_id bigint primary key default nextval('run_seq'),
    period varchar not null,
    status varchar not null,
    started_at timestamp not null default current_timestamp,
    finished_at timestamp,
    message varchar
);
create table if not exists source_files (
    source_file_id varchar primary key,
    run_id bigint not null,
    source_name varchar not null,
    source_path varchar not null,
    sha256 varchar not null,
    size_bytes bigint not null,
    loaded_at timestamp not null default current_timestamp,
    row_count bigint,
    schema_version varchar,
    status varchar not null
);
create table if not exists control_results (
    run_id bigint not null,
    control_name varchar not null,
    severity varchar not null,
    status varchar not null,
    expected_value varchar,
    actual_value varchar,
    details varchar,
    checked_at timestamp not null default current_timestamp
);
create table if not exists accounting_insights (
    run_id bigint not null,
    insight_code varchar not null,
    severity varchar not null,
    title varchar not null,
    description varchar not null,
    amount decimal(38, 2),
    evidence_json json,
    created_at timestamp not null default current_timestamp
);
create table if not exists system_settings (
    setting_key varchar primary key,
    setting_value varchar not null,
    updated_at timestamp not null default current_timestamp
);
create table if not exists allowed_users (
    email varchar primary key,
    is_active boolean not null default true,
    role varchar not null default 'user',
    allowed_pages varchar not null default '[]',
    google_sub varchar,
    identity_subject varchar,
    last_login_at timestamp,
    created_at timestamp not null default current_timestamp,
    updated_at timestamp not null default current_timestamp
);
"""

AUTH_MIGRATIONS = (
    "alter table allowed_users add column if not exists role varchar default 'user'",
    "alter table allowed_users add column if not exists allowed_pages varchar default '[]'",
    "alter table allowed_users add column if not exists google_sub varchar",
    "alter table allowed_users add column if not exists identity_subject varchar",
    "alter table allowed_users add column if not exists last_login_at timestamp",
    # Carimbo das alterações de acesso feitas por administradores (o login altera
    # updated_at, por isso a lista central de acessos usa esta coluna própria).
    "alter table allowed_users add column if not exists access_changed_at varchar",
    "alter table allowed_users add column if not exists access_changed_by varchar",
)


def _open_with_retry(database: Path, wait_seconds: float = 15.0) -> duckdb.DuckDBPyConnection:
    # Jobs de importação e requisições da interface abrem conexões curtas em threads
    # do mesmo processo. Quando a última conexão fecha, o DuckDB faz o checkpoint e só
    # então libera o arquivo; uma abertura concorrente nesse instante recebe "File is
    # already open", mesmo sendo o próprio processo. A trava é transitória: tenta de
    # novo por alguns segundos antes de desistir.
    # O texto varia: às vezes o DuckDB inclui "File is already open in <processo>",
    # às vezes só repassa a mensagem do Windows (em português ou inglês), e duas
    # aberturas simultâneas podem gerar "Unique file handle conflict ... already attached".
    lock_markers = (
        "already open",
        "sendo usado por outro processo",
        "used by another process",
        "already attached",
        "unique file handle conflict",
    )
    deadline = time.monotonic() + wait_seconds
    delay = 0.05
    while True:
        try:
            # Serializa só o instante da abertura (rápido): evita que duas threads
            # criem a mesma instância do banco ao mesmo tempo.
            with _OPEN_LOCK:
                if _DATABASE_AVAILABLE.is_set():
                    return duckdb.connect(str(database))
            # Restauração começou entre a espera e a abertura: aguarda terminar.
            if not _DATABASE_AVAILABLE.wait(MAINTENANCE_WAIT_SECONDS):
                raise RuntimeError("O banco local está sendo restaurado a partir de um backup. Tente novamente em instantes.")
            continue
        except (duckdb.IOException, duckdb.BinderException) as exc:
            message = str(exc).lower()
            if not any(marker in message for marker in lock_markers) or time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.5)


def connect(database: Path) -> duckdb.DuckDBPyConnection:
    database.parent.mkdir(parents=True, exist_ok=True)
    if not _DATABASE_AVAILABLE.wait(MAINTENANCE_WAIT_SECONDS):
        raise RuntimeError("O banco local está sendo restaurado a partir de um backup. Tente novamente em instantes.")
    connection = _open_with_retry(database)
    connection.execute(SCHEMA_SQL)
    for statement in AUTH_MIGRATIONS:
        connection.execute(statement)
    connection.execute("update allowed_users set role='user' where role is null or trim(role)='' ")
    connection.execute("update allowed_users set allowed_pages='[]' where allowed_pages is null")
    return connection
