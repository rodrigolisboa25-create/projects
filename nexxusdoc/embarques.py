"""Pagina Embarques (19/11/2026, pedido do usuario): indice da pasta Sua Area > Processos.

A equipe continua salvando como sempre (uma pasta por embarque). Este modulo SO LE a pasta: acha as pastas de processo
de cada operacao (INLINE, PROMO, AMOSTRAS, ZELUS), classifica os arquivos, le os documentos que tem texto (fatura
comercial Nike/TCCI, BL, proforma, checklist documental, fatura da Zelus) e faz a pre-conferencia do Checklist ID 677
(BL x TCCI x proforma). Nada e estimado: o que o documento nao traz fica vazio.

Cache por processo (pasta compartilhada embarques/processos/<id>.json): um arquivo so e lido de novo quando muda de
tamanho ou de data. O indice (embarques/indice.json) e o que a tela le.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import threading
import time
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

OPERACOES = ("INLINE", "PROMO", "AMOSTRAS", "ZELUS")
VERSAO_LEITURA = 3  # mudou a leitura: os processos sao lidos de novo
# Pasta de processo: BL/HAWB/AWB + numero, referencia FISIA da Zelus ou codigo de embarque (3-4 letras + 6 ou mais digitos)
PROC_RE = re.compile(r"^(BL|BOL|HAWB|AWB|MAWB)\s*\S|\(FISIA\s*\d+\)|^FISIA\s*\d+|^\d{0,2}[A-Z]{2,5}-?\d{6,}", re.I)
SCAC = {"MAEU": "Maersk", "CMDU": "CMA CGM", "SUDU": "Hamburg Süd", "HLCU": "Hapag-Lloyd", "ONEY": "ONE", "MSCU": "MSC",
        "MEDU": "MSC", "COSU": "COSCO", "EGLV": "Evergreen", "OOLU": "OOCL", "ZIMU": "ZIM", "HDMU": "HMM", "YMLU": "Yang Ming"}
TIPOS_ARQUIVO = {"checklist": "Checklist documental", "tcci": "Fatura comercial (TCCI)", "proforma": "Proforma",
                 "pl": "Packing list", "bl": "BL", "awb": "HAWB / AWB", "ci": "Fatura comercial", "nf": "Nota fiscal",
                 "fci": "FCI", "outro": "Outro"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
CONFERENCIA_DESDE = "2025-01-01"  # pre-conferencia (situacao) so dos processos criados a partir desta data


def norm(text: Any) -> str:
    text = unicodedata.normalize("NFD", str(text or "").casefold())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def num_eu(value: str) -> float | None:
    """'9.081,60' -> 9081.6; '231,330' -> 231.33 (formato das faturas Nike)."""
    value = (value or "").strip().replace(" ", "")
    if not value:
        return None
    if "," in value or re.fullmatch(r"\d{1,3}(\.\d{3})+", value):  # '4.000' = quatro mil (ponto de milhar)
        value = value.replace(".", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def num_us(value: str) -> float | None:
    """'5326.360' -> 5326.36; '1,237.00' -> 1237.0 (formato dos BLs)."""
    try:
        return float((value or "").replace(",", ""))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Conteiner: codigo ISO 6346 com digito verificador (evita confundir com numero de BL ou booking)
# ---------------------------------------------------------------------------
_ISO_VAL = {}
_v = 10
for _ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    if _v % 11 == 0:
        _v += 1
    _ISO_VAL[_ch] = _v
    _v += 1


def conteiner_valido(code: str) -> bool:
    if not re.fullmatch(r"[A-Z]{4}\d{7}", code or ""):
        return False
    total = sum((_ISO_VAL[c] if c.isalpha() else int(c)) * (2 ** i) for i, c in enumerate(code[:10]))
    return total % 11 % 10 == int(code[10])


def conteineres(text: str) -> list[str]:
    return sorted({c for c in re.findall(r"(?<![A-Z])([A-Z]{4}\d{7})(?!\d)", text or "") if conteiner_valido(c)})


# ---------------------------------------------------------------------------
# Classificacao dos arquivos pelo nome
# ---------------------------------------------------------------------------
INVOICE_NAME = re.compile(r"^[A-Z0-9-]{6,}_\d{10}_\d{5}", re.I)  # HAWB_PO_linha.pdf: fatura Nike por item de PO


def tipo_arquivo(name: str) -> str:
    n = norm(name)
    if "checklist" in n:
        return "checklist"
    if "tcci" in n or INVOICE_NAME.match(name):
        return "tcci"
    if re.search(r"pro ?forma", n):
        return "proforma"
    if re.search(r"(^|[^a-z])(pl|pls)([^a-z]|$)|packing", n):
        return "pl"
    # "FATURA COMERCIAL HAWB PNH1340614.pdf" e a fatura (antes caia em HAWB por causa do numero no nome)
    if re.search(r"fatura comercial|commercial invoice|(^|[^a-z])invoices?([^a-z]|$)", n):
        return "ci"
    if re.search(r"(^|[^a-z])(hawb|awb|mawb)([^a-z]|$)", n):
        return "awb"
    if re.search(r"(^|[^a-z])(bl|bol|mbl|hbl|b ?/ ?l)([^a-z]|$)|bill of lading", n):  # BOL = B/L = BL
        return "bl"
    if re.search(r"(^|[^a-z])(ci|invoice|invoices|fatura|commercial)([^a-z]|$)", n):
        return "ci"
    if re.search(r"(^|[^a-z])(nf|nfe|danfe)([^a-z]|$)|nota fiscal", n):
        return "nf"
    if re.search(r"(^|[^a-z])fci([^a-z]|$)", n):
        return "fci"
    return "outro"


# Palavras que podem acompanhar o numero no nome do documento de transporte ("ORIGINAL 2 - HCM00016822.pdf",
# "SGN4872558 - Final.pdf", "HKG5249417 Draft.pdf", "CMB0750904 (1).pdf"); qualquer outra palavra ("SD", "DI", "NF")
# mantem o arquivo como "outro".
_TRANSP_EXTRA = {"original", "final", "draft", "revised", "revisado", "revisada", "rev", "copia", "copy", "hawb", "awb",
                 "mawb", "bl", "hbl", "mbl", "bol"}


def tipo_no_processo(f: dict[str, Any], p: dict[str, Any]) -> str:
    """Tipo do arquivo dentro do processo (versao 23/11/2026, conferida com as pastas reais):
    1. o conteudo lido manda (PDF generico em que o sistema achou BL, AWB ou fatura: campo "tipo_lido");
    2. o nome do arquivo (tipo_arquivo);
    3. arquivo na subpasta de faturas ("TCCIs/02s9ayOH.pdf") = fatura;
    4. PDF com o numero do processo e nada mais no nome = documento de transporte (BL na pasta "BL ...", AWB na pasta
       "HAWB ..."), como a equipe salva o AWB das amostras ("HCM00016822.pdf")."""
    if f.get("tipo_lido"):
        return f["tipo_lido"]
    nome, rel = f.get("nome", ""), f.get("rel", "")
    t = tipo_arquivo(nome)
    if t != "outro":
        return t
    ext = Path(nome).suffix.lower()
    pasta = norm(rel.rsplit("/", 1)[0]) if "/" in rel else ""
    if pasta and ext in {".pdf", ".zip"} and re.search(r"tcci|invoice|fatura", pasta):
        return "tcci"
    num = re.sub(r"[^a-z0-9]", "", norm(p.get("numero", "")))
    if ext == ".pdf" and len(num) >= 6:
        toks = re.findall(r"[a-z0-9]+", norm(Path(nome).stem))
        resto = [w for w in toks if num not in w]
        if len(resto) < len(toks) and all(w in _TRANSP_EXTRA or (w.isdigit() and len(w) <= 2) for w in resto):
            pn = norm(p.get("nome", ""))
            if re.match(r"(bl|bol|b ?/ ?l)\b", pn) or (not re.match(r"(hawb|awb|mawb)\b", pn) and p.get("modal") == "Marítimo"):
                return "bl"
            if re.match(r"(hawb|awb|mawb)\b", pn) or p.get("modal") == "Aéreo":
                return "awb"
    return "outro"


def arquivos_classificados(p: dict[str, Any]) -> list[dict[str, Any]]:
    return [{**f, "tipo": tipo_no_processo(f, p)} for f in p.get("arquivos", [])]


def tipo_pelo_conteudo(text: str) -> str:
    """PDF generico ("Documentos.pdf"): o que o texto mostra (so a 1a e a 2a pagina)."""
    up = (text or "").upper()
    if "COMMERCIAL INVOICE" in up and "INVOICE NUMBER:" in up:
        return "tcci"
    if "BILL OF LADING" in up or "B/L NO" in up:
        return "bl"
    if "AIR WAYBILL" in up or "AIR WAY BILL" in up:
        return "awb"
    return ""


# Pais de origem como vem nas faturas (ingles, portugues ou cortado no acento: "Vietn", "Indon", "Tail") -> nome unico
_PAISES = {"vietnam": "Vietnã", "vietn": "Vietnã", "vietna": "Vietnã", "viet nam": "Vietnã",
           "indonesia": "Indonésia", "indon": "Indonésia", "china": "China", "thailand": "Tailândia", "tail": "Tailândia",
           "tailandia": "Tailândia", "india": "Índia", "cambodia": "Camboja", "camboja": "Camboja", "sri lanka": "Sri Lanka",
           "pakistan": "Paquistão", "paquist": "Paquistão", "paquistao": "Paquistão", "georgia": "Geórgia", "ge": "Geórgia",
           "argentina": "Argentina", "turkey": "Turquia", "turquia": "Turquia", "turkiye": "Turquia", "malaysia": "Malásia",
           "mal": "Malásia", "malasia": "Malásia", "bosnia-herz": "Bósnia e Herzegovina", "bosnia": "Bósnia e Herzegovina",
           "bosnia and herzegovina": "Bósnia e Herzegovina", "jordan": "Jordânia", "jord": "Jordânia", "jordania": "Jordânia",
           "philippines": "Filipinas", "filipinas": "Filipinas", "egypt": "Egito", "egito": "Egito", "honduras": "Honduras",
           "taiwan": "Taiwan", "mexico": "México", "italy": "Itália", "it": "Itália", "italia": "Itália",
           "guatemala": "Guatemala", "singapore": "Singapura", "cingapura": "Singapura", "south korea": "Coreia do Sul",
           "korea": "Coreia do Sul", "coreia do sul": "Coreia do Sul", "el salvador": "El Salvador", "bulg": "Bulgária",
           "bulgaria": "Bulgária", "brazil": "Brasil", "brasil": "Brasil", "bangladesh": "Bangladesh", "portugal": "Portugal",
           "united states": "Estados Unidos", "usa": "Estados Unidos", "japan": "Japão", "japao": "Japão"}


def pais(nome: str) -> str:
    chave = re.sub(r"\s+", " ", norm(nome)).strip(" .,;")
    return _PAISES.get(chave, (nome or "").strip().title())


# ---------------------------------------------------------------------------
# Leitura dos documentos
# ---------------------------------------------------------------------------
def _pdf_text(data: bytes, pages: int = 1) -> str:
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages[:pages])


def _find(pattern: str, text: str, flags: int = 0) -> str:
    m = re.search(pattern, text, flags)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _cabecalho_em_bloco(text: str) -> dict[str, str]:
    """Modelo da fatura Nike em que os rótulos vêm todos juntos e os valores depois (achado na auditoria de 25/11/2026: o
    número saía "Invoice"): "Invoice Number:\\nInvoice Date:\\n...\\nCustomer PO number #:\\n4543786533\\nSeptember 29, 2026...".
    Devolve rótulo -> valor na mesma ordem; vazio quando o PDF é do modelo normal (rótulo e valor na mesma linha)."""
    linhas = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    try:
        i = linhas.index("Invoice Number:")
    except ValueError:
        return {}
    rot = []
    while i < len(linhas) and linhas[i].endswith(":") and len(linhas[i]) < 40:
        rot.append(linhas[i][:-1].strip())
        i += 1
    if len(rot) < 2:
        return {}
    vals = [l for l in linhas[i:i + len(rot) + 6] if l][:len(rot)]
    return dict(zip(rot, vals)) if len(vals) == len(rot) else {}


def ler_fatura_nike(text: str) -> dict[str, Any] | None:
    """Fatura comercial da Nike (TCCI): um PDF por item de PO."""
    if "COMMERCIAL INVOICE" not in text or "Invoice Number:" not in text:
        return None
    blk = _cabecalho_em_bloco(text)
    if blk:  # modelo com rótulos em bloco: monta um texto "rótulo: valor" para as mesmas regras de sempre
        text = "\n".join(f"{k}: {v}" for k, v in blk.items()) + "\n" + text.replace("Invoice Number:", "Invoice Number (bloco):")
    fab = re.search(r"Manufacturing Factory:\s*\n(.+?)\n(.*?)\n", text)
    fabricante = ""
    if fab:
        fabricante = fab.group(1).strip()
        if fab.group(2).strip() and fab.group(2).strip().isupper() and len(fab.group(2).strip()) < 40 and not re.search(r"\d", fab.group(2)):
            fabricante += " " + fab.group(2).strip()  # nome que quebrou em duas linhas ("... JOINT STOCK / COMPANY")
    data = _find(r"Invoice Date:\s*([A-Za-z]+ \d{1,2}, \d{4})", text)
    try:
        data_iso = datetime.strptime(data, "%B %d, %Y").date().isoformat() if data else ""
    except ValueError:
        data_iso = ""
    return {"fatura": _find(r"Invoice Number:\s*(\S+)", text), "data": data_iso,
            "vendedor": text.strip().splitlines()[0].strip()[:80],
            "incoterm": _find(r"Terms of Sale:\s*(\S+)", text), "modal": _find(r"Mode of Transportation:\s*(.+)", text),
            "origem": _find(r"Country of Origin:\s*\n?\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .,'-]+)", text) or _find(r"From:\s*(.+)", text),
            "doc_transporte": _find(r"Transport Document #:\s*(\S+)", text),
            "po_cliente": _find(r"Customer PO number #:\s*(\S+)", text), "po": _find(r"\bPO#:\s*(\S+)", text),
            "material": _find(r"Material#:\s*(\S+)", text), "temporada": _find(r"Season Code & Year#:\s*(\S+)", text),
            "quantidade": num_eu(_find(r"Total Invoice\s*\n?\s*Quantity:\s*\n?\s*([\d.,]+)", text)),
            "valor": num_eu(_find(r"Total Amount:\s*([\d.,]+)", text)),
            "peso_bruto": num_eu(_find(r"Total Gross Weight:\s*([\d.,]+)", text)),
            "peso_liquido": num_eu(_find(r"Total Net Weight:\s*([\d.,]+)", text)),
            "caixas": num_eu(_find(r"Total Number of\s*\n?\s*Cartons:\s*\n?\s*([\d.,]+)", text)),
            "fabricante": fabricante}


def ler_fatura_manual(text: str) -> dict[str, Any] | None:
    """Fatura manual da Nike ("Commercial Invoice" com "Invoice No:" e uma tabela de material; achada na auditoria de
    25/11/2026 no BL JKT012777). O pedido vem do nome do arquivo (validar_fatura)."""
    if "Commercial Invoice" not in text or not re.search(r"Invoice No:\s*\d", text):
        return None
    item = re.search(r"\n([A-Z0-9]{4,8}-\d{3})\s+.+?\s+(\d+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+\$", text)
    data = _find(r"Inv Date:\s*(\d{1,2}-[A-Za-z]{3}-\d{2,4})", text)
    try:
        data_iso = datetime.strptime(data, "%d-%b-%y" if len(data.split("-")[-1]) == 2 else "%d-%b-%Y").date().isoformat()
    except ValueError:
        data_iso = ""
    return {"fatura": _find(r"Invoice No:\s*(\d+)", text), "data": data_iso, "vendedor": "NIKE (fatura manual)",
            "incoterm": _find(r"Price Term:\s*(\S+)", text), "modal": "", "origem": _find(r"Port of Loading:\s*(.+)", text),
            "doc_transporte": _find(r"BL No:\s*(\S+)", text), "po_cliente": "", "po": "",
            "material": item.group(1) if item else "", "temporada": "",
            "quantidade": num_us(item.group(3)) if item else None, "valor": num_us(_find(r"Grand Total \$\s*\n?.*?([\d,]+\.\d{2})\s*$", text, re.M)),
            "peso_bruto": num_us(item.group(5)) if item else None, "peso_liquido": num_us(item.group(4)) if item else None,
            "caixas": num_us(item.group(2)) if item else None, "fabricante": "", "manual": True}


def numero_fatura_ok(v: Any) -> bool:
    return bool(re.fullmatch(r"\d{8,12}", str(v or "")))


def validar_fatura(f: dict[str, Any] | None, nome: str) -> tuple[dict[str, Any] | None, str]:
    """Trava da leitura (pedido do usuario: os PDFs nem sempre vem no mesmo layout): so vale fatura com numero de 8 a 12
    digitos; o pedido e o numero sao comparados com o NOME do arquivo (diferenca vira alerta na conferencia). O que nao
    passa volta como None + motivo e vai para "Conferir PDF" (nunca entra como fatura lida)."""
    if not f:
        return None, ""
    if not numero_fatura_ok(f.get("fatura")):
        return None, f"número da fatura não reconhecido no PDF (lido: \"{str(f.get('fatura') or '')[:20]}\")"
    info = nome_pdf_fatura(nome)
    alertas = []
    if info.get("po"):
        if not f.get("po"):
            f["po"] = info["po"]
        elif f["po"] != info["po"]:
            alertas.append(f"pedido no PDF ({f['po']}) diferente do nome do arquivo ({info['po']})")
    if info.get("fatura") and info["fatura"] != f["fatura"]:
        alertas.append(f"número no PDF ({f['fatura']}) diferente do nome do arquivo ({info['fatura']})")
    if not f.get("material"):
        alertas.append("material não lido no PDF")
    if f.get("quantidade") in (None, 0):
        alertas.append("quantidade não lida no PDF")
    if f.get("manual"):
        alertas.append("fatura manual (outro modelo de PDF)")
    if alertas:
        f["alerta"] = "; ".join(alertas)
    return f, ""


def ler_bl(text: str, nome: str = "") -> dict[str, Any]:
    """BL: armador pelo prefixo (SCAC), conteineres (com digito verificador), NCM, pesos e, no BL da Maersk (texto
    picotado: lido com as quebras removidas), navio, viagem, portos, data de embarque e fretes por conteiner."""
    flat = re.sub(r"\s*\n\s*", "", text)
    out: dict[str, Any] = {"conteineres": conteineres(text) or conteineres(flat)}
    scac = re.search(r"\b(" + "|".join(SCAC) + r")", f"{nome} {flat[:3000]}".upper())
    if not scac and "maersk" in text.casefold():
        scac = re.match("(MAEU)", "MAEU")
    out["armador"] = SCAC.get(scac.group(1), "") if scac else ""
    ncm = re.search(r"NCM\s*:?\s*((?:\d{4,8}[\s,;/.]*){1,40})", text)
    out["ncm"] = sorted({c[:4] for c in re.findall(r"\d{4,8}", ncm.group(1))}) if ncm else []
    if out["armador"] == "Maersk":
        # So vale texto com cara de nome (o BL da Maersk tem mais de um layout; no outro o trecho vem com lixo)
        nome_ok = lambda v, n=60: v[:n] if re.fullmatch(r"[A-Za-z][A-Za-z0-9 ,.'/-]{2,}", v or "") else ""  # noqa: E731
        out["navio"] = nome_ok(_find(r"Vessel(.+?)Voyage No\.", flat))
        out["viagem"] = _find(r"Voyage No\.([A-Z0-9]{2,8})(?:Port of Loading|Place of)", flat)
        out["porto_embarque"] = nome_ok(_find(r"Port of Loading(.+?)Place of", flat))
        out["porto_descarga"] = nome_ok(_find(r"Port of Discharge(.+?)(?:Signed|Place of|Freight)", flat))
        out["embarque"] = _find(r"Shipped on Board Date \( ?Local Time ?\)(\d{4}-\d{2}-\d{2})", flat)
        tot = re.search(r"B/L TOTAL SUMMARY-+(\d+)CTN ([\d.,]+)CBM ([\d.,]+)KGS", flat)
        if tot:
            out.update(caixas=float(tot.group(1)), cbm=num_us(tot.group(2)), peso_bruto=num_us(tot.group(3)))
        frete = re.search(r"Basic Ocean Freight([\d.,]+)Per ContainerUSD", flat)
        bunker = re.search(r"Fossil Fuel Fee([\d.,]+)Per ContainerUSD", flat)
        out["frete_usd_cntr"] = num_us(frete.group(1)) if frete else None
        out["bunker_usd_cntr"] = num_us(bunker.group(1)) if bunker else None
    else:
        # CMA e outros: linha do conteiner "CMAU5597104 1 x 40HC 1096 CARTONS 6486.450 3860 67.360"
        rows = re.findall(r"([A-Z]{4}\d{7})\s+\d+\s*x\s*(\w+)\s+(\d+)\s+CARTONS?\s+([\d.,]+)\s+[\d.,]+\s+([\d.,]+)", text)
        if rows:
            out.update(caixas=float(sum(int(r[2]) for r in rows)), peso_bruto=round(sum(num_us(r[3]) or 0 for r in rows), 3),
                       cbm=round(sum(num_us(r[4]) or 0 for r in rows), 3))
    return out


def ler_fatura_zelus(text: str) -> dict[str, Any] | None:
    if "IMPORTER OF RECORD" not in text.upper() and "Zelus" not in text:
        return None
    return {"fatura": _find(r"Invoice Number\s+(\S+)", text), "fabricante": _find(r"Co Name\s+(.+?),", text)[:80],
            "modal": _find(r"Mode of Transport:\s*(\w+)", text), "origem": _find(r"Country of Origin:\s*([A-Za-z ]+?)(?:\s{2,}|\n|VAT|$)", text),
            "peso_bruto": num_us(_find(r"Gross Weight:\s*([\d.,]+)", text)),
            "peso_liquido": num_us(_find(r"Net Weight:\s*([\d.,]+)", text)), "caixas": num_us(_find(r"Cartons:\s*([\d.,]+)", text))}


def ler_proforma(data: bytes) -> dict[str, Any]:
    """Proforma (Excel da equipe): soma das linhas pelos cabecalhos (Quantity, Gross Weight, Total $...)."""
    import openpyxl
    book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        ws = book.worksheets[0]
        head, cols = None, {}
        out: dict[str, Any] = {"linhas": 0, "quantidade": 0.0, "peso_bruto": 0.0, "peso_liquido": 0.0, "valor": 0.0,
                               "fabricantes": set(), "ncm": set(), "tcci": set(), "conteineres": set(), "alt_preco": 0, "alt_qtd": 0}
        want = {"quantity": "quantidade", "gross weight": "peso_bruto", "net weight": "peso_liquido", "total $": "valor",
                "factory name": "fabricantes", "hts code": "ncm", "tcci number": "tcci", "cntr. id": "conteineres",
                "flag alt. preco": "alt_preco", "flag. alt. qtd.": "alt_qtd"}
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i > 3000:
                break
            if head is None:
                labels = [norm(c).strip() if isinstance(c, str) else "" for c in row]
                if "po fisia" in labels and "quantity" in labels:
                    head = labels
                    cols = {want[l]: j for j, l in enumerate(labels) if l in want}
                continue
            if not any(v not in (None, "") for v in row):
                continue
            q = row[cols["quantidade"]] if "quantidade" in cols and cols["quantidade"] < len(row) else None
            if not isinstance(q, (int, float)):
                continue
            out["linhas"] += 1
            for key in ("quantidade", "peso_bruto", "peso_liquido", "valor"):
                v = row[cols[key]] if key in cols and cols[key] < len(row) else None
                if isinstance(v, (int, float)):
                    out[key] += float(v)
            for key in ("fabricantes", "ncm", "tcci", "conteineres"):
                v = row[cols[key]] if key in cols and cols[key] < len(row) else None
                if v not in (None, ""):
                    v = str(v).strip()
                    out[key].add(v[:4] if key == "ncm" else v[:80])
            for key in ("alt_preco", "alt_qtd"):
                v = row[cols[key]] if key in cols and cols[key] < len(row) else None
                if v not in (None, "", 0, "0", False) and norm(v) not in {"nao", "n", "-", "ok"}:
                    out[key] += 1
        if head is None:
            return {"lida": False}
        for key in ("fabricantes", "ncm", "tcci", "conteineres"):
            out[key] = sorted(out[key])
        for key in ("quantidade", "peso_bruto", "peso_liquido", "valor"):
            out[key] = round(out[key], 3)
        out["conteineres"] = [c for c in out["conteineres"] if conteiner_valido(c.upper())]
        out["lida"] = True
        return out
    finally:
        book.close()


def ler_checklist(data: bytes, nome: str) -> dict[str, Any]:
    from xml.etree import ElementTree as ET
    z = zipfile.ZipFile(io.BytesIO(data))
    root = ET.fromstring(z.read("word/document.xml"))
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    text = "\n".join("".join(t.text or "" for t in p.iter(ns + "t")) for p in root.iter(ns + "p"))
    return checklist_do_texto(text, nome)


def checklist_do_texto(text: str, nome: str) -> dict[str, Any]:
    """Checklist ID 677: cada item e "- Shipper - OK" (preenchido) ou "- Shipper - " (vazio). Os itens de identificacao
    ("Numeracao BOL", "Identificacao BOL") trazem o numero, nao OK, e nao contam como item conferido (23/11/2026: desde
    08/2026 a maioria chega so com a identificacao preenchida, sem nenhum item conferido)."""
    oks = len(re.findall(r"-\s*OK\b", text, re.I))
    itens = [m for linha in text.split("\n") for m in re.finditer(r"-\s*([^-\n]+?)\s*-\s*(OK\b)?", linha, re.I)
             if "BOL" not in m.group(1).upper()]
    analista = _find(r"Nome Analista:[ \t]*([^\n]+)", text)
    bol = _find(r"BOL:[ \t]*([A-Z0-9]{6,})", text.upper())
    return {"id": _find(r"ID\s*(\d+)", nome), "revisado": _find(r"REVISADO\s*(\d{2}\.\d{2}\.\d{4})", nome.upper()),
            "itens_ok": oks, "itens_total": len(itens), "identificado": bool(bol), "preenchido": oks >= 3,
            "analista": analista[:60] if analista and len(analista) > 2 else ""}


# ---------------------------------------------------------------------------
# Pastas de processo
# ---------------------------------------------------------------------------
def numero_processo(name: str) -> str:
    base = re.sub(r"\(.*?\)", " ", name)
    base = re.split(r"\s+-\s+|\s{2,}", base.strip())[0]
    base = re.sub(r"^(BL|BOL|HAWB|AWB|MAWB)\s+", "", base.strip(), flags=re.I)
    return re.sub(r"\s+", "", base).upper()[:30]


def achar_processos(raiz: Path) -> list[dict[str, Any]]:
    """Pastas de processo de cada operacao (sem entrar nas subpastas do processo)."""
    found: list[dict[str, Any]] = []

    def walk(path: Path, op: str, labels: list[str], depth: int) -> None:
        try:
            entries = sorted((e for e in os.scandir(path) if e.is_dir() and not e.name.startswith((".", "~", "$"))),
                             key=lambda e: e.name)
        except OSError:
            return
        for e in entries:
            if PROC_RE.search(e.name) and not (op == "ZELUS" and not labels):
                found.append({"op": op, "pasta": e.path, "nome": e.name, "grupos": labels})
            elif depth < 3:
                walk(Path(e.path), op, labels + [e.name], depth + 1)

    for op in OPERACOES:
        if (raiz / op).is_dir():
            walk(raiz / op, op, [], 0)
    return found


def _id(pasta: str, raiz: Path) -> str:
    return hashlib.sha1(os.path.relpath(pasta, raiz).replace("\\", "/").casefold().encode("utf-8")).hexdigest()[:16]


def _modal(op: str, nome: str, grupos: list[str], tipos: set[str]) -> str:
    n, g = norm(nome), norm(" ".join(grupos))
    if re.match(r"(bl|bol|b ?/ ?l)\b", n) or "maritimo" in g:
        return "Marítimo"
    if re.match(r"(hawb|awb|mawb)\b", n) or "aereo" in g or "awb" in tipos:
        return "Aéreo"
    return "Marítimo" if "bl" in tipos else ""


def ler_processo(info: dict[str, Any], raiz: Path, anterior: dict[str, Any] | None) -> dict[str, Any]:
    """Le uma pasta de processo; reaproveita a leitura dos arquivos que nao mudaram."""
    pasta = Path(info["pasta"])
    old_files = {f["rel"]: f for f in (anterior or {}).get("arquivos", [])} if (anterior or {}).get("v") == VERSAO_LEITURA else {}
    files = []
    for dirpath, _dirs, names in os.walk(pasta):
        for name in names:
            if name.lower() in {"desktop.ini", "thumbs.db"} or name.startswith("~$"):
                continue
            full = Path(dirpath) / name
            try:
                st = full.stat()
            except OSError:
                continue
            rel = os.path.relpath(full, pasta).replace("\\", "/")
            item = {"rel": rel, "nome": name, "tipo": tipo_arquivo(name), "tam": st.st_size,
                    "mod": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds")}
            prev = old_files.get(rel)
            if prev and prev.get("tam") == item["tam"] and prev.get("mod") == item["mod"]:
                item["dados"] = prev.get("dados")
                item["erro"] = prev.get("erro", "")
                for k in ("tipo_lido", "conteudo_lido"):
                    if prev.get(k):
                        item[k] = prev[k]
            else:
                item["dados"], item["erro"] = _ler_arquivo(full, item["tipo"], name)
            files.append(item)
    files.sort(key=lambda f: f["rel"].casefold())
    try:
        criada = datetime.fromtimestamp(os.stat(pasta).st_ctime, timezone.utc)
    except OSError:
        criada = None
    tipos = {f["tipo"] for f in files}
    proc = {"numero": numero_processo(info["nome"]), "nome": info["nome"], "arquivos": files,
            "modal": _modal(info["op"], info["nome"], info["grupos"], tipos)}
    completar_classificacao(proc, pasta)
    tipos = {f["tipo"] for f in arquivos_classificados(proc)}
    return {"v": VERSAO_LEITURA, "id": _id(info["pasta"], raiz), "op": info["op"], "nome": info["nome"],
            "grupos": info["grupos"], "rel": os.path.relpath(info["pasta"], raiz).replace("\\", "/"),
            "numero": numero_processo(info["nome"]), "wfadim": _find(r"(WFADIM\d+)", info["nome"].upper()),
            "ref_fisia": _find(r"(FISIA\s*\d+)", info["nome"].upper()).replace(" ", ""),
            # Anotacao da equipe no nome da pasta: "(Pendente de LI)", "(Liberado com Pendência de NTC)", "(INFLUENCER)"
            "obs": "; ".join(o.strip() for o in re.findall(r"\(([^)]{3,60})\)", info["nome"])
                             if not re.fullmatch(r"\s*(FISIA\s*\d+|\d+)\s*", o, re.I)),
            "modal": _modal(info["op"], info["nome"], info["grupos"], tipos),
            "criada": criada.isoformat(timespec="seconds") if criada else "", "arquivos": files,
            "lido_em": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def completar_classificacao(proc: dict[str, Any], pasta: Path) -> int:
    """Depois da classificacao pelo nome: (1) le os arquivos que viraram fatura/BL/AWB pela pasta ou pelo numero e
    ainda nao tem dados; (2) se ainda falta o documento de transporte ou a fatura, abre os PDFs genericos (ate 5,
    "Documentos.pdf") e ve pelo texto se sao BL, AWB ou fatura. Devolve quantos arquivos leu."""
    lidos = 0
    for f in proc["arquivos"]:
        t = tipo_no_processo(f, proc)
        if t != f["tipo"] and f.get("dados") is None and not f.get("erro") and t in {"tcci", "bl", "awb"}:
            f["dados"], f["erro"] = _ler_arquivo(pasta / f["rel"], t, f["nome"])
            lidos += 1
    tipos = {tipo_no_processo(f, proc) for f in proc["arquivos"]}
    falta_transp = not (tipos & {"bl", "awb"})
    falta_fatura = not (tipos & {"tcci", "ci"})
    if not (falta_transp or falta_fatura):
        return lidos
    candidatos = [f for f in proc["arquivos"] if tipo_no_processo(f, proc) == "outro" and f["nome"].lower().endswith(".pdf")
                  and not f.get("conteudo_lido") and 0 < f.get("tam", 0) < 25_000_000][:5]
    for f in candidatos:
        f["conteudo_lido"] = True
        try:
            text = _pdf_text((pasta / f["rel"]).read_bytes(), 2)
        except Exception:  # noqa: BLE001 - PDF quebrado: continua "outro"
            continue
        lidos += 1
        t = tipo_pelo_conteudo(text)
        if (t == "bl" and falta_transp) or (t == "awb" and falta_transp) or (t == "tcci" and falta_fatura):
            f["tipo_lido"] = t
            f["dados"] = ler_bl(text, f["nome"]) if t == "bl" else {"conteineres": conteineres(text)} if t == "awb" \
                else ({"faturas": [fv]} if (fv := validar_fatura(ler_fatura_nike(text), f["nome"])[0]) else None)
    return lidos


def _ler_arquivo(full: Path, tipo: str, name: str) -> tuple[Any, str]:
    ext = full.suffix.lower()
    try:
        if tipo == "tcci" and ext == ".zip":
            data = full.read_bytes()
            z = zipfile.ZipFile(io.BytesIO(data))
            faturas, nao_lidos = [], []
            for n in z.namelist():
                if not n.lower().endswith(".pdf"):
                    continue
                tam = z.getinfo(n).file_size
                if tam >= 20_000_000:
                    nao_lidos.append([n, "arquivo grande demais"])
                    continue
                motivo = ""
                try:
                    t = _pdf_text(z.read(n), 1) if tam else ""
                    f, motivo = validar_fatura(ler_fatura_nike(t) or ler_fatura_manual(t), n)
                    if not f and not motivo:
                        motivo = "PDF vazio (0 bytes)" if not tam else "PDF sem texto (imagem)" if len(t.strip()) < 60 else "modelo de PDF não reconhecido"
                except Exception as exc:  # noqa: BLE001 - PDF quebrado dentro do zip: segue com os outros
                    f, motivo = None, f"PDF não abre ({type(exc).__name__})"
                if f:
                    faturas.append(f)
                else:  # nunca calado: o PDF que não virou fatura vai para a conferência com o OTR (auditoria de 25/11/2026)
                    nao_lidos.append([n, motivo])
            return {"faturas": faturas, "pdfs": sum(1 for n in z.namelist() if n.lower().endswith(".pdf")),
                    "nao_lidos": nao_lidos}, ""
        if ext == ".pdf" and tipo in {"tcci", "ci", "bl", "awb"} and full.stat().st_size < 25_000_000:
            text = _pdf_text(full.read_bytes(), 2)
            if len(text.strip()) < 60:
                return None, "sem texto (imagem escaneada)"
            if tipo in {"tcci", "ci"}:
                f, motivo = validar_fatura(ler_fatura_nike(text) or ler_fatura_manual(text), name)
                if f:
                    return {"faturas": [f]}, ""
                if motivo:
                    return None, motivo
                z = ler_fatura_zelus(text)
                return ({"zelus": z}, "") if z else (None, "formato não reconhecido")
            if tipo == "bl":
                return ler_bl(text, name), ""
            return {"conteineres": conteineres(text)}, ""
        if tipo == "proforma" and ext in {".xlsx", ".xlsm"} and full.stat().st_size < 40_000_000:
            return ler_proforma(full.read_bytes()), ""
        if tipo == "checklist" and ext == ".docx":
            return ler_checklist(full.read_bytes(), name), ""
    except Exception as exc:  # noqa: BLE001 - arquivo corrompido ou bloqueado: registra e segue
        return None, f"não foi possível ler ({type(exc).__name__})"
    return None, ""


# ---------------------------------------------------------------------------
# Resumo do processo e pre-conferencia (Checklist ID 677)
# ---------------------------------------------------------------------------
def _rel_diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or (not a and not b):
        return None
    return abs(a - b) / max(abs(a), abs(b))


def resumir(p: dict[str, Any]) -> dict[str, Any]:
    files = arquivos_classificados(p)
    tipos = {f["tipo"] for f in files}
    faturas = [f for x in files for f in ((x.get("dados") or {}).get("faturas") or [])]
    zelus = [(x.get("dados") or {}).get("zelus") for x in files if (x.get("dados") or {}).get("zelus")]
    bls = [x["dados"] for x in files if x["tipo"] == "bl" and isinstance(x.get("dados"), dict)]
    profs = [x["dados"] for x in files if x["tipo"] == "proforma" and (x.get("dados") or {}).get("lida")]
    cks = [x["dados"] for x in files if x["tipo"] == "checklist" and isinstance(x.get("dados"), dict)]
    # Proforma revisada: vale a mais recente (ultima na ordem de modificacao)
    prof_files = sorted([x for x in files if x["tipo"] == "proforma" and (x.get("dados") or {}).get("lida")], key=lambda x: x["mod"])
    prof = prof_files[-1]["dados"] if prof_files else None
    bl = max(bls, key=lambda b: len([k for k, v in b.items() if v]), default=None)
    # Faturas iguais repetidas (zip e PDF solto, TCCIs revisadas): conta cada numero de fatura uma vez
    unicas = {}
    for f in faturas:  # numero invalido ("Invoice") nunca junta faturas diferentes
        unicas[f.get("fatura") if numero_fatura_ok(f.get("fatura")) else id(f)] = f
    fat = list(unicas.values())
    soma = lambda k: round(sum(f.get(k) or 0 for f in fat), 3) if fat and any(f.get(k) is not None for f in fat) else None  # noqa: E731
    z_peso = round(sum(z.get("peso_bruto") or 0 for z in zelus), 3) if any(z.get("peso_bruto") for z in zelus) else None
    # Fabricante = a fabrica da fatura ("Manufacturing Factory"); a coluna "Factory Name" da proforma traz a empresa
    # fornecedora (outra coisa), entao so entra quando o processo nao tem fatura lida.
    fabricantes = fabricantes_unicos([f["fabricante"] for f in fat if f.get("fabricante")]
                                     + [z["fabricante"] for z in zelus if z.get("fabricante")])
    if not fabricantes:
        fabricantes = fabricantes_unicos(list((prof or {}).get("fabricantes") or []))
    origens = sorted({pais(f["origem"]) for f in fat if f.get("origem")} | {pais(z["origem"]) for z in zelus if z.get("origem")})
    armador = (bl or {}).get("armador") or next((SCAC[k] for k in SCAC if k in p.get("nome", "").upper() or any(k in f["nome"].upper() for f in files)), "")
    criada = p.get("criada", "")
    # BOL completo (23/11/2026, pedido do usuario): a pasta chama "BL 280813701", o BL e MAEU280813701. Vem do documento de
    # transporte citado nas faturas; sem fatura, do nome de algum arquivo (codigo do armador + numero da pasta).
    num = re.sub(r"[^A-Z0-9]", "", (p.get("numero") or "").upper())
    citados: dict[str, int] = {}
    for f in fat:
        d = re.sub(r"[^A-Z0-9]", "", (f.get("doc_transporte") or "").upper())
        if d and num and num in d:
            citados[d] = citados.get(d, 0) + 1
    bol = max(citados, key=citados.get) if citados else ""
    # Faturas que citam OUTRO BL na mesma pasta (23/11/2026: ~410 processos, quase todos de 2022-2023). A proforma decide:
    # - so as faturas do BL batem com a proforma = fatura de outro embarque salva por engano: fica fora das somas (aviso);
    # - todas batem = processo consolidado (varios BLs na mesma proforma): somas com todas (aviso, nao divergencia);
    # - nenhuma bate (ou sem proforma) = fica como antes e a conferencia do BL nas faturas aponta.
    def _do_proc(f: dict[str, Any]) -> bool:
        d = re.sub(r"[^A-Z0-9]", "", (f.get("doc_transporte") or "").upper())
        return not d or not num or num in d or d in num
    outras = sorted({re.sub(r"[^A-Z0-9]", "", (f.get("doc_transporte") or "").upper()) for f in fat if not _do_proc(f)})
    consolidado = False
    q_prof = (prof or {}).get("quantidade")
    if outras and q_prof and any(_do_proc(f) for f in fat):
        q_todas = sum(f.get("quantidade") or 0 for f in fat)
        q_bl = sum(f.get("quantidade") or 0 for f in fat if _do_proc(f))
        if abs(q_bl - q_prof) < 0.5 and abs(q_todas - q_prof) >= 0.5:
            fat = [f for f in fat if _do_proc(f)]
        elif abs(q_todas - q_prof) < 0.5:
            consolidado = True
        else:
            outras = []
    else:
        outras = []
    if not bol and num:
        bol = next((m.group(1) for x in files for m in [re.search(r"(?<![A-Z0-9])([A-Z]{4}" + re.escape(num) + r")(?![0-9])",
                    x["nome"].upper().replace(" ", ""))] if m), "")
    out = {"id": p["id"], "op": p["op"], "nome": p["nome"], "numero": p["numero"], "grupo": " › ".join(p.get("grupos") or []),
           "bol": bol if bol != num else "",
           "wfadim": p.get("wfadim", ""), "ref": p.get("ref_fisia", ""), "obs": p.get("obs", ""),
           "modal": p.get("modal", ""), "criada": criada,
           "ano": int(criada[:4]) if criada else None, "mes": int(criada[5:7]) if criada else None,
           "armador": armador, "origens": origens, "fabricantes": fabricantes[:12],
           "temporadas": sorted({f["temporada"] for f in fat if f.get("temporada")}),
           "faturas": len(fat), "faturas_outras": outras[:6], "consolidado": consolidado, "qtd": soma("quantidade"),
           "valor_usd": soma("valor"),
           "peso_bruto": soma("peso_bruto") if fat else z_peso, "caixas": soma("caixas"),
           "conteineres": (bl or {}).get("conteineres") or (prof or {}).get("conteineres") or [],
           "navio": (bl or {}).get("navio", ""), "porto_embarque": (bl or {}).get("porto_embarque", ""),
           "porto_descarga": (bl or {}).get("porto_descarga", ""), "embarque": (bl or {}).get("embarque", ""),
           "frete_usd_cntr": (bl or {}).get("frete_usd_cntr"), "bunker_usd_cntr": (bl or {}).get("bunker_usd_cntr"),
           "docs": sorted(tipos - {"outro"}), "n_arquivos": len(files),
           # checklist na pasta que ainda nao foi lido (ex.: erro ao abrir o .docx) NAO e "sem checklist"
           "checklist": next(({"id": c.get("id"), "revisado": c.get("revisado"), "preenchido": c.get("preenchido"),
                               "itens_ok": c.get("itens_ok"), "itens_total": c.get("itens_total"),
                               "identificado": c.get("identificado")} for c in cks),
                             {"id": None, "revisado": None, "preenchido": None, "nao_lido": True} if "checklist" in tipos else None),
           "sem_texto": sum(1 for f in files if f.get("erro", "").startswith("sem texto"))}
    # Faturas × OTR Nike (25/11/2026): lista compacta das faturas lidas (número, pedido, material, quantidade, peso bruto),
    # para conferir com o OTR sem reabrir o processo; fica fora da lista enviada à tela (_emb_row)
    out["tccis"] = [[f["fatura"], f.get("po") or "", f.get("material") or "", f.get("quantidade"), f.get("peso_bruto"),
                     f.get("alerta") or ""] for f in fat if numero_fatura_ok(f.get("fatura"))]
    # trava da leitura: fatura gravada com numero invalido (leituras antigas) vai para "Conferir PDF" pelo pedido+material
    out["pdf_sem_leitura"] = pdfs_sem_leitura(files) + [
        [f"fatura do pedido {f.get('po') or '?'} ({f.get('material') or '?'})",
         f"número da fatura não reconhecido no PDF (lido: \"{str(f.get('fatura') or '')[:20]}\")", 1,
         {"po": f.get("po") or "", "material": f.get("material") or ""}]
        for f in fat if not numero_fatura_ok(f.get("fatura"))]
    if out["checklist"]:
        out["checklist"]["estado"] = checklist_estado(out["checklist"])
    # Pre-conferencia so a partir de 2025 (23/11/2026, pedido do usuario: "pra nao baguncar o sistema"; as divergencias
    # antigas eram quase todas de 2022-2023, com pastas consolidadas e faturas de outros BLs). Os anteriores continuam na
    # lista e na busca, com os documentos, mas sem conferencia (situacao "historico").
    if criada and criada < CONFERENCIA_DESDE:
        out["conferencia"], out["situacao"] = [], "historico"
        return out
    out["conferencia"] = conferir(p, out, fat, bl, prof)
    out["situacao"] = situacao(out["conferencia"])
    return out


FAB_GENERIC = {"vietnam", "viet", "nam", "the", "pt", "cong", "ty", "co", "company", "ltd", "limited", "inc", "corp",
               "corporation", "industrial", "industries", "industry", "international", "group", "jsc", "joint", "stock",
               "sdn", "bhd", "tnhh", "pvt", "private", "shoes", "shoe", "footwear", "garment", "garments", "apparel", "mfg"}


def fab_chave(name: str) -> str:
    """Chave do fabricante para comparar nomes escritos de jeitos diferentes ('VIETNAM CHING LUH SHOES' =
    'Vietnam Chingluh Shoes Co. Ltd.'): palavras sem acento e sem as genericas, juntas, 10 primeiras letras."""
    words = [w for w in re.findall(r"[a-z0-9]+", norm(name)) if w not in FAB_GENERIC]
    return "".join(words)[:10]


def fab_igual(a: str, b: str) -> bool:
    """Mesma fabrica com grafia diferente ('NAM DIHN STELLA' x 'Nam Dinh Stella'): chave igual, uma comecando pela
    outra ou 80% parecidas."""
    import difflib
    if not a or not b:
        return False
    return a == b or (min(len(a), len(b)) >= 6 and (a.startswith(b) or b.startswith(a))) or \
        difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def fabricantes_unicos(names: list[str]) -> list[str]:
    keys: list[str] = []
    out: list[str] = []
    for n in names:
        k = fab_chave(n)
        if k and not any(fab_igual(k, x) for x in keys):
            keys.append(k)
            out.append(re.sub(r"\s+", " ", n.strip()))
    return sorted(out, key=norm)


def _check(nome: str, status: str, detalhe: str) -> dict[str, str]:
    return {"item": nome, "status": status, "detalhe": detalhe}


def _n(v: float | None, casas: int = 0) -> str:
    if v is None:
        return "-"
    return f"{v:,.{casas}f}".replace(",", "#").replace(".", ",").replace("#", ".")


def conferir(p: dict[str, Any], r: dict[str, Any], fat: list[dict[str, Any]], bl: dict[str, Any] | None,
             prof: dict[str, Any] | None) -> list[dict[str, str]]:
    """Pre-conferencia do Checklist ID 677: ok, verificar ou sem dado (nunca conclui sem os dois lados)."""
    checks = []
    docs = set(r["docs"])
    if r["modal"] == "Marítimo":
        need = {"bl": "BL", "tcci": "faturas (TCCI)", "proforma": "proforma"}
    elif r["modal"] == "Aéreo":
        need = {"awb": "HAWB/AWB", "proforma": "proforma"}
        if p["op"] != "ZELUS":
            need["tcci"] = "faturas (TCCI)"
    else:
        need = {"proforma": "proforma"}
    if p["op"] == "ZELUS":
        need.pop("tcci", None)
        need["ci"] = "fatura comercial (CI)"
    if "ci" in docs:
        docs = docs | {"tcci"}  # "Fatura comercial HAWB ..." tambem e a fatura do processo
    falta = [label for k, label in need.items() if k not in docs]
    checks.append(_check("Documentos na pasta", "verificar" if falta else "ok",
                         f"Falta: {', '.join(falta)}." if falta else "BL/HAWB, faturas e proforma na pasta."))
    if fat:
        num = re.sub(r"[^A-Z0-9]", "", r["numero"])
        docs_t = {re.sub(r"[^A-Z0-9]", "", (f.get("doc_transporte") or "").upper()) for f in fat if f.get("doc_transporte")}
        if docs_t and num:
            bad = [d for d in docs_t if num not in d and d not in num]
            if r.get("consolidado"):  # varios BLs na mesma proforma: aviso, nao divergencia
                checks.append(_check("BL/HAWB nas faturas", "aviso",
                                     f"Processo consolidado: a proforma inclui faturas de {', '.join(sorted(bad)[:4])}."))
            else:
                checks.append(_check("BL/HAWB nas faturas", "verificar" if bad else "ok",
                                     f"Faturas com outro documento de transporte: {', '.join(sorted(bad)[:4])}." if bad
                                     else "As faturas deste embarque citam o BL/HAWB." if r.get("faturas_outras")
                                     else "Todas as faturas citam este embarque."))
    if r.get("faturas_outras") and not r.get("consolidado"):  # aviso: arquivo de outro embarque salvo na pasta
        checks.append(_check("Faturas de outro embarque na pasta", "aviso",
                             f"Faturas de {', '.join(r['faturas_outras'][:4])} estão nesta pasta; ficaram fora das somas."))
    if fat and prof:
        q_f, q_p = r["qtd"], prof.get("quantidade")
        if q_f is not None and q_p:
            checks.append(_check("Quantidade: faturas × proforma", "ok" if abs(q_f - q_p) < 0.5 else "verificar",
                                 f"Faturas {_n(q_f)} × proforma {_n(q_p)} unidades."))
        v_f, v_p = r["valor_usd"], prof.get("valor")
        d = _rel_diff(v_f, v_p)
        if d is not None:
            checks.append(_check("Valor: faturas × proforma", "ok" if d <= 0.005 else "verificar",
                                 f"Faturas US$ {_n(v_f, 2)} × proforma US$ {_n(v_p, 2)}."))
    if fat and bl and bl.get("peso_bruto"):
        d = _rel_diff(r["peso_bruto"], bl["peso_bruto"])
        if d is not None:
            checks.append(_check("Peso bruto: faturas × BL", "ok" if d <= 0.01 else "verificar",
                                 f"Faturas {_n(r['peso_bruto'], 1)} kg × BL {_n(bl['peso_bruto'], 1)} kg."))
    if bl and prof and bl.get("conteineres") and prof.get("conteineres"):
        a, b = set(bl["conteineres"]), {c.upper() for c in prof["conteineres"]}
        checks.append(_check("Contêiner: BL × proforma", "ok" if a == b else "verificar",
                             f"BL {', '.join(sorted(a))} × proforma {', '.join(sorted(b))}."))
    if bl and prof and bl.get("ncm") and prof.get("ncm"):
        fora = sorted(set(prof["ncm"]) - set(bl["ncm"]))
        checks.append(_check("NCM: proforma × BL", "verificar" if fora else "ok",
                             f"NCM da proforma que não está no BL: {', '.join(fora)}." if fora else "As NCMs da proforma estão no BL."))
    # Fabricante NAO e conferido: a proforma traz o fornecedor e a fatura a fabrica (nomes diferentes por natureza).
    ck = r.get("checklist")
    if r["modal"] == "Marítimo" and p["op"] == "INLINE" and r.get("criada", "") >= "2025-06-06":
        checks.append(_check("Checklist documental", *checklist_situacao(ck)))
    return checks


CHECKLIST_ESTADOS = {"completo": "preenchido", "parcial": "preenchido em parte", "identificacao": "só identificação",
                     "branco": "em branco", "nao_lido": "ainda não lido", "sem_ok": "nenhum item conferido"}


def checklist_estado(ck: dict[str, Any] | None) -> str:
    """completo (todos os itens com OK), parcial, identificacao (so o BOL, nenhum item conferido), branco, nao_lido."""
    if not ck:
        return ""
    if ck.get("nao_lido"):
        return "nao_lido"
    ok, tot = ck.get("itens_ok") or 0, ck.get("itens_total")
    if tot:  # leitura que conta os itens
        return "completo" if ok >= tot else "parcial" if ok else "identificacao" if ck.get("identificado") else "branco"
    return "completo" if ck.get("preenchido") else "sem_ok"  # leitura antiga (sem a contagem dos itens)


def checklist_situacao(ck: dict[str, Any] | None) -> tuple[str, str]:
    """(status, detalhe) do Checklist documental na pre-conferencia."""
    e, ok, tot = checklist_estado(ck), (ck or {}).get("itens_ok") or 0, (ck or {}).get("itens_total")
    return {"": ("verificar", "Sem checklist na pasta."),
            "nao_lido": ("verificar", "Checklist na pasta, ainda não lido pelo sistema (ele é lido na próxima leitura)."),
            "completo": ("ok", f"Checklist preenchido: {tot} de {tot} itens com OK." if tot else "Checklist preenchido."),
            "parcial": ("verificar", f"Checklist preenchido em parte: {ok} de {tot} itens com OK."),
            "identificacao": ("verificar", f"Checklist só com a identificação do processo (BOL): nenhum dos {tot} itens conferido (sem OK)."),
            "branco": ("verificar", "Checklist na pasta, mas em branco (nenhum item com OK)."),
            "sem_ok": ("verificar", "Checklist na pasta, sem nenhum item conferido (sem OK).")}[e]


def situacao(checks: list[dict[str, str]]) -> str:
    """incompleto (tela: Em montagem), verificar (Divergência), checklist (Checklist pendente: tudo bate e so falta concluir
    o checklist), ok (Conferido), sem_conferencia. Status "aviso" (ex.: fatura de outro embarque na pasta) nao muda a
    situacao (23/11/2026, pedido do usuario: "Falta documento" e "Verificar" soavam fortes demais)."""
    if any(c["item"] == "Documentos na pasta" and c["status"] == "verificar" for c in checks):
        return "incompleto"
    if any(c["status"] == "verificar" and c["item"] != "Checklist documental" for c in checks):
        return "verificar"
    if any(c["status"] == "verificar" for c in checks):
        return "checklist"
    return "ok" if len(checks) > 1 else "sem_conferencia"


# ---------------------------------------------------------------------------
# Faturas (TCCI) × OTR Nike (25/11/2026, pedido do usuario a partir da reuniao com a Leticia Rocha): o numero de cada
# fatura (PDF do zip "TCCI - <BL>.zip" na pasta do processo) tem de existir no OTR 1998 da Nike daquele BL, e cada
# fatura do OTR tem de ter o PDF. O OTR do dia fica em Sua Area > Inbound Optimization > OTR > OTR 1998 > <ano> >
# <mes>; o fluxo "NexxusDoc - OTR Nike" do n8n le e grava nexxusdoc_otr_n8n.json (so ele escreve).
# Licoes da auditoria de 25/11/2026 (contra o OTR bruto e os zips; pedido do usuario: "nao podemos ter falso negativo"):
#  1. o OTR e uma JANELA (~6 meses): as linhas dos embarques antigos saem do relatorio. Por isso o arquivo guarda o
#     HISTORICO por pedido+linha (otr_mesclar) e nunca so o OTR do dia;
#  2. ha PDF da Nike com os rotulos em bloco (o numero saia "Invoice"): _cabecalho_em_bloco;
#  3. PDF do zip que nao vira fatura (vazio, imagem, fatura manual) nunca fica calado: vai para a conferencia pelo nome
#     do arquivo (numero da fatura ou pedido+linha) e o processo fica "Conferir PDF";
#  4. a fatura da pasta que esta no OTR em OUTRO BL/HAWB e apontada (mesmo quando o BL da pasta nao esta no OTR).
# ---------------------------------------------------------------------------
def chave_bl(v: Any) -> str:
    """'MAEU281344858', 'BL 281344858' e '281344858' viram '281344858' (sem o codigo do armador)."""
    s = re.sub(r"[^A-Z0-9]", "", str(v or "").upper())
    m = re.match(r"^(?:[A-Z]{4}|BL|HAWB|AWB)(\d{6,}[A-Z]?)$", s)
    return m.group(1) if m else s


def otr_do_processo(row: dict[str, Any], otr_bls: dict[str, list]) -> list | None:
    """Linhas do OTR do processo, pelo BOL completo ou pelo numero da pasta."""
    for v in (row.get("bol"), row.get("numero"), row.get("nome")):
        k = chave_bl(v)
        if k and k in otr_bls:
            return otr_bls[k]
    return None


def _otr_txt(v: Any) -> str:
    s = "" if v is None else str(v).strip()
    return s[:-2] if re.fullmatch(r"\d+\.0", s) else s


def _otr_num(v: Any) -> float | None:
    try:
        return round(float(str(v).replace(",", ".")), 3) if v not in (None, "") else None
    except ValueError:
        return None


def otr_mesclar(hist: dict[str, list], linhas_planilha: list[dict[str, Any]], visto: str) -> int:
    """Junta um OTR ao HISTORICO (mesma regra do no 'OTR: montar' do n8n). hist[pedido|linha] = [BL, HAWB (aereo),
    numero da fatura, material, quantidade embarcada, peso bruto, visto (AAAAMMDDhhmmss do arquivo)]. O dado mais recente
    vale; a linha que saiu do relatorio continua. Devolve quantas linhas a planilha tinha."""
    n = 0
    for r in linhas_planilha:
        bol, po = _otr_txt(r.get("BOL_MAWB")), _otr_txt(r.get("PURCHASE_ORDER_ID"))
        if not bol or not po:
            continue
        n += 1
        ln = _otr_txt(r.get("PO_LINE_NUMBER")).lstrip("0")
        hawb = _otr_txt(r.get("CONTR_HAWB_PRONBR")) if _otr_txt(r.get("MODE_OF_TRANSPORT_CODE1")) not in ("VL", "") else ""
        k = f"{po}|{ln}"
        if k not in hist or str(visto) >= str(hist[k][6]):
            hist[k] = [chave_bl(bol), chave_bl(hawb) if hawb else "", _otr_txt(r.get("TCCI_BILLING_NUMBER")),
                       _otr_txt(r.get("MATERIAL")), _otr_num(r.get("TOTAL_SHIPPED_QUANTITY")), _otr_num(r.get("GROSS_WEIGHT1")),
                       str(visto)]
    return n


def otr_indices(hist: dict[str, list]) -> tuple[dict[str, list], dict[str, list]]:
    """Do historico: linhas por BL/HAWB ([fatura, pedido, linha, material, qtd, peso]) e em que embarque esta cada
    fatura ([[BL/MAWB, HAWB, pedido, linha, material, qtd, peso], ...])."""
    bls: dict[str, list] = {}
    faturas: dict[str, list] = {}
    for k in sorted(hist):
        b, h, t, mat, q, p = hist[k][:6]
        po, ln = k.split("|", 1)
        for c in dict.fromkeys(x for x in (b, h) if x):
            bls.setdefault(c, []).append([t, po, ln, mat, q, p])
        if t and not any(x[:4] == [b, h, po, ln] for x in faturas.setdefault(t, [])):
            faturas[t].append([b, h, po, ln, mat, q, p])
    return bls, faturas


def nome_pdf_fatura(nome: str) -> dict[str, str]:
    """O que o NOME do PDF diz (para o PDF que nao foi lido): 'BL_4511085550_00020.pdf' = pedido e linha;
    'MANUAL INVOICES 7609566260_10_4511030311.pdf' = ordem de venda, linha e pedido; '4543456608.pdf' = numero da fatura."""
    base = re.sub(r"\.pdf$", "", str(nome).replace("\\", "/").rsplit("/", 1)[-1].rsplit("›", 1)[-1].strip(), flags=re.I)
    m = re.search(r"(?<!\d)\d{10}_(\d{1,5})_(\d{10})(?!\d)", base)
    if m:
        return {"po": m.group(2), "linha": m.group(1).lstrip("0")}
    m = re.search(r"_(\d{10})_(\d{5})(?!\d)", base)
    if m:
        return {"po": m.group(1), "linha": m.group(2).lstrip("0")}
    m = re.search(r"(?<!\d)(45[2-9]\d{7})(?!\d)", base)
    return {"fatura": m.group(1)} if m else {}


def pdfs_sem_leitura(files: list[dict[str, Any]]) -> list[list]:
    """PDFs de fatura da pasta que NAO viraram fatura lida: [arquivo, motivo, quantos (0 = o zip inteiro)]."""
    out: list[list] = []
    for x in files:
        if x.get("tipo") != "tcci":
            continue
        d, rel = x.get("dados") or {}, x.get("rel") or x.get("nome") or ""
        if rel.lower().endswith(".zip"):
            if not d:
                out.append([rel, x.get("erro") or "zip ainda não lido", 0])
            elif d.get("nao_lidos") is not None:
                out += [[f"{rel} › {n}", m, 1] for n, m in d["nao_lidos"]]
            elif (d.get("pdfs") or 0) > len(d.get("faturas") or []):
                out.append([rel, "PDF do zip sem leitura", d["pdfs"] - len(d.get("faturas") or [])])
        elif rel.lower().endswith(".pdf") and not d.get("faturas"):
            out.append([rel, x.get("erro") or "não é o modelo de fatura Nike", 1])
    return out


# Resultado de cada linha do quadro PDF × OTR, na ordem em que aparecem
OTR_ORDEM = ["numero", "outro_bl", "fora", "sem_pdf", "pdf_nao_lido", "nao_lido", "pdf_nome", "pdf_extra", "aviso",
             "pelo_numero", "aguardando", "ok"]
OTR_DIVERGE = {"numero", "outro_bl", "fora", "sem_pdf"}      # divergente: cobrar a Nike ou arrumar a pasta
OTR_VERIFICA = {"pdf_nao_lido", "nao_lido", "pdf_nome"}      # conferir o PDF: o conteudo nao foi lido
OTR_AVISO = {"aviso", "pdf_extra", "pelo_numero"}             # so aviso


def conferir_otr(tccis: list | None, linhas: list | None, sem_leitura: list | None = None,
                 faturas_otr: dict[str, list] | None = None) -> dict[str, Any]:
    """Status: divergente > verificar (PDF que o sistema nao leu) > aguardando (bate pelo pedido; a Nike ainda nao pos o
    numero no OTR) > ok; sem_otr (BL nao esta no OTR e nenhuma fatura dele esta em outro BL) e sem_tcci (o OTR tem o BL
    e a pasta nao tem fatura). `quadro`: uma linha por fatura, o PDF ao lado do OTR (pedido do usuario: "onde esta de
    fato a verificacao?"). Quantidade e peso diferentes sao so aviso (o foco e o NUMERO da fatura)."""
    linhas, sem_leitura, faturas_otr = linhas or [], sem_leitura or [], faturas_otr or {}
    fat: dict[str, list] = {}
    for tc in tccis or []:  # [numero, pedido, material, qtd, peso, alerta da leitura (opcional)]
        fat.setdefault(str(tc[0]), [str(tc[1] or ""), str(tc[2] or ""), tc[3], tc[4], tc[5] if len(tc) > 5 else ""])
    quadro: list[dict[str, Any]] = []

    def lin(r, pdf, otr_n, po, ln, mat, qp, qo, pp, po_, obs=""):
        quadro.append({"r": r, "pdf": pdf, "otr": otr_n, "po": po, "linha": ln, "material": mat, "q_pdf": qp, "q_otr": qo,
                       "p_pdf": pp, "p_otr": round(po_, 3) if isinstance(po_, (int, float)) else po_, "obs": obs})

    if not linhas:
        # O BL/HAWB da pasta nao esta no OTR. Aereo: a Nike as vezes registra o embarque so pelo MAWB (sem HAWB); se TODAS
        # as faturas estao no OTR num mesmo MAWB sem HAWB, confere pelo numero (aviso). Fatura no OTR com OUTRO HAWB =
        # divergente (ex.: fatura salva na pasta errada).
        outros = {n: faturas_otr[n] for n in fat if faturas_otr.get(n)}
        if not outros:
            return {"status": "sem_otr", "pdfs": len(fat)}
        def _hawb_real(b, h):
            return bool(h) and h != b and bool(re.search(r"[A-Z]", h))
        so_mawb = {x[0] for n in outros for x in outros[n] if not _hawb_real(x[0], x[1])}
        todas_num_mawb = len(outros) == len(fat) and len(so_mawb) == 1 and not any(
            _hawb_real(x[0], x[1]) for n in outros for x in outros[n])
        for n, v in fat.items():
            if n not in outros:
                lin("fora", n, "", v[0], "", v[1], v[2], None, v[3], None, "na pasta e o número não está no OTR")
            else:
                xs = outros[n]
                ln_o = "/".join(dict.fromkeys(x[3] for x in xs if x[3]))
                q_o, p_o = sum(x[5] or 0 for x in xs), sum(x[6] or 0 for x in xs)
                if todas_num_mawb:
                    lin("pelo_numero", n, n, v[0], ln_o, v[1], v[2], q_o, v[3], p_o,
                        f"OTR só com o MAWB {next(iter(so_mawb))} (sem HAWB): conferido pelo número")
                else:
                    lin("outro_bl", n, n, v[0], ln_o, v[1], v[2], q_o, v[3], p_o, "no OTR, mas em outro embarque: " + ", ".join(
                        f"HAWB {x[1]} (MAWB {x[0]})" if _hawb_real(x[0], x[1]) else f"BL/MAWB {x[0]}" for x in xs))
        return _otr_fim(quadro, fat, linhas, sum(1 for x in quadro if x["r"] == "pelo_numero"))
    if not fat and not sem_leitura:
        return {"status": "sem_tcci", "otr": len(linhas), "pdfs": 0}
    por_num: dict[str, list] = {}
    sem_num = []
    for t, po, ln, mat, q, p in linhas:
        (por_num.setdefault(str(t), []) if t else sem_num).append((str(po or ""), str(ln or ""), str(mat or ""), q, p))
    achadas = set(fat) & set(por_num)
    livres = {n: fat[n] for n in sorted(set(fat) - set(por_num))}
    falta_pdf = []  # linhas do OTR sem PDF lido: (numero, pedido, linha, material, qtd, peso)
    for po, ln, mat, q, p in sem_num:  # OTR sem numero: o pedido + material casa com uma fatura que sobrou
        n = next((n for n, v in livres.items() if v[0] == po and v[1] == mat), None)
        if n:
            v = livres.pop(n)
            lin("aguardando", n, "", po, ln, mat, v[2], q, v[3], p, "; ".join(x for x in ("a Nike ainda não pôs o número desta fatura no OTR", v[4]) if x))
        else:
            falta_pdf.append(("", po, ln, mat, q, p))
    for t in sorted(set(por_num) - set(fat)):
        xs = por_num[t]
        # o PDF que sobrou com o mesmo pedido e material e a mesma fatura com outro numero: um ao lado do outro
        cand = [n for n, v in livres.items() if any(v[0] == x[0] and v[1] == x[2] for x in xs)]
        if cand:
            q_otr = sum(x[3] or 0 for x in xs)
            n = min(cand, key=lambda n: abs((livres[n][2] or 0) - q_otr))
            v = livres.pop(n)
            lido = bool(re.fullmatch(r"\d{6,}", n))
            lin("numero" if lido else "nao_lido", n, t, v[0], "/".join(dict.fromkeys(x[1] for x in xs if x[1])), v[1],
                v[2], q_otr, v[3], sum(x[4] or 0 for x in xs),
                "mesmo pedido e material, número diferente" if lido else "o número não foi lido no PDF; pedido e material batem")
            continue
        falta_pdf += [(t, po, ln, mat, q, p) for po, ln, mat, q, p in xs]
    # PDFs que nao viraram fatura: pelo nome do arquivo (numero da fatura ou pedido+linha); nunca calados
    pend = [[e[0], e[1], e[2], e[3] if len(e) > 3 else nome_pdf_fatura(e[0])] for e in sem_leitura]
    for t, po, ln, mat, q, p in falta_pdf:
        e = (next((e for e in pend if t and e[3].get("fatura") == t), None)
             or next((e for e in pend if e[3].get("po") == po and (e[3].get("linha") == ln.lstrip("0") or e[3].get("material") == mat)), None)
             or next((e for e in pend if not e[3]), None))
        if not e:
            lin("sem_pdf", "", t, po, ln, mat, None, q, None, p, "no OTR e sem o PDF da fatura na pasta")
            continue
        grave = not e[3] or not e[3].get("fatura") or re.search(r"vazio|não abre|grande", e[1])
        lin("pdf_nao_lido" if grave else "pdf_nome", e[3].get("fatura", ""), t, po, ln, mat, None, q, None, p,
            f"{e[1]}: {e[0]}" + ("" if grave else " (número conferido pelo nome do arquivo)"))
        if e[2] == 1:
            pend.remove(e)
        elif e[2] > 1:
            e[2] -= 1
    for a, m, k, info in pend:
        if k == 0 and any(x["obs"].endswith(a) for x in quadro):
            continue
        lin("pdf_extra", info.get("fatura", ""), "", info.get("po", ""), info.get("linha", ""), "", None, None, None, None,
            f"{m}: {a}" + (f" ({k} PDFs)" if k > 1 else ""))
    for n, v in livres.items():
        outros = faturas_otr.get(n) or []
        if outros:
            lin("outro_bl", n, n, v[0], "/".join(dict.fromkeys(x[3] for x in outros if x[3])), v[1], v[2],
                sum(x[5] or 0 for x in outros), v[3], sum(x[6] or 0 for x in outros), "no OTR, mas em outro embarque: " + ", ".join(
                f"HAWB {x[1]} (MAWB {x[0]})" if x[1] and x[1] != x[0] else f"BL/MAWB {x[0]}" for x in outros))
        else:
            lin("fora", n, "", v[0], "", v[1], v[2], None, v[3], None, "na pasta e o número não está no OTR")
    for n in sorted(achadas):
        xs = por_num[n]
        q_otr, p_otr = sum(x[3] or 0 for x in xs), sum(x[4] or 0 for x in xs)
        q_f, p_f = fat[n][2] or 0, fat[n][3] or 0
        campos = []
        if abs(q_otr - q_f) > .5:
            campos.append("quantidade")
        if p_otr and p_f and abs(p_otr - p_f) > max(.5, .005 * p_otr):
            campos.append("peso bruto")
        obs = "; ".join(x for x in ((" e ".join(campos) + " diferente") if campos else "", fat[n][4]) if x)
        lin("aviso" if obs else "ok", n, n, fat[n][0] or "/".join(dict.fromkeys(x[0] for x in xs)),
            "/".join(dict.fromkeys(x[1] for x in xs if x[1])), fat[n][1] or "/".join(dict.fromkeys(x[2] for x in xs)),
            fat[n][2], q_otr, fat[n][3], p_otr, obs)
    return _otr_fim(quadro, fat, linhas, len(achadas))


def _otr_fim(quadro: list[dict[str, Any]], fat: dict, linhas: list, conferidas: int) -> dict[str, Any]:
    quadro.sort(key=lambda x: (OTR_ORDEM.index(x["r"]), x["pdf"] or x["otr"], x["po"], x["linha"]))
    rs = [x["r"] for x in quadro]
    status = ("divergente" if OTR_DIVERGE & set(rs) else "verificar" if OTR_VERIFICA & set(rs)
              else "aguardando" if "aguardando" in rs else "ok")
    so = lambda *k: [x for x in quadro if x["r"] in k]  # noqa: E731
    return {"status": status, "pdfs": len(fat), "otr": len(linhas), "conferidas": conferidas,
            "aguardando": so("aguardando"), "sem_pdf": so("sem_pdf"), "fora": so("fora", "outro_bl"),
            "numero_dif": so("numero"), "verificar": so(*OTR_VERIFICA), "dif": so(*OTR_AVISO), "quadro": quadro}


# ---------------------------------------------------------------------------
# Andamento na PGL (23/11/2026, pedido do usuario): o FUP que a PGL manda por e-mail varias vezes ao dia ("Relatorio de
# Follow Up - FISIA" e "- Fisia / Zelus") traz, por processo, chegada, presenca de carga, DI, canal, desembaraco e a
# ENTREGA DA MERCADORIA no CD. O n8n le o anexo no Gmail e grava nexxusdoc_embarques_fup.json (so ele escreve; a mesma
# regra esta em JavaScript no fluxo). Liga ao processo pelo BL/HAWB (coluna CONHECIMENTO; 99% dos processos) e, na
# Zelus, pela referencia FISIA###. Processo que sai do FUP continua no arquivo (o historico vai crescendo).
# ---------------------------------------------------------------------------
FUP_CAMPOS = {"MODAL": "modal", "PROCESSO": "wfadim", "AGENTE CARGA": "agente", "REF CLIENTE": "ref",
              "CONHECIMENTO": "conhecimento", "DANFE": "danfe", "PLANTA": "planta", "INICIATIVA PROMO AMOSTRA": "iniciativa",
              "COLECAO": "colecao", "TOTAL": "qtd", "VOLUME": "volume", "MARCA NUMERO": "conteiner",
              "EMBARQUE NA ORIGEM": "embarque", "NAVIO": "navio", "PREVISAO_CHEGADA": "prev_chegada",
              "CHEGADA MERCADORIA": "chegada", "ARMAZEM DESCARGA": "armazem", "ARMAZEM DESCARGA TMS": "cd",
              "PRESENCA CARGA": "presenca", "REGISTRO DI": "registro_di", "NR_DI": "di", "CANAL": "canal",
              "TRANSPORTADORA": "transportadora", "DESEMBARACO": "desembaraco", "INSPECAO DE MADEIRA": "insp_madeira",
              "ENTREGA DOC TRANSP": "entrega_doc", "PREVISAO ENTR MERC_FAB": "prev_entrega", "ENTREGA DA MERC": "entrega",
              "STATUS": "status", "OBSERVACOES": "obs", "DT ICMS PAGO": "icms_pago", "VALOR CIF R$": "cif",
              "RECINTO_DESEMBARACO": "recinto", "TERMINAL_ATRACACAO": "terminal"}
FUP_DATAS = {"embarque", "prev_chegada", "chegada", "presenca", "registro_di", "desembaraco", "insp_madeira", "entrega_doc",
             "prev_entrega", "entrega", "icms_pago"}
FUP_MONEY = ("cif",)


def fup_chave(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def fup_data(value: Any) -> str:
    """Data do FUP em AAAA-MM-DD: datetime (openpyxl), numero de serie do Excel (n8n) ou texto."""
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, (int, float)) and 20000 < value < 80000:
        return datetime.fromordinal(datetime(1899, 12, 30).toordinal() + int(value)).date().isoformat()
    text = str(value).strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})\b", text)
    if m:
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:  # 'm/d/aa' e o formato que a planilha usa quando vira texto (padrao do Excel em ingles)
            d, mth, y = mth, d, y + 2000
        return f"{y:04d}-{mth:02d}-{d:02d}" if 1 <= mth <= 12 and 1 <= d <= 31 else ""
    return ""


def fup_registro(row: dict[str, Any], fonte: str, visto: str) -> tuple[str, dict[str, Any]] | None:
    """Uma linha do FUP (cabecalho -> valor) vira (chave, registro). Sem BL/HAWB nem referencia, fica de fora."""
    rec: dict[str, Any] = {}
    row = {str(k).strip().upper(): v for k, v in row.items()}
    for col, key in FUP_CAMPOS.items():
        value = row.get(col)
        if key in FUP_DATAS:
            value = fup_data(value)
        elif isinstance(value, float) and value.is_integer() and key != "cif":
            value = int(value)
        elif isinstance(value, str):
            value = re.sub(r"\s+", " ", value).strip()
        if value not in (None, ""):
            rec[key] = value
    chave = fup_chave(rec.get("conhecimento")) or fup_chave(rec.get("ref")) or fup_chave(rec.get("wfadim"))
    if not chave:
        return None
    if isinstance(rec.get("qtd"), str) and rec["qtd"].isdigit():
        rec["qtd"] = int(rec["qtd"])
    if isinstance(rec.get("cif"), str):
        try:
            rec["cif"] = float(rec["cif"].replace(",", ""))
        except ValueError:
            rec.pop("cif")
    rec["fonte"], rec["visto"] = fonte, visto
    return chave, rec


def fup_etapa(status: str) -> tuple[int, str]:
    """'15 Carga Entregue' -> (15, 'Carga entregue')."""
    m = re.match(r"\s*(\d+)\s*(.*)", str(status or ""))
    if not m:
        return 0, str(status or "").strip().capitalize()
    texto = re.sub(r"\s+", " ", m.group(2)).strip()
    return int(m.group(1)), (texto[:1].upper() + texto[1:].lower()) if texto else ""


def fup_indice(fup: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Chaves de busca: BL/HAWB, a referencia do cliente e, na Zelus, o FISIA### que vem no lugar do conhecimento."""
    idx: dict[str, dict[str, Any]] = {}
    for chave, rec in (fup.get("processos") or {}).items():
        for k in (chave, fup_chave(rec.get("ref"))):
            if k and k not in idx:
                idx[k] = rec
    return idx


def fup_do_processo(row: dict[str, Any], idx: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    numero = fup_chave(row.get("numero"))
    chaves = [numero, re.sub(r"^[A-Z]{4}(?=[A-Z]{3}\d)", "", numero), fup_chave(row.get("bol"))]  # BL com o SCAC na frente (CMDUSGN... = SGN...)
    if row.get("op") == "ZELUS" and row.get("ref"):
        chaves.append(fup_chave(row["ref"]))
    for k in chaves:
        if k and k in idx:
            return idx[k]
    return None


# ---------------------------------------------------------------------------
# Atualizacao do indice (roda em segundo plano no computador do master)
# ---------------------------------------------------------------------------
def consolidar(resumos: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Mesmo numero de processo em duas pastas da mesma operacao (ex.: PROMO "Abertura de Processos" e
    "Documentação Completa"): fica uma linha, a da pasta com mais documentos; a outra vai em outras_pastas."""
    por_chave: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in resumos.values():
        por_chave.setdefault((r["op"], r["numero"]), []).append(r)
    final = []
    for grupo in por_chave.values():
        grupo.sort(key=lambda r: (len(r["docs"]), r["n_arquivos"]), reverse=True)
        principal = dict(grupo[0])
        principal["outras_pastas"] = [{"id": g["id"], "grupo": g["grupo"], "nome": g["nome"]} for g in grupo[1:]]
        final.append(principal)
    final.sort(key=lambda r: r.get("criada", ""), reverse=True)
    return final


class Indexador:
    def __init__(self, raiz: Path, destino: Path, log: Callable[[str], None] = print) -> None:
        self.raiz, self.destino, self.log = raiz, destino, log
        self.lock = threading.Lock()
        self.estado: dict[str, Any] = {"rodando": False}

    def _ler_json(self, path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _gravar(self, path: Path, data: Any) -> None:
        if path.name == "status.json" and isinstance(data, dict):
            data["atualizado"] = datetime.now(timezone.utc).isoformat(timespec="seconds")  # sinal de vida da leitura
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, path)

    def _publicar(self, resumos: dict[str, dict[str, Any]], st: dict[str, Any], parcial: bool) -> list[dict[str, Any]]:
        """Grava os resumos e o indice (carga do historico)."""
        final = consolidar(resumos)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._gravar(self.destino / "resumos.json", {"gerado_em": now, "processos": list(resumos.values())})
        self._gravar(self.destino / "indice.json", {"gerado_em": now, "raiz": str(self.raiz), "parcial": parcial,
                                                    "processos": final})
        if parcial:
            self._gravar(self.destino / "status.json", st)
        return final

    def status(self) -> dict[str, Any]:
        st = self._ler_json(self.destino / "status.json")
        try:
            parado = time.time() - datetime.fromisoformat(st.get("atualizado", "")).timestamp()
        except (TypeError, ValueError):
            parado = 10 ** 9
        if st.get("rodando") and parado >= 900 and not self.estado.get("rodando"):
            st.update(rodando=False, interrompida=True)  # o sistema fechou no meio: a proxima leitura segue de onde parou
        return {**st, **({"rodando": True} if self.estado.get("rodando") else {})}

    def rodar(self, por: str = "") -> dict[str, Any]:
        if not self.lock.acquire(blocking=False):
            return {"feito": False, "motivo": "A leitura já está em andamento."}
        started = time.monotonic()
        try:
            if not self.raiz.is_dir():
                return {"feito": False, "motivo": f"A pasta {self.raiz} não está disponível neste computador."}
            antes = self._ler_json(self.destino / "status.json")
            try:
                parado = time.time() - datetime.fromisoformat(antes.get("atualizado", "")).timestamp()
            except (TypeError, ValueError):
                parado = 10 ** 9
            if antes.get("rodando") and parado < 900:
                return {"feito": False, "motivo": "A leitura já está em andamento em outro processo."}
            achados = achar_processos(self.raiz)

            def criada(info: dict[str, Any]) -> float:
                try:
                    return os.stat(info["pasta"]).st_ctime
                except OSError:
                    return 0.0
            achados.sort(key=criada, reverse=True)  # os mais novos primeiro: ficam prontos antes na tela
            total = len(achados)
            st = {"rodando": True, "inicio": datetime.now(timezone.utc).isoformat(timespec="seconds"), "total": total,
                  "feitos": 0, "lidos_de_novo": 0, "por": por}
            self.estado.update(rodando=True)
            self._gravar(self.destino / "status.json", st)
            pasta_cache = self.destino / "processos"
            ids = {_id(info["pasta"], self.raiz) for info in achados}
            # Resumos da rodada anterior: valem ate o processo ser conferido nesta rodada (se o sistema fechar no meio
            # da leitura, o indice continua completo e a proxima rodada segue de onde parou, pelo cache).
            anteriores = {r["id"]: r for r in self._ler_json(self.destino / "resumos.json").get("processos", []) if r.get("id") in ids}
            resumos: dict[str, dict[str, Any]] = dict(anteriores)

            def um(info: dict[str, Any]) -> tuple[str, dict[str, Any], bool]:
                pid = _id(info["pasta"], self.raiz)
                cache = pasta_cache / f"{pid}.json"
                antes = self._ler_json(cache)
                try:  # pasta, subpastas e arquivos (arquivo editado no lugar nao muda a data da pasta)
                    mtime = max([os.stat(info["pasta"]).st_mtime]
                                + [os.stat(os.path.join(d, x)).st_mtime for d, dirs, fs in os.walk(info["pasta"]) for x in dirs + fs])
                except OSError:
                    mtime = 0
                if antes.get("v") == VERSAO_LEITURA and antes.get("_mtime") == mtime:
                    return pid, antes, False
                proc = ler_processo(info, self.raiz, antes)
                proc["_mtime"] = mtime
                self._gravar(cache, proc)
                return pid, proc, True

            # Varias pastas em paralelo: quase todo o tempo e espera pelo download do Google Drive.
            from concurrent.futures import ThreadPoolExecutor
            feitos = 0
            with ThreadPoolExecutor(max_workers=6) as pool:
                for start in range(0, total, 48):
                    for pid, proc, novo in pool.map(um, achados[start:start + 48]):
                        resumos[pid] = resumir(proc)
                        st["lidos_de_novo"] += int(novo)
                        feitos += 1
                    st["feitos"] = feitos
                    st["segundos"] = round(time.monotonic() - started)
                    if (start // 48) % 3 == 2:
                        self._publicar(resumos, st, parcial=True)
                    else:
                        self._gravar(self.destino / "status.json", st)
            final = self._publicar(resumos, st, parcial=False)
            # Cache de pasta que sumiu sai (a pasta foi renomeada ou apagada pela equipe)
            for f in pasta_cache.glob("*.json"):
                if f.stem not in ids:
                    try:
                        f.unlink()
                    except OSError:
                        pass
            st.update(rodando=False, fim=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      segundos=round(time.monotonic() - started), processos=len(final))
            self._gravar(self.destino / "status.json", st)
            self.log(f"Embarques: {len(final)} processos ({st['lidos_de_novo']} lidos de novo) em {st['segundos']} s")
            return {"feito": True, **st}
        except Exception as exc:  # noqa: BLE001 - o erro fica no status para a tela mostrar
            self._gravar(self.destino / "status.json", {"rodando": False, "erro": str(exc)[:300],
                                                        "fim": datetime.now(timezone.utc).isoformat(timespec="seconds")})
            self.log(f"Embarques: falha na leitura: {exc!r}")
            return {"feito": False, "motivo": str(exc)[:300]}
        finally:
            self.estado.update(rodando=False)
            self.lock.release()
