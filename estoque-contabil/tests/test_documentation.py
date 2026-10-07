"""Página Documentação: PDF publicado, busca por palavras-chave, ponte do Drive e permissões."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import ops_contabil.documentation as documentation
from ops_contabil.auth import page_catalog
from ops_contabil.documentation import (
    current_document,
    document_info,
    publish_documentation,
    search_document,
    sync_documentation,
)
from test_bridge_api import ADMIN, USER, make_machine

PAGES = [
    "ESTOQUE CONTÁBIL\nEspecificação Técnico-Documental\nVersão documental 1.0",
    "6. Fontes de dados e contratos\nA MB59 usa a variante BASE GR. A ponte de dados leva as competências.",
    "18. Configurações\nBackup programado e restauração. A Ponte de Dados não apaga nada.\nMB59 também aparece aqui.",
]


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, key: str) -> Path:
        assert key == "database"
        return self.root / "OpsContabil" / "processed" / "ops.duckdb"


def write_doc(folder: Path, generated_at: str, pdf_bytes: bytes = b"%PDF-1.7 teste") -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Especificacao.pdf").write_bytes(pdf_bytes)
    index = {
        "title": "Especificação Técnico-Documental — Estoque Contábil",
        "doc_version": "1.0",
        "version": f"{generated_at.replace(':', '').replace('-', '')}-abc",
        "generated_at": generated_at,
        "source_modified": generated_at,
        "pdf_name": "Especificacao.pdf",
        "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "pdf_size": len(pdf_bytes),
        "pages": len(PAGES),
        "outline": [
            {"title": "6. Fontes de dados e contratos", "level": 1, "page": 2},
            {"title": "18. Configurações", "level": 1, "page": 3},
        ],
        "page_text": PAGES,
    }
    (folder / "indice.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return index


@pytest.fixture()
def packaged(tmp_path: Path, monkeypatch) -> Path:
    folder = tmp_path / "pacote"
    monkeypatch.setattr(documentation, "PACKAGED_DIR", folder)
    return folder


def test_search_ignores_accents_and_case_and_requires_all_terms(tmp_path: Path, packaged: Path) -> None:
    write_doc(packaged, "2026-10-01T10:00:00-03:00")
    settings = FakeSettings(tmp_path)

    result = search_document(settings, "ponte DADOS")
    assert [hit["page"] for hit in result["pages"]] == [2, 3]
    assert result["pages"][1]["section"] == "18. Configurações"
    snippet = result["pages"][1]["snippets"][0]
    marked = [snippet["text"][start:end] for start, end in snippet["marks"]]
    assert "Ponte" in marked and "Dados" in marked

    assert [hit["page"] for hit in search_document(settings, "restauracao")["pages"]] == [3]  # sem acento
    assert [hit["page"] for hit in search_document(settings, "mb59 backup")["pages"]] == [3]  # todos os termos
    assert search_document(settings, '"base gr"')["pages"][0]["page"] == 2  # frase exata
    assert search_document(settings, '"gr base"')["pages"] == []
    assert search_document(settings, "")["pages"] == []


def test_newest_copy_wins_and_bridge_carries_it_between_machines(tmp_path: Path, packaged: Path) -> None:
    drive = tmp_path / "Estoque_Cont"
    drive.mkdir()
    admin = FakeSettings(tmp_path / "admin")
    user = FakeSettings(tmp_path / "user")

    write_doc(packaged, "2026-10-01T10:00:00-03:00")
    assert publish_documentation(admin, drive) == "enviada"
    assert publish_documentation(admin, drive) == "Drive em dia"
    assert sync_documentation(user, drive) == "máquina em dia"  # a mesma versão já está no pacote

    # Uma versão nova chega à máquina do administrador e vai para o Drive.
    newer = tmp_path / "admin" / "OpsContabil" / "documentacao"
    write_doc(newer, "2026-10-02T09:00:00-03:00", b"%PDF-1.7 versao nova")
    assert current_document(admin).origin == "ponte"
    assert publish_documentation(admin, drive) == "enviada"

    # Enquanto o Google Drive não terminou de baixar o PDF, nada muda na outra máquina.
    pointer = json.loads((drive / "documentacao" / "atual.json").read_text(encoding="utf-8"))
    pdf_on_drive = drive / "documentacao" / pointer["version"] / "Especificacao.pdf"
    complete = pdf_on_drive.read_bytes()
    pdf_on_drive.write_bytes(complete[:5])
    assert sync_documentation(user, drive) == "aguardando o Google Drive"
    assert document_info(user)["generated_at"] == "2026-10-01T10:00:00-03:00"

    pdf_on_drive.write_bytes(complete)
    assert sync_documentation(user, drive) == "recebida"
    info = document_info(user)
    assert info["generated_at"] == "2026-10-02T09:00:00-03:00" and info["origin"] == "ponte"
    assert current_document(user).pdf.read_bytes() == b"%PDF-1.7 versao nova"
    assert sync_documentation(user, drive) == "máquina em dia"


def test_packaged_documentation_is_complete_and_consistent() -> None:
    folder = Path(documentation.__file__).with_name("knowledge") / "documentacao"
    index = json.loads((folder / "indice.json").read_text(encoding="utf-8"))
    pdf = folder / index["pdf_name"]
    assert pdf.read_bytes()[:5] == b"%PDF-"
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == index["pdf_sha256"]
    assert index["pages"] == len(index["page_text"]) > 5
    titles = [item["title"] for item in index["outline"] if item["level"] == 1]
    assert any("Páginas do sistema" in title for title in titles)
    for item in index["outline"]:
        assert item["title"].split()[0] in index["page_text"][item["page"] - 1]


def test_documentation_api_and_page_permission(tmp_path: Path, packaged: Path) -> None:
    write_doc(packaged, "2026-10-01T10:00:00-03:00")
    assert {"key": "docs", "label": "Documentação"} in page_catalog()
    _, admin, csrf = make_machine(tmp_path, "admin", ADMIN, "admin", "[]")
    _, user, _ = make_machine(tmp_path, "user", USER, "user", '["overview","agent"]')
    _, reader, _ = make_machine(tmp_path, "reader", "docs.reader@gruposbf.com.br", "user", '["overview","docs"]')

    info = admin.get("/api/docs/info").json()
    assert info["available"] and info["pages"] == 3 and info["outline"][0]["page"] == 2
    pdf = admin.get("/api/docs/pdf?v=x")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"].startswith("inline")
    assert admin.get("/api/docs/pdf?download=true").headers["content-disposition"].startswith("attachment")
    assert [hit["page"] for hit in admin.get("/api/docs/search", params={"q": "backup"}).json()["pages"]] == [3]

    # Documentação é obrigatória para todo perfil Usuário, mesmo sem marcá-la.
    for path in ("/api/docs/info", "/api/docs/pdf", "/api/docs/search?q=mb59"):
        assert user.get(path).status_code == 200
        assert reader.get(path).status_code == 200

    granted = admin.post(
        "/api/settings/access",
        json={"email": USER, "role": "user", "pages": ["agent"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert granted.status_code == 200, granted.text
    saved = next(item for item in granted.json()["allowed_users"] if item["email"] == USER)
    assert saved["pages"] == ["overview", "agent", "docs"]
    assert any(page["key"] == "docs" for page in granted.json()["page_catalog"])


def test_user_profile_gets_only_interface_and_notifications_in_settings(tmp_path: Path) -> None:
    _, user, csrf = make_machine(tmp_path, "user", USER, "user", '["overview"]')
    session = user.get("/api/auth/session").json()
    assert "docs" in session["user"]["pages"]

    # Interface e experiência: lê e grava só os campos de interface.
    prefs = user.get("/api/preferences/interface").json()
    assert set(prefs) == {"density", "default_page_size", "animations_enabled", "chart_animations_enabled", "card_animations_enabled"}
    saved = user.put("/api/preferences/interface", json={"density": "comfortable", "card_animations_enabled": False},
                     headers={"X-CSRF-Token": csrf})
    assert saved.status_code == 200 and saved.json()["density"] == "comfortable" and saved.json()["card_animations_enabled"] is False
    assert user.put("/api/preferences/interface", json={"density": "gigante"}, headers={"X-CSRF-Token": csrf}).status_code == 422

    # Notificações: também liberadas. O restante de Configurações continua só de administradores.
    assert user.get("/api/notifications/preferences").status_code == 200
    for path in ("/api/settings", "/api/settings/backup/list", "/api/installer/download"):
        assert user.get(path).status_code == 403
    assert user.put("/api/settings", json={"density": "compact"}, headers={"X-CSRF-Token": csrf}).status_code == 403
