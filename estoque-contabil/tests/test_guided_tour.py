"""Tour guiado: abre sozinho uma única vez por usuário e fica em Configurações para rever."""

from __future__ import annotations

from pathlib import Path

from test_optimus_import import ADMIN, USER, env  # noqa: F401 - fixture reaproveitada

TEMPLATE = Path(__file__).resolve().parents[1] / "src" / "ops_contabil" / "web" / "templates" / "dashboard.html"


def test_tour_is_shown_once_per_user(env) -> None:  # noqa: F811
    _settings, _db, _downloads, client_for, _sent, _replies = env
    admin, admin_csrf = client_for(ADMIN)
    user, user_csrf = client_for(USER)
    assert admin.get("/api/tour").json()["seen"] is False
    assert user.get("/api/tour").json()["seen"] is False

    started = admin.post("/api/tour/seen", headers={"X-CSRF-Token": admin_csrf}, json={"step": 0}).json()
    assert started["seen"] is True and started["finished"] is False and started["seen_at"]
    finished = admin.post("/api/tour/seen", headers={"X-CSRF-Token": admin_csrf}, json={"step": 19, "finished": True}).json()
    assert finished["finished"] is True and finished["seen_at"] == started["seen_at"] and finished["replays"] == 0
    replay = admin.post("/api/tour/seen", headers={"X-CSRF-Token": admin_csrf}, json={"step": 0}).json()
    assert replay["replays"] == 1 and replay["finished"] is True  # rever em Configurações não apaga o histórico

    # Cada usuário tem o seu registro: o perfil Usuário (sem página extra) ainda não viu.
    assert user.get("/api/tour").json()["seen"] is False
    assert user.post("/api/tour/seen", headers={"X-CSRF-Token": user_csrf}, json={"step": 0}).status_code == 200
    assert user.get("/api/tour").json()["seen"] is True
    assert admin.post("/api/tour/seen", json={"step": 0}).status_code in (401, 403)  # exige CSRF


def test_tour_screen_starts_after_loading_and_is_available_in_settings() -> None:
    html = TEMPLATE.read_text(encoding="utf-8")
    assert "await preloadSystem();if(window.opsTour)window.opsTour.auto();" in html
    assert 'id="tour-card"' in html and 'id="tour-replay"' in html
    assert ":not(#tour-card)" in html  # o perfil Usuário também vê o cartão em Configurações
    for view in ("sap", "all-brazil", "mapping", "inventory", "overview", "closing", "governance", "health", "agent", "docs", "settings"):
        assert f"view:'{view}'" in html
    # Visão e relatórios: passo a passo do Mapa mental, dos Filtros e do Share Link (só administradores têm o botão).
    assert "sel:'#mindmap-btn'" in html and "sel:'#overview-filter-btn'" in html
    assert "sel:'#share-html',admin:true" in html and "Baixar HTML" in html
    assert "sel:'#gr-form'" in html  # Season e Year dos pedidos (Base GR / SQVI)
    assert "sel:'#conference-card'" in html  # Agente de conferência (opcional)
    assert "floating:true" in html and "!s.floating||" in html  # Optimus flutuante: some do tour se estiver desligado
    assert "admin:true,sel:'#cv-launch'" in html  # Inserir visuais: só administradores
