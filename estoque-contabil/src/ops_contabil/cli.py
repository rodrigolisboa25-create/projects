from __future__ import annotations

import os
import platform
import shutil
import sys
import time
import webbrowser
from datetime import date
from pathlib import Path

import typer

from .db import connect
from .extractors.sap_gui import SapGuiRobot
from .inventory import import_inventory_xlsb
from .pipeline import run_pipeline
from .settings import load_settings
from .sources.all_brazil import enrich_inventory_from_all_brazil

app = typer.Typer(help="Ops Contábil")
sap_app = typer.Typer(help="Extrações SAP GUI")
app.add_typer(sap_app, name="sap")


@app.command()
def doctor() -> None:
    """Valida pré-requisitos sem alterar dados."""
    settings = load_settings()
    checks = {
        "Python 64 bits": platform.architecture()[0] == "64bit",
        "Versão Python suportada": (3, 12) <= sys.version_info[:2] < (3, 14),
        "Configuração": True,
        "Microsoft Excel": bool(shutil.which("excel.exe")) or Path(
            os.environ.get("ProgramFiles", "C:/Program Files"), "Microsoft Office/Office16/EXCEL.EXE"
        ).exists(),
        "Pasta de entrada": settings.path("inbox").exists(),
    }
    try:
        with connect(settings.path("database")):
            checks["DuckDB"] = True
    except Exception:
        checks["DuckDB"] = False
    for name, passed in checks.items():
        typer.echo(f"{'OK' if passed else 'FALHA':5}  {name}")
    if not all(checks.values()):
        raise typer.Exit(code=1)


@app.command("run")
def run(period: str = typer.Option(..., help="Competência AAAA-MM")) -> None:
    run_id = run_pipeline(load_settings(), period)
    typer.echo(f"Execução registrada: {run_id}")


@app.command("bootstrap")
def bootstrap(period: str = typer.Option("2026-07", help="Competência da base de exemplo")) -> None:
    """Prepara a grade online; se a fonte não mudou, retorna imediatamente."""
    result = import_inventory_xlsb(load_settings(), period)
    typer.echo(f"Base online: {result['rows']} linhas ({result['status']}).")


@app.command("enrich-all-brazil")
def enrich_all_brazil(
    period: str = typer.Option(..., help="Competência AAAA-MM"),
    as_of: str = typer.Option(..., help="Data-base AAAA-MM-DD"),
) -> None:
    """Seleciona o snapshot do mês, mede o join e enriquece a posição."""
    try:
        parsed_as_of = date.fromisoformat(as_of)
    except ValueError as exc:
        raise typer.BadParameter("Use AAAA-MM-DD na data-base.") from exc
    result = enrich_inventory_from_all_brazil(load_settings(), period, parsed_as_of)
    typer.echo(
        f"All Brazil: {result['matched_keys']}/{result['inventory_keys']} chaves "
        f"({result['coverage_pct']}%)."
    )


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8765),
    open_browser: bool = typer.Option(False, "--open-browser"),
) -> None:
    import uvicorn

    if open_browser:
        import threading

        threading.Timer(1.2, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run("ops_contabil.web.app:app", host=host, port=port, reload=False)


@sap_app.command("zmm119")
def sap_zmm119() -> None:
    settings = load_settings()
    started = time.time()
    with SapGuiRobot(settings.raw["runtime"]["sap_timeout_seconds"]) as robot:
        robot.run_zmm119()
    typer.echo(f"ZMM119 concluída às {date.today().isoformat()} (início {started:.0f}).")


@sap_app.command("mb59")
def sap_mb59(
    date_from: str = typer.Option(..., help="Data inicial AAAA-MM-DD"),
    date_to: str = typer.Option(..., help="Data final AAAA-MM-DD"),
) -> None:
    settings = load_settings()
    variant = settings.raw["sources"]["mb59"].get("variant", "BASE GR")
    try:
        parsed_from = date.fromisoformat(date_from)
        parsed_to = date.fromisoformat(date_to)
    except ValueError as exc:
        raise typer.BadParameter("Use o formato AAAA-MM-DD para as datas.") from exc
    with SapGuiRobot(settings.raw["runtime"]["sap_timeout_seconds"]) as robot:
        robot.run_mb59(parsed_from, parsed_to, variant)
    typer.echo(f"MB59 concluída para {parsed_from} a {parsed_to}.")
