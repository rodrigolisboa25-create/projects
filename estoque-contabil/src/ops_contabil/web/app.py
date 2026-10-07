from __future__ import annotations

import calendar
import hashlib
import json
import os
import re
import shutil
import threading
from types import SimpleNamespace
import time
import uuid
import tempfile
import httpx
from datetime import date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator

from ..db import connect
from ..auth import (
    BOOTSTRAP_ADMINS,
    CSRF_COOKIE,
    SESSION_COOKIE,
    authorize_windows_user,
    create_session_token,
    current_user,
    ensure_auth_schema,
    new_csrf_token,
    normalize_corporate_email,
    page_catalog,
    sanitize_role_pages,
    session_hours,
    windows_corporate_email,
)
from ..extractors.sap_gui import SapGuiCancelled, SapGuiError, SapGuiRobot
from ..inventory import dashboard_summary, ensure_inventory_schema, export_inventory_xlsx, import_zmm119_xlsx, inventory_columns, list_inventory
from ..health_center import connectivity_indicators, governance_status, system_health
from ..mappings import (
    apply_mapping_rules,
    delete_mapping_row,
    list_mapping_groups,
    list_mapping_rows,
    save_mapping_row,
)
from ..mb59 import enrich_inventory_pass_step, import_mb59_xlsx, mb59_status
from ..backup import (
    backup_is_due,
    default_backup_folder,
    local_backup_folder,
    mirror_local_copy,
    replace_previous_backups,
    run_backup,
)
from ..backup_restore import RestoreError, apply_restore, discard_prepared, list_backups, prepare_restore
from ..folder_picker import pick_file, pick_folder
from ..system_manual import manual_for_question, manual_index, manual_lookup, render_sections
from ..documentation import (
    current_document,
    document_info,
    publish_documentation,
    search_document,
    sync_documentation,
)
from ..drive_bridge import (
    BridgeUnavailable,
    bridge_enabled,
    bridge_root,
    bridge_status,
    load_state as load_bridge_state,
    mark_local_change,
    mark_local_deletion,
    publish_all as bridge_publish_all,
    publish_pending as bridge_publish_pending,
    record_sync_error as bridge_record_sync_error,
    resolve_root as bridge_resolve_root,
    set_root as bridge_set_root,
    sync_from_bridge,
)
from ..optimus_watch import (
    CONNECTIVITY_KEYS,
    collect_events,
    connectivity_cause,
    documentation_matches,
    health_events,
    inventory_gaps,
    latest_period,
    mapping_gaps,
    new_events,
)
from ..periods import delete_compiled_period
from ..sap_upload import (
    SAP_EXPORT_SEARCH_DAYS,
    SAP_UPLOAD_MAX_BYTES,
    export_search_folders,
    find_sap_export_candidates,
    identify_sap_export,
    install_upload,
    quick_identify_sap_export,
    is_xlsx_archive,
    landing_target,
    restore_previous,
    validate_sap_upload,
    wrong_transaction_message,
)
from ..pipeline import run_pipeline
from ..settings import Settings, load_settings
from ..reporting import generate_report_html, generate_report_pdf
from ..shared_data import publication_status, publish_period, sync_latest_publication
from ..notifications import Notifier
from ..access_sync import (
    access_status,
    mark_publisher,
    record_change as record_access_change,
    record_error as record_access_error,
    sync_access,
    verification as access_verification,
)
from ..sources.all_brazil import (
    MONTH_NAMES,
    SNAPSHOT_PATTERN,
    enrich_inventory_from_all_brazil,
    list_all_brazil_snapshots,
    query_all_brazil_snapshot,
    resolve_all_brazil,
    resolve_all_brazil_root,
)


class RunRequest(BaseModel):
    period: str = Field(pattern=r"^\d{4}-\d{2}$")


class ImportRequest(BaseModel):
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    force: bool = False


class SapRunRequest(BaseModel):
    transaction: str = Field(pattern=r"^(ZMM119|MB59)$")
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    connection_name: str = Field(default="", max_length=100)
    date_from: date | None = None
    date_to: date | None = None
    as_of: date | None = None
    variant: str = Field(default="BASE GR", max_length=40)
    fisia_only: bool = True


class SystemSettingsRequest(BaseModel):
    density: str = Field(default="compact", pattern=r"^(compact|comfortable)$")
    default_page_size: int = Field(default=50, ge=10, le=200)
    animations_enabled: bool = True
    chart_animations_enabled: bool = True
    card_animations_enabled: bool = True
    backup_enabled: bool = False
    backup_folder: str = Field(default="", max_length=500)
    backup_frequency: str = Field(default="daily", pattern=r"^(daily|weekly|monthly)$")
    backup_retention_days: int = Field(default=90, ge=7, le=3650)


class AccessUserRequest(BaseModel):
    email: str = Field(pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$", max_length=254)
    role: str = Field(default="user", pattern=r"^(admin|user)$")
    pages: list[str] = Field(default_factory=list, max_length=8)


class CorporateLoginRequest(BaseModel):
    email: str = Field(pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$", max_length=254)


class FolderPickRequest(BaseModel):
    purpose: str = Field(pattern=r"^(backup|bridge)$")
    initial: str | None = Field(default=None, max_length=500)


class InterfacePreferencesRequest(BaseModel):
    density: str | None = Field(default=None, pattern=r"^(compact|comfortable)$")
    default_page_size: int | None = Field(default=None, ge=10, le=200)
    animations_enabled: bool | None = None
    chart_animations_enabled: bool | None = None
    card_animations_enabled: bool | None = None


class NotificationPreferencesRequest(BaseModel):
    enabled: bool | None = None
    sound: bool | None = None
    sap: bool | None = None
    uploads: bool | None = None
    optimus: bool | None = None
    bridge: bool | None = None
    backup: bool | None = None
    connectivity: bool | None = None


class NotificationActivateRequest(BaseModel):
    view: str = Field(default="", pattern=r"^[a-z-]{0,30}$")
    id: int | None = None

    @field_validator("id", mode="before")
    @classmethod
    def _blank_id(cls, value: object) -> object:
        return None if value in ("", None) else value


class NotificationReadRequest(BaseModel):
    ids: list[int] = Field(default_factory=list, max_length=200)
    all: bool = False


class OptimusNotifyRequest(BaseModel):
    text: str = Field(default="", max_length=4000)
    title: str | None = Field(default=None, max_length=80)


class RestoreInspectRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1000)


class RestoreApplyRequest(BaseModel):
    token: str = Field(pattern=r"^[0-9a-f]{32}$")
    confirmation: str = Field(max_length=20)


class BridgeRootRequest(BaseModel):
    path: str | None = Field(default=None, max_length=500)
    leave_redirect: bool = True


class DeletePeriodRequest(BaseModel):
    confirmation: str = Field(pattern=r"^\d{4}-\d{2}$")

class OptimusChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(min_length=8, max_length=200)
    period: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    # Resposta a um aviso proativo específico (botão "Responder a este aviso" no chat).
    reply_to: str | None = Field(default=None, max_length=64)

class MappingRowRequest(BaseModel):
    key_value: str = Field(min_length=1, max_length=200)
    value_1: str | None = Field(default=None, max_length=500)
    value_2: str | None = Field(default=None, max_length=500)


SAP_JOBS: dict[str, dict[str, object]] = {}
SAP_JOB_LOCK = threading.Lock()
SAP_JOB_CANCEL_EVENTS: dict[str, threading.Event] = {}
SAP_JOB_ROBOTS: dict[str, SapGuiRobot] = {}
SAP_IMPORT_LOCK = threading.Lock()
SAP_CONFIRMATIONS: dict[str, dict[str, object]] = {}
SAP_CONFIRMATION_LOCK = threading.Lock()
# Ações que o Optimus prepara e só executa após o "sim" (confirm_sap). Excluir competência, excluir usuário,
# restaurar backup, trocar a pasta do Drive e o instalador ficam de fora por decisão do negócio.
AGENT_ACTION_KINDS = {
    "reprocess", "mapping", "bridge_sync", "backup", "backup_schedule", "access_save", "access_disable",
    "notification_prefs", "interface_prefs",
}
SELF_SERVICE_ACTION_KINDS = {"notification_prefs", "interface_prefs"}
AGENT_ACTION_TOOLS = {
    "settings_overview", "reprocess_enrichment", "save_mapping_rule", "sync_bridge_now", "backup_now", "set_backup_schedule",
    "save_user_access", "disable_user_access", "set_notification_preferences", "set_interface_preferences",
}
SELF_SERVICE_TOOLS = {"set_notification_preferences", "set_interface_preferences"}
# Mensagens proativas do Optimus (ex.: extração falhou, mas o SAP salvou a planilha): entregues ao chat.
OPTIMUS_OFFERS: list[dict[str, object]] = []
OPTIMUS_OFFERS_LOCK = threading.Lock()
OPTIMUS_OFFER_TTL_SECONDS = 12 * 3600
INVENTORY_RELOAD_JOBS: dict[str, dict[str, object]] = {}
INVENTORY_RELOAD_LOCK = threading.Lock()
INVENTORY_RELOAD_STAGE_PROGRESS = {
    "QUEUED": 2,
    "VALIDATING": 5,
    "IMPORTING_ZMM119": 10,
    "ZMM119_READY": 45,
    "ENRICHING_ALL_BRAZIL": 50,
    "ALL_BRAZIL_READY": 68,
    "PASS_STEP": 72,
    "PASS_STEP_READY": 88,
    "APPLYING_MAPPINGS": 92,
    "FINALIZING": 97,
    "COMPLETED": 100,
}
SAP_STAGE_PROGRESS = {
    "QUEUED": 2,
    "UPLOAD_RECEIVED": 20,
    "UPLOAD_VALIDATING": 45,
    "STARTING": 6,
    "CONNECTION_SELECTED": 14,
    "OPENING_SAP": 20,
    "OPENING_CONNECTION": 27,
    "WAITING_FOR_LOGIN": 33,
    "RUNNING": 44,
    "EXPORTING": 60,
    "EXPORTING_FILE": 76,
    "FILE_READY": 86,
    "IMPORTING": 90,
    "ENRICHING": 96,
    "COMPLETED": 100,
}
SAP_TERMINAL_STATUSES = {"COMPLETED", "FAILED", "ACTION_REQUIRED", "CANCELLED"}


DEFAULT_SYSTEM_SETTINGS: dict[str, object] = {
    "density": "compact",
    "default_page_size": 50,
    "animations_enabled": True,
    "chart_animations_enabled": True,
    "card_animations_enabled": True,
    "backup_enabled": False,
    # Vazio = automático: pasta "backups" do Drive compartilhado desta máquina,
    # ou %LOCALAPPDATA%\OpsContabil\backup quando o Drive não estiver acessível.
    "backup_folder": "",
    "backup_frequency": "daily",
    "backup_retention_days": 90,
}


INSTALLER_ARCHIVE_NAME = "INSTALAR_ESTOQUE_CONTABIL.zip"
INSTALLER_MANIFEST_NAME = "INSTALAR_ESTOQUE_CONTABIL.manifest.json"


def _installer_archive_path(settings: Settings) -> Path:
    """Prefer the published local package without requiring access to the source Drive."""
    candidates: list[Path] = []
    project_root = os.getenv("OPS_PROJECT_ROOT", "").strip()
    roots = [Path(project_root)] if project_root else []
    roots.append(settings.root)
    for root in roots:
        dist = root / "dist"
        try:
            versioned = sorted(
                dist.glob("INSTALAR_ESTOQUE_CONTABIL_*.zip"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            versioned = []
        candidates.extend(versioned)
        candidates.append(dist / INSTALLER_ARCHIVE_NAME)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return candidates[0] if candidates else settings.root / "dist" / INSTALLER_ARCHIVE_NAME


def _installer_metadata(archive: Path) -> dict[str, object]:
    manifest_path = archive.with_name(INSTALLER_MANIFEST_NAME)
    manifest: dict[str, object] = {}
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                manifest = loaded
        except (OSError, json.JSONDecodeError):
            manifest = {}
    archive_digest = ""
    if archive.is_file():
        hasher = hashlib.sha256()
        with archive.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        archive_digest = hasher.hexdigest()
    source = "runtime"
    local_runtime = (
        Path(os.environ.get("LOCALAPPDATA", Path.home()))
        / "OpsContabil"
        / "runtime"
        / "app"
    ).resolve()
    try:
        archive.relative_to(local_runtime)
    except ValueError:
        project_root = os.getenv("OPS_PROJECT_ROOT", "").strip()
        if project_root:
            try:
                archive.relative_to(Path(project_root).resolve())
                source = "project"
            except ValueError:
                pass
    return {
        "version": str(manifest.get("version") or "não versionado"),
        "built_at": manifest.get("built_at"),
        "archive_sha256": archive_digest,
        "archive_size_bytes": archive.stat().st_size if archive.is_file() else 0,
        "source": source,
        "snapshot": manifest.get("snapshot") if isinstance(manifest.get("snapshot"), dict) else {},
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="Estoque Contábil", version="0.2.0")
    ensure_auth_schema(settings)

    # ------------------------------------------------------------------
    # Lista central de acessos (Estoque_Cont/acesso): cadastros, desativações e
    # exclusões feitos por administradores valem em todas as máquinas.
    # ------------------------------------------------------------------
    # Notificações nativas do Windows desta máquina (preferências em Configurações / sino do topo).
    notifier = Notifier(settings)
    app.state.notifier = notifier

    def period_label(period: str) -> str:
        year, month = str(period).split("-")[:2]
        return f"{month}/{year}"

    def notify_job_result(category: str, view: str, tag: str, what: str, period: str, result: dict[str, object]) -> None:
        """Aviso de conclusão de uma tarefa (substitui o aviso de início, mesma etiqueta)."""
        status = str(result.get("status") or "")
        message = str(result.get("message") or "")
        if status == "COMPLETED":
            optimus_watch_trigger()  # base mudou: o vigia do Optimus verifica de novo
        titles = {
            "COMPLETED": f"{what} concluída · {period_label(period)}",
            "FAILED": f"{what} falhou · {period_label(period)}",
            "ACTION_REQUIRED": f"{what} precisa de atenção · {period_label(period)}",
            "CANCELLED": f"{what} cancelada · {period_label(period)}",
        }
        if status in titles:
            notifier.notify(category, titles[status], message or "Abra o sistema para ver os detalhes.", view=view, tag=tag,
                            silent=status == "CANCELLED", replace=True)

    access_sync_lock = threading.Lock()
    access_check_cache: dict[str, object] = {"at": 0.0, "expired": False}

    def access_sync_once() -> dict[str, object] | None:
        if not bridge_enabled(settings):
            return None
        with access_sync_lock:
            try:
                result = sync_access(settings, bridge_root(settings))
            except BridgeUnavailable as exc:
                record_access_error(settings, str(exc))
                return None
            except Exception as exc:  # noqa: BLE001 - registrado e tentado de novo no próximo ciclo
                record_access_error(settings, f"Falha ao sincronizar a lista de acessos: {exc}")
                return None
        access_check_cache["at"] = 0.0
        return result

    def access_sync_soon() -> None:
        threading.Thread(target=access_sync_once, daemon=True).start()

    def access_check_expired(user: dict[str, object]) -> bool:
        """Usuário comum bloqueado quando a máquina passa do prazo sem verificar a lista."""
        if user.get("role") == "admin" or not bridge_enabled(settings):
            return False
        if time.monotonic() - float(access_check_cache["at"]) > 30:
            access_check_cache["expired"] = bool(access_verification(settings)["expired"])
            access_check_cache["at"] = time.monotonic()
        return bool(access_check_cache["expired"])

    ACCESS_EXPIRED_MESSAGE = (
        "Não foi possível confirmar sua liberação na lista central de acessos há mais de 7 dias. "
        "Conecte o Google Drive (pasta Estoque_Cont) e a VPN e tente novamente."
    )

    access_sync_soon()

    public_api_paths = {"/api/config", "/api/auth/session", "/api/auth/login", "/api/auth/logout", "/api/notifications/activate"}

    def required_page(path: str) -> str | None:
        if path.startswith("/api/settings") or path.startswith("/api/installer"):
            return "settings"
        if path.startswith("/api/dashboard"):
            return "overview"
        if path.startswith("/api/reports"):
            return "overview"
        # A lista de competências alimenta o seletor global de todas as páginas
        # (inclusive Visão e relatórios e Optimus); não expõe linhas da base.
        if path == "/api/inventory/periods":
            return None
        if path.startswith("/api/inventory") or path.startswith("/api/sources/mb59"):
            return "inventory"
        if path.startswith("/api/mappings"):
            return "mapping"
        if path.startswith("/api/sources/all-brazil"):
            return "all-brazil"
        if path.startswith("/api/sap"):
            return "sap"
        if path.startswith("/api/runs"):
            return "governance"
        if path.startswith("/api/governance"):
            return "governance"
        if path.startswith("/api/health-center"):
            return "health"
        if path.startswith("/api/docs"):
            return "docs"
        if path.startswith("/api/agent") or path.startswith("/api/optimus"):
            return "agent"
        return None

    def csrf_is_valid(request: Request) -> bool:
        cookie = request.cookies.get(CSRF_COOKIE, "")
        header = request.headers.get("X-CSRF-Token", "")
        return bool(cookie and header and cookie == header)

    @app.middleware("http")
    async def corporate_access_guard(request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/") or path in public_api_paths or path == "/health":
            return await call_next(request)

        expected_api_token = os.getenv("OPS_API_TOKEN", "").strip()
        supplied_api_token = request.headers.get("Authorization", "")
        if expected_api_token and supplied_api_token == f"Bearer {expected_api_token}":
            user = {"email": "system@localhost", "role": "admin", "pages": []}
            request.state.api_token_authenticated = True
        else:
            user = current_user(settings, request.cookies.get(SESSION_COOKIE))
            request.state.api_token_authenticated = False
        if user is None:
            return JSONResponse(status_code=401, content={"detail": "Faça login com a conta corporativa conectada ao Windows."})
        if not request.state.api_token_authenticated and access_check_expired(user):
            return JSONResponse(status_code=401, content={"detail": ACCESS_EXPIRED_MESSAGE})

        page = required_page(path)
        if page and page != "settings" and user["role"] != "admin" and page not in user["pages"]:
            return JSONResponse(status_code=403, content={"detail": "Seu perfil não possui acesso a esta página."})
        admin_only = (
            path.startswith("/api/sap/run")
            or path.startswith("/api/sap/upload")
            or path.startswith("/api/bridge/publish")
            or path.startswith("/api/shared/publish")
            or (path.startswith("/api/reports/") and request.method != "GET")
            or (path.startswith("/api/mappings") and request.method != "GET")
            or path.startswith("/api/installer")
            or (path.startswith("/api/settings") and path not in {"/api/settings/environment"})
        )
        if admin_only and user["role"] != "admin":
            return JSONResponse(status_code=403, content={"detail": "Esta ação é exclusiva de administradores."})
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not request.state.api_token_authenticated:
            if not csrf_is_valid(request):
                return JSONResponse(status_code=403, content={"detail": "Sessão de segurança inválida. Atualize a página e tente novamente."})
        request.state.user = user
        return await call_next(request)

    def require_token(request: Request) -> None:
        if not getattr(request.state, "user", None):
            raise HTTPException(status_code=401, detail="Sessão corporativa necessária")

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return (Path(__file__).parent / "templates" / "dashboard.html").read_text(encoding="utf-8")

    @app.post("/api/notifications/activate")
    def activate_notification(payload: NotificationActivateRequest, request: Request) -> dict[str, object]:
        # Chamado pelo clique na notificação do Windows (protocolo estoquecontabil:). Fica
        # fora do login, mas exige a chave local que só o usuário do Windows consegue ler.
        tabs = notifier.activate(request.headers.get("X-Ops-Activation", ""), payload.view, payload.id)
        if tabs is None:
            raise HTTPException(status_code=403, detail="Chave de ativação inválida.")
        return {"tabs": tabs}

    @app.get("/optimus", response_class=HTMLResponse)
    def optimus_page() -> str:
        return (Path(__file__).parent / "templates" / "optimus.html").read_text(encoding="utf-8")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "application": "Estoque Contábil"}

    @app.get("/api/auth/session")
    def auth_session(request: Request, response: Response) -> dict[str, object]:
        csrf = request.cookies.get(CSRF_COOKIE) or new_csrf_token()
        response.set_cookie(
            CSRF_COOKIE,
            csrf,
            max_age=session_hours(settings) * 3600,
            httponly=False,
            samesite="strict",
            secure=os.getenv("OPS_COOKIE_SECURE", "false").lower() == "true",
        )
        user = current_user(settings, request.cookies.get(SESSION_COOKIE))
        return {
            "authenticated": user is not None,
            "user": user,
            "csrf_token": csrf,
            "allowed_domains": ["gruposbf.com.br", "fisia.com.br"],
            "identity_method": "windows_upn",
        }

    @app.post("/api/auth/login")
    def corporate_login(request: CorporateLoginRequest, http_request: Request, response: Response) -> dict[str, object]:
        if not csrf_is_valid(http_request):
            raise HTTPException(status_code=403, detail="Validação de segurança expirada. Atualize a página.")
        # Consulta a lista central antes de validar: quem acabou de ser liberado (ou
        # desativado) por um administrador em outra máquina já vale neste login.
        login_sync = threading.Thread(target=access_sync_once, daemon=True)
        login_sync.start()
        login_sync.join(timeout=8)
        try:
            user, identity_subject = authorize_windows_user(settings, request.email)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        if access_check_expired(user):
            raise HTTPException(status_code=403, detail=ACCESS_EXPIRED_MESSAGE)
        if user.get("role") == "admin" and bridge_enabled(settings):
            mark_publisher(settings)
            access_sync_soon()

        def _sync_latest_publication_background() -> None:
            try:
                sync_latest_publication(settings)
            except Exception:
                pass
            bridge_sync_once()

        threading.Thread(
            target=_sync_latest_publication_background,
            daemon=True,
        ).start()

        response.set_cookie(
            SESSION_COOKIE,
            create_session_token(settings, user["email"], identity_subject),
            max_age=session_hours(settings) * 3600,
            httponly=True,
            samesite="strict",
            secure=os.getenv("OPS_COOKIE_SECURE", "false").lower() == "true",
        )
        return {"authenticated": True, "user": user}

    @app.post("/api/auth/logout")
    def logout(http_request: Request, response: Response) -> dict[str, bool]:
        if not csrf_is_valid(http_request):
            raise HTTPException(status_code=403, detail="Validação de segurança expirada. Atualize a página.")
        response.delete_cookie(SESSION_COOKIE)
        return {"authenticated": False}

    def default_period() -> str:
        configured = os.getenv("OPS_DEFAULT_PERIOD", "").strip()
        if configured:
            return configured
        try:
            with connect(settings.path("database")) as connection:
                ensure_inventory_schema(connection)
                row = connection.execute("select max(period) from inventory_rows").fetchone()
            if row and row[0]:
                return str(row[0])
        except Exception:
            pass
        return "2026-07"

    @app.get("/api/config")
    def client_config() -> dict[str, object]:
        return {
            "n8n_chat_url": os.getenv("N8N_CHAT_URL", ""),
            "default_period": default_period(),
            "agent_provider": "Google Gemini via n8n",
            "sap_connection_name": os.getenv("SAP_CONNECTION_NAME", ""),
            "identity_method": "Conta corporativa do Windows",
        }

    @app.get("/api/inventory/columns", dependencies=[Depends(require_token)])
    def get_inventory_columns() -> list[dict[str, str]]:
        return inventory_columns()

    @app.get("/api/inventory/periods", dependencies=[Depends(require_token)])
    def get_inventory_periods() -> dict[str, object]:
        """Lista somente competências que já possuem Base de Estoque compilada."""
        with connect(settings.path("database")) as connection:
            ensure_inventory_schema(connection)
            rows = connection.execute(
                """select r.period, count(*) as rows,
                          max(i.imported_at) as imported_at
                   from inventory_rows r
                   left join inventory_imports i on i.period=r.period
                   group by r.period
                   having count(*) > 0
                   order by r.period desc"""
            ).fetchall()
        periods = []
        for period, row_count, imported_at in rows:
            year, month = map(int, str(period).split("-"))
            periods.append(
                {
                    "period": str(period),
                    "label": f"{MONTH_NAMES[month]} de {year}",
                    "rows": int(row_count),
                    "imported_at": None if imported_at is None else str(imported_at),
                }
            )
        return {"periods": periods, "default_period": periods[0]["period"] if periods else default_period()}

    @app.get("/api/inventory", dependencies=[Depends(require_token)])
    def get_inventory(
        period: str = Query(default="2026-07", pattern=r"^\d{4}-\d{2}$"),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=10, le=200),
        q: str = Query(default="", max_length=120),
        sort: str = Query(default="source_row", max_length=50),
        direction: str = Query(default="asc", pattern=r"^(asc|desc)$"),
        filters: str = Query(default="{}", max_length=4000),
        pending_joins: bool = Query(default=False),
    ) -> dict[str, object]:
        try:
            column_filters = json.loads(filters)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="Filtros de coluna inválidos") from exc
        if not isinstance(column_filters, dict):
            raise HTTPException(status_code=422, detail="Filtros de coluna devem ser um objeto")
        return list_inventory(
            settings, period, page, page_size, q, sort, direction, column_filters, pending_joins
        )

    @app.get("/api/inventory/export", dependencies=[Depends(require_token)])
    def export_inventory(
        period: str = Query(default="2026-07", pattern=r"^\d{4}-\d{2}$"),
        q: str = Query(default="", max_length=120),
        sort: str = Query(default="source_row", max_length=50),
        direction: str = Query(default="asc", pattern=r"^(asc|desc)$"),
        filters: str = Query(default="{}", max_length=4000),
        pending_joins: bool = Query(default=False),
    ):
        try:
            column_filters = json.loads(filters)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="Filtros de coluna inválidos") from exc
        if not isinstance(column_filters, dict):
            raise HTTPException(status_code=422, detail="Filtros de coluna devem ser um objeto")

        temp_dir = Path(os.getenv("TEMP") or tempfile.gettempdir()) / "OpsContabil" / "exports"
        temp_dir.mkdir(parents=True, exist_ok=True)
        target = temp_dir / f"Base_Estoque_{period}_{uuid.uuid4().hex[:8]}.xlsx"
        try:
            result = export_inventory_xlsx(
                settings,
                target,
                period,
                q,
                sort,
                direction,
                column_filters,
                pending_joins,
            )
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        filename = f"Base_Estoque_{period}.xlsx"
        headers = {"X-Exported-Rows": str(result.get("rows", 0))}
        return FileResponse(
            target,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
            background=BackgroundTask(lambda: target.unlink(missing_ok=True)),
        )

    def _detected_identity_email() -> str:
        try:
            return windows_corporate_email(settings)
        except RuntimeError:
            return ""

    # ------------------------------------------------------------------
    # Ponte de dados (Drive compartilhado) e backup programado
    # ------------------------------------------------------------------
    bridge_publish_lock = threading.Lock()
    backup_lock = threading.Lock()

    def read_preferences() -> dict[str, object]:
        values = dict(DEFAULT_SYSTEM_SETTINGS)
        with connect(settings.path("database")) as connection:
            for key, raw_value in connection.execute("select setting_key, setting_value from system_settings").fetchall():
                if key in values:
                    try:
                        values[key] = json.loads(raw_value)
                    except (json.JSONDecodeError, TypeError):
                        values[key] = raw_value
        return values

    def _state_setting(key: str) -> dict[str, object]:
        with connect(settings.path("database")) as connection:
            row = connection.execute("select setting_value from system_settings where setting_key=?", [key]).fetchone()
        try:
            value = json.loads(row[0]) if row else {}
        except (json.JSONDecodeError, TypeError):
            value = {}
        return value if isinstance(value, dict) else {}

    def _save_state_setting(key: str, value: dict[str, object]) -> None:
        with connect(settings.path("database")) as connection:
            connection.execute(
                """insert into system_settings(setting_key,setting_value,updated_at) values (?,?,current_timestamp)
                   on conflict(setting_key) do update set setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
                [key, json.dumps(value, ensure_ascii=False, default=str)],
            )

    def effective_backup_folder(preferences: dict[str, object]) -> Path:
        configured = str(preferences.get("backup_folder") or "").strip()
        if configured:
            return Path(os.path.expandvars(configured))
        root = bridge_resolve_root(settings)
        return default_backup_folder(Path(str(root["path"])) if root.get("available") else None, settings.path("database"))

    def backup_status() -> dict[str, object]:
        preferences = read_preferences()
        state = _state_setting("backup_state")
        return {
            "enabled": bool(preferences.get("backup_enabled")),
            "frequency": preferences.get("backup_frequency"),
            "retention_days": preferences.get("backup_retention_days"),
            "configured_folder": preferences.get("backup_folder") or "",
            "effective_folder": str(effective_backup_folder(preferences)),
            "last_backup_at": state.get("last_backup_at"),
            "last_backup_file": state.get("last_backup_file"),
            "last_backup_local_copy": state.get("last_backup_local_copy"),
            "last_backup_error": state.get("last_backup_error"),
        }

    def run_backup_now(force: bool = False) -> dict[str, object]:
        """Executa o backup se estiver ativo e vencido (ou imediatamente com force)."""
        with backup_lock:
            preferences = read_preferences()
            state = _state_setting("backup_state")
            last = None
            try:
                last = datetime.fromisoformat(str(state["last_backup_at"])) if state.get("last_backup_at") else None
            except ValueError:
                last = None
            if not force and (not preferences.get("backup_enabled") or not backup_is_due(last, str(preferences.get("backup_frequency")))):
                return {"status": "not_due", **backup_status()}
            folder = effective_backup_folder(preferences)
            try:
                # O novo backup é gravado e conferido; só então os anteriores deste
                # computador são apagados (cada backup substitui o anterior).
                path = run_backup(settings, folder)
                removed = replace_previous_backups(folder, path)
                # Cópia também neste computador: se a pasta do backup (Drive) se perder,
                # os backups mais recentes continuam disponíveis para restaurar.
                local_copy = mirror_local_copy(path, local_backup_folder(settings.path("database")))
                state.update(
                    last_backup_at=datetime.now().replace(microsecond=0).isoformat(),
                    last_backup_file=str(path),
                    last_backup_local_copy=str(local_copy) if local_copy else None,
                    last_backup_error=None,
                    last_removed=len(removed),
                )
                _save_state_setting("backup_state", state)
                if not force:  # o botão "Fazer backup agora" já mostra o resultado na tela
                    notifier.notify("backup", "Backup programado concluído",
                                    f"Cópia do banco gravada em {folder}. O backup anterior foi substituído.",
                                    view="settings", tag="backup", silent=True)
                return {"status": "created", "file": str(path), "removed": len(removed), **backup_status()}
            except Exception as exc:  # noqa: BLE001 - registrado para a tela de Configurações
                state.update(last_backup_error=f"{datetime.now():%d/%m/%Y %H:%M}: {exc}")
                _save_state_setting("backup_state", state)
                notifier.notify("backup", "Backup falhou", f"O backup anterior continua guardado. Motivo: {exc}",
                                view="settings", tag="backup")
                if force:
                    raise
                return {"status": "failed", "error": str(exc), **backup_status()}

    def bridge_sync_once() -> dict[str, object] | None:
        if not bridge_enabled(settings):
            return None
        try:
            # Mesma trava das importações: a ponte nunca grava junto com uma carga local.
            result = sync_from_bridge(settings, apply_lock=SAP_IMPORT_LOCK)
            applied = [item for item in result.get("applied") or [] if item.get("period")]
            if len(applied) == 1:
                item = applied[0]
                notifier.notify(
                    "bridge",
                    f"Competência {period_label(str(item['period']))} atualizada pelo Drive",
                    f"{int(item.get('rows') or 0):,} linhas recebidas de outra máquina. Os relatórios já mostram os dados novos.".replace(",", "."),
                    view="overview",
                    tag=f"bridge-{item['period']}",
                )
            elif applied:
                notifier.notify(
                    "bridge",
                    f"{len(applied)} competências atualizadas pelo Drive",
                    "Recebidas de outra máquina: " + ", ".join(period_label(str(item["period"])) for item in applied)
                    + ". Os relatórios já mostram os dados novos.",
                    view="overview",
                    tag="bridge-varias",
                )
            return result
        except BridgeUnavailable as exc:
            bridge_record_sync_error(settings, str(exc))
        except Exception as exc:  # noqa: BLE001 - registrado e tentado de novo no próximo ciclo
            bridge_record_sync_error(settings, f"Falha ao receber do Drive: {exc}")
        return None

    def bridge_publish_pending_now(published_by: str = "") -> None:
        if not bridge_enabled(settings):
            return
        with bridge_publish_lock:
            try:
                bridge_publish_pending(settings, published_by=published_by)
            except Exception:  # noqa: BLE001 - publish_pending registra o erro e mantém pendente
                pass

    def bridge_after_local_change(periods: list[str], reason: str, published_by: str = "") -> None:
        """Depois de uma atualização local concluída, publica as competências no Drive."""
        if not bridge_enabled(settings) or not periods:
            return
        try:
            mark_local_change(settings, sorted(set(periods)), reason)
        except Exception:  # noqa: BLE001 - nunca interfere na atualização local já concluída
            return
        threading.Thread(target=bridge_publish_pending_now, args=(published_by,), daemon=True).start()

    def bridge_documentation_once() -> None:
        """Documentação pela ponte: envia a versão mais nova desta máquina e recebe a do Drive."""
        if not bridge_enabled(settings):
            return
        try:
            root = bridge_root(settings)
        except BridgeUnavailable:
            return
        for step in (publish_documentation, sync_documentation):
            try:
                step(settings, root)
            except Exception:  # noqa: BLE001 - sem permissão de escrita ou arquivo em uso: tenta no próximo ciclo
                continue

    def background_worker() -> None:
        interval = int((settings.raw.get("bridge") or {}).get("sync_interval_seconds") or 120)
        next_bridge_cycle = 0.0
        while True:
            now = time.monotonic()
            if now >= next_bridge_cycle:
                next_bridge_cycle = now + interval
                bridge_publish_pending_now()
                bridge_sync_once()
                bridge_documentation_once()
                access_sync_once()
            try:
                run_backup_now()
            except Exception:  # noqa: BLE001 - erro fica registrado no estado do backup
                pass
            time.sleep(30)

    if (settings.raw.get("runtime") or {}).get("background_worker"):
        threading.Thread(target=background_worker, daemon=True, name="ops-background").start()

    def settings_payload() -> dict[str, object]:
        def visible_pages(role: str, raw_pages: str | None) -> list[str]:
            if role == "admin":
                return []
            try:
                parsed = json.loads(raw_pages or "[]")
            except (json.JSONDecodeError, TypeError):
                parsed = []
            return sanitize_role_pages("user", parsed if isinstance(parsed, list) else [])[1]

        values = dict(DEFAULT_SYSTEM_SETTINGS)
        with connect(settings.path("database")) as connection:
            for key, raw_value in connection.execute(
                "select setting_key, setting_value from system_settings"
            ).fetchall():
                if key in values:
                    try:
                        values[key] = json.loads(raw_value)
                    except (json.JSONDecodeError, TypeError):
                        values[key] = raw_value
            users = connection.execute(
                """select email, is_active, role, allowed_pages, identity_subject is not null,
                          last_login_at, created_at, updated_at, access_changed_at, access_changed_by
                   from allowed_users order by is_active desc, role, email"""
            ).fetchall()
            compiled_periods = []
            inventory_exists = connection.execute(
                "select 1 from information_schema.tables where table_schema='main' and table_name='inventory_rows'"
            ).fetchone()
            if inventory_exists:
                compiled_periods = connection.execute(
                    """select period, count(*) as rows,
                              coalesce(sum(unrestricted_quantity),0) as quantity,
                              coalesce(sum(fiscal_total_amount),0) as fiscal_value
                         from inventory_rows group by period order by period desc"""
                ).fetchall()
        return {
            "preferences": values,
            "allowed_users": [
                {
                    "email": row[0],
                    "is_active": bool(row[1]),
                    "role": "admin" if row[2] == "admin" else "user",
                    "pages": visible_pages(row[2], row[3]),
                    "identity_verified": bool(row[4]),
                    "last_login_at": row[5].isoformat() if row[5] else None,
                    "created_at": row[6].isoformat() if row[6] else None,
                    "updated_at": row[7].isoformat() if row[7] else None,
                    "bootstrap_admin": row[0] in BOOTSTRAP_ADMINS,
                    "access_changed_at": row[8],
                    "access_changed_by": row[9],
                }
                for row in users
            ],
            "access_enforcement": True,
            "identity_login_available": True,
            "detected_corporate_email": _detected_identity_email(),
            "page_catalog": page_catalog(),
            "backup": backup_status(),
            "bridge_enabled": bridge_enabled(settings),
            "access_sync": access_status(settings) if bridge_enabled(settings) else None,
            "compiled_periods": [
                {
                    "period": row[0],
                    "rows": int(row[1]),
                    "quantity": float(row[2] or 0),
                    "fiscal_value": float(row[3] or 0),
                }
                for row in compiled_periods
            ],
        }

    @app.get("/api/settings", dependencies=[Depends(require_token)])
    def get_system_settings() -> dict[str, object]:
        return settings_payload()

    @app.get("/api/settings/environment", dependencies=[Depends(require_token)])
    def environment_status() -> dict[str, object]:
        archive = _installer_archive_path(settings)
        metadata = _installer_metadata(archive)
        return {
            "application_ready": True,
            "python_ready": True,
            "dependencies_ready": True,
            "installer_available": archive.is_file(),
            "installer_name": archive.name,
            "installer_version": metadata["version"],
            "installer_built_at": metadata["built_at"],
            "installer_sha256": metadata["archive_sha256"],
            "installer_size_bytes": metadata["archive_size_bytes"],
            "installer_source": metadata["source"],
            "installer_snapshot": metadata["snapshot"],
            "message": "Ambiente local pronto para consultar as bases e relatórios.",
        }

    @app.get("/api/installer/download", dependencies=[Depends(require_token)])
    def download_installer() -> FileResponse:
        archive = _installer_archive_path(settings)
        if not archive.is_file():
            raise HTTPException(status_code=404, detail="O instalador ainda não foi publicado.")
        metadata = _installer_metadata(archive)
        headers = {
            "X-Ops-Installer-Version": str(metadata["version"]),
            "ETag": f'"{metadata["archive_sha256"]}"',
            "Cache-Control": "no-store",
        }
        return FileResponse(
            archive,
            filename=archive.name,
            media_type="application/zip",
            headers=headers,
        )

    @app.put("/api/settings", dependencies=[Depends(require_token)])
    def save_system_settings(request: SystemSettingsRequest) -> dict[str, object]:
        with connect(settings.path("database")) as connection:
            for key, value in request.model_dump().items():
                connection.execute(
                    """insert into system_settings(setting_key, setting_value, updated_at)
                       values (?, ?, current_timestamp)
                       on conflict(setting_key) do update set
                         setting_value=excluded.setting_value,
                         updated_at=excluded.updated_at""",
                    [key, json.dumps(value, ensure_ascii=False)],
                )
        return settings_payload()

    @app.post("/api/settings/access", dependencies=[Depends(require_token)])
    def add_allowed_user(request: AccessUserRequest, http_request: Request) -> dict[str, object]:
        try:
            email = normalize_corporate_email(settings, request.email)
            role, pages = sanitize_role_pages(request.role, request.pages)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if email in BOOTSTRAP_ADMINS:
            role, pages = "admin", []
        with connect(settings.path("database")) as connection:
            connection.execute(
                """insert into allowed_users(email, is_active, role, allowed_pages, updated_at)
                   values (?, true, ?, ?, current_timestamp)
                   on conflict(email) do update set
                     is_active=true,
                     role=excluded.role,
                     allowed_pages=excluded.allowed_pages,
                     updated_at=excluded.updated_at""",
                [email, role, json.dumps(pages, ensure_ascii=False)],
            )
        record_access_change(settings, email, by=http_request.state.user["email"])
        access_sync_soon()
        return settings_payload()

    @app.post("/api/settings/access/{email}/disable", dependencies=[Depends(require_token)])
    def disable_allowed_user(email: str, request: Request) -> dict[str, object]:
        normalized = email.strip().lower()
        if normalized in BOOTSTRAP_ADMINS:
            raise HTTPException(status_code=422, detail="O administrador inicial não pode ser desativado.")
        with connect(settings.path("database")) as connection:
            connection.execute(
                "update allowed_users set is_active=false, updated_at=current_timestamp where email=?",
                [normalized],
            )
        record_access_change(settings, normalized, by=request.state.user["email"])
        access_sync_soon()
        return settings_payload()

    @app.delete("/api/settings/access/{email}", dependencies=[Depends(require_token)])
    def delete_allowed_user(email: str, request: Request) -> dict[str, object]:
        if request.state.user["role"] != "admin":
            raise HTTPException(status_code=403, detail="A exclusão de acessos é exclusiva de administradores.")
        try:
            normalized = normalize_corporate_email(settings, email)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if normalized in BOOTSTRAP_ADMINS:
            raise HTTPException(status_code=422, detail="O administrador inicial não pode ser excluído.")
        if normalized == request.state.user["email"]:
            raise HTTPException(status_code=422, detail="Você não pode excluir o próprio acesso durante a sessão.")
        with connect(settings.path("database")) as connection:
            exists = connection.execute(
                "select 1 from allowed_users where email=?", [normalized]
            ).fetchone()
            if exists is None:
                raise HTTPException(status_code=404, detail="Usuário não encontrado.")
            connection.execute("delete from allowed_users where email=?", [normalized])
        record_access_change(settings, normalized, by=request.state.user["email"], deleted=True)
        access_sync_soon()
        return settings_payload()

    @app.delete("/api/settings/periods/{period}", dependencies=[Depends(require_token)])
    def delete_period(period: str, payload: DeletePeriodRequest, request: Request) -> dict[str, object]:
        if payload.confirmation != period:
            raise HTTPException(status_code=422, detail="A confirmação não corresponde à competência selecionada.")
        try:
            result = delete_compiled_period(settings, period, request.state.user["email"])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if bridge_enabled(settings):
            # A exclusão vale só para esta máquina; a ponte não traz de volta a versão excluída.
            mark_local_deletion(settings, period)
        return {"deletion": result, "settings": settings_payload()}

    @app.get("/api/bridge/status", dependencies=[Depends(require_token)])
    def get_bridge_status() -> dict[str, object]:
        return {**bridge_status(settings), "backup": backup_status()}

    @app.get("/api/bridge/revision", dependencies=[Depends(require_token)])
    def get_bridge_revision() -> dict[str, object]:
        # Consulta leve usada pela tela para recarregar quando a ponte trouxer dados novos.
        return {"data_revision": int(load_bridge_state(settings).get("data_revision", 0))}

    @app.post("/api/bridge/sync", dependencies=[Depends(require_token)])
    def post_bridge_sync() -> dict[str, object]:
        if not bridge_enabled(settings):
            raise HTTPException(status_code=409, detail="A ponte de dados pelo Drive está desativada nesta instalação.")
        result = bridge_sync_once()
        bridge_publish_pending_now()
        return {"result": result, **bridge_status(settings)}

    @app.post("/api/bridge/publish", dependencies=[Depends(require_token)])
    def post_bridge_publish(request: Request) -> dict[str, object]:
        if not bridge_enabled(settings):
            raise HTTPException(status_code=409, detail="A ponte de dados pelo Drive está desativada nesta instalação.")
        with bridge_publish_lock:
            try:
                results = bridge_publish_all(settings, published_by=request.state.user["email"])
            except BridgeUnavailable as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"results": results, **bridge_status(settings)}

    @app.put("/api/settings/bridge-root", dependencies=[Depends(require_token)])
    def put_bridge_root(payload: BridgeRootRequest, request: Request) -> dict[str, object]:
        try:
            bridge_set_root(
                settings,
                payload.path,
                leave_redirect=payload.leave_redirect,
                changed_by=request.state.user["email"],
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {**bridge_status(settings), "backup": backup_status()}

    folder_picker_lock = threading.Lock()

    @app.post("/api/settings/pick-folder", dependencies=[Depends(require_token)])
    def post_pick_folder(payload: FolderPickRequest) -> dict[str, object]:
        # Abre a janela nativa do Windows neste computador (o servidor é local).
        if not folder_picker_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Já existe uma janela de seleção de pasta aberta nesta máquina.")
        try:
            title = {
                "backup": "Selecione a pasta de backup do Estoque Contábil",
                "bridge": "Selecione a pasta compartilhada da ponte de dados",
            }[payload.purpose]
            chosen = pick_folder(title, payload.initial)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Não foi possível abrir a seleção de pasta do Windows: {exc}") from exc
        finally:
            folder_picker_lock.release()
        return {"path": chosen, "cancelled": chosen is None}

    @app.post("/api/settings/backup/run", dependencies=[Depends(require_token)])
    def post_backup_run() -> dict[str, object]:
        try:
            return run_backup_now(force=True)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Não foi possível gerar o backup: {exc}") from exc

    # ------------------------------------------------------------------
    # Restauração a partir de um backup
    # ------------------------------------------------------------------
    restore_lock = threading.Lock()
    prepared_restores: dict[str, str] = {}

    def backup_search_folders() -> list[tuple[Path, str]]:
        folders: list[tuple[Path, str]] = []
        try:
            folders.append((effective_backup_folder(read_preferences()), "Pasta de backup"))
        except Exception:  # noqa: BLE001 - pasta indisponível: segue com as demais
            pass
        folders.append((local_backup_folder(settings.path("database")), "Este computador"))
        root = bridge_resolve_root(settings) if bridge_enabled(settings) else {"available": False}
        if root.get("available"):
            backups_root = Path(str(root["path"])) / "backups"
            try:
                machines = sorted(item for item in backups_root.iterdir() if item.is_dir()) if backups_root.is_dir() else []
            except OSError:
                machines = []
            for machine in machines:
                folders.append((machine, f"Drive — {machine.name}"))
        return folders

    @app.get("/api/settings/backup/list", dependencies=[Depends(require_token)])
    def get_backup_list() -> dict[str, object]:
        return {"backups": list_backups(backup_search_folders())}

    @app.post("/api/settings/backup/pick-file", dependencies=[Depends(require_token)])
    def post_backup_pick_file() -> dict[str, object]:
        if not folder_picker_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Já existe uma janela de seleção aberta nesta máquina.")
        try:
            try:
                initial = str(effective_backup_folder(read_preferences()))
            except Exception:  # noqa: BLE001
                initial = str(local_backup_folder(settings.path("database")))
            chosen = pick_file("Selecione o backup do Estoque Contábil (.zip)", initial)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Não foi possível abrir a seleção de arquivo do Windows: {exc}") from exc
        finally:
            folder_picker_lock.release()
        return {"path": chosen, "cancelled": chosen is None}

    @app.post("/api/settings/backup/inspect", dependencies=[Depends(require_token)])
    def post_backup_inspect(payload: RestoreInspectRequest) -> dict[str, object]:
        archive = Path(os.path.expandvars(payload.path.strip()))
        if archive.suffix.lower() != ".zip":
            raise HTTPException(status_code=422, detail="Escolha um arquivo de backup .zip do Estoque Contábil.")
        if not restore_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Já existe uma restauração em andamento nesta máquina.")
        try:
            summary = prepare_restore(settings.path("database"), archive)
        except RestoreError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            restore_lock.release()
        prepared_restores.clear()
        prepared_restores[str(summary["token"])] = str(archive)
        return summary

    @app.post("/api/settings/backup/restore", dependencies=[Depends(require_token)])
    def post_backup_restore(payload: RestoreApplyRequest, request: Request) -> dict[str, object]:
        if payload.confirmation.strip().upper() != "RESTAURAR":
            raise HTTPException(status_code=422, detail="Digite RESTAURAR para confirmar a restauração.")
        source = prepared_restores.get(payload.token)
        if source is None:
            raise HTTPException(status_code=422, detail="Confira o backup novamente antes de restaurar.")
        if not restore_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Já existe uma restauração em andamento nesta máquina.")
        try:
            if not SAP_IMPORT_LOCK.acquire(blocking=False):
                raise HTTPException(
                    status_code=409,
                    detail="Há uma importação de base em andamento. Aguarde terminar e restaure novamente.",
                )
            try:
                # Nenhum envio ao Drive nem backup programado roda durante a troca do banco.
                if not bridge_publish_lock.acquire(timeout=120):
                    raise HTTPException(status_code=409, detail="Um envio ao Drive está em andamento. Tente em instantes.")
                try:
                    if not backup_lock.acquire(timeout=300):
                        raise HTTPException(status_code=409, detail="Um backup está em andamento. Tente em instantes.")
                    try:
                        result = apply_restore(
                            settings.path("database"),
                            payload.token,
                            restored_by=request.state.user["email"],
                            source_file=source,
                        )
                    except RestoreError as exc:
                        raise HTTPException(status_code=422, detail=str(exc)) from exc
                    finally:
                        backup_lock.release()
                finally:
                    bridge_publish_lock.release()
            finally:
                SAP_IMPORT_LOCK.release()
        finally:
            restore_lock.release()
        prepared_restores.clear()
        notifier.notify("backup", "Restauração concluída",
                        "Competências restauradas: " + (", ".join(period_label(p) for p in result.get("periods") or []) or "nenhuma")
                        + ". O banco anterior ficou guardado como cópia.", view="settings", tag="restore")
        if bridge_enabled(settings):
            # Recebe do Drive o que lá estiver mais novo e reenvia o que o Drive não tiver.
            def after_restore(email: str = request.state.user["email"]) -> None:
                bridge_sync_once()
                bridge_publish_pending_now(email)

            threading.Thread(target=after_restore, daemon=True).start()
        return result

    @app.delete("/api/settings/backup/inspect/{token}", dependencies=[Depends(require_token)])
    def delete_backup_inspection(token: str) -> dict[str, object]:
        if token in prepared_restores:
            prepared_restores.pop(token, None)
            discard_prepared(settings.path("database"), token)
        return {"discarded": True}

    @app.get("/api/shared/status", dependencies=[Depends(require_token)])
    def get_shared_status() -> dict[str, object]:
        return publication_status(settings)

    @app.post("/api/shared/sync", dependencies=[Depends(require_token)])
    def sync_shared_data() -> dict[str, object]:
        try:
            return sync_latest_publication(settings, force=True)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/shared/publish", dependencies=[Depends(require_token)])
    def publish_shared_data(request: RunRequest, http_request: Request) -> dict[str, object]:
        try:
            return publish_period(settings, request.period, http_request.state.user["email"])
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/reports/pdf", dependencies=[Depends(require_token)])
    def create_report_pdf(request: RunRequest, http_request: Request) -> FileResponse:
        try:
            path = generate_report_pdf(settings, request.period, user_email=http_request.state.user["email"])
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return FileResponse(path, filename=path.name, media_type="application/pdf")

    @app.get("/api/reports/pdf/download", dependencies=[Depends(require_token)])
    def download_report_pdf(
        request: Request,
        period: str = Query(pattern=r"^\d{4}-\d{2}$"),
    ) -> FileResponse:
        """Gera o PDF sob demanda e o entrega sem expor caminho local."""
        try:
            path = generate_report_pdf(settings, period, user_email=request.state.user["email"])
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return FileResponse(path, filename=path.name, media_type="application/pdf")

    @app.get("/api/reports/html/download", dependencies=[Depends(require_token)])
    def download_report_html(
        request: Request,
        period: str = Query(pattern=r"^\d{4}-\d{2}$"),
    ) -> FileResponse:
        if request.state.user["role"] != "admin":
            raise HTTPException(status_code=403, detail="O compartilhamento HTML é exclusivo de administradores.")
        try:
            path = generate_report_html(settings, period, user_email=request.state.user["email"])
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return FileResponse(path, filename=path.name, media_type="text/html; charset=utf-8")

    def executive_presentation_payload(period: str) -> dict[str, object]:
        summary = dashboard_summary(settings, period)
        return {
            "artifact": "executive_presentation",
            "period": period,
            "title": f"Posição Contábil do Estoque — {period}",
            "source": "Base de Estoque compilada no Ops Contábil",
            "kpis": {
                "fiscal_value": summary["fiscal_value"],
                "quantity": summary["quantity"],
                "materials": summary["materials"],
                "pmm": summary["pmm"],
                "all_brazil_coverage": summary["all_brazil_coverage"],
            },
            "comparison": {
                "previous_period": summary["previous_period"],
                "pmm": summary["pmm_comparison"],
                "division_variance": summary["division_variance"],
            },
            "visuals": {
                "monthly_trend": summary["trend"],
                "division": summary["division"],
                "locations": summary["locations"],
                "origins": summary["origins"],
                "lifecycle_aging": summary["lifecycle_aging"],
                "aging_for_season": summary["aging_for_season"],
                "division_aging": summary["division_aging"],
                "pmm_breakdowns": summary["pmm_breakdowns"],
                "cost_composition": summary["cost_composition"],
            },
            "slide_outline": [
                "Capa e competência",
                "Resumo executivo e KPIs",
                "Evolução mensal da posição de estoque",
                "PMM analítico por período, divisão, centro, local e season",
                "Composição do custo fiscal",
                "Mix e variação por categoria",
                "Aging, lifecycle e season",
                "Concentração por local, centro e origem",
                "Controles, fontes e próximos pontos de atenção",
            ],
            "n8n_handoff": {
                "ready": True,
                "recommended_nodes": ["Google Slides", "Google Drive", "PDF"],
                "instruction": "Usar somente os dados deste payload; não estimar indicadores ausentes.",
            },
        }

    @app.get("/api/reports/presentation/context", dependencies=[Depends(require_token)])
    def presentation_context(
        period: str = Query(pattern=r"^\d{4}-\d{2}$"),
    ) -> dict[str, object]:
        return executive_presentation_payload(period)

    @app.get("/api/dashboard/summary", dependencies=[Depends(require_token)])
    def get_dashboard_summary(
        period: str = Query(default="2026-07", pattern=r"^\d{4}-\d{2}$")
    ) -> dict[str, object]:
        return dashboard_summary(settings, period)

    @app.get("/api/governance/status", dependencies=[Depends(require_token)])
    def get_governance_status(
        period: str = Query(pattern=r"^\d{4}-\d{2}$"),
    ) -> dict[str, object]:
        try:
            return governance_status(settings, period)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/health-center", dependencies=[Depends(require_token)])
    def get_health_center(
        request: Request,
        period: str = Query(pattern=r"^\d{4}-\d{2}$"),
    ) -> dict[str, object]:
        with SAP_JOB_LOCK:
            jobs = sorted(
                (dict(job) for job in SAP_JOBS.values()),
                key=lambda job: str(job.get("created_at") or ""),
                reverse=True,
            )[:4]
        return system_health(
            settings,
            period,
            request.state.user,
            os.getenv("N8N_CHAT_URL", "").strip(),
            jobs,
            backup=backup_status() if request.state.user.get("role") == "admin" else None,
        )

    # Notificações: preferências desta máquina (qualquer perfil logado ajusta as próprias).
    @app.get("/api/notifications/preferences", dependencies=[Depends(require_token)])
    def get_notification_preferences() -> dict[str, object]:
        return notifier.status()

    @app.put("/api/notifications/preferences", dependencies=[Depends(require_token)])
    def put_notification_preferences(payload: NotificationPreferencesRequest) -> dict[str, object]:
        notifier.save_preferences(payload.model_dump(exclude_none=True))
        return notifier.status()

    # Eventos em tempo real para as abas abertas do sistema (contador do sino e entrega
    # das notificações pelo navegador, para o clique voltar à mesma aba).
    @app.get("/api/notifications/stream", dependencies=[Depends(require_token)])
    async def notification_stream(request: Request, can_notify: bool = False) -> StreamingResponse:
        import asyncio

        client_id, events_queue = notifier.hub.connect(asyncio.get_running_loop(), can_notify)

        async def events():
            try:
                yield "retry: 5000\n\n"
                while not await request.is_disconnected():
                    try:
                        item = await asyncio.wait_for(events_queue.get(), timeout=10)
                        yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": ativo\n\n"
            finally:
                notifier.hub.disconnect(client_id)

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # Interface e experiência: disponível a qualquer perfil (o perfil Usuário vê em
    # Configurações apenas esta seção e Notificações). Não expõe dados de administração.
    INTERFACE_KEYS = ("density", "default_page_size", "animations_enabled", "chart_animations_enabled", "card_animations_enabled")

    @app.get("/api/preferences/interface", dependencies=[Depends(require_token)])
    def get_interface_preferences() -> dict[str, object]:
        values = read_preferences()
        return {key: values.get(key, DEFAULT_SYSTEM_SETTINGS.get(key)) for key in INTERFACE_KEYS}

    @app.put("/api/preferences/interface", dependencies=[Depends(require_token)])
    def put_interface_preferences(payload: InterfacePreferencesRequest) -> dict[str, object]:
        with connect(settings.path("database")) as connection:
            for key, value in payload.model_dump(exclude_none=True).items():
                connection.execute(
                    """insert into system_settings(setting_key, setting_value, updated_at) values (?, ?, current_timestamp)
                       on conflict(setting_key) do update set setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
                    [key, json.dumps(value, ensure_ascii=False)],
                )
        return get_interface_preferences()

    # Caixa de notificações (sino): histórico do que já foi enviado nesta máquina.
    @app.get("/api/notifications", dependencies=[Depends(require_token)])
    def get_notifications(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, object]:
        return notifier.history(limit)

    @app.post("/api/notifications/read", dependencies=[Depends(require_token)])
    def post_notifications_read(payload: NotificationReadRequest) -> dict[str, object]:
        return notifier.mark_read(None if payload.all else payload.ids)

    @app.delete("/api/notifications", dependencies=[Depends(require_token)])
    def delete_notifications() -> dict[str, object]:
        return notifier.clear()

    @app.post("/api/notifications/test", dependencies=[Depends(require_token)])
    def post_notification_test() -> dict[str, object]:
        notifier.notify("test", "Notificações ativas", "É assim que o Estoque Contábil avisa quando uma tarefa termina.",
                        view="", tag="teste", force=True)
        return {"sent": True, **notifier.status()}

    @app.post("/api/optimus/notify", dependencies=[Depends(require_token)])
    def post_optimus_notification(payload: OptimusNotifyRequest) -> dict[str, object]:
        # Chamado pela tela do chat só quando o usuário está em outra janela ou página.
        preview = " ".join(payload.text.split())
        sent = notifier.notify("optimus", payload.title or "Optimus respondeu",
                               (preview[:180] + "…") if len(preview) > 180 else (preview or "A resposta está pronta no chat."),
                               view="agent", tag="optimus")
        return {"sent": sent}

    @app.get("/api/docs/info", dependencies=[Depends(require_token)])
    def get_documentation_info() -> dict[str, object]:
        return document_info(settings)

    @app.get("/api/docs/pdf", dependencies=[Depends(require_token)])
    def get_documentation_pdf(download: bool = False) -> FileResponse:
        document = current_document(settings)
        if document is None:
            raise HTTPException(status_code=404, detail="A documentação ainda não foi publicada nesta instalação.")
        return FileResponse(
            document.pdf,
            media_type="application/pdf",
            filename=document.pdf.name,
            content_disposition_type="attachment" if download else "inline",
            headers={"Cache-Control": "no-cache", "ETag": f'"{document.index.get("pdf_sha256", "")}"'},
        )

    @app.get("/api/docs/search", dependencies=[Depends(require_token)])
    def get_documentation_search(q: str = Query(default="", max_length=200)) -> dict[str, object]:
        return search_document(settings, q)

    def _perform_inventory_import(
        request: ImportRequest,
        progress_callback=None,
    ) -> dict[str, object]:
        def progress(status: str, message: str) -> None:
            if progress_callback is not None:
                progress_callback(
                    status,
                    INVENTORY_RELOAD_STAGE_PROGRESS.get(status, 0),
                    message,
                )

        def ranged_progress(status: str, start: int, end: int):
            if progress_callback is None:
                return None
            span = max(0, end - start)
            return lambda fraction, message: progress_callback(
                status,
                min(end, start + round(max(0.0, min(1.0, float(fraction))) * span)),
                message,
            )

        progress("VALIDATING", "Validando a exportação ZMM119 da competência.")
        target = (
            settings.path("landing")
            / "zmm119"
            / request.period
            / f"ZMM119_{request.period}.xlsx"
        )
        if not target.is_file():
            raise FileNotFoundError(
                f"A extração ZMM119 da competência {request.period} ainda não está disponível. "
                "Execute a ZMM119 antes de recarregar a Base de Estoque."
            )

        progress("IMPORTING_ZMM119", "Importando as linhas da ZMM119 para a Base de Estoque.")
        loaded = import_zmm119_xlsx(
            settings,
            request.period,
            target,
            progress_callback=ranged_progress("IMPORTING_ZMM119", 10, 44),
        )
        progress("ZMM119_READY", f"ZMM119 importada: {loaded.get('rows', 0)} linhas.")

        year, month = map(int, request.period.split("-"))
        effective_as_of = date(year, month, calendar.monthrange(year, month)[1])

        progress(
            "ENRICHING_ALL_BRAZIL",
            "Aplicando somente o último arquivo All Brazil válido do mês.",
        )
        enriched = enrich_inventory_from_all_brazil(
            settings,
            request.period,
            effective_as_of,
            progress_callback=ranged_progress("ENRICHING_ALL_BRAZIL", 50, 67),
        )
        progress(
            "ALL_BRAZIL_READY",
            f"All Brazil aplicado. Cobertura: {enriched.get('coverage_pct', 0)}%.",
        )

        progress(
            "PASS_STEP",
            "Aplicando PASSO A PASSO: MB59 por CE & MAT, posição anterior e All Brazil por Material.",
        )
        pass_step = enrich_inventory_pass_step(
            settings,
            request.period,
            effective_as_of,
            progress_callback=ranged_progress("PASS_STEP", 72, 87),
        )
        progress("PASS_STEP_READY", "PASSO A PASSO concluído.")

        progress("APPLYING_MAPPINGS", "Recalculando fórmulas, Aging, Season e regras de Mapping.")
        apply_mapping_rules(settings, request.period, effective_as_of)
        progress("FINALIZING", "Finalizando a Base de Estoque e preparando a atualização da tela.")

        return {
            **loaded,
            "source": "ZMM119",
            "source_path": str(target),
            "all_brazil_coverage_pct": enriched.get("coverage_pct"),
            "all_brazil_snapshot": enriched.get("snapshot"),
            "pass_step_status": pass_step.get("status"),
            "pass_step": pass_step,
        }

    def _perform_inventory_enrichment(
        request: ImportRequest,
        progress_callback=None,
    ) -> dict[str, object]:
        """Reaplica joins e cálculos sem reler ou substituir a ZMM119 já carregada."""
        def report(status: str, progress: int, message: str) -> None:
            if progress_callback is not None:
                progress_callback(status, progress, message)

        def ranged_progress(status: str, start: int, end: int):
            if progress_callback is None:
                return None
            span = max(0, end - start)
            return lambda fraction, message: progress_callback(
                status,
                min(end, start + round(max(0.0, min(1.0, float(fraction))) * span)),
                message,
            )

        with connect(settings.path("database")) as connection:
            ensure_inventory_schema(connection)
            count = int(
                connection.execute(
                    "select count(*) from inventory_rows where period=?", [request.period]
                ).fetchone()[0]
            )
        if count <= 0:
            raise ValueError(
                f"A competência {request.period} ainda não possui Base de Estoque carregada."
            )

        year, month = map(int, request.period.split("-"))
        effective_as_of = date(year, month, calendar.monthrange(year, month)[1])

        report("ENRICHING_ALL_BRAZIL", 5, "Reaplicando o último All Brazil por Material e fallback por Estilo-Cor.")
        enriched = enrich_inventory_from_all_brazil(
            settings,
            request.period,
            effective_as_of,
            progress_callback=ranged_progress("ENRICHING_ALL_BRAZIL", 5, 52),
        )
        report(
            "ALL_BRAZIL_READY",
            55,
            f"All Brazil reaplicado. Cobertura: {enriched.get('coverage_pct', 0)}%.",
        )

        report(
            "PASS_STEP",
            58,
            "Reaplicando PASSO A PASSO: MB59 por CE & MAT, posição anterior e All Brazil por Material/Estilo-Cor.",
        )
        pass_step = enrich_inventory_pass_step(
            settings,
            request.period,
            effective_as_of,
            progress_callback=ranged_progress("PASS_STEP", 58, 87),
        )
        report("PASS_STEP_READY", 89, "PASSO A PASSO reaplicado.")

        report("APPLYING_MAPPINGS", 92, "Recalculando Aging, Season e regras de Mapping.")
        apply_mapping_rules(settings, request.period, effective_as_of)
        report("FINALIZING", 98, "Finalizando o reprocessamento dos joins.")

        return {
            "rows": count,
            "period": request.period,
            "all_brazil_coverage_pct": enriched.get("coverage_pct"),
            "all_brazil_snapshot": enriched.get("snapshot"),
            "pass_step_status": pass_step.get("status"),
            "pass_step": pass_step,
            "reloaded_zmm119": False,
        }

    @app.post("/api/inventory/import", dependencies=[Depends(require_token)])
    def import_inventory(request: ImportRequest) -> dict[str, object]:
        try:
            return _perform_inventory_import(request)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    def _run_inventory_reload_job(job_id: str, request: ImportRequest) -> None:
        started = time.time()

        def report(status: str, progress: int, message: str) -> None:
            with INVENTORY_RELOAD_LOCK:
                job = INVENTORY_RELOAD_JOBS.get(job_id)
                if job is None:
                    return
                current = int(job.get("progress", 0) or 0)
                job.update(
                    status=status,
                    progress=max(current, int(progress)),
                    message=message,
                    updated_at=datetime.now().isoformat(timespec="seconds"),
                )

        def notify_reload(status: str, message: str) -> None:
            notify_job_result("uploads", "inventory", f"reload-{job_id}", "Recarga da Base de Estoque", request.period,
                              {"status": status, "message": message})

        try:
            result = _perform_inventory_import(request, report)
            notify_reload("COMPLETED", f"Base de Estoque atualizada: {int(result.get('rows', 0) or 0):,} linhas.".replace(",", "."))
            bridge_after_local_change([request.period], "Recarga da Base de Estoque")
            with INVENTORY_RELOAD_LOCK:
                job = INVENTORY_RELOAD_JOBS.get(job_id)
                if job is not None:
                    job.update(
                        status="COMPLETED",
                        progress=100,
                        message=(
                            f"Base de Estoque atualizada: {result.get('rows', 0)} linhas. "
                            f"All Brazil: {result.get('all_brazil_snapshot') or 'arquivo selecionado'}."
                        ),
                        result=result,
                        finished_at=datetime.now().isoformat(timespec="seconds"),
                        duration_seconds=round(time.time() - started, 1),
                    )
        except Exception as exc:
            with INVENTORY_RELOAD_LOCK:
                job = INVENTORY_RELOAD_JOBS.get(job_id)
                if job is not None:
                    job.update(
                        status="FAILED",
                        message=str(exc),
                        finished_at=datetime.now().isoformat(timespec="seconds"),
                        duration_seconds=round(time.time() - started, 1),
                    )
            notify_reload("FAILED", str(exc))

    @app.post("/api/inventory/import/start", dependencies=[Depends(require_token)])
    def start_inventory_import(request: ImportRequest) -> dict[str, object]:
        with INVENTORY_RELOAD_LOCK:
            active = next(
                (
                    dict(job)
                    for job in INVENTORY_RELOAD_JOBS.values()
                    if job.get("status") not in {"COMPLETED", "FAILED"}
                ),
                None,
            )
            if active is not None:
                return active

            job_id = str(uuid.uuid4())
            job = {
                "job_id": job_id,
                "period": request.period,
                "status": "QUEUED",
                "progress": INVENTORY_RELOAD_STAGE_PROGRESS["QUEUED"],
                "message": "Recarga da Base de Estoque adicionada à fila.",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            INVENTORY_RELOAD_JOBS.clear()
            INVENTORY_RELOAD_JOBS[job_id] = job

        threading.Thread(
            target=_run_inventory_reload_job,
            args=(job_id, request),
            daemon=True,
        ).start()
        return dict(job)

    def _run_inventory_enrichment_job(job_id: str, request: ImportRequest) -> None:
        started = time.time()

        def report(status: str, progress: int, message: str) -> None:
            with INVENTORY_RELOAD_LOCK:
                job = INVENTORY_RELOAD_JOBS.get(job_id)
                if job is None:
                    return
                current = int(job.get("progress", 0) or 0)
                job.update(
                    status=status,
                    progress=max(current, int(progress)),
                    message=message,
                    updated_at=datetime.now().isoformat(timespec="seconds"),
                )

        def notify_enrichment(status: str, message: str) -> None:
            notify_job_result("uploads", "inventory", f"joins-{job_id}", "Reprocessamento de joins", request.period,
                              {"status": status, "message": message})

        try:
            result = _perform_inventory_enrichment(request, report)
            notify_enrichment("COMPLETED", f"Joins reaplicados em {int(result.get('rows', 0) or 0):,} linhas.".replace(",", "."))
            bridge_after_local_change([request.period], "Reprocessamento de joins")
            with INVENTORY_RELOAD_LOCK:
                job = INVENTORY_RELOAD_JOBS.get(job_id)
                if job is not None:
                    job.update(
                        status="COMPLETED",
                        progress=100,
                        message=(
                            f"Joins reprocessados em {result.get('rows', 0)} linhas sem reler a ZMM119. "
                            f"All Brazil: {result.get('all_brazil_snapshot') or 'arquivo selecionado'}."
                        ),
                        result=result,
                        finished_at=datetime.now().isoformat(timespec="seconds"),
                        duration_seconds=round(time.time() - started, 1),
                    )
        except Exception as exc:
            with INVENTORY_RELOAD_LOCK:
                job = INVENTORY_RELOAD_JOBS.get(job_id)
                if job is not None:
                    job.update(
                        status="FAILED",
                        message=str(exc),
                        finished_at=datetime.now().isoformat(timespec="seconds"),
                        duration_seconds=round(time.time() - started, 1),
                    )
            notify_enrichment("FAILED", str(exc))

    @app.post("/api/inventory/enrichment/start", dependencies=[Depends(require_token)])
    def start_inventory_enrichment(request: ImportRequest) -> dict[str, object]:
        with INVENTORY_RELOAD_LOCK:
            active = next(
                (
                    dict(job)
                    for job in INVENTORY_RELOAD_JOBS.values()
                    if job.get("status") not in {"COMPLETED", "FAILED"}
                ),
                None,
            )
            if active is not None:
                return active

            job_id = str(uuid.uuid4())
            job = {
                "job_id": job_id,
                "period": request.period,
                "job_type": "ENRICHMENT_ONLY",
                "status": "QUEUED",
                "progress": 2,
                "message": "Reprocessamento dos joins adicionado à fila. A ZMM119 já carregada será preservada.",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            INVENTORY_RELOAD_JOBS.clear()
            INVENTORY_RELOAD_JOBS[job_id] = job

        threading.Thread(
            target=_run_inventory_enrichment_job,
            args=(job_id, request),
            daemon=True,
        ).start()
        return dict(job)

    @app.get("/api/inventory/import/jobs/{job_id}", dependencies=[Depends(require_token)])
    def inventory_import_job(job_id: str) -> dict[str, object]:
        with INVENTORY_RELOAD_LOCK:
            job = INVENTORY_RELOAD_JOBS.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Recarga da Base de Estoque não encontrada.")
            return dict(job)

    @app.get("/api/mappings", dependencies=[Depends(require_token)])
    def mapping_groups() -> list[dict[str, object]]:
        return list_mapping_groups(settings)

    @app.get("/api/mappings/{group_key}", dependencies=[Depends(require_token)])
    def mapping_rows(group_key: str) -> dict[str, object]:
        try:
            return list_mapping_rows(settings, group_key)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    def refresh_mapping_dependents() -> dict[str, object]:
        with connect(settings.path("database")) as connection:
            ensure_inventory_schema(connection)
            period_rows = connection.execute(
                "select period, count(*) from inventory_rows group by period order by period"
            ).fetchall()
        for period, _row_count in period_rows:
            apply_mapping_rules(settings, period)
        optimus_watch_trigger()  # Mapping mudou: o vigia do Optimus verifica de novo
        return {
            "periods": [str(row[0]) for row in period_rows],
            "period_count": len(period_rows),
            "row_count": sum(int(row[1] or 0) for row in period_rows),
        }

    @app.post("/api/mappings/{group_key}", dependencies=[Depends(require_token)])
    def create_mapping_row(group_key: str, request: MappingRowRequest) -> dict[str, object]:
        try:
            result = save_mapping_row(settings, group_key, **request.model_dump())
            result["recalculated"] = refresh_mapping_dependents()
            bridge_after_local_change(list(result["recalculated"].get("periods") or []), "Alteração de Mapping")
            return result
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.put("/api/mappings/{group_key}/{mapping_id}", dependencies=[Depends(require_token)])
    def update_mapping_row(group_key: str, mapping_id: int, request: MappingRowRequest) -> dict[str, object]:
        try:
            result = save_mapping_row(settings, group_key, mapping_id=mapping_id, **request.model_dump())
            result["recalculated"] = refresh_mapping_dependents()
            bridge_after_local_change(list(result["recalculated"].get("periods") or []), "Alteração de Mapping")
            return result
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.delete("/api/mappings/{group_key}/{mapping_id}", dependencies=[Depends(require_token)])
    def remove_mapping_row(group_key: str, mapping_id: int) -> dict[str, str]:
        try:
            delete_mapping_row(settings, group_key, mapping_id)
            recalculated = refresh_mapping_dependents()
            bridge_after_local_change(list(recalculated.get("periods") or []), "Alteração de Mapping")
            return {"status": "deleted", "recalculated": recalculated}
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/sources/all-brazil", dependencies=[Depends(require_token)])
    def all_brazil_source(as_of: date = Query()) -> dict[str, object]:
        try:
            snapshot = resolve_all_brazil(settings, as_of)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "period": snapshot.period,
            "snapshot_date": snapshot.snapshot_date.isoformat(),
            "file_name": snapshot.path.name,
            "source_path": str(snapshot.path),
            "snapshot_count": 1,
            "files": [snapshot.path.name],
            "selection_rule": "latest_snapshot_on_or_before_as_of_only",
            "join_key": "Material exato; se ausente, Estilo-Cor (10 caracteres) = Material Nbr do All Brazil; nunca por Centro",
        }

    @app.get("/api/sources/mb59/status", dependencies=[Depends(require_token)])
    def get_mb59_status(
        period: str = Query(pattern=r"^\d{4}-\d{2}$"),
    ) -> dict[str, object]:
        return mb59_status(settings, period)

    def all_brazil_month_folder(year: int, month: int) -> Path:
        root = resolve_all_brazil_root(settings)
        return root / str(year) / f"{month:02d}. {MONTH_NAMES[month]}"

    @app.get("/api/sources/all-brazil/catalog", dependencies=[Depends(require_token)])
    def all_brazil_catalog() -> dict[str, object]:
        config = settings.raw["sources"]["all_brazil_materials"]
        root = resolve_all_brazil_root(settings)
        drive_map_path = settings.root / "config" / "all_brazil_drive_folders.json"
        try:
            drive_map = json.loads(drive_map_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            drive_map = {"root_url": f"https://drive.google.com/drive/folders/{config['drive_id']}", "years": {}}
        years: list[dict[str, object]] = []
        for year_text, mapped_months in sorted(drive_map.get("years", {}).items(), reverse=True):
            year = int(year_text)
            months: list[dict[str, object]] = []
            for month_text, drive_url in sorted(mapped_months.items(), reverse=True):
                month = int(month_text)
                folder = all_brazil_month_folder(year, month)
                files: list[dict[str, object]] = []
                try:
                    if not folder.is_dir():
                        raise FileNotFoundError
                    candidates = sorted(
                        (
                            path
                            for path in folder.iterdir()
                            if path.is_file() and SNAPSHOT_PATTERN.match(path.name)
                        ),
                        key=lambda path: path.name.casefold(),
                        reverse=True,
                    )
                    for path in candidates:
                        match = SNAPSHOT_PATTERN.match(path.name)
                        files.append(
                            {
                                "name": path.name,
                                "snapshot_date": (
                                    f"{year}-{int(match.group('month')):02d}-{int(match.group('day')):02d}"
                                    if match
                                    else None
                                ),
                            }
                        )
                except OSError:
                    files = []
                months.append(
                    {
                        "month": month,
                        "label": f"{month:02d}. {MONTH_NAMES[month]}",
                        "path": str(folder),
                        "drive_url": drive_url,
                        "files": files,
                    }
                )
            if months:
                years.append({"year": year, "months": months})
        return {"root": str(root), "root_url": drive_map.get("root_url"), "years": years}

    # Importação e enriquecimento compartilhados pela extração automática (robô)
    # e pela carga manual (upload). Devem ser chamados sob SAP_IMPORT_LOCK.
    def import_sap_landing(transaction: str, period: str, target: Path, report_status) -> dict[str, object]:
        if transaction == "ZMM119":
            report_status("IMPORTING", "Importando a base ZMM119 para o Estoque Contábil.")
            return import_zmm119_xlsx(settings, period, target)
        report_status("IMPORTING", "Importando a Base GR da MB59 para as consultas por CE & MAT.")
        return import_mb59_xlsx(settings, period, target)

    def enrich_sap_landing(
        transaction: str,
        period: str,
        target: Path,
        as_of: date | None,
        loaded: dict[str, object],
        report_status,
        ensure_not_cancelled,
        uploaded: bool = False,
    ) -> dict[str, object]:
        year, month = map(int, period.split("-"))
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        if transaction == "ZMM119":
            effective_as_of = as_of or month_end
            report_status("ENRICHING", "Aplicando All Brazil, PASSO A PASSO e os cálculos contábeis.")
            enriched = enrich_inventory_from_all_brazil(settings, period, effective_as_of)
            pass_step = enrich_inventory_pass_step(settings, period, effective_as_of)
            apply_mapping_rules(settings, period, effective_as_of)
            ensure_not_cancelled()
            origin = " por upload" if uploaded else ""
            message = (
                f"ZMM119 carregada{origin} ({loaded['rows']} linhas) e enriquecida "
                f"pelo All Brazil ({enriched['coverage_pct']}%)."
                f" {pass_step.get('message', 'PASSO A PASSO processado.')}"
            )
        else:
            report_status("ENRICHING", "Aplicando a prioridade PASSO A PASSO à Base de Estoque.")
            pass_step = enrich_inventory_pass_step(settings, period, month_end)
            if pass_step.get("status") == "enriched":
                apply_mapping_rules(settings, period, month_end)
            ensure_not_cancelled()
            verb = "carregada por upload" if uploaded else "extraída"
            message = (
                f"MB59 {verb} e indexada ({loaded['lookup_rows']} chaves CE & MAT). "
                f"{pass_step.get('message', '')}"
            )
        return {
            "status": "COMPLETED",
            "progress": 100,
            "message": message,
            "target_path": str(target),
            "pass_step": pass_step,
        }

    def run_sap_job(job_id: str, request: SapRunRequest) -> None:
        started = time.time()
        with SAP_JOB_LOCK:
            cancel_event = SAP_JOB_CANCEL_EVENTS.setdefault(job_id, threading.Event())
            SAP_JOBS[job_id].update(
                status="STARTING",
                message="Localizando o SAP GUI nesta máquina.",
                progress=SAP_STAGE_PROGRESS["STARTING"],
                started_at=datetime.now().isoformat(timespec="seconds"),
            )
        notifier.notify(
            "sap",
            f"Extração {request.transaction} iniciada · {period_label(request.period)}",
            "O robô está conduzindo o SAP nesta máquina. Você será avisado quando a base estiver carregada no sistema.",
            view="sap",
            tag=f"sap-{job_id}",
            silent=True,
            replace=True,
        )

        def report_status(status: str, message: str) -> None:
            with SAP_JOB_LOCK:
                current = int(SAP_JOBS[job_id].get("progress", 0))
                SAP_JOBS[job_id].update(
                    status=status,
                    message=message,
                    progress=max(current, SAP_STAGE_PROGRESS.get(status, current)),
                )

        def ensure_not_cancelled() -> None:
            if cancel_event.is_set():
                raise SapGuiCancelled("Execução SAP cancelada pelo usuário.")

        try:
            ensure_not_cancelled()
            timeout = int(settings.raw["runtime"]["sap_timeout_seconds"])
            connection_name = request.connection_name.strip() or os.getenv("SAP_CONNECTION_NAME", "").strip()
            robot = SapGuiRobot(
                timeout_seconds=timeout,
                connection_name=connection_name,
                status_callback=report_status,
                cancel_event=cancel_event,
            )
            with SAP_JOB_LOCK:
                SAP_JOB_ROBOTS[job_id] = robot
            with robot:
                if request.transaction == "ZMM119":
                    target = settings.path("landing") / "zmm119" / request.period / f"ZMM119_{request.period}.xlsx"
                    robot.run_zmm119(
                        fisia_only=request.fisia_only,
                        output_path=target,
                        period=request.period,
                    )
                else:
                    if request.date_from is None or request.date_to is None:
                        raise ValueError("MB59 exige data inicial e data final.")
                    target = settings.path("landing") / "mb59" / request.period / f"MB59_{request.period}.xlsx"
                    robot.run_mb59(request.date_from, request.date_to, request.variant, output_path=target)
            ensure_not_cancelled()
            if target.exists():
                report_status(
                    "IMPORTING",
                    f"Arquivo {request.transaction} pronto. Aguardando a etapa sincronizada de importação.",
                )
                # Exportações SAP podem ocorrer em paralelo, mas a consolidação
                # no DuckDB é serializada para impedir duas cargas de atualizarem os
                # mesmos enriquecimentos/Mapping ao mesmo tempo.
                with SAP_IMPORT_LOCK:
                    ensure_not_cancelled()
                    loaded = import_sap_landing(request.transaction, request.period, target, report_status)
                    result = enrich_sap_landing(
                        request.transaction,
                        request.period,
                        target,
                        request.as_of,
                        loaded,
                        report_status,
                        ensure_not_cancelled,
                    )
            else:
                result = {
                    "status": "ACTION_REQUIRED",
                    "message": "O arquivo XLSX ainda não foi confirmado no destino oficial.",
                    "target_path": str(target),
                }
        except SapGuiCancelled as exc:
            result = {"status": "CANCELLED", "message": str(exc), "progress": 0}
        except (SapGuiError, ValueError, TimeoutError) as exc:
            result = {"status": "FAILED", "message": str(exc)}
        except Exception as exc:
            result = {"status": "FAILED", "message": f"Falha não prevista: {exc}"}
        if result.get("status") == "COMPLETED":
            bridge_after_local_change([request.period], f"Extração SAP {request.transaction}")
        with SAP_JOB_LOCK:
            SAP_JOB_ROBOTS.pop(job_id, None)
            if result.get("status") != "COMPLETED":
                result.setdefault("progress", SAP_JOBS[job_id].get("progress", 0))
            SAP_JOBS[job_id].update(
                **result,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                duration_seconds=round(time.time() - started, 1),
            )
        notify_job_result("sap", "sap", f"sap-{job_id}", f"Extração {request.transaction}", request.period, result)
        if str(result.get("status") or "") in {"FAILED", "ACTION_REQUIRED"}:
            try:
                offer_import_after_failure(job_id, request, started, target_path=settings.path("landing") / request.transaction.lower()
                                           / request.period / f"{request.transaction}_{request.period}.xlsx", result=result)
            except Exception:  # noqa: BLE001 - a oferta nunca derruba o registro da extração
                pass

    def build_upload_pending(chosen: dict[str, object], sap_period: str, as_of_value: date | None) -> tuple[dict[str, object], str]:
        """Parâmetros e resumo de uma importação contingencial (usados pela ferramenta e pela oferta proativa)."""
        transaction = str(chosen["transaction"])
        saved = datetime.fromisoformat(str(chosen["modified_at"])).strftime("%d/%m/%Y %H:%M")
        size_mb = int(chosen["size_bytes"]) / 1048576
        parameters = {
            "kind": "upload",
            "transaction": transaction,
            "period": sap_period,
            "as_of": as_of_value.isoformat() if as_of_value else None,
            "source_path": chosen["path"],
            "file_name": chosen["file_name"],
            "size_bytes": chosen["size_bytes"],
            "modified_at": chosen["modified_at"],
        }
        summary = (
            f"Importar {chosen['file_name']} ({size_mb:.1f} MB, salva em {saved}) como {transaction} da competência "
            f"{sap_period}"
            + (f" | Data-base contábil {as_of_value.strftime('%d/%m/%Y')}" if as_of_value else "")
            + " | Substitui a base atual da competência, como o upload contingencial da página Extrações SAP"
        )
        return parameters, summary

    def offer_import_after_failure(
        job_id: str, request: SapRunRequest, started: float, *, target_path: Path, result: dict[str, object],
    ) -> dict[str, object]:
        """Extração falhou: o Optimus procura a planilha que o SAP já salvou e oferece importá-la."""
        window_start = started - 120
        candidates = [
            item for item in find_sap_export_candidates(settings)
            if item["transaction"] == request.transaction
            and datetime.fromisoformat(str(item["modified_at"])).timestamp() >= window_start
        ]
        try:
            stat = target_path.stat()
        except OSError:
            stat = None
        if stat is not None and stat.st_mtime >= window_start and str(target_path) not in {str(item["path"]) for item in candidates}:
            try:
                detected = quick_identify_sap_export(settings, target_path)
            except Exception:  # noqa: BLE001 - arquivo incompleto no destino oficial
                detected = None
            if detected == request.transaction:
                candidates.append({
                    "path": str(target_path), "file_name": target_path.name, "folder": str(target_path.parent),
                    "size_bytes": stat.st_size, "transaction": detected,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                })
        chosen = max(candidates, key=lambda item: str(item["modified_at"]), default=None)
        parameters = summary = None
        file_facts = None
        if chosen is not None:
            parameters, summary = build_upload_pending(
                chosen, request.period, request.as_of if request.transaction == "ZMM119" else None,
            )
            file_facts = {
                "file_name": chosen["file_name"],
                "folder": chosen["folder"],
                "size_mb": round(int(chosen["size_bytes"]) / 1048576, 1),
                "saved_at": chosen["modified_at"],
            }
        # Só fatos: a mensagem do chat é escrita pelo próprio agente Optimus.
        offer = queue_optimus_event(
            {
                "type": "sap_extraction_failed",
                "topic": "Upload manual de planilha SAP (contingência)",
                "transaction": request.transaction,
                "period": request.period,
                "error": str(result.get("message") or ""),
                "status": str(result.get("status") or ""),
                "saved_export": file_facts,
            },
            parameters=parameters,
            summary=summary,
            notified=True,
        )
        # Mesma etiqueta do aviso de falha: o Windows mostra um único aviso, que abre o Optimus.
        notifier.notify(
            "sap",
            f"Extração {request.transaction} falhou · {period_label(request.period)}",
            "O Optimus deixou uma mensagem no chat"
            + (" sobre a planilha que o SAP já salvou." if chosen is not None else " com a orientação para seguir."),
            view="agent",
            tag=f"sap-{job_id}",
            replace=True,
        )
        return offer

    def mark_offer_resolved(pending: dict[str, object] | None) -> None:
        """A decisão sobre o aviso foi tomada (sim ou não): ele não volta a ficar pendente."""
        offer_id = (pending or {}).get("proactive_offer_id")
        if not offer_id:
            return
        with OPTIMUS_OFFERS_LOCK:
            for item in OPTIMUS_OFFERS:
                if item.get("offer_id") == offer_id:
                    item["resolved"] = True

    def queue_optimus_event(
        event: dict[str, object], *, parameters: dict[str, object] | None = None, summary: str | None = None,
        notified: bool = False, key: str | None = None, system: bool = False, first: bool = False,
    ) -> dict[str, object]:
        """Fila de eventos proativos: o agente escreve a mensagem quando o chat de um administrador busca.

        ``system``: aviso do próprio sistema (agente sem conexão), entregue sem passar pelo n8n.
        """
        now = time.time()
        item = {
            "offer_id": str(uuid.uuid4()),
            "key": key,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "created_ts": now,
            "event": event,
            "parameters": parameters,
            "summary": summary,
            "notified": notified,
            "system": system,
            "status": "queued",
        }
        with OPTIMUS_OFFERS_LOCK:
            OPTIMUS_OFFERS[:] = [
                existing for existing in OPTIMUS_OFFERS
                if now - float(existing["created_ts"]) < OPTIMUS_OFFER_TTL_SECONDS
                and not (key and existing.get("key") == key and existing.get("status") == "queued")
            ]
            OPTIMUS_OFFERS.insert(0, item) if first else OPTIMUS_OFFERS.append(item)
        return item

    # Presença: o vigia só trabalha enquanto um administrador está com o sistema aberto
    # (o chat do Optimus é carregado em segundo plano e consulta /api/optimus/proactive a cada 15 s).
    # "outage": o agente está sem conexão (n8n inacessível, em geral por VPN desligada).
    optimus_watch = {"last_admin_poll": 0.0, "admin": None, "next_run": 0.0, "event": True,
                     "next_connectivity": 0.0, "outage": None, "last_delivery": {}, "min_gap": 60.0}
    app.state.optimus_watch = optimus_watch
    # Ciclo completo a cada 5 min (além dos gatilhos imediatos: carga concluída, Mapping salvo...);
    # VPN/n8n a cada 2 min. Contra poluição: cada fato só é avisado uma vez (impressão digital)
    # e o chat recebe no máximo um aviso do agente por minuto ("min_gap").
    WATCH_INTERVAL_SECONDS = 300
    CONNECTIVITY_INTERVAL_SECONDS = 120

    def optimus_watch_trigger() -> None:
        optimus_watch["event"] = True

    def connectivity_check() -> dict[str, object] | None:
        """VPN e n8n a cada 2 minutos. Sem n8n o agente não consegue escrever: o próprio sistema avisa
        (notificação do Windows + aviso do Health Center no chat). Quando a conexão volta, o agente
        escreve sobre o retorno e entrega os avisos que ficaram na fila."""
        indicators = connectivity_indicators(os.getenv("N8N_CHAT_URL", "").strip())
        cause = connectivity_cause(indicators)
        outage = optimus_watch.get("outage")
        now = datetime.now()
        if cause is not None:
            facts = {name: cause.get(name) for name in ("key", "title", "level", "status", "summary", "details", "fix")}
            if outage is None:
                outage = {"since": now.isoformat(timespec="seconds"), "indicator": facts}
                optimus_watch["outage"] = outage
                queue_optimus_event({"type": "connectivity_lost", "topic": "Health Center", "indicator": facts},
                                    key="connectivity_lost", system=True, notified=True)
                notifier.notify(
                    "connectivity",
                    f"Optimus sem conexão · {facts['title']}: {facts['status']}",
                    str(facts.get("fix") or facts.get("details") or ""),
                    view="health",
                    tag="connectivity",
                )
            else:
                outage["indicator"] = facts
        elif outage is not None:
            optimus_watch["outage"] = None
            with OPTIMUS_OFFERS_LOCK:
                for item in OPTIMUS_OFFERS:
                    # avisos de queda ainda não entregues já não valem: a conexão voltou
                    if item.get("status") == "queued" and (item.get("key") in CONNECTIVITY_KEYS or item.get("key") == "connectivity_lost"):
                        item["status"] = "superseded"
                waiting = sum(1 for item in OPTIMUS_OFFERS if item.get("status") == "queued" and not item.get("system"))
            since = datetime.fromisoformat(str(outage["since"]))
            queue_optimus_event(
                {"type": "connectivity_restored", "topic": "Health Center VPN / rede e n8n / Optimus",
                 "offline_since": outage["since"], "restored_at": now.isoformat(timespec="seconds"),
                 "minutes_offline": max(1, round((now - since).total_seconds() / 60)),
                 "cause": outage["indicator"], "queued_warnings": waiting},
                key="connectivity_restored", first=True,
            )
        # VPN fora com o n8n acessível: o agente escreve normalmente (health:network).
        # Durante a queda só a memória é atualizada; o aviso do sistema já foi dado.
        offline = optimus_watch.get("outage") is not None
        events = health_events({"indicators": indicators}, None if offline else (lambda title: documentation_matches(settings, title)))
        fresh = new_events(settings, events, scope=CONNECTIVITY_KEYS)
        if not offline:
            for item in fresh:
                queue_optimus_event(item["event"], parameters=item.get("parameters"), summary=item.get("summary"), key=item["key"])
        return optimus_watch.get("outage")

    app.state.optimus_connectivity_check = connectivity_check

    def optimus_watch_once() -> list[dict[str, object]]:
        admin = optimus_watch.get("admin")
        period = latest_period(settings)
        if not admin or not period:
            return []
        with SAP_JOB_LOCK:
            jobs = sorted((dict(job) for job in SAP_JOBS.values()), key=lambda job: str(job.get("created_at") or ""), reverse=True)[:4]
        try:
            health = system_health(settings, period, admin, os.getenv("N8N_CHAT_URL", "").strip(), jobs, backup=backup_status())
        except Exception:  # noqa: BLE001 - o Health Center indisponível não impede as demais verificações
            health = None
        fresh = new_events(settings, collect_events(settings, period, health, jobs=jobs))
        for item in fresh:
            if item["key"] in CONNECTIVITY_KEYS and optimus_watch.get("outage") is not None:
                continue  # agente sem conexão: o aviso do sistema já cobre a VPN
            queue_optimus_event(item["event"], parameters=item.get("parameters"), summary=item.get("summary"), key=item["key"])
        return fresh

    app.state.optimus_watch_once = optimus_watch_once

    def optimus_watch_loop() -> None:
        while True:
            time.sleep(20)
            now = time.time()
            if now - float(optimus_watch["last_admin_poll"]) > 90:
                continue  # nenhum administrador com o sistema aberto
            if now >= float(optimus_watch["next_connectivity"]):
                optimus_watch["next_connectivity"] = now + CONNECTIVITY_INTERVAL_SECONDS
                try:
                    connectivity_check()
                except Exception:  # noqa: BLE001 - tenta de novo em 2 minutos
                    pass
            if optimus_watch["event"] or now >= float(optimus_watch["next_run"]):
                optimus_watch["event"] = False
                optimus_watch["next_run"] = now + WATCH_INTERVAL_SECONDS
                try:
                    optimus_watch_once()
                except Exception:  # noqa: BLE001 - tenta de novo no próximo ciclo
                    pass

    if (settings.raw.get("runtime") or {}).get("background_worker"):
        threading.Thread(target=optimus_watch_loop, daemon=True, name="optimus-watch").start()

    @app.get("/api/optimus/proactive", dependencies=[Depends(require_token)])
    async def optimus_proactive(
        request: Request,
        session_id: str = Query(min_length=8, max_length=200),
        period: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    ) -> dict[str, object]:
        """Entrega ao chat do administrador o próximo evento proativo, escrito pelo próprio agente Optimus."""
        user = getattr(request.state, "user", None) or {}
        if str(user.get("role", "")) != "admin":
            return {"messages": []}
        if not optimus_watch.get("admin"):
            optimus_watch["event"] = True  # primeira consulta desde que o sistema abriu: verifica logo
        optimus_watch["last_admin_poll"] = time.time()
        optimus_watch["admin"] = dict(user)
        now = time.time()
        offline = optimus_watch.get("outage") is not None
        deliveries: dict[str, float] = optimus_watch["last_delivery"]  # type: ignore[assignment]
        spaced = now - deliveries.get(session_id, 0.0) >= float(optimus_watch["min_gap"])  # type: ignore[arg-type]
        with SAP_CONFIRMATION_LOCK:
            has_pending = session_id in SAP_CONFIRMATIONS
        with OPTIMUS_OFFERS_LOCK:
            item = next(
                (
                    candidate for candidate in OPTIMUS_OFFERS
                    if candidate.get("status") == "queued"
                    and now - float(candidate["created_ts"]) < OPTIMUS_OFFER_TTL_SECONDS
                    and not (candidate.get("parameters") and has_pending)  # uma decisão pendente por vez
                    # sem conexão só o aviso do sistema sai; os do agente esperam a conexão voltar
                    and (candidate.get("system") or (not offline and (spaced or candidate.get("notified"))))
                ),
                None,
            )
            if item is None:
                return {"messages": [], "offline": offline}
            item["status"] = "in_progress"
        if item.get("system"):
            # Agente sem conexão: o aviso é o próprio indicador do Health Center, sem texto inventado.
            facts = dict((item["event"] or {}).get("indicator") or {})  # type: ignore[union-attr]
            text = "\n".join(part for part in (
                f"{facts.get('title')}: {facts.get('status')}",
                str(facts.get("details") or ""),
                f"Como resolver: {facts['fix']}" if facts.get("fix") else "",
            ) if part)
            with OPTIMUS_OFFERS_LOCK:
                item["status"] = "delivered"
            return {"messages": [{
                "id": item["offer_id"], "kind": "system", "title": "Aviso do sistema · Health Center",
                "text": text, "created_at": item["created_at"], "notify": False,
            }], "offline": offline}
        confirmation_id = None
        if item.get("parameters"):
            confirmation_id = str(uuid.uuid4())
            with SAP_CONFIRMATION_LOCK:
                SAP_CONFIRMATIONS[session_id] = {
                    "confirmation_id": confirmation_id,
                    "parameters": item["parameters"],
                    "summary": item["summary"],
                    "created_at": item["created_at"],
                    "origin": "optimus_proactive",
                    "proactive_event": item["event"],
                    "proactive_offer_id": item["offer_id"],
                }
        event = dict(item["event"])  # type: ignore[arg-type]
        try:
            answer = await _optimus_chat(
                OptimusChatRequest(
                    message=f"[evento proativo] {event.get('topic') or event.get('type')}"[:4000],
                    session_id=session_id,
                    period=str(event.get("period") or period or default_period()),
                ),
                request,
                proactive_event=event,
            )
            text = _n8n_text(answer.get("response")).strip()
            if not text:
                raise ValueError("resposta vazia")
        except Exception:  # noqa: BLE001 - n8n indisponível: o evento volta para a fila
            with OPTIMUS_OFFERS_LOCK:
                item["status"] = "queued"
            if confirmation_id:
                with SAP_CONFIRMATION_LOCK:
                    current = SAP_CONFIRMATIONS.get(session_id)
                    if current and current.get("confirmation_id") == confirmation_id:
                        SAP_CONFIRMATIONS.pop(session_id, None)
            optimus_watch["next_connectivity"] = 0.0  # confere VPN/n8n já no próximo ciclo do vigia
            return {"messages": [], "offline": optimus_watch.get("outage") is not None}
        with OPTIMUS_OFFERS_LOCK:
            item["status"] = "delivered"
            item["text"] = text  # guardado para quando o usuário responder a este aviso
        deliveries[session_id] = time.time()
        return {"messages": [{
            "id": item["offer_id"],
            "text": text,
            "created_at": item["created_at"],
            "notify": not item.get("notified"),
        }], "offline": False}

    @app.post("/api/sap/run", dependencies=[Depends(require_token)])
    def start_sap(request: SapRunRequest) -> dict[str, object]:
        if request.transaction == "MB59" and (request.date_from is None or request.date_to is None):
            raise HTTPException(status_code=422, detail="Informe as datas inicial e final para a MB59.")
        if request.date_from and request.date_to and request.date_to < request.date_from:
            raise HTTPException(status_code=422, detail="A data final não pode ser anterior à inicial.")
        if request.transaction == "MB59" and request.date_from and request.date_to:
            expected_period = request.period
            if (
                request.date_from.strftime("%Y-%m") != expected_period
                or request.date_to.strftime("%Y-%m") != expected_period
            ):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "As datas da MB59 devem pertencer à mesma competência selecionada "
                        f"({expected_period})."
                    ),
                )
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "transaction": request.transaction,
            "period": request.period,
            "status": "QUEUED",
            "progress": SAP_STAGE_PROGRESS["QUEUED"],
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "parameters": request.model_dump(mode="json"),
        }
        register_sap_job(job)
        threading.Thread(target=run_sap_job, args=(job_id, request), daemon=True).start()
        return job

    def register_sap_job(job: dict[str, object]) -> None:
        job_id = str(job["job_id"])
        with SAP_JOB_LOCK:
            active_jobs = any(
                str(existing.get("status") or "") not in SAP_TERMINAL_STATUSES
                for existing in SAP_JOBS.values()
            )
            if not active_jobs:
                SAP_JOBS.clear()
                SAP_JOB_CANCEL_EVENTS.clear()
                SAP_JOB_ROBOTS.clear()
            else:
                # Ao iniciar uma transação enquanto outra está ativa, preserva
                # todas as execuções correntes e remove somente histórico terminal.
                for existing_id in [
                    existing_id
                    for existing_id, existing in SAP_JOBS.items()
                    if str(existing.get("status") or "") in SAP_TERMINAL_STATUSES
                ]:
                    SAP_JOBS.pop(existing_id, None)
                    SAP_JOB_CANCEL_EVENTS.pop(existing_id, None)
                    SAP_JOB_ROBOTS.pop(existing_id, None)
            SAP_JOBS[job_id] = job
            SAP_JOB_CANCEL_EVENTS[job_id] = threading.Event()

    def run_upload_job(job_id: str, transaction: str, period: str, as_of: date | None, staging: Path, file_name: str) -> None:
        started = time.time()
        with SAP_JOB_LOCK:
            cancel_event = SAP_JOB_CANCEL_EVENTS.setdefault(job_id, threading.Event())
            SAP_JOBS[job_id].update(started_at=datetime.now().isoformat(timespec="seconds"))

        def report_status(status: str, message: str) -> None:
            with SAP_JOB_LOCK:
                current = int(SAP_JOBS[job_id].get("progress", 0))
                SAP_JOBS[job_id].update(
                    status=status,
                    message=message,
                    progress=max(current, SAP_STAGE_PROGRESS.get(status, current)),
                )

        def ensure_not_cancelled() -> None:
            if cancel_event.is_set():
                raise SapGuiCancelled("Carga da planilha cancelada pelo usuário.")

        try:
            report_status("UPLOAD_VALIDATING", f"Validando {file_name}: layout, colunas e competência {period}.")
            validate_sap_upload(settings, transaction, period, staging)
            ensure_not_cancelled()
            report_status("FILE_READY", "Planilha válida. Aguardando a etapa sincronizada de importação.")
            target = landing_target(settings, transaction, period)
            # Mesma trava da extração automática: nunca duas cargas consolidando
            # joins/Mapping ao mesmo tempo, mesmo que o robô esteja rodando.
            with SAP_IMPORT_LOCK:
                ensure_not_cancelled()
                backup = install_upload(staging, target)
                try:
                    loaded = import_sap_landing(transaction, period, target, report_status)
                except Exception:
                    # A importação falhou antes de gravar: volta o arquivo anterior
                    # para que o destino oficial continue coerente com o banco.
                    restore_previous(target, backup)
                    raise
                result = enrich_sap_landing(
                    transaction,
                    period,
                    target,
                    as_of,
                    loaded,
                    report_status,
                    ensure_not_cancelled,
                    uploaded=True,
                )
        except SapGuiCancelled as exc:
            result = {"status": "CANCELLED", "message": str(exc), "progress": 0}
        except (ValueError, FileNotFoundError) as exc:
            result = {"status": "FAILED", "message": str(exc)}
        except Exception as exc:
            result = {"status": "FAILED", "message": f"Falha não prevista na carga da planilha: {exc}"}
        finally:
            staging.unlink(missing_ok=True)
        if result.get("status") == "COMPLETED":
            bridge_after_local_change([period], f"Upload {transaction}")
        with SAP_JOB_LOCK:
            if result.get("status") != "COMPLETED":
                result.setdefault("progress", SAP_JOBS[job_id].get("progress", 0))
            SAP_JOBS[job_id].update(
                **result,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                duration_seconds=round(time.time() - started, 1),
            )
        notify_job_result("uploads", "sap", f"upload-{job_id}", f"Carga da planilha {transaction}", period, result)

    @app.post("/api/sap/upload", dependencies=[Depends(require_token)])
    async def upload_sap_export(
        request: Request,
        transaction: str = Query(pattern=r"^(ZMM119|MB59)$"),
        period: str = Query(pattern=r"^\d{4}-\d{2}$"),
        file_name: str = Query(default="", max_length=260),
        as_of: date | None = Query(default=None),
    ) -> dict[str, object]:
        # O navegador envia o XLSX como corpo binário (sem multipart); ele é
        # gravado em disco à medida que chega, sem ocupar memória.
        if not file_name.casefold().endswith(".xlsx"):
            raise HTTPException(status_code=422, detail="Envie a planilha no formato .xlsx exportado do SAP.")
        declared = int(request.headers.get("content-length") or 0)
        if declared > SAP_UPLOAD_MAX_BYTES:
            raise HTTPException(status_code=413, detail="A planilha excede o limite de 500 MB.")
        folder = settings.path("landing") / "uploads"
        folder.mkdir(parents=True, exist_ok=True)
        # A extensão final precisa ser .xlsx: o openpyxl recusa outras extensões.
        staging = folder / f"{transaction}_{period}_{uuid.uuid4().hex[:12]}.upload.xlsx"
        size = 0
        try:
            with staging.open("wb") as handle:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > SAP_UPLOAD_MAX_BYTES:
                        raise HTTPException(status_code=413, detail="A planilha excede o limite de 500 MB.")
                    handle.write(chunk)
            if size == 0:
                raise HTTPException(status_code=422, detail="O arquivo enviado está vazio.")
            if not is_xlsx_archive(staging):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "O arquivo enviado não é uma planilha XLSX válida. No SAP, exporte a grade "
                        "no formato XLSX (Excel 2007 ou superior) e envie esse arquivo."
                    ),
                )
            # Guardrail imediato: planilha de outra transação (ou de outro sistema)
            # é recusada no envio, antes de criar o job ou tocar em qualquer dado.
            detected = await run_in_threadpool(identify_sap_export, settings, staging)
            if detected != transaction:
                raise HTTPException(status_code=422, detail=wrong_transaction_message(transaction, detected))
        except BaseException:
            staging.unlink(missing_ok=True)
            raise
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "transaction": transaction,
            "period": period,
            "source": "upload",
            "file_name": Path(file_name).name,
            "status": "UPLOAD_RECEIVED",
            "progress": SAP_STAGE_PROGRESS["UPLOAD_RECEIVED"],
            "message": f"Planilha {Path(file_name).name} recebida ({size / 1048576:.1f} MB).",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "parameters": {"transaction": transaction, "period": period, "as_of": as_of.isoformat() if as_of else None},
        }
        register_sap_job(job)
        threading.Thread(
            target=run_upload_job,
            args=(job_id, transaction, period, as_of, staging, Path(file_name).name),
            daemon=True,
        ).start()
        return job

    @app.get("/api/sap/jobs/{job_id}", dependencies=[Depends(require_token)])
    def get_sap_job(job_id: str) -> dict[str, object]:
        with SAP_JOB_LOCK:
            job = SAP_JOBS.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Execução SAP não encontrada.")
            return dict(job)

    @app.get("/api/sap/jobs", dependencies=[Depends(require_token)])
    def list_sap_jobs() -> list[dict[str, object]]:
        with SAP_JOB_LOCK:
            jobs = sorted(
                (dict(job) for job in SAP_JOBS.values()),
                key=lambda job: str(job.get("created_at") or ""),
                reverse=True,
            )
            return jobs[:4]

    @app.post("/api/sap/jobs/{job_id}/cancel", dependencies=[Depends(require_token)])
    def cancel_sap_job(job_id: str) -> dict[str, object]:
        with SAP_JOB_LOCK:
            job = SAP_JOBS.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Execução SAP não encontrada.")
            status = str(job.get("status") or "")
            if status in SAP_TERMINAL_STATUSES:
                return dict(job)
            cancel_event = SAP_JOB_CANCEL_EVENTS.setdefault(job_id, threading.Event())
            cancel_event.set()
            robot = SAP_JOB_ROBOTS.get(job_id)
            if robot is not None:
                robot.cancel()
            job.update(
                status="CANCEL_REQUESTED",
                message="Cancelamento solicitado. Interrompendo o robô SAP e liberando a sessão.",
            )
            return dict(job)

    @app.post("/api/sap/jobs/cancel-active", dependencies=[Depends(require_token)])
    def cancel_active_sap_jobs() -> dict[str, object]:
        cancelled: list[str] = []
        with SAP_JOB_LOCK:
            for job_id, job in SAP_JOBS.items():
                if str(job.get("status") or "") in SAP_TERMINAL_STATUSES:
                    continue
                cancel_event = SAP_JOB_CANCEL_EVENTS.setdefault(job_id, threading.Event())
                cancel_event.set()
                robot = SAP_JOB_ROBOTS.get(job_id)
                if robot is not None:
                    robot.cancel()
                job.update(
                    status="CANCEL_REQUESTED",
                    message="Cancelamento solicitado. Interrompendo o robô SAP e liberando a sessão.",
                )
                cancelled.append(job_id)
        return {"status": "ok", "cancelled": cancelled, "count": len(cancelled)}

    @app.post("/api/runs", dependencies=[Depends(require_token)])
    def create_run(request: RunRequest) -> dict[str, int | str]:
        run_id = run_pipeline(settings, request.period)
        with connect(settings.path("database")) as connection:
            status = connection.execute("select status from pipeline_runs where run_id=?", [run_id]).fetchone()[0]
        return {"run_id": run_id, "period": request.period, "status": status}

    @app.get("/api/runs", dependencies=[Depends(require_token)])
    def list_runs(limit: int = Query(default=20, ge=1, le=200)) -> list[dict[str, object]]:
        with connect(settings.path("database")) as connection:
            rows = connection.execute(
                "select run_id, period, status, started_at, finished_at, message from pipeline_runs order by run_id desc limit ?",
                [limit],
            ).fetchall()
        keys = ["run_id", "period", "status", "started_at", "finished_at", "message"]
        return [dict(zip(keys, row, strict=True)) for row in rows]

    @app.get("/api/runs/{run_id}", dependencies=[Depends(require_token)])
    def get_run(run_id: int) -> dict[str, object]:
        with connect(settings.path("database")) as connection:
            row = connection.execute(
                "select run_id, period, status, started_at, finished_at, message from pipeline_runs where run_id=?",
                [run_id],
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Execução não encontrada")
        keys = ["run_id", "period", "status", "started_at", "finished_at", "message"]
        return dict(zip(keys, row, strict=True))
    
    AGENT_SYSTEM_KNOWLEDGE: dict[str, object] = {
        "purpose": "Estoque Contábil substitui planilhas pesadas por processamento Python auditável para posição de estoque, enriquecimento e controles contábeis.",
        "sources": {
            "ZMM119": "Posição de estoque SAP. A Base de Estoque considera exclusivamente a Empresa 7170; registros de outras empresas, como 8000, são descartados na importação. Origina centro, material, descrição, unidade, NCM, quantidades e valores/custos da posição.",
            "MB59": "Base GR consultada por CE & MAT como primeira prioridade dos campos PASSO A PASSO.",
            "ALL_BRAZIL": "Cadastro mestre que fornece Division Description, Material Origin, Lifecycle e Lifecycle Description. O vínculo é somente por Material, sem Centro. Em cada competência, somente o último arquivo válido da pasta mensal até a data-base é considerado; arquivos anteriores do mesmo mês não são usados como fallback.",
            "MAPPING": "Regras auxiliares editáveis para status operacional, locais, faixas e demais dimensões configuradas no sistema.",
        },
        "business_rules": {
            "center_material_key": "Centro + Material, tratados como campos/chave sem concatenação ambígua.",
            "company_unit_cost": "Vlr Tot Emp / Utilização livre, com proteção contra divisão por zero.",
            "style_color": "10 primeiros caracteres do Material. Este campo é apenas uma dimensão analítica e NÃO é usado no join com All Brazil.",
            "sap_all_brazil_join": "All Brazil nunca usa Centro. Primeiro relaciona Material completo com Material Nbr; se o SKU completo não existir, usa Estilo-Cor de 10 caracteres. O sistema usa somente o último arquivo válido da pasta mensal até a data-base.",
            "pass_step_priority": "Product Offer End Date, Season e Year tentam, por campo: 1) MB59 da competência por CE & MAT; 2) posição do mês anterior por CE & MAT; 3) All Brazil por Material sem Centro. Se nenhuma fonte trouxer valor, o campo fica sem valor e deve ser informado como Não localizado; nunca inferir ou inventar números.",
            "sap_extraction_policy": (
                "O Optimus interpreta semanticamente a intenção do usuário. "
                "Datas informadas em formato brasileiro ou linguagem natural devem "
                "ser normalizadas internamente; nunca peça ao usuário para converter "
                "uma data para AAAA-MM-DD. "
                "Para ZMM119, a competência é obrigatória e a data-base contábil usa "
                "por padrão o último dia da competência. "
                "Para MB59, quando as datas não forem informadas, use o primeiro e o "
                "último dia da competência; quando a variante não for informada, use "
                "BASE GR. FISIA é fixo e não deve ser perguntado. "
                "Com os parâmetros resolvidos, use run_sap para registrar a solicitação "
                "e apresentar o resumo. Enquanto houver pending_sap_confirmation, "
                "interprete semanticamente confirmação, cancelamento ou alteração. "
                "Nunca execute sem confirmação explícita."
            ),
            "sap_contingency_import_policy": (
                "Quando um administrador pedir para importar/carregar uma planilha ZMM119 ou MB59 que já baixou do SAP "
                "(contingência), use find_sap_exports para listar as planilhas recentes desta máquina; apresente as "
                "opções e use import_sap_file com a escolhida e a competência. O resumo devolvido deve ser mostrado e "
                "a importação só começa com confirm_sap após confirmação explícita. Usuários comuns não podem importar."
            ),
            "report_artifacts_policy": (
                "Quando o usuário pedir o PDF da Visão e relatórios, use report_pdf. "
                "Quando pedir apresentação executiva, slides ou deck, use executive_presentation. "
                "O payload retornado é a única fonte dos artefatos; não estime métricas ausentes."
            ),
            "style": "6 primeiros caracteres de Estilo-Cor.",
            "fiscal_unit_cost": "Vlr Tot Fisc / Utilização livre, com proteção contra divisão por zero.",
            "aging_days": "Data-base contábil menos Product Offer End Date.",
            "aging_bucket": "Valores negativos = Futures; demais distribuídos nas faixas versionadas do sistema.",
            "cost_split": "FOB 50%, II 35% e Outros Custos 15% do Vlr Tot Fisc, conforme regra vigente mapeada.",
            "season_year": "Season + Year; anos anteriores a 2022 podem ser agrupados como <2022 nas visões históricas.",
        },
        # Faixas padrão do Mapping "Faixas de aging" (dias iniciais entre parênteses);
        # as vigentes podem ser editadas e são consultadas pela ferramenta mappings.
        "aging_reference": [
            "0) Futures (Days negativo)",
            "1) 0-3 meses (0)",
            "2) 3-6 meses (105)",
            "3) 6-9 meses (195)",
            "4) 9-12 meses (285)",
            "5) 12-18 meses (375)",
            "6) 18-24 meses (555)",
            "7) 2-5 anos (735)",
            "8) >5 anos (1815)",
        ],
        "analysis_guidelines": [
            "Cruzar valor fiscal e quantidade para evitar conclusões baseadas só em volume.",
            "Distinguir fato observado de hipótese ou interpretação.",
            "Explicar concentração, materialidade, cobertura e exceções quando forem relevantes.",
            "Sempre informar a competência usada quando a resposta depender dos dados.",
            "Nunca inventar causa, saldo, material, centro, data, Season, Year ou qualquer valor ausente. Quando as fontes não retornarem o dado, responder explicitamente: Não localizado.",
        ],
    }

    def _period_end(period: str) -> date:
        year, month = map(int, period.split("-"))
        return date(year, month, calendar.monthrange(year, month)[1])

    def _parse_agent_date(
        value: object,
        period: str,
        default: date,
    ) -> date:
        raw = str(value or "").strip()

        if not raw:
            return default

        # Formato técnico: AAAA-MM-DD
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass

        # Formato brasileiro completo: DD/MM/AAAA
        try:
            return datetime.strptime(raw, "%d/%m/%Y").date()
        except ValueError:
            pass

        # Formato brasileiro curto: DD/MM
        try:
            parsed = datetime.strptime(raw, "%d/%m")
            year = int(period[:4])
            return date(year, parsed.month, parsed.day)
        except ValueError:
            pass

        raise ValueError(f"Data inválida: {raw}")

    def _all_brazil_agent_source(period: str) -> dict[str, object]:
        try:
            snapshot = resolve_all_brazil(settings, _period_end(period))
            return {
                "available": True,
                "snapshot_date": snapshot.snapshot_date.isoformat(),
                "file_name": snapshot.path.name,
                "source_path": str(snapshot.path),
                "snapshot_count": 1,
                "files": [snapshot.path.name],
                "selection_rule": "somente o último arquivo válido da pasta mensal até a data-base",
                "join_key": "Material exato; fallback Estilo-Cor (10 caracteres) = Material Nbr, sem Centro",
            }
        except Exception as exc:
            return {"available": False, "detail": str(exc)}

    def _all_brazil_enrichment_status(period: str) -> dict[str, object]:
        try:
            with connect(settings.path("database")) as connection:
                row = connection.execute(
                    """select snapshot_date, source_path, inventory_keys, matched_keys,
                              coverage_pct, duplicate_keys, conflict_keys, imported_at
                       from all_brazil_imports
                       where period=?
                       order by imported_at desc
                       limit 1""",
                    [period],
                ).fetchone()
        except Exception as exc:
            return {"available": False, "period": period, "detail": str(exc)}

        if row is None:
            return {
                "available": False,
                "period": period,
                "detail": "A competência ainda não possui registro de enriquecimento All Brazil.",
            }

        keys = [
            "snapshot_date",
            "source_path",
            "inventory_keys",
            "matched_keys",
            "coverage_pct",
            "duplicate_keys",
            "conflict_keys",
            "imported_at",
        ]
        result = dict(zip(keys, row, strict=True))
        result["available"] = True
        result["period"] = period
        result["join_rule"] = (
            "Material completo da Base de Estoque = Material Nbr; se ausente, Estilo-Cor de 10 caracteres = Material Nbr, sem Centro. "
            "Somente o último arquivo válido do mês até a data-base é considerado."
        )
        return result

    def _mapping_catalog_for_agent() -> list[dict[str, object]]:
        try:
            return list_mapping_groups(settings)
        except Exception as exc:
            return [{"error": str(exc)}]

    def _recent_runs_for_agent(period: str, limit: int = 5) -> list[dict[str, object]]:
        with connect(settings.path("database")) as connection:
            rows = connection.execute(
                "select run_id, period, status, started_at, finished_at, message "
                "from pipeline_runs where period=? order by run_id desc limit ?",
                [period, limit],
            ).fetchall()
        keys = ["run_id", "period", "status", "started_at", "finished_at", "message"]
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def _available_periods_for_agent(selected: str) -> list[dict[str, object]]:
        """Todas as competências carregadas, com os mesmos KPIs da Visão e relatórios.

        Sem esta lista o Optimus só enxerga a competência selecionada na tela e pode
        concluir, erradamente, que as demais não foram importadas.
        """
        with connect(settings.path("database")) as connection:
            ensure_inventory_schema(connection)
            rows = connection.execute(
                """select period, count(*), count(distinct material),
                          coalesce(sum(unrestricted_quantity),0), coalesce(sum(fiscal_total_amount),0)
                   from inventory_rows group by period order by period"""
            ).fetchall()

        def variation(current: float, previous: float) -> float | None:
            return round((current - previous) / abs(previous) * 100, 2) if previous else None

        result: list[dict[str, object]] = []
        previous: dict[str, object] | None = None
        for period_value, row_count, materials, quantity, fiscal in rows:
            year, month = map(int, str(period_value).split("-"))
            quantity = float(quantity or 0)
            fiscal = float(fiscal or 0)
            item: dict[str, object] = {
                "period": str(period_value),
                "label": f"{MONTH_NAMES[month]} de {year}",
                "is_selected": str(period_value) == selected,
                "rows": int(row_count),
                "materials": int(materials),
                "quantity": quantity,
                "fiscal_value": round(fiscal, 2),
                "pmm": round(fiscal / quantity, 4) if quantity else 0.0,
            }
            if previous is not None:
                item["previous_period"] = previous["period"]
                item["fiscal_value_variation_pct"] = variation(fiscal, float(previous["fiscal_value"]))
                item["quantity_variation_pct"] = variation(quantity, float(previous["quantity"]))
                item["pmm_variation_pct"] = variation(float(item["pmm"]), float(previous["pmm"]))
            result.append(item)
            previous = item
        return result

    def build_agent_context(period: str) -> dict[str, object]:
        summary = dashboard_summary(settings, period)
        mb59 = mb59_status(settings, period)
        with connect(settings.path("database")) as connection:
            run = connection.execute(
                "select run_id, status from pipeline_runs where period=? order by run_id desc limit 1",
                [period],
            ).fetchone()
            insights = [] if run is None else connection.execute(
                "select insight_code, severity, title, description, amount, evidence_json "
                "from accounting_insights where run_id=? "
                "order by severity, abs(amount) desc nulls last",
                [run[0]],
            ).fetchall()
        with SAP_JOB_LOCK:
            jobs = sorted(
                (dict(job) for job in SAP_JOBS.values()),
                key=lambda job: str(job.get("created_at") or ""),
                reverse=True,
            )
            current_sap_job = jobs[0] if jobs else None
        available_periods = _available_periods_for_agent(period)
        return {
            "period": period,
            "available_periods": available_periods,
            "period_guidance": (
                "available_periods lista TODAS as competências com Base de Estoque carregada nesta máquina "
                f"({', '.join(str(item['period']) for item in available_periods) or 'nenhuma'}), com os mesmos KPIs "
                "da Visão e relatórios (PMM = valor fiscal agregado / quantidade agregada) e as variações contra a "
                f"competência imediatamente anterior da lista. A competência selecionada na tela é {period}: responda "
                "sobre ela por padrão, mas use available_periods para comparar competências e para saber quais "
                "existem. Nunca afirme que uma competência presente nessa lista não foi importada. Para detalhes "
                "de outra competência, use inventory_search com o period correspondente."
            ),
            "run_id": None if run is None else run[0],
            "status": "DATA_AVAILABLE" if run is None and summary["rows"] else ("NOT_PROCESSED" if run is None else run[1]),
            "data_policy": "local_context_plus_validated_tool_bridge",
            "system_knowledge": AGENT_SYSTEM_KNOWLEDGE,
            # Títulos do manual do sistema; o conteúdo segue em [MANUAL_DO_SISTEMA]
            # quando a pergunta é sobre o uso do sistema, ou via ferramenta system_manual.
            "system_manual_index": [item["title"] for item in manual_index()],
            "inventory_field_catalog": inventory_columns(),
            "mapping_catalog": _mapping_catalog_for_agent(),
            "all_brazil": {
                "selected_source": _all_brazil_agent_source(period),
                "enrichment_status": _all_brazil_enrichment_status(period),
                "relationship": "Division Description, Material Origin e Lifecycle vêm somente do último All Brazil válido. O join tenta Material completo e depois Estilo-Cor de 10 caracteres, nunca Centro. Os campos PASSO A PASSO usam MB59 por CE & MAT, depois posição anterior por CE & MAT e por fim o mesmo All Brazil pela regra híbrida de Material.",
            },
            "mb59": mb59,
            "summary": summary,
            "recent_runs": _recent_runs_for_agent(period),
            "current_sap_job": current_sap_job,
            "current_sap_jobs": jobs[:4],
            "local_tools": {
                "system_manual": (
                    "Lê seções do manual oficial do sistema (páginas, botões, parâmetros, bases, regras, "
                    "permissões, rotinas). Use {\"type\":\"system_manual\",\"topics\":[títulos do "
                    "system_manual_index]} e/ou \"query\" com a dúvida do usuário."
                ),
                "inventory_search": "Pesquisa linhas reais da Base Orig. por termo, filtros, ordenação e competência.",
                "mappings": "Lê todas as regras de Mapping configuradas no sistema.",
                "mb59_status": "Consulta o status e metadados da MB59 da competência.",
                "all_brazil_source": "Consulta o snapshot All Brazil selecionado para a data-base da competência.",
                "all_brazil_catalog": "Lista snapshots históricos All Brazil disponíveis no espelho local do Drive, com filtros opcionais de ano e mês.",
                "all_brazil_search": "Consulta atributos canônicos dentro de um snapshot histórico All Brazil por data, Material Nbr ou termo.",
                "all_brazil_enrichment_status": "Mostra como a posição SAP foi relacionada ao All Brazil, incluindo snapshot, cobertura, chaves casadas, duplicidades e conflitos.",
                "runs": "Consulta execuções do pipeline da competência.",
                "sap_status": "Consulta a execução SAP atual.",
                "report_pdf": "Gera o PDF da página Visão e relatórios para a competência e devolve um link protegido de download.",
                "executive_presentation": "Prepara KPIs, comparativos, séries e roteiro executivo para o fluxo n8n criar uma apresentação exportável no Google Slides sem inventar dados.",
                "run_sap": (
                        "Cria ou revisa uma solicitação de extração ZMM119/MB59. "
                        "O backend aplica defaults determinísticos da competência: "
                        "ZMM119 usa o último dia como data-base; MB59 usa primeiro e "
                        "último dia e variante BASE GR. Depois registra uma "
                        "pending_sap_confirmation e pede confirmação."
                    ),
                "find_sap_exports": (
                    "Somente administradores. Lista as planilhas .xlsx salvas nos últimos dias em Downloads, Área de "
                    "Trabalho, Documentos e pastas TEMP desta máquina e reconhece pelo layout se cada uma é ZMM119 ou "
                    "MB59. Use quando o usuário pedir para importar/carregar uma planilha já baixada do SAP "
                    "(contingência). {\"type\":\"find_sap_exports\"}"
                ),
                "import_sap_file": (
                    "Somente administradores. Prepara a importação contingencial de uma planilha listada por "
                    "find_sap_exports: {\"type\":\"import_sap_file\",\"file_name\":\"nome.xlsx\",\"period\":\"AAAA-MM\","
                    "\"transaction\":\"ZMM119|MB59\" (opcional, é detectada),\"as_of\":\"data-base da ZMM119 (opcional)\"}. "
                    "Não importa nada: registra uma pending_sap_confirmation e devolve o resumo. Depois use confirm_sap "
                    "ou cancel_sap, como na extração."
                ),
                "documentation_search": "Busca na Documentação técnica (especificação) os trechos, seções e páginas sobre um assunto: {\"type\":\"documentation_search\",\"query\":\"termos\"}. Use para orientar correções e indicar onde saber mais.",
                "health_center": "Lê todos os indicadores do Health Center (nível, status, detalhe e como corrigir) da competência.",
                "inventory_gaps": "Conta, por campo enriquecido, as linhas da Base de Estoque sem preenchimento (All Brazil, PASSO A PASSO e Mapping), com valor fiscal e causa provável.",
                "mapping_gaps": "Lista os centros da competência sem regra em Planta e local ou em Status da operação, e os locais/status já usados no Mapping.",
                "settings_overview": "Somente administradores. Lê Configurações: acessos e perfis, competências, ponte do Drive, backup e preferências de notificação.",
                "reprocess_enrichment": "Somente administradores. Prepara o reprocessamento dos joins da competência (All Brazil, PASSO A PASSO e Mapping): {\"type\":\"reprocess_enrichment\",\"period\":\"AAAA-MM\"}. Executa só após confirm_sap.",
                "save_mapping_rule": "Somente administradores. Prepara a inclusão/alteração de uma regra de Mapping: {\"type\":\"save_mapping_rule\",\"group\":\"location|operation_status|lifecycle|aging\",\"key_value\":\"chave\",\"value_1\":\"...\",\"value_2\":\"...\"}. location: key_value=Planta, value_1=Local anterior, value_2=Local atual; operation_status: key_value=Planta, value_1=STATUS OPERAÇÃO (ATIVO/BAIXADOS), value_2=Observação. Executa só após confirm_sap e recalcula todas as competências.",
                "sync_bridge_now": "Somente administradores. Prepara a sincronização imediata da ponte do Drive. Executa só após confirm_sap.",
                "backup_now": "Somente administradores. Prepara um backup imediato do banco. Executa só após confirm_sap.",
                "set_backup_schedule": "Somente administradores. Prepara ativar/desativar o backup programado e a frequência, sem trocar a pasta: {\"type\":\"set_backup_schedule\",\"enabled\":true,\"frequency\":\"daily|weekly|monthly\"}. Executa só após confirm_sap.",
                "save_user_access": "Somente administradores. Prepara cadastro/alteração de acesso: {\"type\":\"save_user_access\",\"email\":\"...\",\"role\":\"user|admin\",\"pages\":[\"overview\",\"inventory\",\"sap\",\"all-brazil\",\"mapping\",\"governance\",\"health\",\"agent\",\"docs\"]}. Executa só após confirm_sap.",
                "disable_user_access": "Somente administradores. Prepara a desativação de um acesso (não exclui): {\"type\":\"disable_user_access\",\"email\":\"...\"}. Executa só após confirm_sap.",
                "set_notification_preferences": "Prepara as preferências de notificação deste computador: enabled, sound, sap, uploads, optimus, bridge, backup, connectivity (true/false). Executa só após confirm_sap.",
                "set_interface_preferences": "Prepara Interface e experiência deste computador: density (compact|comfortable), default_page_size, animations_enabled, chart_animations_enabled, card_animations_enabled. Executa só após confirm_sap.",
                "not_available_to_optimus": "Excluir competência, excluir usuário, restaurar backup, trocar a pasta do Drive e o instalador são feitos só pelas páginas, por um administrador; oriente o caminho em Configurações quando pedirem.",
                "confirm_sap": "Confirma semanticamente a pending_sap_confirmation atual (extração SAP, importação de planilha ou qualquer ação preparada pelas ferramentas acima) usando o confirmation_id fornecido no contexto. Só use quando a mensagem mais recente do usuário confirmar a execução.",
                "cancel_sap": "Cancela semanticamente a pending_sap_confirmation atual usando o confirmation_id fornecido no contexto. Só use quando a mensagem mais recente do usuário cancelar ou desistir da execução.",
            },
            "insights": [
                dict(zip(["code", "severity", "title", "description", "amount", "evidence"], row, strict=True))
                for row in insights
            ],
        }

    def _n8n_text(value: object) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            for item in value:
                text = _n8n_text(item)
                if text:
                    return text
            return ""
        if isinstance(value, dict):
            for key in ("output", "response", "answer", "text", "message", "generations"):
                if key in value:
                    text = _n8n_text(value[key])
                    if text:
                        return text
        return ""

    def _extract_local_action(value: object) -> dict[str, object] | None:
        text = _n8n_text(value)
        start_marker = "[[OPS_ACTION]]"
        end_marker = "[[/OPS_ACTION]]"
        start = text.find(start_marker)
        end = text.find(end_marker, start + len(start_marker)) if start >= 0 else -1
        if start < 0 or end < 0:
            return None
        raw = text[start + len(start_marker):end].strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("O Optimus solicitou uma ferramenta local com JSON inválido.") from exc
        if not isinstance(parsed, dict):
            raise ValueError("A solicitação de ferramenta local precisa ser um objeto JSON.")
        return parsed

    def _execute_local_agent_action(
        action: dict[str, object],
        *,
        period: str,
        user: dict[str, object],
        original_message: str,
        session_id: str,
    ) -> dict[str, object]:
        action_type = str(action.get("type", "")).strip().casefold()
        action_period = str(action.get("period") or period).strip()
        if len(action_period) != 7 or action_period[4] != "-":
            raise ValueError("Competência inválida na ferramenta local.")

        if action_type == "inventory_search":
            q = str(action.get("q") or "").strip()[:120]
            filters = action.get("filters") or {}
            if not isinstance(filters, dict):
                filters = {}
            allowed_keys = {item["key"] for item in inventory_columns()}
            filters = {str(key): str(value) for key, value in filters.items() if str(key) in allowed_keys and value not in (None, "")}
            sort = str(action.get("sort") or "fiscal_total_amount")
            if sort not in allowed_keys and sort != "source_row":
                sort = "fiscal_total_amount"
            direction = str(action.get("direction") or "desc").casefold()
            if direction not in {"asc", "desc"}:
                direction = "desc"
            page_size = max(1, min(int(action.get("page_size") or 50), 100))
            return {
                "type": "inventory_search",
                "request": {"period": action_period, "q": q, "filters": filters, "sort": sort, "direction": direction, "page_size": page_size},
                "result": list_inventory(
                    settings, action_period, 1, page_size, q, sort, direction, filters,
                    bool(action.get("pending_joins", False)),
                ),
            }

        if action_type == "mappings":
            groups = list_mapping_groups(settings)
            return {
                "type": "mappings",
                "result": [list_mapping_rows(settings, str(group["key"])) for group in groups],
            }

        if action_type == "system_manual":
            topics_raw = action.get("topics") or []
            if isinstance(topics_raw, str):
                topics_raw = [topics_raw]
            topics = [str(item)[:120] for item in topics_raw if str(item).strip()][:6] if isinstance(topics_raw, list) else []
            query = str(action.get("query") or "").strip()[:500] or (None if topics else original_message)
            return manual_lookup(topics, query)

        if action_type == "mb59_status":
            return {"type": "mb59_status", "result": mb59_status(settings, action_period)}

        if action_type == "all_brazil_source":
            return {"type": "all_brazil_source", "result": _all_brazil_agent_source(action_period)}

        if action_type == "all_brazil_enrichment_status":
            return {
                "type": "all_brazil_enrichment_status",
                "result": _all_brazil_enrichment_status(action_period),
            }

        if action_type == "all_brazil_catalog":
            year_raw = action.get("year")
            month_raw = action.get("month")
            year = None if year_raw in (None, "") else int(year_raw)
            month = None if month_raw in (None, "") else int(month_raw)
            if month is not None and month not in range(1, 13):
                raise ValueError("Mês inválido para o catálogo All Brazil.")
            limit = max(1, min(int(action.get("limit") or 500), 2000))
            return {
                "type": "all_brazil_catalog",
                "result": list_all_brazil_snapshots(
                    settings,
                    year=year,
                    month=month,
                    limit=limit,
                ),
            }

        if action_type == "all_brazil_search":
            as_of_raw = str(action.get("as_of") or _period_end(action_period).isoformat())
            as_of = date.fromisoformat(as_of_raw)
            material_numbers_raw = action.get("material_numbers") or []
            if isinstance(material_numbers_raw, str):
                material_numbers = [material_numbers_raw]
            elif isinstance(material_numbers_raw, list):
                material_numbers = [str(value) for value in material_numbers_raw]
            else:
                raise ValueError("material_numbers deve ser texto ou lista.")

            return {
                "type": "all_brazil_search",
                "result": query_all_brazil_snapshot(
                    settings,
                    as_of=as_of,
                    material_numbers=material_numbers,
                    q=str(action.get("q") or "")[:200],
                    limit=max(1, min(int(action.get("limit") or 50), 100)),
                ),
            }

        if action_type == "runs":
            return {"type": "runs", "result": _recent_runs_for_agent(action_period, limit=20)}

        if action_type == "sap_status":
            with SAP_JOB_LOCK:
                jobs = sorted(
                    (dict(job) for job in SAP_JOBS.values()),
                    key=lambda job: str(job.get("created_at") or ""),
                    reverse=True,
                )[:4]
                result = jobs[0] if jobs else None
            return {"type": "sap_status", "result": result, "jobs": jobs}

        if action_type == "report_pdf":
            pdf_path = generate_report_pdf(settings, action_period, publish=False, user_email=str(user.get("email") or ""))
            return {
                "type": "report_pdf",
                "ok": True,
                "period": action_period,
                "download_url": f"/api/reports/pdf/download?period={action_period}",
                "file_name": pdf_path.name,
                "size_bytes": pdf_path.stat().st_size,
                "message": "PDF validado e pronto. Apresente o link de download ao usuário.",
            }

        if action_type == "executive_presentation":
            return {
                "type": "executive_presentation",
                "ok": True,
                "result": executive_presentation_payload(action_period),
                "message": (
                    "Payload executivo preparado para criar uma apresentação exportável no Google Slides. "
                    "Use somente estes dados e devolva o link do artefato publicado pelo fluxo."
                ),
            }

        if action_type == "cancel_action":
            action_type = "cancel_sap"
        if action_type == "cancel_sap":
            confirmation_id = str(action.get("confirmation_id") or "").strip()
            with SAP_CONFIRMATION_LOCK:
                pending = SAP_CONFIRMATIONS.get(session_id)
                if pending is None:
                    return {
                        "type": "cancel_sap",
                        "ok": False,
                        "status": "NO_PENDING_CONFIRMATION",
                        "message": "Não existe extração SAP aguardando confirmação nesta sessão.",
                    }
                if not confirmation_id or confirmation_id != str(pending.get("confirmation_id") or ""):
                    return {
                        "type": "cancel_sap",
                        "ok": False,
                        "status": "CONFIRMATION_MISMATCH",
                        "message": "A solicitação pendente mudou. Reavalie o contexto antes de cancelar.",
                    }
                summary = str(pending.get("summary") or "Extração SAP")
                SAP_CONFIRMATIONS.pop(session_id, None)
            mark_offer_resolved(pending)
            return {
                "type": "cancel_sap",
                "ok": True,
                "status": "CANCELLED",
                "summary": summary,
                "message": "Solicitação de extração SAP cancelada. Nenhum comando foi enviado ao SAP.",
            }

        if action_type in {"confirm_sap", "confirm_action"}:
            action_type = "confirm_sap"
            with SAP_CONFIRMATION_LOCK:
                pending_kind = str(((SAP_CONFIRMATIONS.get(session_id) or {}).get("parameters") or {}).get("kind") or "")
            # Preferências do próprio computador valem para qualquer perfil; o resto é de administradores.
            if str(user.get("role", "")) != "admin" and pending_kind not in SELF_SERVICE_ACTION_KINDS:
                return {
                    "type": "confirm_sap",
                    "ok": False,
                    "status": "FORBIDDEN",
                    "error": "A execução SAP é exclusiva de administradores.",
                }

            confirmation_id = str(action.get("confirmation_id") or "").strip()
            with SAP_CONFIRMATION_LOCK:
                pending = SAP_CONFIRMATIONS.get(session_id)
                if pending is None:
                    return {
                        "type": "confirm_sap",
                        "ok": False,
                        "status": "NO_PENDING_CONFIRMATION",
                        "message": "Não existe extração SAP aguardando confirmação nesta sessão.",
                    }
                if not confirmation_id or confirmation_id != str(pending.get("confirmation_id") or ""):
                    return {
                        "type": "confirm_sap",
                        "ok": False,
                        "status": "CONFIRMATION_MISMATCH",
                        "message": "A confirmação não corresponde à solicitação SAP atualmente pendente.",
                    }
                parameters = dict(pending.get("parameters") or {})
                summary = str(pending.get("summary") or "Extração SAP")
            mark_offer_resolved(pending)

            if parameters.get("kind") == "upload":
                # Importação contingencial de planilha já baixada: mesmo processo do upload da página.
                return _start_agent_upload(parameters, summary, session_id, confirmation_id)
            if parameters.get("kind") in AGENT_ACTION_KINDS:
                return _run_confirmed_action(parameters, summary, session_id, confirmation_id, user)

            transaction = str(parameters.get("transaction") or "").upper()
            sap_period = str(parameters.get("period") or "")
            if transaction == "ZMM119":
                sap_request = SapRunRequest(
                    transaction="ZMM119",
                    period=sap_period,
                    connection_name=str(parameters.get("connection_name") or ""),
                    as_of=date.fromisoformat(str(parameters["as_of"])),
                    fisia_only=True,
                )
            elif transaction == "MB59":
                sap_request = SapRunRequest(
                    transaction="MB59",
                    period=sap_period,
                    connection_name=str(parameters.get("connection_name") or ""),
                    variant=str(parameters["variant"]),
                    date_from=date.fromisoformat(str(parameters["date_from"])),
                    date_to=date.fromisoformat(str(parameters["date_to"])),
                    fisia_only=True,
                )
            else:
                return {
                    "type": "confirm_sap",
                    "ok": False,
                    "status": "INVALID_PENDING_CONFIRMATION",
                    "error": "A solicitação SAP pendente está inválida e não será executada.",
                }

            job = start_sap(sap_request)
            with SAP_CONFIRMATION_LOCK:
                current = SAP_CONFIRMATIONS.get(session_id)
                if current and str(current.get("confirmation_id") or "") == confirmation_id:
                    SAP_CONFIRMATIONS.pop(session_id, None)

            return {
                "type": "confirm_sap",
                "ok": True,
                "status": "STARTED",
                "summary": summary,
                "result": job,
            }

        if action_type == "run_sap":
            if str(user.get("role", "")) != "admin":
                return {
                    "type": "run_sap",
                    "ok": False,
                    "status": "FORBIDDEN",
                    "error": "A execução SAP é exclusiva de administradores.",
                }

            transaction = str(action.get("transaction") or "").strip().upper()
            if transaction not in {"ZMM119", "MB59"}:
                return {
                    "type": "run_sap",
                    "ok": False,
                    "status": "MISSING_PARAMETERS",
                    "missing_parameters": ["transaction"],
                    "error": "Informe qual transação deve ser executada: ZMM119 ou MB59.",
                }

                        # O Optimus interpreta semanticamente a solicitação.
            # O backend aplica defaults determinísticos da competência
            # e aceita datas em formato técnico ou brasileiro.
            sap_period = str(action.get("period") or period).strip()

            if not re.fullmatch(r"\d{4}-\d{2}", sap_period):
                return {
                    "type": "run_sap",
                    "ok": False,
                    "status": "MISSING_PARAMETERS",
                    "transaction": transaction,
                    "missing_parameters": ["period"],
                    "required_parameters": {
                        "period": "Competência",
                    },
                    "message": (
                        "A competência não foi identificada. "
                        "Pergunte somente qual competência deve ser utilizada."
                    ),
                }

            try:
                period_end = _period_end(sap_period)
                year, month = map(int, sap_period.split("-"))

                if transaction == "ZMM119":
                    as_of_value = _parse_agent_date(
                        action.get("as_of"),
                        sap_period,
                        period_end,
                    )

                    parameters = {
                        "transaction": "ZMM119",
                        "period": sap_period,
                        "as_of": as_of_value.isoformat(),
                        "connection_name": str(
                            action.get("connection_name") or ""
                        ).strip(),
                    }

                    summary = (
                        f"ZMM119 | Competência {sap_period} | "
                        f"Data-base contábil "
                        f"{as_of_value.strftime('%d/%m/%Y')}"
                    )

                else:
                    date_from_value = _parse_agent_date(
                        action.get("date_from"),
                        sap_period,
                        date(year, month, 1),
                    )

                    date_to_value = _parse_agent_date(
                        action.get("date_to"),
                        sap_period,
                        period_end,
                    )

                    variant_raw = (
                        str(action.get("variant") or "BASE GR").strip()
                        or "BASE GR"
                    )

                    if date_to_value < date_from_value:
                        return {
                            "type": "run_sap",
                            "ok": False,
                            "status": "INVALID_PARAMETERS",
                            "error": (
                                "A data final da MB59 não pode ser "
                                "anterior à data inicial."
                            ),
                        }

                    parameters = {
                        "transaction": "MB59",
                        "period": sap_period,
                        "date_from": date_from_value.isoformat(),
                        "date_to": date_to_value.isoformat(),
                        "variant": variant_raw,
                        "connection_name": str(
                            action.get("connection_name") or ""
                        ).strip(),
                    }

                    summary = (
                        f"MB59 | Competência {sap_period} | "
                        f"Período {date_from_value.strftime('%d/%m/%Y')} a "
                        f"{date_to_value.strftime('%d/%m/%Y')} | "
                        f"Variante {variant_raw}"
                    )

            except ValueError as exc:
                return {
                    "type": "run_sap",
                    "ok": False,
                    "status": "INVALID_PARAMETERS",
                    "error": str(exc),
                }

            confirmation_id = str(uuid.uuid4())
            with SAP_CONFIRMATION_LOCK:
                SAP_CONFIRMATIONS[session_id] = {
                    "confirmation_id": confirmation_id,
                    "parameters": parameters,
                    "summary": summary,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }

            return {
                "type": "run_sap",
                "ok": False,
                "status": "CONFIRMATION_REQUIRED",
                "confirmation_id": confirmation_id,
                "transaction": transaction,
                "parameters": parameters,
                "summary": summary,
                "message": (
                    "Apresente o resumo e aguarde a decisão do usuário. "
                    "Na próxima mensagem, interprete semanticamente a intenção no contexto "
                    "desta solicitação pendente. Se confirmar, use confirm_sap; se cancelar, "
                    "use cancel_sap; se alterar parâmetros, use run_sap com os valores revisados."
                ),
            }

        if action_type in {"find_sap_exports", "import_sap_file"} and str(user.get("role", "")) != "admin":
            return {
                "type": action_type,
                "ok": False,
                "status": "FORBIDDEN",
                "error": "A importação de planilhas do SAP é exclusiva de administradores.",
            }

        if action_type == "find_sap_exports":
            candidates = find_sap_export_candidates(settings)
            exports = [item for item in candidates if item["transaction"]]
            return {
                "type": "find_sap_exports",
                "ok": True,
                "days": SAP_EXPORT_SEARCH_DAYS,
                "files": [
                    {**item, "size_mb": round(int(item["size_bytes"]) / 1048576, 1)} for item in exports
                ],
                "other_xlsx_ignored": len(candidates) - len(exports),
                "searched_folders": [str(folder) for folder in export_search_folders()],
                "message": (
                    "Apresente as planilhas encontradas (nome, transação, data de gravação e tamanho). Se o usuário "
                    "não disse qual importar ou a competência, pergunte. Depois use import_sap_file. Se a lista "
                    "estiver vazia, oriente a salvar o XLSX exportado do SAP em Downloads ou usar o upload "
                    "contingencial da página Extrações SAP."
                ),
            }

        if action_type == "import_sap_file":
            wanted = str(action.get("file_name") or action.get("path") or "").strip()
            if not wanted:
                return {
                    "type": "import_sap_file",
                    "ok": False,
                    "status": "MISSING_PARAMETERS",
                    "missing_parameters": ["file_name"],
                    "message": "Informe qual planilha importar. Use find_sap_exports para listar as disponíveis.",
                }
            wanted_key = wanted.casefold()
            candidates = find_sap_export_candidates(settings)
            chosen = next(
                (item for item in candidates
                 if str(item["path"]).casefold() == wanted_key or str(item["file_name"]).casefold() == Path(wanted).name.casefold()),
                None,
            )
            if chosen is None:
                return {
                    "type": "import_sap_file",
                    "ok": False,
                    "status": "FILE_NOT_FOUND",
                    "message": (
                        f"A planilha {wanted} não está entre as planilhas recentes das pastas verificadas. "
                        "Use find_sap_exports para listar as disponíveis."
                    ),
                }
            detected = chosen["transaction"]
            requested = str(action.get("transaction") or "").strip().upper() or None
            if detected is None or (requested and requested != detected):
                return {
                    "type": "import_sap_file",
                    "ok": False,
                    "status": "WRONG_TRANSACTION",
                    "message": wrong_transaction_message(requested or "ZMM119", detected),
                }
            sap_period = str(action.get("period") or period).strip()
            if not re.fullmatch(r"\d{4}-\d{2}", sap_period):
                return {
                    "type": "import_sap_file",
                    "ok": False,
                    "status": "MISSING_PARAMETERS",
                    "missing_parameters": ["period"],
                    "message": "Pergunte somente para qual competência a planilha deve ser importada.",
                }
            try:
                as_of_value = (
                    _parse_agent_date(action.get("as_of"), sap_period, _period_end(sap_period))
                    if detected == "ZMM119" else None
                )
            except ValueError as exc:
                return {"type": "import_sap_file", "ok": False, "status": "INVALID_PARAMETERS", "error": str(exc)}
            parameters, summary = build_upload_pending(chosen, sap_period, as_of_value)
            confirmation_id = str(uuid.uuid4())
            with SAP_CONFIRMATION_LOCK:
                SAP_CONFIRMATIONS[session_id] = {
                    "confirmation_id": confirmation_id,
                    "parameters": parameters,
                    "summary": summary,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }
            return {
                "type": "import_sap_file",
                "ok": False,
                "status": "CONFIRMATION_REQUIRED",
                "confirmation_id": confirmation_id,
                "transaction": detected,
                "parameters": parameters,
                "summary": summary,
                "message": (
                    "Apresente o resumo e aguarde a decisão do usuário. Se confirmar, use confirm_sap; se cancelar, "
                    "use cancel_sap; se mudar a planilha ou a competência, use import_sap_file de novo."
                ),
            }

        # ---------------- consultas para orientar (sem alterar nada)
        if action_type == "documentation_search":
            query = str(action.get("query") or original_message or "").strip()[:200]
            return {"type": "documentation_search", "ok": True, "query": query,
                    "matches": documentation_matches(settings, query, limit=5)}
        if action_type == "health_center":
            with SAP_JOB_LOCK:
                jobs = sorted((dict(job) for job in SAP_JOBS.values()), key=lambda job: str(job.get("created_at") or ""), reverse=True)[:4]
            return {"type": "health_center", "ok": True, "result": system_health(
                settings, action_period, user, os.getenv("N8N_CHAT_URL", "").strip(), jobs,
                backup=backup_status() if str(user.get("role", "")) == "admin" else None,
            )}
        if action_type == "inventory_gaps":
            return {"type": "inventory_gaps", "ok": True, "result": inventory_gaps(settings, action_period)}
        if action_type == "mapping_gaps":
            return {"type": "mapping_gaps", "ok": True, "result": mapping_gaps(settings, action_period)}

        if action_type in AGENT_ACTION_TOOLS and str(user.get("role", "")) != "admin" and action_type not in SELF_SERVICE_TOOLS:
            return {"type": action_type, "ok": False, "status": "FORBIDDEN",
                    "error": "Esta ação é exclusiva de administradores."}

        if action_type == "settings_overview":
            payload = settings_payload()
            return {"type": "settings_overview", "ok": True, "result": {
                **payload,
                "notifications": notifier.status(),
                "bridge": bridge_status(settings) if bridge_enabled(settings) else {"enabled": False},
                "backup": backup_status(),
            }}

        # ---------------- ações: só preparam a pendência; executam após confirm_sap
        def prepare(kind_parameters: dict[str, object], summary: str) -> dict[str, object]:
            confirmation_id = str(uuid.uuid4())
            with SAP_CONFIRMATION_LOCK:
                SAP_CONFIRMATIONS[session_id] = {
                    "confirmation_id": confirmation_id,
                    "parameters": kind_parameters,
                    "summary": summary,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }
            return {
                "type": action_type,
                "ok": False,
                "status": "CONFIRMATION_REQUIRED",
                "confirmation_id": confirmation_id,
                "parameters": kind_parameters,
                "summary": summary,
                "message": (
                    "Nada foi alterado. Apresente o resumo e aguarde a decisão do usuário: confirmar -> confirm_sap; "
                    "desistir -> cancel_sap; mudar algum valor -> chame esta ferramenta de novo."
                ),
            }

        def invalid(message: str) -> dict[str, object]:
            return {"type": action_type, "ok": False, "status": "INVALID_PARAMETERS", "error": message}

        if action_type == "reprocess_enrichment":
            if not re.fullmatch(r"\d{4}-\d{2}", action_period):
                return invalid("Competência inválida.")
            return prepare({"kind": "reprocess", "period": action_period},
                           f"Reprocessar os joins (All Brazil, PASSO A PASSO e Mapping) da Base de Estoque {action_period}. "
                           "A ZMM119 já carregada é preservada.")

        if action_type == "save_mapping_rule":
            group = str(action.get("group") or "").strip()
            key_value = str(action.get("key_value") or action.get("key") or "").strip()
            try:
                listing = list_mapping_rows(settings, group)
            except ValueError:
                return invalid("Grupo de Mapping inválido. Use aging, location, lifecycle ou operation_status.")
            if not key_value:
                return invalid("Informe a chave da regra (key_value), por exemplo o centro.")
            value_1 = None if action.get("value_1") in (None, "") else str(action.get("value_1")).strip()[:500]
            value_2 = None if action.get("value_2") in (None, "") else str(action.get("value_2")).strip()[:500]
            existing = next((row for row in listing["rows"] if str(row["key_value"]).strip() == key_value), None)
            columns = list(listing["group"]["columns"])
            describe = f"{columns[0]} {key_value}: {columns[1]} = {value_1 or '(vazio)'}; {columns[2]} = {value_2 or '(vazio)'}"
            return prepare(
                {"kind": "mapping", "group": group, "key_value": key_value, "value_1": value_1, "value_2": value_2,
                 "mapping_id": existing["mapping_id"] if existing else None},
                f"Mapping · {listing['group']['title']}: {'alterar' if existing else 'nova'} regra — {describe}. "
                "Todas as competências são recalculadas, como na página Mapping.",
            )

        if action_type == "sync_bridge_now":
            if not bridge_enabled(settings):
                return invalid("A ponte de dados pelo Drive está desativada nesta instalação.")
            return prepare({"kind": "bridge_sync"},
                           "Sincronizar agora a ponte de dados do Drive: receber competências mais novas e enviar as desta máquina.")

        if action_type == "backup_now":
            return prepare({"kind": "backup"},
                           "Gerar agora o backup completo do banco na pasta configurada; o backup anterior desta máquina é "
                           "substituído depois que o novo for conferido.")

        if action_type == "set_backup_schedule":
            enabled = action.get("enabled")
            if not isinstance(enabled, bool):
                return invalid("Informe enabled como true (ativar) ou false (desativar).")
            frequency = str(action.get("frequency") or read_preferences().get("backup_frequency") or "daily").strip().lower()
            if frequency not in {"daily", "weekly", "monthly"}:
                return invalid("Frequência inválida: use daily (diária), weekly (semanal) ou monthly (mensal).")
            labels = {"daily": "diária", "weekly": "semanal", "monthly": "mensal"}
            folder = str(backup_status().get("effective_folder") or "")
            return prepare({"kind": "backup_schedule", "enabled": enabled, "frequency": frequency},
                           (f"Backup programado: ativar, frequência {labels[frequency]}, na pasta {folder} (a pasta não muda; "
                            "cada novo backup substitui o anterior desta máquina).") if enabled else
                           "Backup programado: desativar (os backups já feitos continuam onde estão).")

        if action_type == "save_user_access":
            try:
                email = normalize_corporate_email(settings, str(action.get("email") or ""))
                role, pages = sanitize_role_pages(str(action.get("role") or "user"), list(action.get("pages") or []))
            except ValueError as exc:
                return invalid(str(exc))
            with connect(settings.path("database")) as connection:
                exists = connection.execute("select 1 from allowed_users where email=?", [email]).fetchone()
            pages_text = "todas as páginas" if role == "admin" else ", ".join(pages) or "somente as obrigatórias"
            return prepare({"kind": "access_save", "email": email, "role": role, "pages": pages},
                           f"Acesso corporativo: {'atualizar' if exists else 'cadastrar'} {email} como "
                           f"{'Administrador' if role == 'admin' else 'Usuário'} ({pages_text}). Vale em todas as máquinas "
                           "pela lista central de acessos.")

        if action_type == "disable_user_access":
            email = str(action.get("email") or "").strip().lower()
            if email in BOOTSTRAP_ADMINS:
                return invalid("O administrador inicial não pode ser desativado.")
            if email == str(user.get("email") or "").lower():
                return invalid("Você não pode desativar o próprio acesso.")
            with connect(settings.path("database")) as connection:
                exists = connection.execute("select 1 from allowed_users where email=?", [email]).fetchone()
            if not exists:
                return invalid(f"Usuário {email} não encontrado.")
            return prepare({"kind": "access_disable", "email": email},
                           f"Acesso corporativo: desativar {email} (o login fica bloqueado em todas as máquinas; nada é excluído).")

        if action_type == "set_notification_preferences":
            try:
                values = NotificationPreferencesRequest(**{key: action[key] for key in NotificationPreferencesRequest.model_fields if key in action}).model_dump(exclude_none=True)
            except Exception as exc:  # noqa: BLE001 - validação do modelo
                return invalid(str(exc))
            if not values:
                return invalid("Informe ao menos uma preferência: enabled, sound, sap, uploads, optimus, bridge, backup ou connectivity.")
            return prepare({"kind": "notification_prefs", "values": values},
                           "Notificações deste computador: " + ", ".join(f"{key} = {'ligado' if value else 'desligado'}" for key, value in values.items()) + ".")

        if action_type == "set_interface_preferences":
            try:
                values = InterfacePreferencesRequest(**{key: action[key] for key in InterfacePreferencesRequest.model_fields if key in action}).model_dump(exclude_none=True)
            except Exception as exc:  # noqa: BLE001 - validação do modelo
                return invalid(str(exc))
            if not values:
                return invalid("Informe ao menos uma preferência: density, default_page_size, animations_enabled, chart_animations_enabled ou card_animations_enabled.")
            return prepare({"kind": "interface_prefs", "values": values},
                           "Interface e experiência: " + ", ".join(f"{key} = {value}" for key, value in values.items()) + ".")

        raise ValueError(f"Ferramenta local não reconhecida: {action_type or '(vazia)'}")

    def _run_confirmed_action(
        parameters: dict[str, object], summary: str, session_id: str, confirmation_id: str, user: dict[str, object],
    ) -> dict[str, object]:
        """Executa, após o "sim", a ação preparada pelo Optimus — pelos mesmos caminhos das páginas."""
        kind = str(parameters.get("kind") or "")
        actor = SimpleNamespace(state=SimpleNamespace(user=user))
        with SAP_CONFIRMATION_LOCK:
            current = SAP_CONFIRMATIONS.get(session_id)
            if current and str(current.get("confirmation_id") or "") == confirmation_id:
                SAP_CONFIRMATIONS.pop(session_id, None)
        try:
            if kind == "reprocess":
                result: object = start_inventory_enrichment(ImportRequest(period=str(parameters["period"])))
            elif kind == "mapping":
                row = MappingRowRequest(key_value=str(parameters["key_value"]), value_1=parameters.get("value_1"), value_2=parameters.get("value_2"))
                if parameters.get("mapping_id"):
                    result = update_mapping_row(str(parameters["group"]), int(parameters["mapping_id"]), row)
                else:
                    result = create_mapping_row(str(parameters["group"]), row)
                optimus_watch_trigger()
            elif kind == "bridge_sync":
                result = post_bridge_sync()
            elif kind == "backup":
                result = run_backup_now(force=True)
            elif kind == "backup_schedule":
                with connect(settings.path("database")) as connection:
                    for key, value in (("backup_enabled", bool(parameters["enabled"])), ("backup_frequency", str(parameters["frequency"]))):
                        connection.execute(
                            """insert into system_settings(setting_key, setting_value, updated_at) values (?, ?, current_timestamp)
                               on conflict(setting_key) do update set setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
                            [key, json.dumps(value)],
                        )
                result = backup_status()
            elif kind == "access_save":
                add_allowed_user(AccessUserRequest(email=str(parameters["email"]), role=str(parameters["role"]),
                                                   pages=list(parameters.get("pages") or [])), actor)
                result = {"email": parameters["email"], "role": parameters["role"], "pages": parameters.get("pages")}
            elif kind == "access_disable":
                disable_allowed_user(str(parameters["email"]), actor)
                result = {"email": parameters["email"], "active": False}
            elif kind == "notification_prefs":
                notifier.save_preferences(dict(parameters.get("values") or {}))
                result = notifier.status()
            elif kind == "interface_prefs":
                result = put_interface_preferences(InterfacePreferencesRequest(**dict(parameters.get("values") or {})))
            else:
                raise ValueError(f"Ação desconhecida: {kind}")
        except HTTPException as exc:
            return {"type": "confirm_sap", "ok": False, "status": "FAILED", "summary": summary, "error": str(exc.detail)}
        except Exception as exc:  # noqa: BLE001 - devolve o erro ao agente, que explica ao usuário
            return {"type": "confirm_sap", "ok": False, "status": "FAILED", "summary": summary, "error": str(exc)}
        compact = json.loads(json.dumps(result, ensure_ascii=False, default=str))
        if isinstance(compact, dict):
            compact = {key: value for key, value in compact.items() if key not in {"users", "access_users", "indicators"}}
        return {"type": "confirm_sap", "ok": True, "status": "DONE" if kind != "reprocess" else "STARTED",
                "summary": summary, "result": compact}

    def _start_agent_upload(
        parameters: dict[str, object], summary: str, session_id: str, confirmation_id: str,
    ) -> dict[str, object]:
        """Confirmação de import_sap_file: copia a planilha e usa o mesmo job do upload contingencial."""
        source = Path(str(parameters.get("source_path") or ""))
        transaction = str(parameters.get("transaction") or "").upper()
        sap_period = str(parameters.get("period") or "")
        file_name = str(parameters.get("file_name") or source.name)
        try:
            stat = source.stat()
        except OSError:
            stat = None
        if (
            stat is None
            or stat.st_size != int(parameters.get("size_bytes") or -1)
            or datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds") != str(parameters.get("modified_at"))
        ):
            with SAP_CONFIRMATION_LOCK:
                SAP_CONFIRMATIONS.pop(session_id, None)
            return {
                "type": "confirm_sap",
                "ok": False,
                "status": "FILE_CHANGED",
                "message": f"A planilha {file_name} foi movida, apagada ou alterada depois do resumo. Nada foi importado; liste as planilhas de novo.",
            }
        folder = settings.path("landing") / "uploads"
        folder.mkdir(parents=True, exist_ok=True)
        staging = folder / f"{transaction}_{sap_period}_{uuid.uuid4().hex[:12]}.upload.xlsx"
        shutil.copyfile(source, staging)
        as_of_raw = parameters.get("as_of")
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "transaction": transaction,
            "period": sap_period,
            "source": "upload",
            "file_name": file_name,
            "status": "UPLOAD_RECEIVED",
            "progress": SAP_STAGE_PROGRESS["UPLOAD_RECEIVED"],
            "message": f"Planilha {file_name} enviada pelo Optimus ({stat.st_size / 1048576:.1f} MB).",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "parameters": {"transaction": transaction, "period": sap_period, "as_of": as_of_raw, "requested_by": "optimus"},
        }
        register_sap_job(job)
        threading.Thread(
            target=run_upload_job,
            args=(job_id, transaction, sap_period, date.fromisoformat(str(as_of_raw)) if as_of_raw else None, staging, file_name),
            daemon=True,
        ).start()
        with SAP_CONFIRMATION_LOCK:
            current = SAP_CONFIRMATIONS.get(session_id)
            if current and str(current.get("confirmation_id") or "") == confirmation_id:
                SAP_CONFIRMATIONS.pop(session_id, None)
        return {
            "type": "confirm_sap",
            "ok": True,
            "status": "STARTED",
            "summary": summary,
            "result": job,
            "message": "Importação iniciada; o andamento aparece em Extrações SAP e o usuário recebe notificação ao terminar.",
        }

    async def _post_to_optimus_n8n(
        n8n_url: str,
        *,
        session_id: str,
        chat_input: str,
        user_email: str,
        period: str,
    ) -> object:
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    n8n_url,
                    json={"action": "sendMessage", "sessionId": session_id, "chatInput": chat_input},
                    headers={
                        "Content-Type": "application/json",
                        "X-Ops-User": user_email,
                        "X-Ops-Source": "ops-contabil-local",
                        "X-Ops-Period": period,
                    },
                )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail="O n8n não respondeu dentro de 90 segundos. Consulte o Health Center para diferenciar lentidão do workflow, rede e VPN.",
            ) from exc
        except httpx.ConnectError as exc:
            raise HTTPException(
                status_code=502,
                detail="Não foi possível estabelecer conexão com o n8n. Consulte os indicadores de rede e n8n no Health Center.",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Falha de comunicação com o n8n ({exc.__class__.__name__}). Consulte o Health Center.",
            ) from exc
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"O n8n retornou erro HTTP {response.status_code}.")
        try:
            return response.json()
        except ValueError:
            return {"output": response.text}


    @app.post("/api/optimus/chat")
    async def optimus_chat(
        payload: OptimusChatRequest,
        request: Request,
    ) -> dict[str, object]:
        try:
            return await _optimus_chat(payload, request)
        except HTTPException as exc:
            # Erro que impede a resposta (limite de ferramentas, n8n fora do ar, tempo
            # esgotado...): notificação do Windows, mesmo com a janela do chat fechada.
            # Sessão expirada/sem permissão não notifica (o usuário já vê a tela de login).
            if exc.status_code not in {401, 403}:
                notifier.notify(
                    "optimus",
                    "Optimus não conseguiu responder",
                    str(exc.detail or "Falha ao consultar o Optimus."),
                    view="agent",
                    tag="optimus",
                )
            raise

    async def _optimus_chat(
        payload: OptimusChatRequest,
        request: Request,
        proactive_event: dict[str, object] | None = None,
    ) -> dict[str, object]:
        n8n_url = os.getenv("N8N_CHAT_URL", "").strip()

        if not n8n_url:
            raise HTTPException(
                status_code=503,
                detail="A URL do Optimus no n8n não está configurada nesta máquina.",
            )

        user = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Sessão corporativa necessária.",
            )

        period = payload.period or default_period()

        # Resposta a um aviso proativo específico: a decisão pendente passa a ser a DESSE aviso.
        replying_to = None
        if payload.reply_to and not proactive_event:
            with OPTIMUS_OFFERS_LOCK:
                offer = next((dict(item) for item in OPTIMUS_OFFERS if item.get("offer_id") == payload.reply_to), None)
            if offer is not None:
                replying_to = {"offer_id": offer["offer_id"], "event": offer.get("event"), "message": offer.get("text")}
                if offer.get("parameters") and not offer.get("resolved"):
                    with SAP_CONFIRMATION_LOCK:
                        current = SAP_CONFIRMATIONS.get(payload.session_id) or {}
                        if current.get("proactive_offer_id") != offer["offer_id"]:
                            SAP_CONFIRMATIONS[payload.session_id] = {
                                "confirmation_id": str(uuid.uuid4()),
                                "parameters": offer["parameters"],
                                "summary": offer.get("summary"),
                                "created_at": offer.get("created_at"),
                                "origin": "optimus_proactive",
                                "proactive_event": offer.get("event"),
                                "proactive_offer_id": offer["offer_id"],
                            }

        try:
            context = build_agent_context(period)
            if replying_to:
                context["replying_to_warning"] = replying_to
            with SAP_CONFIRMATION_LOCK:
                pending = SAP_CONFIRMATIONS.get(payload.session_id)
                context["pending_sap_confirmation"] = (
                    None
                    if pending is None
                    else {
                        "confirmation_id": pending.get("confirmation_id"),
                        "parameters": pending.get("parameters"),
                        "summary": pending.get("summary"),
                        "created_at": pending.get("created_at"),
                        # Oferta proativa: o próprio Optimus avisou no chat a partir deste evento e aguarda o "sim"/"não".
                        "origin": pending.get("origin") or "conversation",
                        "proactive_event": pending.get("proactive_event"),
                    }
                )
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Não foi possível preparar o contexto local da competência {period}: {exc}",
            ) from exc

        try:
            manual_sections = manual_for_question(
                str(proactive_event.get("topic") or "") if proactive_event else payload.message
            )
        except Exception:  # noqa: BLE001 - o manual nunca impede a conversa
            manual_sections = []
        manual_block = (
            "[MANUAL_DO_SISTEMA]\n"
            "Trechos do manual oficial do Estoque Contábil ligados à pergunta. Use-os como fonte para "
            "dúvidas sobre páginas, botões, parâmetros, bases, regras, permissões e rotinas do sistema; "
            "se faltar algum detalhe, peça outras seções com a ferramenta system_manual.\n\n"
            f"{render_sections(manual_sections)}\n"
            "[/MANUAL_DO_SISTEMA]\n\n"
        ) if manual_sections else ""

        if proactive_event:
            # Evento detectado pelo sistema (não é mensagem do usuário): o agente escreve o aviso.
            message_block = (
                "[EVENTO_PROATIVO]\n"
                f"{json.dumps(proactive_event, ensure_ascii=False, default=str)}\n"
                "[/EVENTO_PROATIVO]\n\n"
                "[INSTRUCAO_EVENTO_PROATIVO]\n"
                "Isto NÃO é uma mensagem do usuário: é um fato detectado agora pelo sistema enquanto um administrador "
                "está com o Estoque Contábil aberto. Escreva você mesmo, em português do Brasil, uma mensagem proativa "
                "curta e direta para esse administrador: diga o que aconteceu, o impacto e como corrigir, usando somente "
                "os fatos do evento e do contexto (nunca invente números, arquivos ou centros). Se precisar de mais "
                "detalhes para orientar, consulte as ferramentas locais (system_manual, documentation_search, "
                "health_center, inventory_gaps, mapping_gaps) antes de responder. Se pending_sap_confirmation tiver "
                "origin \"optimus_proactive\", explique a ação preparada e peça confirmação explícita (sim ou não). "
                "Se a correção depender de um valor que só o usuário sabe (por exemplo, o local de um centro no "
                "Mapping), pergunte esse valor; não execute nada sem confirmação. Em connectivity_restored, o sistema "
                "já avisou a queda (notificação do Windows e aviso do Health Center no chat): diga que a conexão voltou, "
                "por quanto tempo ficou fora e a causa, o que ficou parado nesse tempo (Optimus e extrações SAP) e, se "
                "queued_warnings for maior que zero, que os avisos que aguardavam vêm em seguida.\n"
                "[/INSTRUCAO_EVENTO_PROATIVO]\n\n"
            )
        else:
            message_block = (
                "[PERGUNTA_USUARIO]\n"
                f"{payload.message}\n"
                "[/PERGUNTA_USUARIO]\n\n"
            )
        current_input = (
            "[CONTEXTO_OPS_CONTABIL]\n"
            f"{json.dumps(context, ensure_ascii=False, default=str)}\n"
            "[/CONTEXTO_OPS_CONTABIL]\n\n"
            f"{manual_block}"
            f"{message_block}"
            "[REGRA_SAP_CONVERSACIONAL]\n"
            "Se pending_sap_confirmation estiver preenchida, interprete a mensagem atual do usuário "
            "no contexto dessa solicitação pendente, e não como uma conversa nova. "
            "A decisão é semântica, não baseada em palavras específicas. "
            "Se o usuário confirmar a execução, solicite confirm_sap com o confirmation_id pendente. "
            "Se cancelar/desistir, solicite cancel_sap. "
            "Se alterar algum parâmetro, solicite run_sap usando os parâmetros pendentes mais a alteração informada "
            "(quando parameters.kind for \"upload\", a pendência é a importação de uma planilha já baixada: use "
            "import_sap_file com a alteração). "
            "Se a intenção estiver ambígua, faça uma pergunta de esclarecimento e não execute. "
            "Quando origin for \"optimus_proactive\", foi você mesmo que ofereceu essa ação no chat a partir de um "
            "evento proativo (proactive_event): um \"sim\" confirma a oferta e um \"não\" a cancela. "
            "Quando replying_to_warning estiver preenchido no contexto, o usuário clicou em \"Responder\" naquele aviso: "
            "interprete a mensagem como resposta a ESSE aviso (event e message), não aos outros.\n"
            "[/REGRA_SAP_CONVERSACIONAL]"
        )

        user_email = str(user.get("email", ""))

        for _ in range(4):
            n8n_response = await _post_to_optimus_n8n(
                n8n_url,
                session_id=payload.session_id,
                chat_input=current_input,
                user_email=user_email,
                period=period,
            )

            try:
                action = _extract_local_action(n8n_response)
            except ValueError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=str(exc),
                ) from exc

            if action is None:
                return {
                    "ok": True,
                    "session_id": payload.session_id,
                    "period": period,
                    "response": n8n_response,
                }

            try:
                # Em segundo plano: ferramentas como o PDF abrem a própria página do sistema,
                # e o servidor precisa continuar livre para atendê-la.
                tool_result = await run_in_threadpool(
                    _execute_local_agent_action,
                    action,
                    period=period,
                    user=user,
                    original_message=payload.message,
                    session_id=payload.session_id,
                )
            except Exception as exc:
                tool_result = {
                    "type": str(action.get("type", "")),
                    "ok": False,
                    "error": str(exc),
                }

            current_input = (
                "[RESULTADO_FERRAMENTA_LOCAL]\n"
                f"{json.dumps(tool_result, ensure_ascii=False, default=str)}\n"
                "[/RESULTADO_FERRAMENTA_LOCAL]\n\n"
                "[PERGUNTA_ORIGINAL]\n"
                f"{payload.message}\n"
                "[/PERGUNTA_ORIGINAL]\n\n"
                "Analise o resultado da ferramenta. "
                "Se status=MISSING_PARAMETERS, pergunte somente os parâmetros listados, sem completar valores. "
                "Se status=CONFIRMATION_REQUIRED, mostre o resumo e aguarde a próxima mensagem. "
                "A próxima decisão sobre a pendência deve ser interpretada semanticamente pelo Optimus: "
                "confirmar -> confirm_sap; cancelar -> cancel_sap; alterar parâmetros -> run_sap revisado. "
                "Não use listas de palavras para decidir a intenção. "
                "Se status=STARTED, informe que a extração foi iniciada. "
                "Se status=CANCELLED, informe que foi cancelada. "
                "Se precisar de outra ferramenta local, solicite-a pelo protocolo OPS_ACTION. "
                "Caso contrário, responda ao usuário."
            )

        raise HTTPException(
            status_code=502,
            detail="O Optimus excedeu o limite de interações com ferramentas locais.",
        )

    @app.get("/api/agent/context", dependencies=[Depends(require_token)])
    def agent_context(period: str = Query(pattern=r"^\d{4}-\d{2}$")) -> dict[str, object]:
        return build_agent_context(period)

    return app


app = create_app()
