"""Controles e auditoria: a página mostra exatamente os campos usados nos joins entre as bases."""

from __future__ import annotations

from test_optimus_import import ADMIN, env  # noqa: F401 - fixture reaproveitada


def test_structures_card_explains_every_join(env) -> None:  # noqa: F811
    _settings, _db, _downloads, client_for, _sent, _replies = env
    client, _csrf = client_for(ADMIN)
    response = client.get("/api/governance/status", params={"period": "2026-09"})
    assert response.status_code == 200, response.text
    items = {item["title"]: item for item in response.json()["structures"]}
    assert list(items) == [
        "Posição de Estoque (ZMM119)",
        "All Brazil → Division, Origem e Lifecycle",
        "MB59 (PASSO A PASSO) → Season, Year e Product Offer End Dt",
        "Mapping → Local, STATUS OPERAÇÃO, Lifecycle e AGING",
        "Campos calculados (sem join)",
    ]
    text = {title: " ".join(item["steps"]) for title, item in items.items()}
    assert "CE & MAT = Centro + Material" in text["Posição de Estoque (ZMM119)"] and "Empresa 7170" in text["Posição de Estoque (ZMM119)"]
    ab = text["All Brazil → Division, Origem e Lifecycle"]
    assert "Material da Base de Estoque (maiúsculas, sem espaços) = Material Nbr" in ab
    assert "Estilo-Cor (10 primeiros caracteres do Material) = Material Nbr" in ab and "nunca participa da chave" in ab
    mb = text["MB59 (PASSO A PASSO) → Season, Year e Product Offer End Dt"]
    assert "1º MB59 da competência por CE & MAT" in mb and "2º Base de Estoque do mês anterior por CE & MAT" in mb
    assert "Collection Code → Season" in mb and "Collection Year → Year" in mb
    mapping = text["Mapping → Local, STATUS OPERAÇÃO, Lifecycle e AGING"]
    assert "Centro da Base = Planta → Local" in mapping and "Days = data-base − Product Offer End Dt" in mapping
    assert items["All Brazil → Division, Origem e Lifecycle"]["badge"] == "Sem carga"  # competência sem All Brazil na base de teste
