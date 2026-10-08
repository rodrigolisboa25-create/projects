"""Visão e relatórios: botão Mapa mental na página e fora do HTML/PDF dos relatórios."""

from __future__ import annotations

from fastapi.testclient import TestClient

import ops_contabil.web.app as web_app
from test_optimus_import import env  # noqa: F401 - fixture reaproveitada


def test_mindmap_button_and_component_are_served_and_hidden_in_reports(env) -> None:  # noqa: F811
    settings, *_ = env
    html = TestClient(web_app.create_app(settings)).get("/").text
    assert html.count('id="mindmap-btn"') == 1
    # O botão fica à esquerda dos Filtros e do Share Link.
    assert html.index('id="mindmap-btn"') < html.index('id="overview-filter-btn"') < html.index('id="share-html"')
    assert "window.OpsMindMap={open,close,buildTree}" in html
    assert "OpsMindMap.open(state.currentSummary)" in html
    # Nunca aparece no HTML do Share Link nem no PDF (modo relatório).
    assert "body.report-mode .mindmap-btn,body.report-doc .mindmap-btn,body.report-mode .mm-overlay{display:none!important}" in html
