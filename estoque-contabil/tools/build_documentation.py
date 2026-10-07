"""Gera o PDF e o índice de busca da Especificação Técnico-Documental.

Uso:  python tools/build_documentation.py [--force] [--fix-source-summary]

- Lê ``Especificacao_Tecnico_Documental_Estoque_Contabil.docx`` na raiz do projeto.
- Trabalha numa CÓPIA temporária (o .docx original nunca é alterado, a não ser com
  --fix-source-summary): recalcula as páginas do Sumário, exporta o PDF pelo Word
  (com marcadores de navegação pelos títulos) e extrai o texto de cada página.
- Grava em ``src/ops_contabil/knowledge/documentacao``: o PDF e ``indice.json``
  (versão, data, sumário com páginas e texto por página para a busca).
- Só reconverte quando o .docx mudou (hash), salvo com --force.

Executado automaticamente por tools/build_installer.ps1 antes de empacotar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "Especificacao_Tecnico_Documental_Estoque_Contabil.docx"
TARGET_DIR = PROJECT_ROOT / "src" / "ops_contabil" / "knowledge" / "documentacao"
PDF_NAME = "Especificacao_Tecnico_Documental_Estoque_Contabil.pdf"
INDEX_NAME = "indice.json"
TITLE = "Especificação Técnico-Documental — Estoque Contábil"

WD_EXPORT_FORMAT_PDF = 17
WD_EXPORT_CREATE_HEADING_BOOKMARKS = 1
WD_STATISTIC_PAGES = 2
WD_ACTIVE_END_PAGE_NUMBER = 3
WD_GOTO_PAGE = 1
WD_GOTO_ABSOLUTE = 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean(text: str) -> str:
    text = text.replace("\r\x07", "\n").replace("\x07", " ").replace("\x0b", "\n").replace("\x0c", "\n")
    text = text.replace("\r", "\n").replace("\t", " ")
    text = re.sub(r"[  ]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def heading_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\t", " ")).strip().casefold()


def headings(document) -> list[dict]:
    items = []
    for paragraph in document.Paragraphs:
        level = int(paragraph.OutlineLevel)
        if level not in (1, 2, 3):
            continue
        text = clean(paragraph.Range.Text)
        if text:
            items.append({
                "title": text,
                "level": level,
                "page": int(paragraph.Range.Information(WD_ACTIVE_END_PAGE_NUMBER)),
            })
    return items


def refresh_summary(document) -> int:
    """Atualiza os números de página do Sumário (texto fixo 'Título<TAB>página')."""
    targets = {heading_key(item["title"]): item["page"] for item in headings(document) if item["level"] == 1}
    changed = 0
    inside = False
    for paragraph in document.Paragraphs:
        text = paragraph.Range.Text
        key = heading_key(clean(text))
        if int(paragraph.OutlineLevel) == 1:
            inside = key == "sumário"
            continue
        if not inside or "\t" not in text:
            continue
        title = heading_key(text.rsplit("\t", 1)[0])
        current = text.rsplit("\t", 1)[1].strip("\r\x07 ")
        page = targets.get(title)
        if page is None or current == str(page):
            continue
        start = paragraph.Range.Start + text.rfind("\t") + 1
        end = paragraph.Range.End - 1
        document.Range(start, end).Text = str(page)
        changed += 1
    return changed


def page_texts(document) -> list[str]:
    total = int(document.ComputeStatistics(WD_STATISTIC_PAGES))
    starts = [int(document.GoTo(What=WD_GOTO_PAGE, Which=WD_GOTO_ABSOLUTE, Count=page).Start) for page in range(1, total + 1)]
    starts.append(int(document.Content.End))
    return [clean(document.Range(starts[i], starts[i + 1]).Text) for i in range(total)]


def open_word():
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    return word


def build(force: bool = False, fix_source_summary: bool = False) -> dict:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Documento não encontrado: {SOURCE}")
    source_hash = sha256(SOURCE)
    index_path = TARGET_DIR / INDEX_NAME
    if not force and not fix_source_summary and index_path.is_file() and (TARGET_DIR / PDF_NAME).is_file():
        current = json.loads(index_path.read_text(encoding="utf-8"))
        if current.get("source_sha256") == source_hash:
            return {"status": "unchanged", **{k: current.get(k) for k in ("version", "doc_version", "pages")}}

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    word = open_word()
    try:
        if fix_source_summary:
            document = word.Documents.Open(str(SOURCE), False, False, False)
            try:
                fixed = refresh_summary(document)
                if fixed:
                    document.Save()
            finally:
                document.Close(0)
            source_hash = sha256(SOURCE)
        with tempfile.TemporaryDirectory(prefix="ops-doc-") as temporary:
            working = Path(temporary) / SOURCE.name
            shutil.copy2(SOURCE, working)
            document = word.Documents.Open(str(working), False, False, False)
            try:
                summary_fixed = refresh_summary(document)
                document.Repaginate()
                outline = headings(document)
                texts = page_texts(document)
                pdf_staging = Path(temporary) / PDF_NAME
                document.ExportAsFixedFormat(
                    OutputFileName=str(pdf_staging),
                    ExportFormat=WD_EXPORT_FORMAT_PDF,
                    OpenAfterExport=False,
                    OptimizeFor=0,
                    CreateBookmarks=WD_EXPORT_CREATE_HEADING_BOOKMARKS,
                    DocStructureTags=True,
                )
            finally:
                document.Close(0)
            first_page = texts[0] if texts else ""
            match = re.search(r"Vers[aã]o documental\s+([\d.]+)", first_page, re.I)
            generated_at = datetime.now(timezone.utc).astimezone().replace(microsecond=0)
            index = {
                "title": TITLE,
                "doc_version": match.group(1) if match else None,
                "version": f"{generated_at:%Y%m%dT%H%M%S}-{source_hash[:10]}",
                "generated_at": generated_at.isoformat(),
                "source_name": SOURCE.name,
                "source_sha256": source_hash,
                "source_modified": datetime.fromtimestamp(SOURCE.stat().st_mtime).astimezone().replace(microsecond=0).isoformat(),
                "pdf_name": PDF_NAME,
                "pdf_sha256": sha256(pdf_staging),
                "pdf_size": pdf_staging.stat().st_size,
                "pages": len(texts),
                "summary_pages_fixed": summary_fixed,
                "outline": outline,
                "page_text": texts,
            }
            # PDF primeiro, índice por último: quem lê o índice sempre encontra o PDF dele.
            partial_pdf = TARGET_DIR / f".{PDF_NAME}.parcial"
            shutil.copy2(pdf_staging, partial_pdf)
            os.replace(partial_pdf, TARGET_DIR / PDF_NAME)
            partial_index = TARGET_DIR / f".{INDEX_NAME}.parcial"
            partial_index.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(partial_index, index_path)
    finally:
        word.Quit()
    return {"status": "built", "version": index["version"], "doc_version": index["doc_version"],
            "pages": index["pages"], "summary_pages_fixed": summary_fixed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="reconverte mesmo sem mudança no .docx")
    parser.add_argument("--fix-source-summary", action="store_true", help="grava no .docx os números corrigidos do Sumário")
    args = parser.parse_args()
    result = build(force=args.force, fix_source_summary=args.fix_source_summary)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
