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
    assert catalog["years"][1]["months"][0]["files"] == []  # sem Drive para o mês: continua listado, vazio
