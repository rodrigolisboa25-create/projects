"""Bases All Brazil: anos e meses vêm das pastas reais do Drive (sem lista fixa)."""

from __future__ import annotations

import json
from pathlib import Path

import ops_contabil.web.app as web_app
from ops_contabil.sources.all_brazil import discover_all_brazil_months
from test_optimus_import import ADMIN, env  # noqa: F401 - fixture reaproveitada

ROOT_URL = "https://drive.google.com/drive/folders/raiz"
SEPTEMBER_URL = "https://drive.google.com/drive/folders/setembro"


def drive_tree(root: Path) -> Path:
    for folder, files in {
        "2026/09. Setembro": ["ALL_BRAZIL_29_09.xlsx", "ALL_BRAZIL_30_09.xlsx"],
        "2026/10. Outubro": ["ALL_BRAZIL_01_10.xlsx", "ALL_BRAZIL_08_10.xlsx", "rascunho.xlsx"],
        "2026/Arquivo antigo": ["ALL_BRAZIL_01_01.xlsx"],  # fora do padrão "MM. Mês"
        "Modelos/01. Janeiro": [],  # fora do padrão de ano
    }.items():
        (root / folder).mkdir(parents=True, exist_ok=True)
        for name in files:
            (root / folder / name).write_bytes(b"x")
    return root


def test_discover_months_reads_the_real_folders(tmp_path: Path) -> None:
    found = discover_all_brazil_months(drive_tree(tmp_path / "AB"))
    assert {year: sorted(months) for year, months in found.items()} == {2026: [9, 10]}
    assert discover_all_brazil_months(tmp_path / "nao-existe") == {}


def test_new_month_in_the_drive_appears_in_the_catalog(env, monkeypatch) -> None:  # noqa: F811
    settings, _db, _downloads, client_for, _sent, _replies = env
    root = drive_tree(settings.root / "AB")
    monkeypatch.setattr(web_app, "resolve_all_brazil_root", lambda _settings: root)
    monkeypatch.setattr(web_app.drivefs, "month_folder_ids", lambda _title: {})  # máquina sem DriveFS
    # O arquivo de links só conhece setembro (e um mês antigo que não existe mais no Drive).
    (settings.root / "config" / "all_brazil_drive_folders.json").write_text(
        json.dumps({"root_url": ROOT_URL, "years": {"2026": {"09": SEPTEMBER_URL}, "2025": {"12": "https://x/dez"}}}),
        encoding="utf-8",
    )
    client, _csrf = client_for(ADMIN)
    catalog = client.get("/api/sources/all-brazil/catalog").json()
    assert catalog["root_url"] == ROOT_URL
    assert [item["year"] for item in catalog["years"]] == [2026, 2025]
    months = {item["month"]: item for item in catalog["years"][0]["months"]}
    assert list(months) == [10, 9]  # outubro aparece sozinho, mais recente primeiro
    assert months[10]["label"] == "10. Outubro" and months[10]["drive_url"] == ROOT_URL
    assert [item["name"] for item in months[10]["files"]] == ["ALL_BRAZIL_08_10.xlsx", "ALL_BRAZIL_01_10.xlsx"]
    assert months[9]["drive_url"] == SEPTEMBER_URL  # mês já conhecido mantém o link da própria pasta
    assert months[10]["link_known"] is False and months[9]["link_known"] is True  # outubro: botão "Cadastrar link"
    assert catalog["years"][1]["months"][0]["files"] == []  # sem Drive para o mês: continua listado, vazio


def test_month_link_is_discovered_from_drivefs_and_remembered(env, monkeypatch) -> None:  # noqa: F811
    settings, _db, _downloads, client_for, _sent, _replies = env
    root = drive_tree(settings.root / "AB")
    monkeypatch.setattr(web_app, "resolve_all_brazil_root", lambda _settings: root)
    (settings.root / "config" / "all_brazil_drive_folders.json").write_text(
        json.dumps({"root_url": ROOT_URL, "years": {"2026": {"09": SEPTEMBER_URL}}}), encoding="utf-8")
    # O DriveFS conhece outubro (e setembro, que já tem link no arquivo e não muda); "Modelos" fica de fora.
    ids = {("2026", "10. Outubro"): "idOutubro123", ("2026", "09. Setembro"): "outroId", ("Modelos", "01. Janeiro"): "x"}
    monkeypatch.setattr(web_app.drivefs, "month_folder_ids", lambda title: ids if title == "AB" else {})
    client, _csrf = client_for(ADMIN)
    months = {item["month"]: item for item in client.get("/api/sources/all-brazil/catalog").json()["years"][0]["months"]}
    assert months[10]["drive_url"] == "https://drive.google.com/drive/folders/idOutubro123"
    assert months[10]["link_known"] is True
    assert months[9]["drive_url"] == SEPTEMBER_URL
    # Gravado: mesmo sem DriveFS depois, outubro continua com o link certo.
    monkeypatch.setattr(web_app.drivefs, "month_folder_ids", lambda _title: {})
    months = {item["month"]: item for item in client.get("/api/sources/all-brazil/catalog").json()["years"][0]["months"]}
    assert months[10]["drive_url"] == "https://drive.google.com/drive/folders/idOutubro123"


def test_admin_registers_month_link_when_drivefs_is_missing(env, monkeypatch) -> None:  # noqa: F811
    settings, _db, _downloads, client_for, _sent, _replies = env
    root = drive_tree(settings.root / "AB")
    monkeypatch.setattr(web_app, "resolve_all_brazil_root", lambda _settings: root)
    monkeypatch.setattr(web_app.drivefs, "month_folder_ids", lambda _title: {})
    (settings.root / "config" / "all_brazil_drive_folders.json").write_text(
        json.dumps({"root_url": ROOT_URL, "years": {}}), encoding="utf-8")
    client, csrf = client_for(ADMIN)
    headers = {"X-CSRF-Token": csrf} if csrf else {}
    bad = client.post("/api/sources/all-brazil/link", json={"year": 2026, "month": 10, "url": "https://exemplo.com/pasta/123456"}, headers=headers)
    assert bad.status_code == 422
    saved = client.post(
        "/api/sources/all-brazil/link",
        json={"year": 2026, "month": 10, "url": "https://drive.google.com/drive/u/0/folders/1x89OrwHf25FDD8rBhtglKq?usp=x"},
        headers=headers,
    )
    assert saved.status_code == 200 and saved.json()["url"] == "https://drive.google.com/drive/folders/1x89OrwHf25FDD8rBhtglKq"
    months = {item["month"]: item for item in client.get("/api/sources/all-brazil/catalog").json()["years"][0]["months"]}
    assert months[10]["drive_url"] == "https://drive.google.com/drive/folders/1x89OrwHf25FDD8rBhtglKq"


def test_drivefs_lookup_without_drive_returns_empty(tmp_path: Path, monkeypatch) -> None:
    from ops_contabil import drivefs

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    drivefs._CACHE.clear()
    assert drivefs.month_folder_ids("@All Brazil Materials") == {}
    assert drivefs.folder_url("abc") == "https://drive.google.com/drive/folders/abc"
