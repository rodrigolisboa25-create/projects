from datetime import date
from pathlib import Path

import duckdb
from fastapi.testclient import TestClient
import ops_contabil.health_center as health_center

from ops_contabil.auth import (
    PAGE_KEYS,
    SESSION_COOKIE,
    _user_payload,
    create_session_token,
    sanitize_role_pages,
)
from ops_contabil.db import connect
from ops_contabil.ingestion.excel import normalize_column
from ops_contabil.ingestion.schema_resolver import load_contracts, resolve_headers
from ops_contabil.inventory import dashboard_summary, ensure_inventory_schema
from ops_contabil.mappings import apply_mapping_rules, ensure_mapping_schema
from ops_contabil.mb59 import enrich_inventory_pass_step, ensure_mb59_schema
from ops_contabil.periods import delete_compiled_period
from ops_contabil.reporting import generate_report_html
from ops_contabil.seed_data import apply_snapshot, create_snapshot
from ops_contabil.settings import Settings, load_settings
from ops_contabil.sources.all_brazil import resolve_material_fallback
from ops_contabil.web.app import create_app


def test_normalize_column() -> None:
    assert normalize_column("Descrição material", 1) == "descricao_material"
    assert normalize_column(None, 3) == "column_3"


def test_load_settings() -> None:
    settings = load_settings(Path("config/project.yaml"))
    assert settings.raw["sources"]["mb59"]["transaction"] == "MB59"


def test_mb59_headers_are_order_independent() -> None:
    contract = load_contracts(Path("config/schemas.yaml"))["mb59_base"]
    row = ["Pedido", "Material", "Centro", "Texto breve material", "Depósito", "Tipo de movimento",
           "Doc.material", "Data de lançamento", "Qtd. UM registro", "Nome do usuário",
           "Cód.débito/crédito", "Data de entrada", "Item", "Data do documento", "Montante em MI"]
    row.insert(11, "Referência")
    resolution = resolve_headers([[None], row], contract)
    assert resolution.header_row == 2
    assert resolution.positions["material"] == 1
    assert resolution.positions["purchase_order"] == 0


def test_mb59_contract_accepts_product_offer_end_date() -> None:
    contract = load_contracts(Path("config/schemas.yaml"))["mb59_base"]
    column = next(item for item in contract.columns if item.canonical == "product_offer_end_date")
    assert "Product Offer End Dt" in column.aliases


def test_pass_step_uses_mb59_then_previous_then_all_brazil(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "ops.duckdb"
    settings = Settings(
        root=Path.cwd(),
        raw={
            "project": {"database": str(database)},
            "sources": {"all_brazil_materials": {}},
        },
    )
    with connect(database) as connection:
        ensure_inventory_schema(connection)
        ensure_mb59_schema(connection)
        connection.executemany(
            """insert into inventory_rows(
                   period,source_row,center_material_key,plant,material,
                   product_offer_end_date,season,year
               ) values (?,?,?,?,?,?,?,?)""",
            [
                ["2026-07", 1, "1000MAT-PREV", "1000", "MAT-PREV", date(2026, 7, 10), "FA", 2025],
                ["2026-08", 10, "1000MAT-MB", "1000", "MAT-MB", None, None, None],
                ["2026-08", 11, "1000MAT-PREV", "1000", "MAT-PREV", None, None, None],
                ["2026-08", 12, "1000MAT-AB", "1000", "MAT-AB", None, None, None],
                ["2026-08", 13, "1000MAT-NONE", "1000", "MAT-NONE", None, None, None],
            ],
        )
        connection.execute(
            """insert into mb59_rows(
                   period,center_material_key,material,plant,
                   product_offer_end_date,season,year,season_year,posting_date,source_row
               ) values (?,?,?,?,?,?,?,?,?,?)""",
            [
                "2026-08",
                "1000MAT-MB",
                "MAT-MB",
                "1000",
                date(2026, 8, 5),
                "SP",
                2026,
                "SP2026",
                date(2026, 8, 6),
                2,
            ],
        )

    monkeypatch.setattr(
        "ops_contabil.mb59.pass_step_lookup_from_all_brazil",
        lambda *_args, **_kwargs: {
            "lookup": {
                "MAT-MB": {"product_offer_end_date": date(2030, 1, 1), "season": "HO", "year": 2030},
                "MAT-PREV": {"product_offer_end_date": date(2031, 1, 1), "season": "HO", "year": 2031},
                "MAT-AB": {"product_offer_end_date": date(2026, 8, 20), "season": "SU", "year": 2026},
            },
            "snapshot": "ALL_BRAZIL_31_08.xlsx",
            "snapshot_date": "2026-08-31",
            "snapshots_available": 1,
            "snapshots_scanned": 1,
            "conflict_keys": 0,
        },
    )

    result = enrich_inventory_pass_step(settings, "2026-08", date(2026, 8, 31))

    with connect(database) as connection:
        rows = connection.execute(
            """select material,product_offer_end_date,season,year
                 from inventory_rows where period='2026-08' order by source_row"""
        ).fetchall()
    assert rows == [
        ("MAT-MB", date(2026, 8, 5), "SP", 2026.0),
        ("MAT-PREV", date(2026, 7, 10), "FA", 2025.0),
        ("MAT-AB", date(2026, 8, 20), "SU", 2026.0),
        ("MAT-NONE", None, None, None),
    ]
    assert result["field_sources"]["season"] == {
        "mb59": 1,
        "previous_inventory": 1,
        "all_brazil": 1,
        "not_found": 1,
    }


def test_inventory_loader_hides_percentage_without_real_progress() -> None:
    template = Path("src/ops_contabil/web/templates/dashboard.html").read_text(encoding="utf-8")
    assert "progress!==null&&progress!==undefined&&progress!==''" in template


def test_user_permissions_always_include_reports_and_agent_is_explicit() -> None:
    role, pages = sanitize_role_pages("user", [])
    assert role == "user"
    assert pages == ["overview", "docs"]  # Visão e relatórios e Documentação são obrigatórias
    role, pages = sanitize_role_pages("user", ["agent"])
    assert pages == ["overview", "agent", "docs"]
    assert _user_payload("viewer@gruposbf.com.br", "user", '["agent"]', "")["pages"] == [
        "overview",
        "agent",
        "docs",
    ]
    assert set(_user_payload("admin@gruposbf.com.br", "admin", "[]", "")["pages"]) == set(PAGE_KEYS)
    assert "health" in PAGE_KEYS


def test_mapping_recalculation_clears_deleted_derived_values_in_every_period(tmp_path: Path) -> None:
    database = tmp_path / "ops.duckdb"
    settings = Settings(root=Path.cwd(), raw={"project": {"database": str(database)}, "sources": {}})
    with connect(database) as connection:
        ensure_inventory_schema(connection)
        ensure_mapping_schema(connection)
        connection.executemany(
            """insert into inventory_rows(period,source_row,plant,material,lifecycle_description)
               values (?,?,?,?,?)""",
            [("2026-07", 1, "9999", "MAT-1", "Legacy"), ("2026-08", 1, "9999", "MAT-2", "Legacy")],
        )
        connection.execute(
            "insert into mapping_rules(group_key,key_value,value_1,value_2,position) values ('operation_status','9999','TESTE',null,999)"
        )
        connection.execute(
            "insert into mapping_rules(group_key,key_value,value_1,value_2,position) values ('location','9999',null,'LOCAL TESTE',999)"
        )
        connection.execute(
            "insert into mapping_rules(group_key,key_value,value_1,value_2,position) values ('lifecycle','Legacy','F9',null,999)"
        )
    for period in ("2026-07", "2026-08"):
        apply_mapping_rules(settings, period)
    with connect(database) as connection:
        connection.execute("delete from mapping_rules where key_value in ('9999','Legacy')")
    for period in ("2026-07", "2026-08"):
        apply_mapping_rules(settings, period)
    with connect(database) as connection:
        assert connection.execute(
            "select count(*) from inventory_rows where operation_status is not null or location_group is not null or lifecycle is not null"
        ).fetchone()[0] == 0


def test_corporate_page_access_is_enforced_for_user_profile(tmp_path: Path) -> None:
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
    email = "viewer@gruposbf.com.br"
    subject = f"windows:{email}"
    with connect(database) as connection:
        ensure_inventory_schema(connection)
        connection.execute(
            "insert into inventory_rows(period,source_row,material) values ('2026-08',1,'MAT-1')"
        )
        connection.execute(
            """insert into allowed_users(email,is_active,role,allowed_pages,identity_subject)
               values (?,true,'user','[\"agent\"]',?)""",
            [email, subject],
        )
    token = create_session_token(settings, email, subject)
    client = TestClient(create_app(settings))
    client.cookies.set(SESSION_COOKIE, token)

    assert client.get("/api/dashboard/summary?period=2026-08").status_code == 200
    assert client.get("/api/inventory?period=2026-08").status_code == 403
    assert client.get("/api/agent/check").status_code == 404
    assert client.get("/api/health-center?period=2026-08").status_code == 403

    with connect(database) as connection:
        connection.execute(
            "update allowed_users set allowed_pages='[]' where email=?",
            [email],
        )
    assert client.get("/api/dashboard/summary?period=2026-08").status_code == 200
    assert client.get("/api/agent/check").status_code == 403

    with connect(database) as connection:
        connection.execute(
            "update allowed_users set allowed_pages='[\"agent\",\"health\"]' where email=?",
            [email],
        )
    assert client.get("/api/agent/check").status_code == 404
    assert client.get("/api/health-center?period=2026-08").status_code == 200


def test_admin_can_delete_user_and_existing_session_is_revoked(tmp_path: Path) -> None:
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
    admin_email = "access.admin@gruposbf.com.br"
    user_email = "remove.me@gruposbf.com.br"
    admin_subject = f"windows:{admin_email}"
    user_subject = f"windows:{user_email}"
    with connect(database) as connection:
        ensure_inventory_schema(connection)
        connection.execute(
            """insert into allowed_users(email,is_active,role,allowed_pages,identity_subject)
               values (?,true,'admin','[]',?)""",
            [admin_email, admin_subject],
        )
        connection.execute(
            """insert into allowed_users(email,is_active,role,allowed_pages,identity_subject)
               values (?,true,'user','[\"overview\"]',?)""",
            [user_email, user_subject],
        )
    app = create_app(settings)
    admin = TestClient(app)
    admin.cookies.set(SESSION_COOKIE, create_session_token(settings, admin_email, admin_subject))
    user = TestClient(app)
    user.cookies.set(SESSION_COOKIE, create_session_token(settings, user_email, user_subject))

    assert user.get("/api/dashboard/summary?period=2026-08").status_code == 200
    csrf_token = admin.get("/api/auth/session").json()["csrf_token"]
    response = admin.delete(
        f"/api/settings/access/{user_email}", headers={"X-CSRF-Token": csrf_token}
    )
    assert response.status_code == 200
    assert all(item["email"] != user_email for item in response.json()["allowed_users"])
    with connect(database) as connection:
        assert connection.execute(
            "select count(*) from allowed_users where email=?", [user_email]
        ).fetchone()[0] == 0
    assert user.get("/api/dashboard/summary?period=2026-08").status_code == 401


def test_dashboard_period_and_chart_labels_are_consistent() -> None:
    template = Path("src/ops_contabil/web/templates/dashboard.html").read_text(encoding="utf-8")
    assert "const requestedPeriod=state.period" in template
    assert "if(requestedPeriod!==state.period)return false" in template
    assert "valor fiscal &middot; quantidade livre" in template
    assert "col-bar-wrap series-${si}" in template
    assert "/api/inventory/periods" in template
    assert "opsAllBrazilCollapsedYears" in template
    assert "preloadSystem" in template
    assert "${esc(item.label)}</option>" in template
    assert "${num.format(item.rows)} linhas</option>" not in template
    assert "function lifecycleHorizontalChart" in template
    assert "lifecycle-axis-label" in template
    assert "lifecycle-bar ${tone}" in template
    assert "lifecycle-label-bg ${tone}" in template
    assert "linearGradient id=\"${activeGradient}\"" in template
    assert "trend-axis-label" in template
    assert "trend-bar" in template
    assert "trend-point-value fiscal" in template
    assert "function pmmParetoChart" in template
    assert "id=\"pmm-dimension\"" in template
    assert "Division Description</option>" in template
    assert "Local de estoque</option>" in template
    assert "opsPmmDimension" in template
    assert "function pie3dChart" in template
    assert "chart-pmm-pareto" in template
    assert "chart-cost-composition" in template
    assert "function stockScatterChart" in template
    assert "id=\"stock-dimension\"" in template
    assert "chart-stock-scatter" in template
    assert '[data-panel="overview"] .section .head h2{font-size:17px' in template
    assert "opsStockDimension" in template
    assert "scatter-dot" in template
    assert "Valor fiscal (R$)" in template
    assert "collapse-icon" in template
    assert 'data-panel="health"' in template
    assert "loadHealthCenter" in template
    assert ">Share Link</button>" in template
    assert "/api/reports/html/download" in template
    assert 'id="html-share-dialog"' in template
    assert "navigator.canShare({files:[htmlShareFile]})" in template
    assert "não copie o endereço file:///" in template
    assert 'data-delete-user="${esc(u.email)}"' in template
    assert 'id="access-delete-dialog"' in template
    assert "method:'DELETE'" in template


def test_report_email_delivery_is_not_available() -> None:
    app_source = Path("src/ops_contabil/web/app.py").read_text(encoding="utf-8")
    reporting_source = Path("src/ops_contabil/reporting.py").read_text(encoding="utf-8")
    assert "/api/reports/email" not in app_source
    assert "email_report" not in app_source
    assert "queue_report_email" not in reporting_source
    assert "email_queue" not in reporting_source
    assert not Path("n8n/CONFIGURAR_OPTIMUS_ATUAL.md").exists()
    assert "OPS_REPORT_HTML_WEBAPP_URL" not in app_source
    assert "share-payload" not in app_source


def test_html_report_is_standalone_and_has_no_external_publisher(tmp_path: Path) -> None:
    database = tmp_path / "ops.duckdb"
    settings = Settings(
        root=tmp_path,
        raw={"project": {"database": str(database), "output": str(tmp_path / "output")}, "sources": {}},
    )
    with connect(database) as connection:
        ensure_inventory_schema(connection)
        connection.execute(
            """insert into inventory_rows(period,source_row,material,unrestricted_quantity,fiscal_total_amount)
               values ('2026-08',1,'MAT-1',10,250)"""
        )
    path = generate_report_html(settings, "2026-08", publish=False)
    content = path.read_text(encoding="utf-8")
    assert content.startswith("<!doctype html>")
    assert "2026-08" in content
    assert "<title>Estoque Contábil | Visão e relatórios | 2026-08</title>" in content
    assert "Ops Contábil" not in content
    assert path.name == "Relatorio_Estoque_Contabil_2026-08.html"
    assert "127.0.0.1" not in content
    assert "n8n" not in content.lower()
    assert "script.google" not in content.lower()


def test_optimus_renders_markdown_and_plain_urls_as_safe_links() -> None:
    template = Path("src/ops_contabil/web/templates/optimus.html").read_text(encoding="utf-8")
    assert "function appendInlineMarkdown" in template
    assert "https?:\\/\\/[^\\s<>\"']+" in template
    assert "element.target='_blank'" in template
    assert "element.rel='noopener noreferrer'" in template
    assert ".message.assistant .bubble a{" in template
    assert "overflow-wrap:anywhere" in template
    assert "pdf-download-link" in template
    assert "Baixar PDF" in template
    assert "reports\\/pdf\\/download" in template
    assert "Baixando PDF…" in template
    assert "contentType.includes('application/pdf')" in template
    assert "downloadLink.download=filename" in template
    assert "element.download=''" not in template


def test_health_center_uses_team_support_email() -> None:
    source = Path("src/ops_contabil/health_center.py").read_text(encoding="utf-8")
    template = Path("src/ops_contabil/web/templates/dashboard.html").read_text(encoding="utf-8")
    assert 'SUPPORT_EMAIL = "transformacao_digital@gruposbf.com.br"' in source
    assert 'SUPPORT_EMAIL = "rodrigo.lisboa@gruposbf.com.br"' not in source
    assert "mailto:transformacao_digital@gruposbf.com.br" in template
    assert "mailto:rodrigo.lisboa@gruposbf.com.br" not in template
    assert "configureHealthPolling" in template
    assert "},15000)" in template


def test_n8n_health_does_not_report_http_errors_as_online(monkeypatch) -> None:
    class Response:
        status_code = 403

    monkeypatch.setattr(health_center.httpx, "options", lambda *args, **kwargs: Response())
    ok, detail = health_center._n8n_probe("https://n8n.example.test/webhook/chat")
    assert ok is False
    assert "HTTP 403" in detail


def test_n8n_health_accepts_only_successful_probe(monkeypatch) -> None:
    class Response:
        status_code = 204

    monkeypatch.setattr(health_center.httpx, "options", lambda *args, **kwargs: Response())
    ok, detail = health_center._n8n_probe("https://n8n.example.test/webhook/chat")
    assert ok is True
    assert "HTTP 204" in detail


def test_vpn_detector_recognizes_connected_globalprotect_adapter() -> None:
    sample = """
Adaptador Ethernet Ethernet 3:

   Descrição . . . . . . . . . . . . . . . . . : PANGP Virtual Ethernet Adapter
   Endereço IPv4. . . . . . . .  . . . . . . . : 10.25.8.14(Preferencial)
"""
    pattern = health_center.re.compile(
        r"vpn|globalprotect|palo alto|pangp", health_center.re.IGNORECASE
    )
    assert health_center._active_vpn_adapters_from_ipconfig(sample, pattern) == [
        "Adaptador Ethernet Ethernet 3"
    ]


def test_vpn_detector_ignores_disconnected_globalprotect_adapter() -> None:
    sample = """
Adaptador Ethernet Ethernet 3:

   Estado da mídia. . . . . . . . . . . . . . .  : mídia desconectada
   Descrição . . . . . . . . . . . . . . . . . : PANGP Virtual Ethernet Adapter
"""
    pattern = health_center.re.compile(
        r"vpn|globalprotect|palo alto|pangp", health_center.re.IGNORECASE
    )
    assert health_center._active_vpn_adapters_from_ipconfig(sample, pattern) == []


def test_installer_is_versioned_and_source_runtime_cannot_drift() -> None:
    app_source = Path("src/ops_contabil/web/app.py").read_text(encoding="utf-8")
    dashboard = Path("src/ops_contabil/web/templates/dashboard.html").read_text(encoding="utf-8")
    launcher = Path("ABRIR_ESTOQUE_CONTABIL.bat").read_text(encoding="utf-8")
    installer = Path("installer/installer_main.py").read_text(encoding="utf-8")
    installer_entry = Path("installer/INSTALAR_ESTOQUE_CONTABIL.bat").read_text(encoding="utf-8")
    builder = Path("tools/build_installer.ps1").read_text(encoding="utf-8")

    assert "OPS_PROJECT_ROOT" in app_source
    assert "X-Ops-Installer-Version" in app_source
    assert "Cache-Control" in app_source and "no-store" in app_source
    assert "installer-meta" in dashboard
    assert "loadInstallerStatus" in dashboard
    assert "INSTALAR_ESTOQUE_CONTABIL.zip" in dashboard
    assert "INSTALAR_ESTOQUE_CONTABIL.bat" in dashboard
    assert "Visão e relatórios" in dashboard
    assert "· obrigatória" in dashboard
    assert "Optimus - Agente contábil" in dashboard
    assert "agent:'Optimus'" in dashboard
    assert "data-delete-period" in dashboard
    assert "/api/settings/periods/" in dashboard
    assert "TRANSFERINDO ARQUIVO" in dashboard
    assert "response.body?.getReader()" in dashboard
    assert "Content-Length" in dashboard
    assert 'set "PYTHONPATH=%OPS_PROJECT_ROOT%\\src"' in launcher
    assert "shutil.copytree(payload, staging)" in installer
    assert "app.previous" in installer
    assert "env=env" in installer
    assert "cwd=APP_ROOT" in installer
    assert 'encoding="ascii"' in installer
    assert 'ExpandEnvironmentStrings("%LOCALAPPDATA%\\\\OpsContabil\\\\ABRIR_ESTOQUE_CONTABIL.ps1")' in installer
    assert 'System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"' in installer
    assert "[Environment]::GetFolderPath('Desktop')" in installer
    assert "Estoque Contábil (inicializador direto)" in installer
    assert 'launcher = LOCAL_ROOT / "ABRIR_ESTOQUE_CONTABIL.ps1"' in installer
    assert "ops_contabil.seed_data" in installer
    assert 'staging / "seed" / "ops_contabil.duckdb"' in installer
    assert "runtime_manifest" not in installer
    assert "INSTALAR_ESTOQUE_CONTABIL.bat" in builder
    assert "PyInstaller" not in builder
    assert "ops_contabil.seed_data create" in builder
    assert "Compress-Archive" in builder
    assert "archive_sha256" in builder
    assert "Python.Python.3.13" in installer_entry
    assert "installer_main.py" in installer_entry


def test_installed_runtime_does_not_require_project_drive() -> None:
    builder = Path("tools/build_installer.ps1").read_text(encoding="utf-8")
    launcher_template = Path("installer/installer_main.py").read_text(encoding="utf-8")
    production_config = Path("config/production.yaml").read_text(encoding="utf-8")

    assert "Copy-Item -LiteralPath $Stage -Destination (Join-Path $PackageFolder 'payload') -Recurse" in builder
    assert "$env:OPS_PROJECT_ROOT = $App" in launcher_template
    assert "G:\\Drives compartilhados\\OPERAÇÕES FINANCEIRAS" not in launcher_template
    assert "G:\\Drives compartilhados\\OPERAÇÕES FINANCEIRAS" not in production_config


def test_embedded_snapshot_is_first_install_only_and_never_replaces_local_data(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    seed_v1 = tmp_path / "seed-v1.duckdb"
    seed_v2 = tmp_path / "seed-v2.duckdb"
    installed = tmp_path / "new-user" / "processed" / "ops_contabil.duckdb"
    email = "viewer@gruposbf.com.br"
    with connect(source) as connection:
        ensure_inventory_schema(connection)
        ensure_mapping_schema(connection)
        connection.execute(
            """insert into inventory_rows(
                   period,source_row,material,unrestricted_quantity,fiscal_total_amount
               ) values ('2026-08',1,'MAT-1',10,250)"""
        )
        connection.execute(
            """insert into allowed_users(email,is_active,role,allowed_pages,identity_subject)
               values (?,true,'user','[\"overview\"]','windows:old-machine@gruposbf.com.br')""",
            [email],
        )

    create_snapshot(source, seed_v1, "2026.09.23.9", "2026-09-23T12:00:00+00:00")
    first = apply_snapshot(seed_v1, installed)
    assert first["status"] == "installed"
    with connect(installed) as connection:
        assert connection.execute("select count(*) from inventory_rows").fetchone()[0] == 1
        assert connection.execute(
            "select identity_subject from allowed_users where email=?", [email]
        ).fetchone()[0] is None
        connection.execute(
            "update allowed_users set identity_subject='windows:viewer@gruposbf.com.br' where email=?",
            [email],
        )
        connection.execute(
            "insert into system_settings values ('density','\"comfortable\"',now())"
        )
        connection.execute(
            """insert into inventory_rows(
                   period,source_row,material,unrestricted_quantity,fiscal_total_amount
               ) values ('2026-09',1,'MAT-LOCAL-SEP',20,500)"""
        )

    with connect(source) as connection:
        connection.execute(
            """insert into inventory_rows(
                   period,source_row,material,unrestricted_quantity,fiscal_total_amount
               ) values ('2026-08',2,'MAT-2',5,100)"""
        )
    create_snapshot(source, seed_v2, "2026.09.23.10", "2026-09-23T13:00:00+00:00")
    update = apply_snapshot(seed_v2, installed)
    assert update["status"] == "kept_local_database"
    assert update["incoming_snapshot_version"] == "2026.09.23.10"
    with connect(installed) as connection:
        assert connection.execute("select count(*) from inventory_rows").fetchone()[0] == 2
        assert connection.execute(
            "select count(*) from inventory_rows where period='2026-08'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "select material from inventory_rows where period='2026-09'"
        ).fetchone()[0] == "MAT-LOCAL-SEP"
        assert connection.execute(
            "select identity_subject from allowed_users where email=?", [email]
        ).fetchone()[0] == "windows:viewer@gruposbf.com.br"
        assert connection.execute(
            "select setting_value from system_settings where setting_key='density'"
        ).fetchone()[0] == '"comfortable"'


def test_delete_compiled_period_is_complete_audited_and_recoverable(tmp_path: Path) -> None:
    database = tmp_path / "processed" / "ops.duckdb"
    settings = Settings(
        root=tmp_path,
        raw={
            "project": {"database": str(database), "processed": str(database.parent)},
            "sources": {},
        },
    )
    with connect(database) as connection:
        ensure_inventory_schema(connection)
        ensure_mb59_schema(connection)
        connection.executemany(
            "insert into inventory_rows(period,source_row,material) values (?,?,?)",
            [("2026-07", 1, "MAT-OLD"), ("2026-08", 1, "MAT-KEEP")],
        )
        connection.execute(
            """insert into inventory_imports values
               ('2026-07','old.xlsx','sha','Base Orig.',1,1,'schema',now()),
               ('2026-08','keep.xlsx','sha','Base Orig.',1,1,'schema',now())"""
        )
        connection.execute(
            """insert into mb59_rows(
                   period,center_material_key,material,plant,source_row
               ) values ('2026-07','1000MAT-OLD','MAT-OLD','1000',1)"""
        )
        connection.execute(
            """create table all_brazil_imports(
                   period varchar primary key, snapshot_date date, source_path varchar
               )"""
        )
        connection.execute(
            "insert into all_brazil_imports values ('2026-07','2026-07-31','all-brazil.xlsx')"
        )
        run_id = connection.execute(
            "insert into pipeline_runs(period,status) values ('2026-07','SUCCESS') returning run_id"
        ).fetchone()[0]
        connection.execute(
            "insert into control_results(run_id,control_name,severity,status) values (?,?,?,?)",
            [run_id, "rows", "INFO", "PASS"],
        )

    result = delete_compiled_period(settings, "2026-07", "admin@gruposbf.com.br")
    backup = Path(str(result["backup_path"]))
    assert backup.is_file()
    with connect(database) as connection:
        assert connection.execute(
            "select count(*) from inventory_rows where period='2026-07'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "select count(*) from inventory_rows where period='2026-08'"
        ).fetchone()[0] == 1
        assert connection.execute("select count(*) from mb59_rows").fetchone()[0] == 0
        assert connection.execute("select count(*) from all_brazil_imports").fetchone()[0] == 0
        assert connection.execute("select count(*) from pipeline_runs").fetchone()[0] == 0
        audit = connection.execute(
            "select period,deleted_by from period_deletion_audit"
        ).fetchone()
        assert audit == ("2026-07", "admin@gruposbf.com.br")
    with duckdb.connect(str(backup), read_only=True) as connection:
        assert connection.execute(
            "select count(*) from inventory_rows where period='2026-07'"
        ).fetchone()[0] == 1


def test_dashboard_summary_compares_with_previous_compiled_period(tmp_path: Path) -> None:
    database = tmp_path / "ops.duckdb"
    settings = Settings(
        root=Path.cwd(),
        raw={"project": {"database": str(database)}, "sources": {}},
    )
    with connect(database) as connection:
        ensure_inventory_schema(connection)
        connection.executemany(
            """insert into inventory_rows(
                   period,source_row,material,unrestricted_quantity,
                   fiscal_total_amount,division_description
               ) values (?,?,?,?,?,?)""",
            [
                ["2026-07", 1, "A", 10, 100, "Calçados"],
                ["2026-08", 1, "A", 10, 120, "Calçados"],
                ["2026-08", 2, "B", 5, 30, "Vestuário"],
            ],
        )

    summary = dashboard_summary(settings, "2026-08")

    assert summary["previous_period"] == "2026-07"
    assert summary["pmm_comparison"]["current"] == 10
    assert summary["pmm_comparison"]["previous"] == 10
    assert [item["period"] for item in summary["trend"]] == ["2026-07", "2026-08"]
    assert [item["pmm"] for item in summary["trend"]] == [10, 10]
    assert set(summary["pmm_breakdowns"]) == {"period", "division", "plant", "location", "season"}
    assert [item["pmm"] for item in summary["pmm_breakdowns"]["period"]] == [10, 10]
    calcados = next(item for item in summary["division_variance"] if item["label"] == "Calçados")
    assert calcados["difference"] == 20
    # Risco de obsolescência: valor fiscal de cada Division por faixa de Aging (só da competência pedida).
    aging = summary["division_aging"]
    assert aging["rows"] == ["Calçados", "Vestuário"]
    assert [sum(values) for values in aging["values"]] == [120, 30]
    # Sem regra "Planta e local" no Mapping, o estoque aparece como local "Não informado" e é listado à parte.
    assert summary["locations_unmapped"] == [{"plant": "(sem centro)", "rows": 2, "value": 150.0}]


def test_all_brazil_prefers_exact_material_then_style_color() -> None:
    exact = {"season": "SP"}
    style = {"season": "FA"}
    result = resolve_material_fallback(
        {"ABC123-001-10", "XYZ999-002-8", "NO-MATCH-7"},
        {
            "ABC123-001-10": exact,
            "ABC123-001": style,
            "XYZ999-002": style,
        },
    )
    assert result["ABC123-001-10"] is exact
    assert result["XYZ999-002-8"] is style
    assert "NO-MATCH-7" not in result
