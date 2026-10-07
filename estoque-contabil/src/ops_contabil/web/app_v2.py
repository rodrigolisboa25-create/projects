from __future__ import annotations

import calendar
import json
import os
import threading
import time
import uuid
from datetime import date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..db import connect
from ..extractors.sap_gui import SapGuiError, SapGuiRobot
from ..inventory import dashboard_summary, import_inventory_xlsb, import_zmm119_xlsx, inventory_columns, list_inventory
from ..pipeline import run_pipeline
from ..settings import Settings, load_settings
from ..sources.all_brazil import MONTH_NAMES, SNAPSHOT_PATTERN, enrich_inventory_from_all_brazil, resolve_all_brazil, resolve_all_brazil_root


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
    backup_folder: str = Field(default="", max_length=500)
    backup_frequency: str = Field(default="daily", pattern=r"^(daily|weekly|monthly)$")
    backup_retention_days: int = Field(default=90, ge=7, le=3650)


class AccessUserRequest(BaseModel):
    email: str = Field(pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$", max_length=254)


class AllBrazilFolderRequest(BaseModel):
    year: int = Field(ge=2015, le=2100)
    month: int = Field(ge=1, le=12)


SAP_JOBS: dict[str, dict[str, object]] = {}
SAP_JOB_LOCK = threading.Lock()


DEFAULT_SYSTEM_SETTINGS: dict[str, object] = {
    "density": "compact",
    "default_page_size": 50,
    "animations_enabled": True,
    "backup_folder": str(Path(os.getenv("LOCALAPPDATA", Path.home())) / "OpsContabil" / "backup"),
    "backup_frequency": "daily",
    "backup_retention_days": 90,
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="Ops Contábil", version="0.2.0")

    def require_token(
        authorization: str | None = Header(default=None),
        authenticated_email: str | None = Header(default=None, alias="X-Authenticated-User-Email"),
    ) -> None:
        expected = os.getenv("OPS_API_TOKEN")
        if expected and authorization != f"Bearer {expected}":
            raise HTTPException(status_code=401, detail="Token inválido")
        if os.getenv("OPS_ENFORCE_ALLOWLIST", "false").lower() == "true":
            email = (authenticated_email or "").strip().lower()
            with connect(settings.path("database")) as connection:
                allowed = connection.execute(
                    "select 1 from allowed_users where email=? and is_active=true", [email]
                ).fetchone()
            if not allowed:
                raise HTTPException(status_code=403, detail="E-mail não autorizado para o Ops Contábil")

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return (Path(__file__).parent / "templates" / "dashboard.html").read_text(encoding="utf-8")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "application": "Ops Contábil"}

    @app.get("/api/config")
    def client_config() -> dict[str, object]:
        return {
            "n8n_chat_url": os.getenv("N8N_CHAT_URL", ""),
            "default_period": os.getenv("OPS_DEFAULT_PERIOD", "2026-07"),
            "agent_provider": "Google Gemini via n8n",
            "sap_connection_name": os.getenv("SAP_CONNECTION_NAME", ""),
        }

    @app.get("/api/inventory/columns", dependencies=[Depends(require_token)])
    def get_inventory_columns() -> list[dict[str, str]]:
        return inventory_columns()

    @app.get("/api/inventory", dependencies=[Depends(require_token)])
    def get_inventory(
        period: str = Query(default="2026-07", pattern=r"^\d{4}-\d{2}$"),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=10, le=200),
        q: str = Query(default="", max_length=120),
        sort: str = Query(default="source_row", max_length=50),
        direction: str = Query(default="asc", pattern=r"^(asc|desc)$"),
        filters: str = Query(default="{}", max_length=4000),
    ) -> dict[str, object]:
        try:
            column_filters = json.loads(filters)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="Filtros de coluna inválidos") from exc
        if not isinstance(column_filters, dict):
            raise HTTPException(status_code=422, detail="Filtros de coluna devem ser um objeto")
        return list_inventory(settings, period, page, page_size, q, sort, direction, column_filters)

    def settings_payload() -> dict[str, object]:
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
                "select email, is_active, created_at, updated_at from allowed_users order by is_active desc, email"
            ).fetchall()
        return {
            "preferences": values,
            "allowed_users": [
                {
                    "email": row[0],
                    "is_active": bool(row[1]),
                    "created_at": row[2].isoformat() if row[2] else None,
                    "updated_at": row[3].isoformat() if row[3] else None,
                }
                for row in users
            ],
            "access_enforcement": os.getenv("OPS_ENFORCE_ALLOWLIST", "false").lower() == "true",
            "authenticated_email_header": "X-Authenticated-User-Email",
        }

    @app.get("/api/settings", dependencies=[Depends(require_token)])
    def get_system_settings() -> dict[str, object]:
        return settings_payload()

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
    def add_allowed_user(request: AccessUserRequest) -> dict[str, object]:
        email = request.email.strip().lower()
        with connect(settings.path("database")) as connection:
            connection.execute(
                """insert into allowed_users(email, is_active, updated_at)
                   values (?, true, current_timestamp)
                   on conflict(email) do update set is_active=true, updated_at=excluded.updated_at""",
                [email],
            )
        return settings_payload()

    @app.post("/api/settings/access/{email}/disable", dependencies=[Depends(require_token)])
    def disable_allowed_user(email: str) -> dict[str, object]:
        normalized = email.strip().lower()
        with connect(settings.path("database")) as connection:
            connection.execute(
                "update allowed_users set is_active=false, updated_at=current_timestamp where email=?",
                [normalized],
            )
        return settings_payload()

    @app.get("/api/dashboard/summary", dependencies=[Depends(require_token)])
    def get_dashboard_summary(
        period: str = Query(default="2026-07", pattern=r"^\d{4}-\d{2}$")
    ) -> dict[str, object]:
        return dashboard_summary(settings, period)

    @app.post("/api/inventory/import", dependencies=[Depends(require_token)])
    def import_inventory(request: ImportRequest) -> dict[str, object]:
        try:
            return import_inventory_xlsb(settings, request.period, force=request.force)
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
            "selection_rule": "latest_snapshot_on_or_before_as_of",
            "join_key": "LEFT(Posição.Material, 10) = All Brazil.Material Nbr",
        }

    def all_brazil_month_folder(year: int, month: int) -> Path:
        root = resolve_all_brazil_root(settings)
        return root / str(year) / f"{month:02d}. {MONTH_NAMES[month]}"

    @app.get("/api/sources/all-brazil/catalog", dependencies=[Depends(require_token)])
    def all_brazil_catalog() -> dict[str, object]:
        root = resolve_all_brazil_root(settings)
        years: list[dict[str, object]] = []
        current_year = date.today().year
        for year in range(current_year, current_year - 8, -1):
            months: list[dict[str, object]] = []
            for month in range(12, 0, -1):
                folder = all_brazil_month_folder(year, month)
                if not folder.is_dir():
                    continue
                files: list[dict[str, object]] = []
                try:
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
                        "files": files,
                    }
                )
            if months:
                years.append({"year": year, "months": months})
        return {"root": str(root), "years": years}

    @app.post("/api/sources/all-brazil/open-folder", dependencies=[Depends(require_token)])
    def open_all_brazil_folder(request: AllBrazilFolderRequest) -> dict[str, object]:
        folder = all_brazil_month_folder(request.year, request.month)
        root = resolve_all_brazil_root(settings).resolve()
        resolved = folder.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Pasta fora da raiz All Brazil configurada") from exc
        if not resolved.is_dir():
            raise HTTPException(status_code=404, detail=f"Pasta All Brazil não encontrada: {resolved}")
        if os.name != "nt":
            raise HTTPException(status_code=501, detail="A abertura da pasta é suportada no Windows")
        os.startfile(str(resolved))
        return {"ok": True, "path": str(resolved)}

    def run_sap_job(job_id: str, request: SapRunRequest) -> None:
        started = time.time()
        with SAP_JOB_LOCK:
            SAP_JOBS[job_id].update(
                status="STARTING",
                message="Localizando o SAP GUI nesta máquina.",
                started_at=datetime.now().isoformat(timespec="seconds"),
            )

        def report_status(status: str, message: str) -> None:
            with SAP_JOB_LOCK:
                SAP_JOBS[job_id].update(status=status, message=message)

        try:
            timeout = int(settings.raw["runtime"]["sap_timeout_seconds"])
            connection_name = request.connection_name.strip() or os.getenv("SAP_CONNECTION_NAME", "").strip()
            with SapGuiRobot(
                timeout_seconds=timeout,
                connection_name=connection_name,
                status_callback=report_status,
            ) as robot:
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
            if target.exists() and request.transaction == "ZMM119":
                loaded = import_zmm119_xlsx(settings, request.period, target)
                year, month = map(int, request.period.split("-"))
                effective_as_of = request.as_of or date(year, month, calendar.monthrange(year, month)[1])
                enriched = enrich_inventory_from_all_brazil(settings, request.period, effective_as_of)
                result = {
                    "status": "COMPLETED",
                    "message": f"ZMM119 carregada ({loaded['rows']} linhas) e enriquecida pelo All Brazil ({enriched['coverage_pct']}%).",
                    "target_path": str(target),
                }
            elif target.exists():
                result = {
                    "status": "COMPLETED",
                    "message": "MB59 extraída; arquivo pronto para a consolidação da competência.",
                    "target_path": str(target),
                }
            else:
                result = {
                    "status": "ACTION_REQUIRED",
                    "message": "O SAP concluiu a exportação, mas não confirmou o arquivo no destino. Salve o XLSX na pasta indicada e processe a competência.",
                    "target_path": str(target),
                }
        except (SapGuiError, ValueError, TimeoutError) as exc:
            result = {"status": "FAILED", "message": str(exc)}
        except Exception as exc:
            result = {"status": "FAILED", "message": f"Falha não prevista: {exc}"}
        with SAP_JOB_LOCK:
            SAP_JOBS[job_id].update(
                **result,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                duration_seconds=round(time.time() - started, 1),
            )

    @app.post("/api/sap/run", dependencies=[Depends(require_token)])
    def start_sap(request: SapRunRequest) -> dict[str, object]:
        if request.transaction == "MB59" and (request.date_from is None or request.date_to is None):
            raise HTTPException(status_code=422, detail="Informe as datas inicial e final para a MB59.")
        if request.date_from and request.date_to and request.date_to < request.date_from:
            raise HTTPException(status_code=422, detail="A data final não pode ser anterior à inicial.")
        if request.transaction == "MB59" and request.date_from and request.date_to:
            if (
                request.date_from.strftime("%Y-%m") != request.period
                or request.date_to.strftime("%Y-%m") != request.period
            ):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "As datas da MB59 devem pertencer à mesma competência selecionada "
                        f"({request.period})."
                    ),
                )
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "transaction": request.transaction,
            "period": request.period,
            "status": "QUEUED",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "parameters": request.model_dump(mode="json"),
        }
        with SAP_JOB_LOCK:
            SAP_JOBS[job_id] = job
        threading.Thread(target=run_sap_job, args=(job_id, request), daemon=True).start()
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
            return list(reversed([dict(job) for job in SAP_JOBS.values()]))[:20]

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

    @app.get("/api/agent/context", dependencies=[Depends(require_token)])
    def agent_context(period: str = Query(pattern=r"^\d{4}-\d{2}$")) -> dict[str, object]:
        summary = dashboard_summary(settings, period)
        with connect(settings.path("database")) as connection:
            run = connection.execute(
                "select run_id, status from pipeline_runs where period=? order by run_id desc limit 1", [period]
            ).fetchone()
            insights = [] if run is None else connection.execute(
                "select insight_code, severity, title, description, amount, evidence_json from accounting_insights where run_id=? order by severity, abs(amount) desc nulls last",
                [run[0]],
            ).fetchall()
        return {
            "period": period,
            "run_id": None if run is None else run[0],
            "status": "DATA_AVAILABLE" if run is None and summary["rows"] else ("NOT_PROCESSED" if run is None else run[1]),
            "data_policy": "aggregated_read_only",
            "summary": summary,
            "insights": [
                dict(zip(["code", "severity", "title", "description", "amount", "evidence"], row, strict=True))
                for row in insights
            ],
        }

    return app


app = create_app()
