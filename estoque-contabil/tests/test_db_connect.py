from pathlib import Path

import duckdb
import pytest

import ops_contabil.db as db


def test_transient_file_lock_is_retried(tmp_path: Path, monkeypatch) -> None:
    real_connect = duckdb.connect
    attempts = {"count": 0}

    def flaky_connect(path: str):
        attempts["count"] += 1
        if attempts["count"] <= 2:
            raise duckdb.IOException('IO Error: Cannot open file "x.duckdb". File is already open in python.exe (PID 1)')
        return real_connect(path)

    monkeypatch.setattr(db.duckdb, "connect", flaky_connect)
    with db.connect(tmp_path / "ops.duckdb") as connection:
        assert connection.execute("select 1").fetchone()[0] == 1
    assert attempts["count"] == 3


def test_windows_sharing_violation_text_is_also_retried(tmp_path: Path, monkeypatch) -> None:
    real_connect = duckdb.connect
    attempts = {"count": 0}

    def flaky_connect(path: str):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise duckdb.IOException(
                'IO Error: Cannot open file "x.duckdb": O arquivo já está sendo usado por outro processo.'
            )
        return real_connect(path)

    monkeypatch.setattr(db.duckdb, "connect", flaky_connect)
    with db.connect(tmp_path / "ops.duckdb") as connection:
        assert connection.execute("select 1").fetchone()[0] == 1
    assert attempts["count"] == 2


def test_concurrent_attach_conflict_is_retried(tmp_path: Path, monkeypatch) -> None:
    real_connect = duckdb.connect
    attempts = {"count": 0}

    def flaky_connect(path: str):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise duckdb.BinderException(
                'Binder Error: Unique file handle conflict: Cannot attach "ops" - the database file '
                '"x.duckdb" is already attached by database "ops"'
            )
        return real_connect(path)

    monkeypatch.setattr(db.duckdb, "connect", flaky_connect)
    with db.connect(tmp_path / "ops.duckdb") as connection:
        assert connection.execute("select 1").fetchone()[0] == 1
    assert attempts["count"] == 2


def test_many_threads_opening_the_same_database_never_fail(tmp_path: Path) -> None:
    import threading

    database = tmp_path / "ops.duckdb"
    with db.connect(database) as connection:
        connection.execute("create table t(x integer)")
    errors: list[Exception] = []

    def worker(index: int) -> None:
        try:
            for step in range(15):
                with db.connect(database) as connection:
                    if step % 3 == 0:
                        connection.execute("insert into t values (?)", [index])
                    connection.execute("select count(*) from t").fetchone()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    with db.connect(database) as connection:
        assert connection.execute("select count(*) from t").fetchone()[0] == 8 * 5


def test_other_io_errors_are_not_retried(tmp_path: Path, monkeypatch) -> None:
    attempts = {"count": 0}

    def broken_connect(_path: str):
        attempts["count"] += 1
        raise duckdb.IOException("IO Error: disk full")

    monkeypatch.setattr(db.duckdb, "connect", broken_connect)
    with pytest.raises(duckdb.IOException, match="disk full"):
        db.connect(tmp_path / "ops.duckdb")
    assert attempts["count"] == 1
