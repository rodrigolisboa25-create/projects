from __future__ import annotations

import html
import os
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .inventory import dashboard_summary
from .shared_data import shared_root


_PDF_LOCK = threading.Lock()


def _money(value: Any) -> str:
    return "R$ " + f"{float(value or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _number(value: Any) -> str:
    return f"{float(value or 0):,.0f}".replace(",", ".")


def _bars(title: str, rows: list[dict[str, Any]]) -> str:
    maximum = max([abs(float(item.get("value") or 0)) for item in rows] or [1])
    items = "".join(
        f'<div class="bar"><span>{html.escape(str(row.get("label") or "Sem classificação"))}</span>'
        f'<i><b style="width:{max(2, abs(float(row.get("value") or 0)) / maximum * 100):.1f}%"></b></i>'
        f'<strong>{_money(row.get("value"))}</strong></div>'
        for row in rows[:12]
    )
    return f'<section><h2>{html.escape(title)}</h2>{items or "<p>Sem dados.</p>"}</section>'


def _matrix_table(title: str, matrix: dict[str, Any]) -> str:
    rows = list(matrix.get("rows") or [])
    columns = list(matrix.get("columns") or [])
    values = list(matrix.get("values") or [])
    if not rows or not columns:
        return f'<section><h2>{html.escape(title)}</h2><p>Sem dados.</p></section>'
    header = "".join(f"<th>{html.escape(str(column))}</th>" for column in columns) + "<th>Total</th>"
    body: list[str] = []
    column_totals = [0.0] * len(columns)
    for row_index, row_label in enumerate(rows):
        row_values = values[row_index] if row_index < len(values) else []
        numbers = [float(row_values[index] or 0) if index < len(row_values) else 0.0 for index in range(len(columns))]
        column_totals = [total + number for total, number in zip(column_totals, numbers)]
        cells = "".join(f"<td>{_money(number)}</td>" for number in numbers) + f"<td><b>{_money(sum(numbers))}</b></td>"
        body.append(f"<tr><th>{html.escape(str(row_label))}</th>{cells}</tr>")
    # Linha Total: soma por coluna; o total geral é igual ao card Valor fiscal.
    body.append("<tr><th>Total</th>" + "".join(f"<td><b>{_money(total)}</b></td>" for total in column_totals)
                + f"<td><b>{_money(sum(column_totals))}</b></td></tr>")
    return (
        f'<section class="matrix-section"><h2>{html.escape(title)}</h2>'
        f'<div class="matrix-wrap"><table class="matrix"><tr><th></th>{header}</tr>'
        + "".join(body)
        + "</table></div></section>"
    )


def _location_bars(rows: list[dict[str, Any]]) -> str:
    maximum = max([abs(float(item.get("value") or 0)) for item in rows] or [1])
    if not rows:
        return "<section><h2>Local de estoque</h2><p>Sem dados.</p></section>"
    items = "".join(
        (
            f'<div class="location-bar"><span>{html.escape(str(row.get("label") or "Sem classificação"))}</span>'
            f'<i><b style="width:{max(2, abs(float(row.get("value") or 0)) / maximum * 100):.1f}%"></b></i>'
            f'<strong>{_number(row.get("quantity"))} un. · {_money(row.get("value"))}</strong></div>'
        )
        for row in rows[:12]
    )
    return f"<section><h2>Local de estoque</h2>{items}</section>"


def _trend_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(row.get('period') or ''))}</td><td>{_money(row.get('fiscal_value'))}</td><td>{_number(row.get('quantity'))}</td></tr>"
        for row in rows
    )
    return f'<section><h2>Evolução da posição de estoque</h2><table class="summary-table"><tr><th>Competência</th><th>Valor fiscal</th><th>Quantidade livre</th></tr>{body}</table></section>'


def _variance_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(row.get('label') or 'Não informado'))}</td><td>{_money(row.get('current_value'))}</td><td>{_money(row.get('difference'))}</td><td>{_number(row.get('variation_pct'))}%</td></tr>"
        for row in rows[:12]
    )
    return f'<section><h2>Variação por categoria</h2><table class="summary-table"><tr><th>Categoria</th><th>Atual</th><th>Variação</th><th>%</th></tr>{body}</table></section>'


def _pmm_bars(rows: list[dict[str, Any]]) -> str:
    normalized = [
        {"label": row.get("label") or row.get("period"), "value": row.get("pmm") or 0}
        for row in rows
    ]
    return _bars("PMM por competência", normalized)


def _cost_table(composition: dict[str, Any]) -> str:
    rows = [
        ("FOB", composition.get("fob")),
        ("Imposto de importação", composition.get("ii")),
        ("Outros custos", composition.get("others")),
    ]
    total = sum(float(value or 0) for _label, value in rows) or 1
    body = "".join(
        f"<tr><td>{label}</td><td>{_money(value)}</td><td>{float(value or 0) / total * 100:.2f}%</td></tr>"
        for label, value in rows
    )
    return f'<section><h2>Composição do custo fiscal</h2><table class="summary-table"><tr><th>Componente</th><th>Valor</th><th>Participação</th></tr>{body}</table></section>'


def _scatter_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(row.get('label') or row.get('period') or ''))}</td><td>{_money(row.get('fiscal_value'))}</td><td>{_number(row.get('quantity'))}</td><td>{_number(row.get('rows'))}</td></tr>"
        for row in rows[:15]
    )
    return f'<section class="span-two"><h2>Dispersão do estoque livre</h2><table class="summary-table"><tr><th>Agrupamento</th><th>Valor fiscal</th><th>Quantidade livre</th><th>Registros</th></tr>{body}</table></section>'


def report_html(summary: dict[str, Any], period: str) -> str:
    generated = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")
    title = f"Estoque Contábil | Visão e relatórios | {period}"
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>
@page{{size:A4 landscape;margin:10mm}}*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;color:#111;margin:0;background:#fff}}
header{{display:flex;justify-content:space-between;align-items:end;border-bottom:4px solid #005E27;padding-bottom:10px}}h1{{margin:0;color:#005E27;font-size:26px}}header p{{margin:4px 0 0;color:#42584a}}.seal{{background:#005E27;color:#fff;border-radius:8px;padding:9px 14px;font-weight:700}}
.kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:12px 0}}.kpi{{border:4px double #005E27;border-radius:9px;padding:10px;background:#fff;min-height:82px}}.kpi small{{font-weight:800;text-transform:uppercase;color:#234d32}}.kpi b{{font-size:19px;display:block;margin-top:10px}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}}section{{border:2px solid #6ca47a;border-radius:9px;background:#efffd8;padding:10px;break-inside:avoid}}section.span-two{{grid-column:1/-1}}h2{{font-size:15px;margin:0 0 8px;color:#111}}
.bar,.location-bar{{display:grid;grid-template-columns:145px 1fr 145px;align-items:center;gap:7px;font-size:10px;margin:5px 0}}.bar span,.location-bar span{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.bar i,.location-bar i{{height:9px;background:#fff;border:1px solid #8ab99a;border-radius:5px;overflow:hidden}}.bar b,.location-bar b{{display:block;height:100%;background:#F86A2E}}.bar strong,.location-bar strong{{text-align:right}}
.matrix-wrap{{overflow:hidden}}.matrix{{width:100%;border-collapse:collapse;font-size:8px}}.matrix th,.matrix td{{border:1px solid #bed0c2;padding:4px;text-align:right}}.matrix th{{background:#f7fff1;font-weight:700}}.matrix tr th:first-child{{text-align:left;white-space:nowrap}}.matrix td{{background:#fff4ee}}
.summary-table{{width:100%;border-collapse:collapse;font-size:9px}}.summary-table th,.summary-table td{{border-bottom:1px solid #bed0c2;padding:5px;text-align:right}}.summary-table th:first-child,.summary-table td:first-child{{text-align:left}}.summary-table th{{background:#f7fff1}}
footer{{margin-top:9px;color:#526259;font-size:9px;display:flex;justify-content:space-between}}
</style></head><body><header><div><h1>Estoque Contábil · Posição contábil do estoque - Fisia</h1><p>Visão executiva da competência {html.escape(period)}</p></div><div class="seal">Relatório contábil</div></header>
<div class="kpis"><div class="kpi"><small>💰 Valor fiscal</small><b>{_money(summary.get('fiscal_value'))}</b></div><div class="kpi"><small>📦 Utilização livre</small><b>{_number(summary.get('quantity'))}</b></div><div class="kpi"><small>🧾 Materiais</small><b>{_number(summary.get('materials'))}</b></div><div class="kpi"><small>📊 Média PMM</small><b>{_money(summary.get('pmm'))}</b></div><div class="kpi"><small>🌎 Cobertura All Brazil</small><b>{float(summary.get('all_brazil_coverage') or 0):.2f}%</b></div></div>
<div class="grid">{_matrix_table('Lifecycle × Aging', summary.get('lifecycle_aging') or {})}{_matrix_table('Aging for Season', summary.get('aging_for_season') or {})}{_bars('Division Description', summary.get('division') or [])}{_location_bars(summary.get('locations') or [])}{_bars('Valor por centro', summary.get('plants') or [])}{_bars('Origem do material', summary.get('origins') or [])}{_trend_table(summary.get('trend') or [])}{_variance_table(summary.get('division_variance') or [])}{_pmm_bars((summary.get('pmm_breakdowns') or {}).get('period') or [])}{_cost_table(summary.get('cost_composition') or {})}{_scatter_table((summary.get('pmm_breakdowns') or {}).get('period') or [])}</div>
<footer><span>Gerado em {generated}</span><span>Estoque Contábil · Op. Contábeis</span></footer></body></html>'''


# ----------------------------------------------------------------------------
# Relatório com os MESMOS gráficos da página Visão e relatórios
# ----------------------------------------------------------------------------
# O sistema abre a própria página no modo relatório (?modo=relatorio) num Edge invisível,
# com a sessão do usuário que pediu o relatório, espera os gráficos e:
#  - HTML (Share Link): copia o painel já desenhado (SVG + estilos), autônomo;
#  - PDF (Optimus): imprime esse mesmo HTML em A4 paisagem.
# Se o Edge não estiver disponível ou algo falhar, usa o relatório simplificado abaixo.

DASHBOARD_TEMPLATE = Path(__file__).parent / "web" / "templates" / "dashboard.html"
RENDER_TIMEOUT_SECONDS = 120
REPORT_VIEWPORT_WIDTH = 1440


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _session_token(settings: Any, email: str) -> str:
    from .auth import create_session_token
    from .db import connect

    with connect(settings.path("database")) as connection:
        row = connection.execute(
            "select identity_subject from allowed_users where email=? and is_active", [email.strip().lower()]
        ).fetchone()
    if row is None or not row[0]:
        raise RuntimeError("Usuário sem sessão válida para gerar o relatório.")
    return create_session_token(settings, email.strip().lower(), str(row[0]))


def render_dashboard_report(settings: Any, period: str, user_email: str) -> tuple[str, bytes]:
    """Desenha a Visão e relatórios no Edge e devolve (HTML autônomo, PDF)."""
    import base64
    import json
    import urllib.request

    from websockets.sync.client import connect as ws_connect

    from .auth import SESSION_COOKIE

    base = f"http://127.0.0.1:{os.getenv('OPS_PORT', '8765').strip() or '8765'}"
    token = _session_token(settings, user_email)
    debug_port = _free_port()
    with tempfile.TemporaryDirectory(prefix="ops-report-") as temporary:
        temporary_path = Path(temporary)
        process = subprocess.Popen(
            [str(_edge_path()), "--headless=new", f"--remote-debugging-port={debug_port}",
             f"--user-data-dir={temporary_path / 'perfil'}", "--no-first-run", "--disable-extensions",
             "--hide-scrollbars", "--disable-gpu", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            deadline = time.monotonic() + 30
            target = None
            while time.monotonic() < deadline and target is None:
                try:
                    pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json/list", timeout=2))
                    target = next((page for page in pages if page.get("type") == "page"), None)
                except Exception:  # noqa: BLE001 - o Edge ainda está iniciando
                    time.sleep(0.3)
            if target is None:
                raise RuntimeError("O Edge não iniciou para gerar o relatório.")
            with ws_connect(target["webSocketDebuggerUrl"], max_size=256 * 1024 * 1024, open_timeout=15) as socket_:
                counter = [0]

                def command(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
                    counter[0] += 1
                    message_id = counter[0]
                    socket_.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
                    while True:
                        message = json.loads(socket_.recv(timeout=RENDER_TIMEOUT_SECONDS))
                        if message.get("id") == message_id:
                            if "error" in message:
                                raise RuntimeError(f"{method}: {message['error']}")
                            return message.get("result", {})

                def evaluate(expression: str) -> Any:
                    result = command("Runtime.evaluate", {"expression": expression, "returnByValue": True})
                    if "exceptionDetails" in result:
                        raise RuntimeError(str(result["exceptionDetails"])[:300])
                    return result.get("result", {}).get("value")

                command("Network.enable")
                command("Network.setCookie", {"name": SESSION_COOKIE, "value": token, "url": base, "httpOnly": True})
                command("Emulation.setDeviceMetricsOverride",
                        {"width": REPORT_VIEWPORT_WIDTH, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
                command("Page.enable")
                command("Page.navigate", {"url": f"{base}/?modo=relatorio&competencia={period}#overview"})
                ready = ""
                deadline = time.monotonic() + RENDER_TIMEOUT_SECONDS
                while time.monotonic() < deadline:
                    time.sleep(0.5)
                    try:
                        ready = str(evaluate("window.__reportReady||''"))
                    except RuntimeError:
                        ready = ""
                    if ready:
                        break
                if ready != "ok":
                    raise RuntimeError(f"A página não terminou de desenhar o relatório ({ready or 'tempo esgotado'}).")
                document = str(evaluate("buildReportDocument()"))
                if "<svg" not in document:
                    raise RuntimeError("O relatório foi gerado sem gráficos.")
                source = temporary_path / "relatorio.html"
                source.write_text(document, encoding="utf-8")
                command("Page.navigate", {"url": source.as_uri()})
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline and evaluate("document.readyState") != "complete":
                    time.sleep(0.2)
                time.sleep(0.5)
                printed = command("Page.printToPDF", {
                    # A4 paisagem: largura e altura já informadas deitadas.
                    "landscape": False, "printBackground": True, "preferCSSPageSize": False,
                    "paperWidth": 11.69, "paperHeight": 8.27,
                    "marginTop": 0.25, "marginBottom": 0.25, "marginLeft": 0.25, "marginRight": 0.25,
                    "scale": 0.74,
                })
                return document, base64.b64decode(printed["data"])
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def generate_report_html(settings: Any, period: str, publish: bool = False, user_email: str | None = None) -> Path:
    """Gera um relatório HTML autônomo, sem links para o servidor local."""
    summary = dashboard_summary(settings, period)
    if not summary.get("rows"):
        raise ValueError(f"Não há dados publicados para a competência {period}.")
    output = settings.path("output") / "html" / f"Relatorio_Estoque_Contabil_{period}.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    content = None
    if user_email:
        with _PDF_LOCK:
            try:
                content, _pdf = render_dashboard_report(settings, period, user_email)
            except Exception:  # noqa: BLE001 - sem Edge/sessão: relatório simplificado
                content = None
    if content is None:
        content = report_html(summary, period)
    output.write_text(content, encoding="utf-8")
    if not output.is_file() or output.stat().st_size < 1000:
        raise RuntimeError("Não foi possível concluir o relatório HTML.")
    if publish:
        destination = shared_root(settings) / "reports" / period / output.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    return output


def _edge_path() -> Path:
    candidates = [
        Path(os.getenv("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.getenv("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("Microsoft Edge não foi localizado para gerar o PDF.")


def _valid_pdf(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 1000:
        return False
    content = path.read_bytes()
    return content.startswith(b"%PDF-") and b"%%EOF" in content[-4096:]


def generate_report_pdf(settings: Any, period: str, publish: bool = False, force: bool = False,
                        user_email: str | None = None) -> Path:
    output = settings.path("output") / "pdf" / f"Relatorio_Estoque_Contabil_{period}.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    with _PDF_LOCK:
        database = settings.path("database")
        # O PDF guardado só vale se for posterior aos dados e ao layout da página.
        newest_input = max(
            database.stat().st_mtime if database.is_file() else 0,
            DASHBOARD_TEMPLATE.stat().st_mtime if DASHBOARD_TEMPLATE.is_file() else 0,
        )
        if not force and _valid_pdf(output) and output.stat().st_mtime >= newest_input:
            return output
        summary = dashboard_summary(settings, period)
        if not summary.get("rows"):
            raise ValueError(f"Não há dados publicados para a competência {period}.")
        if user_email:
            try:
                _document, pdf_bytes = render_dashboard_report(settings, period, user_email)
                if pdf_bytes.startswith(b"%PDF-"):
                    partial = output.with_suffix(".parcial.pdf")
                    partial.write_bytes(pdf_bytes)
                    os.replace(partial, output)
                    if _valid_pdf(output):
                        if publish:
                            destination = shared_root(settings) / "reports" / period / output.name
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            destination.write_bytes(pdf_bytes)
                        return output
            except Exception:  # noqa: BLE001 - sem Edge/sessão: relatório simplificado
                pass
        if output.exists():
            output.unlink()
        with tempfile.TemporaryDirectory(prefix="ops-report-") as temporary:
            temporary_path = Path(temporary)
            source = temporary_path / "report.html"
            profile = temporary_path / "edge-profile"
            source.write_text(report_html(summary, period), encoding="utf-8")
            result = subprocess.run(
                [str(_edge_path()), "--headless", "--disable-gpu", "--disable-extensions", "--no-first-run", "--allow-file-access-from-files", "--run-all-compositor-stages-before-draw", "--virtual-time-budget=3000", f"--user-data-dir={profile}", "--print-to-pdf-no-header", "--no-pdf-header-footer", f"--print-to-pdf={output}", source.as_uri()],
                capture_output=True, text=True, timeout=90, check=False,
            )
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if output.is_file() and output.stat().st_size >= 1000:
                    break
                time.sleep(0.15)
        if result.returncode != 0 or not _valid_pdf(output):
            raise RuntimeError("Não foi possível concluir o PDF do relatório.")
        pdf_bytes = output.read_bytes()
        if publish:
            destination = shared_root(settings) / "reports" / period / output.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(pdf_bytes)
    return output
