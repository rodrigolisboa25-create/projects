"""Segurança do servidor local: só atende pedidos endereçados ao próprio computador."""

from __future__ import annotations

from test_optimus_import import ADMIN, env  # noqa: F401 - fixture reaproveitada

from ops_contabil.web.app import allowed_hosts


def test_only_local_host_names_are_accepted(env, monkeypatch) -> None:  # noqa: F811
    _settings, _db, _downloads, client_for, _sent, _replies = env
    client, _csrf = client_for(ADMIN)
    # Um site externo que se passa pelo servidor local (DNS rebinding) não recebe nada.
    assert client.get("/api/auth/session", headers={"Host": "atacante.exemplo.com"}).status_code == 400
    assert client.get("/health", headers={"Host": "atacante.exemplo.com:8765"}).status_code == 400
    # O próprio computador continua funcionando, com ou sem a porta.
    assert client.get("/health", headers={"Host": "127.0.0.1:8765"}).status_code == 200
    assert client.get("/api/auth/session", headers={"Host": "localhost:8765"}).json()["authenticated"] is True
    monkeypatch.delenv("OPS_ALLOWED_HOSTS")
    assert allowed_hosts() == ["127.0.0.1", "localhost"]
