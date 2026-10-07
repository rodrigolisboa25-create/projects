"""Página Documentação: Especificação Técnico-Documental em PDF, com busca.

O PDF e o índice (texto por página, sumário) são gerados a partir do .docx do
projeto por ``tools/build_documentation.py`` e vão no pacote
(``knowledge/documentacao``). Para que as máquinas recebam uma versão nova sem
reinstalar, a versão mais recente também trafega pela ponte do Drive
(``Estoque_Cont/documentacao``); a recebida fica em
``%LOCALAPPDATA%/OpsContabil/documentacao``. Vale sempre a mais recente.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PACKAGED_DIR = Path(__file__).with_name("knowledge") / "documentacao"
INDEX_NAME = "indice.json"
POINTER_NAME = "atual.json"
BRIDGE_FOLDER = "documentacao"
KEEP_BRIDGE_VERSIONS = 3
MAX_RESULTS = 60
SNIPPET_RADIUS = 90


@dataclass(frozen=True)
class DocumentCopy:
    folder: Path
    index: dict[str, Any]
    origin: str  # "pacote" ou "ponte"

    @property
    def pdf(self) -> Path:
        return self.folder / str(self.index["pdf_name"])

    @property
    def generated_at(self) -> str:
        return str(self.index.get("generated_at") or "")


def received_dir(settings: Any) -> Path:
    """%LOCALAPPDATA%/OpsContabil/documentacao (ao lado da pasta do banco)."""
    return settings.path("database").parent.parent / BRIDGE_FOLDER


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_index(folder: Path) -> dict[str, Any] | None:
    try:
        index = json.loads((folder / INDEX_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(index, dict) or not index.get("pdf_name") or not (folder / str(index["pdf_name"])).is_file():
        return None
    return index


def _copies(settings: Any) -> list[DocumentCopy]:
    found = []
    for folder, origin in ((PACKAGED_DIR, "pacote"), (received_dir(settings), "ponte")):
        index = _read_index(folder)
        if index is not None:
            found.append(DocumentCopy(folder, index, origin))
    return found


def current_document(settings: Any) -> DocumentCopy | None:
    """A cópia mais recente disponível nesta máquina (pacote ou recebida pela ponte)."""
    copies = _copies(settings)
    if not copies:
        return None
    return max(copies, key=lambda item: (item.generated_at, item.origin == "pacote"))


def document_info(settings: Any) -> dict[str, Any]:
    document = current_document(settings)
    if document is None:
        return {"available": False}
    index = document.index
    return {
        "available": True,
        "title": index.get("title"),
        "doc_version": index.get("doc_version"),
        "version": index.get("version"),
        "generated_at": index.get("generated_at"),
        "source_modified": index.get("source_modified"),
        "pages": index.get("pages"),
        "pdf_name": index.get("pdf_name"),
        "pdf_size": index.get("pdf_size"),
        "origin": document.origin,
        "outline": index.get("outline") or [],
    }


# ---------------------------------------------------------------- busca


def _fold(text: str) -> str:
    """Minúsculas sem acento, preservando o comprimento (para mapear posições)."""
    out = []
    for char in text:
        base = unicodedata.normalize("NFKD", char)
        kept = "".join(c for c in base if not unicodedata.combining(c)) or char
        out.append(kept[0].casefold() if kept else char)
    return "".join(out)


def _terms(query: str) -> list[str]:
    phrases = re.findall(r'"([^"]+)"', query)
    rest = re.sub(r'"[^"]*"', " ", query)
    words = [word for word in re.split(r"\s+", rest) if len(word.strip()) >= 2]
    terms = [_fold(term.strip()) for term in [*phrases, *words] if term.strip()]
    unique: list[str] = []
    for term in terms:
        if term not in unique:
            unique.append(term)
    return unique[:8]


def _snippet(text: str, folded: str, position: int, length: int, terms: list[str]) -> dict[str, Any]:
    start = max(0, position - SNIPPET_RADIUS)
    end = min(len(text), position + length + SNIPPET_RADIUS)
    if start > 0:
        space = text.rfind(" ", 0, start + 15)
        start = space + 1 if space >= start - 15 and space != -1 else start
    if end < len(text):
        space = text.find(" ", end - 15)
        end = space if space != -1 and space <= end + 15 else end
    raw_piece = text[start:end]
    folded_piece = folded[start:end]
    marks: list[list[int]] = []
    for term in terms:
        for match in re.finditer(re.escape(term), folded_piece):
            marks.append([match.start(), match.end()])
    marks.sort()
    merged: list[list[int]] = []
    for mark in marks:
        if merged and mark[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], mark[1])
        else:
            merged.append(mark)
    # Quebras de linha viram " · " no trecho exibido; as posições acompanham a troca.
    shift = [0] * (len(raw_piece) + 1)
    pieces: list[str] = []
    extra = 0
    for index, char in enumerate(raw_piece):
        shift[index] = index + extra
        if char == "\n":
            pieces.append(" · ")
            extra += 2
        else:
            pieces.append(char)
    shift[len(raw_piece)] = len(raw_piece) + extra
    return {
        "text": "".join(pieces),
        "prefix": start > 0,
        "suffix": end < len(text),
        "marks": [[shift[a], shift[b]] for a, b in merged],
    }


def search_document(settings: Any, query: str) -> dict[str, Any]:
    """Páginas que contêm TODOS os termos (acentos e maiúsculas ignorados).

    Termos entre aspas são buscados como frase exata.
    """
    document = current_document(settings)
    terms = _terms(query or "")
    if document is None or not terms:
        return {"query": query, "terms": terms, "total_matches": 0, "pages": []}
    outline = sorted(document.index.get("outline") or [], key=lambda item: item["page"])
    results = []
    total = 0
    for number, text in enumerate(document.index.get("page_text") or [], start=1):
        folded = _fold(text)
        positions = {term: [m.start() for m in re.finditer(re.escape(term), folded)] for term in terms}
        if not all(positions.values()):
            continue
        count = sum(len(items) for items in positions.values())
        total += count
        anchor_term = max(terms, key=len)
        snippets = []
        used_until = -1
        for position in positions[anchor_term]:
            if position < used_until:
                continue
            snippet = _snippet(text, folded, position, len(anchor_term), terms)
            snippets.append(snippet)
            used_until = position + SNIPPET_RADIUS
            if len(snippets) == 3:
                break
        section = next((item["title"] for item in reversed(outline) if item["page"] <= number), None)
        results.append({"page": number, "matches": count, "section": section, "snippets": snippets})
        if len(results) >= MAX_RESULTS:
            break
    return {"query": query, "terms": terms, "total_matches": total, "pages": results}


# ---------------------------------------------------------- ponte do Drive


def _bridge_pointer(root: Path) -> dict[str, Any] | None:
    try:
        pointer = json.loads((root / BRIDGE_FOLDER / POINTER_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return pointer if isinstance(pointer, dict) and pointer.get("version") else None


def publish_documentation(settings: Any, root: Path) -> str:
    """Envia ao Drive a versão desta máquina, se for mais nova que a do Drive."""
    document = current_document(settings)
    if document is None:
        return "sem documento"
    pointer = _bridge_pointer(root)
    if pointer is not None and str(pointer.get("generated_at") or "") >= document.generated_at:
        return "Drive em dia"
    folder = root / BRIDGE_FOLDER
    version = str(document.index["version"])
    staging = folder / f".enviando-{version}"
    final = folder / version
    staging.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(document.pdf, staging / document.pdf.name)
        shutil.copy2(document.folder / INDEX_NAME, staging / INDEX_NAME)
        if final.exists():
            shutil.rmtree(final, ignore_errors=True)
        os.replace(staging, final)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    pointer = {key: document.index.get(key) for key in ("version", "generated_at", "doc_version", "pdf_name", "pdf_sha256", "pdf_size")}
    partial = folder / f".{POINTER_NAME}.parcial"
    partial.write_text(json.dumps(pointer, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(partial, folder / POINTER_NAME)
    versions = sorted((item for item in folder.iterdir() if item.is_dir() and not item.name.startswith(".")), key=lambda item: item.name, reverse=True)
    for old in versions[KEEP_BRIDGE_VERSIONS:]:
        if old.name != version:
            shutil.rmtree(old, ignore_errors=True)
    return "enviada"


def sync_documentation(settings: Any, root: Path) -> str:
    """Recebe do Drive a versão mais nova (completa e conferida pelo hash)."""
    pointer = _bridge_pointer(root)
    if pointer is None:
        return "Drive sem documentação"
    document = current_document(settings)
    if document is not None and document.generated_at >= str(pointer.get("generated_at") or ""):
        return "máquina em dia"
    source = root / BRIDGE_FOLDER / str(pointer["version"])
    pdf = source / str(pointer.get("pdf_name") or "")
    try:
        if pdf.stat().st_size != int(pointer.get("pdf_size") or -1) or _sha256(pdf) != pointer.get("pdf_sha256"):
            return "aguardando o Google Drive"
        index = json.loads((source / INDEX_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "aguardando o Google Drive"
    if index.get("version") != pointer.get("version"):
        return "aguardando o Google Drive"
    target = received_dir(settings)
    staging = target.with_name(f".{BRIDGE_FOLDER}-recebendo")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    shutil.copy2(pdf, staging / pdf.name)
    (staging / INDEX_NAME).write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    previous = target.with_name(f".{BRIDGE_FOLDER}-anterior")
    shutil.rmtree(previous, ignore_errors=True)
    if target.exists():
        os.replace(target, previous)
    os.replace(staging, target)
    shutil.rmtree(previous, ignore_errors=True)
    return "recebida"
