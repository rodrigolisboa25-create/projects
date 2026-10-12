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


def save_deck(settings, deck_id: str, period: str, email: str, updated: str, title: str) -> None:
    import json

    folder = settings.root / "presentations" / deck_id
    folder.mkdir(parents=True)
    deck = f"<!DOCTYPE html><html><body><section class='slide'>{title}</section><script>var x='</script>';</script></body></html>"
    (folder / "v2.html").write_text(deck, encoding="utf-8")
    (folder / "meta.json").write_text(json.dumps({"deck_id": deck_id, "period": period, "version": 2, "title": title,
                                                  "slides": 9, "created_by": email, "updated_at": updated}), encoding="utf-8")


def test_html_report_embeds_the_presentation_before_the_page_but_not_the_pdf(settings, monkeypatch):
    document = "<html><body class='report-doc'><h1>Posição contábil</h1>" + "<svg></svg>" * 200 + "</body></html>"
    pdf = b"%PDF-1.7\n" + b"0" * 4000 + b"\n%%EOF\n"
    monkeypatch.setattr(reporting, "render_dashboard_report", lambda *_args: (document, pdf))
    save_deck(settings, "20261010-100000-aaaaaa", "2026-09", "outro@gruposbf.com.br", "2026-10-10T12:00:00", "Deck de outra pessoa")
    save_deck(settings, "20261010-090000-bbbbbb", "2026-09", "admin@gruposbf.com.br", "2026-10-10T09:00:00", "Meu deck")
    save_deck(settings, "20261010-110000-cccccc", "2026-08", "admin@gruposbf.com.br", "2026-10-10T13:00:00", "Deck de agosto")

    content = reporting.generate_report_html(settings, "2026-09", user_email="admin@gruposbf.com.br").read_text(encoding="utf-8")
    assert content.index('class="ec-deck"') < content.index("Posição contábil")  # antes da Visão e relatórios
    assert "Meu deck" in content and "Deck de agosto" not in content  # a de quem gera, da competência certa
    assert "<\\/script>" in content and content.count("</html>") == 1  # apresentação embutida sem quebrar o HTML
    assert "Abrir em nova aba" in content and "Baixar apresentação" in content

    pdf_path = reporting.generate_report_pdf(settings, "2026-09", user_email="admin@gruposbf.com.br", force=True)
    assert pdf_path.read_bytes() == pdf  # o PDF sai da página, sem a apresentação

    # Sem apresentação da competência: relatório igual ao de antes.
    assert 'class="ec-deck"' not in reporting.generate_report_html(settings, "2026-07", user_email="admin@gruposbf.com.br").read_text(encoding="utf-8")


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
