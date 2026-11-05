"""Gera o PDF e o índice de busca da Especificação Técnico-Documental do NexxusDoc.

Uso:  python tools/build_documentation.py [--force]

- Lê ``Especificacao_Tecnica_NexxusDoc.docx`` na raiz do projeto (o original nunca é alterado: o Word trabalha numa
  cópia temporária).
- Reconstrói a tabela do Sumário a partir dos títulos (níveis 1 e 2) e recalcula as páginas, exporta o PDF pelo Word
  (com marcadores de navegação pelos títulos) e extrai o texto de cada página.
- Grava em ``static/documentacao``: o PDF e ``indice.json`` (versão, data, sumário com páginas e texto por página para a
  busca). A pasta ``static`` vai para as máquinas pela publicação assinada (rode o publicar.py depois).
- Só reconverte quando o .docx mudou (hash), salvo com --force.
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
SOURCE = PROJECT_ROOT / "Especificacao_Tecnica_NexxusDoc.docx"
TARGET_DIR = PROJECT_ROOT / "static" / "documentacao"
PDF_NAME = "Especificacao_Tecnica_NexxusDoc.pdf"
INDEX_NAME = "indice.json"
TITLE = "Especificação Técnico-Documental · NexxusDoc"

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


def headings(document) -> list[dict]:
    items = []
    for paragraph in document.Paragraphs:
        level = int(paragraph.OutlineLevel)
        if level not in (1, 2, 3):
            continue
        text = clean(paragraph.Range.Text)
        if text:
            items.append({"title": text, "level": level,
                          "page": int(paragraph.Range.Information(WD_ACTIVE_END_PAGE_NUMBER))})
    return items


def summary_table(document):
    """A tabela 'Pág. | Seção' logo depois do título Sumário."""
    for table in document.Tables:
        if clean(table.Cell(1, 1).Range.Text) == "Pág." and clean(table.Cell(1, 2).Range.Text) == "Seção":
            return table
    return None


def refresh_summary(document) -> int:
    """Refaz as linhas do Sumário com os títulos atuais (níveis 1 e 2) e grava as páginas (duas passagens, porque o
    tamanho do próprio Sumário pode empurrar as páginas)."""
    table = summary_table(document)
    if table is None:
        return 0
    entries = [item for item in headings(document) if item["level"] in (1, 2) and item["title"].casefold() != "sumário"]
    while table.Rows.Count > 1:
        table.Rows(table.Rows.Count).Delete()
    for item in entries:
        row = table.Rows.Add()
        row.Cells(1).Range.Text = str(item["page"])
        row.Cells(2).Range.Text = item["title"]
    for _ in range(2):
        document.Repaginate()
        pages = {item["title"]: item["page"] for item in headings(document)}
        for index, item in enumerate(entries, start=2):
            table.Cell(index, 1).Range.Text = str(pages.get(item["title"], item["page"]))
    return len(entries)


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


def build(force: bool = False) -> dict:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Documento não encontrado: {SOURCE}")
    source_hash = sha256(SOURCE)
    index_path = TARGET_DIR / INDEX_NAME
    if not force and index_path.is_file() and (TARGET_DIR / PDF_NAME).is_file():
        current = json.loads(index_path.read_text(encoding="utf-8"))
        if current.get("source_sha256") == source_hash:
            return {"status": "unchanged", **{k: current.get(k) for k in ("version", "doc_version", "pages")}}

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    word = open_word()
    try:
        with tempfile.TemporaryDirectory(prefix="nexxus-doc-") as temporary:
            working = Path(temporary) / SOURCE.name
            shutil.copy2(SOURCE, working)
            document = word.Documents.Open(str(working), False, False, False)
            try:
                summary_rows = refresh_summary(document)
                document.Repaginate()
                outline = headings(document)
                texts = page_texts(document)
                pdf_staging = Path(temporary) / PDF_NAME
                document.ExportAsFixedFormat(OutputFileName=str(pdf_staging), ExportFormat=WD_EXPORT_FORMAT_PDF,
                                             OpenAfterExport=False, OptimizeFor=0,
                                             CreateBookmarks=WD_EXPORT_CREATE_HEADING_BOOKMARKS, DocStructureTags=True)
            finally:
                document.Close(0)
            match = re.search(r"Vers[aã]o documental\s+([\d.]+)", texts[0] if texts else "", re.I)
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
                "summary_rows": summary_rows,
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
            "pages": index["pages"], "summary_rows": summary_rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="reconverte mesmo sem mudança no .docx")
    args = parser.parse_args()
    print(json.dumps(build(force=args.force), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
