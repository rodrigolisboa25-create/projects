from __future__ import annotations

import calendar
import os
from datetime import date, datetime
from pathlib import Path

from .audit import append_event
from .db import connect
from .inventory import import_inventory_xlsb, import_zmm119_xlsx
from .mappings import apply_mapping_rules
from .mb59 import enrich_inventory_pass_step, import_mb59_xlsx
from .settings import Settings
from .sources.all_brazil import enrich_inventory_from_all_brazil


def run_pipeline(settings: Settings, period: str) -> int:
    parsed = datetime.strptime(period, "%Y-%m")
    as_of = date(parsed.year, parsed.month, calendar.monthrange(parsed.year, parsed.month)[1])
    with connect(settings.path("database")) as connection:
        run_id = connection.execute(
            "insert into pipeline_runs(period, status) values (?, 'RUNNING') returning run_id", [period]
        ).fetchone()[0]
        append_event(settings.path("logs"), "pipeline_started", run_id=run_id, period=period)
        try:
            project_root = Path(os.getenv("OPS_PROJECT_ROOT", settings.root))
            zmm_directory = settings.path("landing") / "zmm119" / period
            zmm_exports = sorted(zmm_directory.glob("*.xlsx"), key=lambda item: item.stat().st_mtime)
            mb59_directory = settings.path("landing") / "mb59" / period
            mb59_exports = sorted(
                mb59_directory.glob("*.xlsx"),
                key=lambda item: item.stat().st_mtime,
            )
            mb59_loaded = None
            if mb59_exports:
                # A Base GR fica indexada antes da posição para que a cascata
                # esteja pronta assim que a ZMM119 terminar de carregar.
                mb59_loaded = import_mb59_xlsx(settings, period, mb59_exports[-1])
            if zmm_exports:
                inventory = import_zmm119_xlsx(settings, period, zmm_exports[-1])
                inventory_source = "ZMM119 extraída do SAP"
            else:
                inventory = import_inventory_xlsb(settings, period, project_root / "Posição de Estoque - FISIA.xlsb")
                inventory_source = "planilha estrutural de exemplo"
            all_brazil = enrich_inventory_from_all_brazil(settings, period, as_of)
            pass_step = enrich_inventory_pass_step(settings, period, as_of)
            apply_mapping_rules(settings, period, as_of)
            mb59_ready = mb59_loaded is not None
            status = "READY_FOR_RECONCILIATION" if mb59_ready else "AWAITING_MB59"
            message = (
                f"Posição carregada ({inventory['rows']} linhas; {inventory_source}). "
                f"All Brazil {all_brazil['snapshot']}: {all_brazil['coverage_pct']}% de cobertura. "
                f"PASSO A PASSO com {sum(pass_step['not_found'].values())} campos não localizados. "
                + (
                    f"MB59 localizada e indexada ({mb59_loaded['lookup_rows']} chaves CE & MAT)."
                    if mb59_loaded
                    else "Aguardando extração MB59 da competência."
                )
            )
            connection.execute("delete from control_results where run_id=?", [run_id])
            connection.executemany(
                """insert into control_results(run_id,control_name,severity,status,expected_value,actual_value,details)
                   values (?,?,?,?,?,?,?)""",
                [
                    [run_id, "inventory_rows", "ERROR", "PASS", ">0", str(inventory["rows"]), inventory_source],
                    [run_id, "all_brazil_coverage", "WARNING", "PASS" if all_brazil["coverage_pct"] >= 95 else "FAIL", ">=95%", str(all_brazil["coverage_pct"]), all_brazil["snapshot"]],
                    [run_id, "pass_step_not_found", "WARNING", "PASS" if not any(pass_step["not_found"].values()) else "FAIL", "0 campos", str(sum(pass_step["not_found"].values())), str(pass_step["not_found"])],
                    [run_id, "mb59_available", "ERROR", "PASS" if mb59_ready else "PENDING", "arquivo da competência", str(mb59_ready), (str(mb59_exports[-1]) if mb59_exports else str(mb59_directory))],
                ],
            )
            connection.execute(
                "update pipeline_runs set status=?, finished_at=current_timestamp, message=? where run_id=?",
                [status, message, run_id],
            )
            append_event(settings.path("logs"), "pipeline_finished", run_id=run_id, period=period, status=status)
            return int(run_id)
        except Exception as exc:
            connection.execute(
                "update pipeline_runs set status='FAILED', finished_at=current_timestamp, message=? where run_id=?",
                [str(exc), run_id],
            )
            append_event(settings.path("logs"), "pipeline_failed", run_id=run_id, error=str(exc))
            raise
