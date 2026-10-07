from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from ops_contabil import reporting

TEMPLATE = Path(reporting.__file__).parent / "web" / "templates" / "dashboard.html"
SUMMARY = {"rows": 10, "kpis": {}, "lifecycle_aging": []}


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, name: str) -> Path:
        if name == "database":
            return self.root / "base.duckdb"
        return self.root / name


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setattr(reporting, "dashboard_summary", lambda _settings, _period: SUMMARY)
    monkeypatch.setattr(reporting, "report_html", lambda _summary, period: f"<html>{'x' * 2000} simplificado {period}</html>")
    return FakeSettings(tmp_path)


def test_dashboard_has_report_mode():
    content = TEMPLATE.read_text(encoding="utf-8")
    assert "modo')==='relatorio'" in content
    assert "function buildReportDocument()" in content
    assert "__reportReady=ok===false?'erro':'ok'" in content
    assert "if(REPORT_MODE)awaitstartReportMode()" in content.replace(" ", "")


def test_html_uses_dashboard_render(settings, monkeypatch):
    document = "<html><body class='report-doc'>" + "<svg></svg>" * 200 + "</body></html>"
    calls = []

    def fake_render(_settings, period, email):
        calls.append((period, email))
        return document, b"%PDF-1.7"

    monkeypatch.setattr(reporting, "render_dashboard_report", fake_render)
    output = reporting.generate_report_html(settings, "2026-09", user_email="admin@gruposbf.com.br")
    assert calls == [("2026-09", "admin@gruposbf.com.br")]
    assert output.read_text(encoding="utf-8") == document


def test_html_falls_back_when_render_fails(settings, monkeypatch):
    def broken(*_args):
        raise RuntimeError("sem Edge")

    monkeypatch.setattr(reporting, "render_dashboard_report", broken)
    output = reporting.generate_report_html(settings, "2026-09", user_email="admin@gruposbf.com.br")
    assert "simplificado 2026-09" in output.read_text(encoding="utf-8")


def test_html_without_user_uses_simplified_report(settings, monkeypatch):
    monkeypatch.setattr(reporting, "render_dashboard_report", lambda *_args: pytest.fail("não deveria renderizar"))
    output = reporting.generate_report_html(settings, "2026-09")
    assert "simplificado" in output.read_text(encoding="utf-8")


def test_pdf_uses_dashboard_render_and_cache(settings, monkeypatch):
    pdf = b"%PDF-1.7\n" + b"0" * 4000 + b"\n%%EOF\n"
    calls = []

    def fake_render(*_args):
        calls.append(1)
        return "<html></html>", pdf

    monkeypatch.setattr(reporting, "render_dashboard_report", fake_render)
    settings.path("database").write_bytes(b"db")
    old = time.time() - 3600
    os.utime(settings.path("database"), (old, old))
    monkeypatch.setattr(reporting, "DASHBOARD_TEMPLATE", settings.root / "dashboard.html")
    (settings.root / "dashboard.html").write_text("layout", encoding="utf-8")
    os.utime(settings.root / "dashboard.html", (old, old))

    output = reporting.generate_report_pdf(settings, "2026-09", user_email="admin@gruposbf.com.br")
    assert output.read_bytes() == pdf
    assert not output.with_suffix(".parcial.pdf").exists()
    reporting.generate_report_pdf(settings, "2026-09", user_email="admin@gruposbf.com.br")
    assert len(calls) == 1  # reaproveitou o PDF válido

    # Layout da página mais novo que o PDF: o relatório é refeito.
    newer = time.time() + 60
    os.utime(settings.root / "dashboard.html", (newer, newer))
    reporting.generate_report_pdf(settings, "2026-09", user_email="admin@gruposbf.com.br")
    assert len(calls) == 2
