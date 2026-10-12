"""Gravação rápida de XLSX em fluxo (sem openpyxl) para exportações grandes.

A Base de Estoque tem ~500 mil linhas × 39 colunas (~19 milhões de células). O openpyxl levava
cerca de 5 minutos e gravava temporários na pasta TEMP. Aqui o XML da planilha é gerado como
texto e compactado direto no ZIP do arquivo final, em blocos — memória baixa e poucos segundos
por 100 mil linhas. Números e datas saem como valores do Excel (datas com formato dd/mm/aaaa);
textos saem como "inline strings", aceitas por Excel, LibreOffice e openpyxl.
"""

from __future__ import annotations

import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

_INVALID_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")
_EXCEL_EPOCH = date(1899, 12, 30)

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""
_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
_WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
# Estilos: 0 = padrão, 1 = data dd/mm/aaaa, 2 = cabeçalho em negrito.
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts>
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def _text(value: Any) -> str:
    text = _INVALID_XML.sub("", str(value))
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "<c/>"
    if isinstance(value, bool):
        return f'<c t="b"><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            return "<c/>"
        return f"<c><v>{value!r}</v></c>" if isinstance(value, float) else f"<c><v>{value}</v></c>"
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return f'<c s="1"><v>{(value - _EXCEL_EPOCH).days}</v></c>'
    return f'<c t="inlineStr"><is><t xml:space="preserve">{_text(value)}</t></is></c>'


def write_xlsx(destination: Path, sheet_name: str, header: Sequence[str], rows: Iterable[Sequence[Any]],
               chunk_rows: int = 2000) -> int:
    """Grava ``rows`` (iterável de sequências) num XLSX de uma aba, com cabeçalho fixo. Devolve as linhas gravadas."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".parcial")
    count = 0
    try:
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
            archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
            archive.writestr("_rels/.rels", _ROOT_RELS)
            archive.writestr("xl/workbook.xml", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f'<sheets><sheet name="{_text(sheet_name)[:31]}" sheetId="1" r:id="rId1"/></sheets></workbook>'))
            archive.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
            archive.writestr("xl/styles.xml", _STYLES)
            with archive.open("xl/worksheets/sheet1.xml", "w", force_zip64=True) as sheet:
                sheet.write((
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                    '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
                    '</sheetView></sheetViews><sheetData>'
                    '<row r="1">' + "".join(f'<c t="inlineStr" s="2"><is><t>{_text(h)}</t></is></c>' for h in header) + "</row>"
                ).encode("utf-8"))
                buffer: list[str] = []
                for count, row in enumerate(rows, start=1):
                    buffer.append(f'<row r="{count + 1}">' + "".join(_cell(value) for value in row) + "</row>")
                    if len(buffer) >= chunk_rows:
                        sheet.write("".join(buffer).encode("utf-8"))
                        buffer.clear()
                if buffer:
                    sheet.write("".join(buffer).encode("utf-8"))
                sheet.write(b"</sheetData></worksheet>")
        partial.replace(destination)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return count
