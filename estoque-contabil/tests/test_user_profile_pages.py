"""Perfil Usuário com apenas Visão e relatórios + Optimus precisa carregar as duas páginas."""

from pathlib import Path

from fastapi.testclient import TestClient

from ops_contabil.auth import SESSION_COOKIE, create_session_token
from ops_contabil.db import connect
from ops_contabil.inventory import ensure_inventory_schema
from ops_contabil.settings import Settings
from ops_contabil.web.app import create_app


def test_overview_and_optimus_user_can_load_the_global_period_list(tmp_path: Path) -> None:
    database = tmp_path / "processed" / "ops.duckdb"
    settings = Settings(
        root=tmp_path,
        raw={
            "project": {
                "database": str(database),
                "processed": str(database.parent),
                "landing": str(tmp_path / "landing"),
                "output": str(tmp_path / "output"),
            },
            "sources": {"all_brazil_materials": {}},
        },
    )
    email = "felipe.teste@gruposbf.com.br"
    subject = f"windows:{email}"
    with connect(database) as connection:
        ensure_inventory_schema(connection)
        connection.execute("insert into inventory_rows(period,source_row,material) values ('2026-09',1,'MAT-1')")
        connection.execute(
            """insert into allowed_users(email,is_active,role,allowed_pages,identity_subject)
               values (?,true,'user','["overview","agent"]',?)""",
            [email, subject],
        )
    client = TestClient(create_app(settings))
    client.cookies.set(SESSION_COOKIE, create_session_token(settings, email, subject))

    periods = client.get("/api/inventory/periods")
    assert periods.status_code == 200
    assert any(item["period"] == "2026-09" for item in periods.json()["periods"])
    assert client.get("/api/dashboard/summary?period=2026-09").status_code == 200
    # A Base de estoque em si continua restrita a quem tem a página.
    assert client.get("/api/inventory?period=2026-09").status_code == 403
    assert client.get("/api/inventory/columns").status_code == 403
