"""Gera base_manuais.json: texto dos manuais e procedimentos oficiais EM VIGOR da Logistica Internacional (pasta de documentos configurada), para as "Consultas gerais" do Chat Nexxus detalharem o passo a passo e citar o manual com link.

Regras: entra so a versao mais recente de cada procedimento (as antigas sao historico); senhas, logins, hosts, tokens
e e-mails pessoais sao removidos antes de gravar (o arquivo vai para todas as maquinas pela publicacao assinada).
Uso: python tools/build_manuais.py   (depois publicar)"""
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# O manifesto e a pasta de documentos são privados e fornecidos pela implantação.
# Nunca versionar a lista real de documentos nem seus IDs no Drive.
import os
ROOT = Path(os.environ.get("NEXXUS_MANUALS_ROOT", ""))
OUT = Path(__file__).resolve().parent.parent / "base_manuais.json"
LIMIT = 30000
D = "https://drive.google.com/file/d/{}/view"
MANIFEST = Path(os.environ.get("NEXXUS_MANUALS_MANIFEST", str(Path(__file__).resolve().parent / "manuais_manifest.json")))
MANUAIS = json.loads(MANIFEST.read_text(encoding="utf-8")).get("manuais", []) if MANIFEST.is_file() else []

GOOGLE_LINK = {".gslides": "https://docs.google.com/presentation/d/{}/view", ".gdoc": "https://docs.google.com/document/d/{}/view"}
# Arquivos do Google (Apresentacoes/Documentos) nao sao legiveis no disco: o texto fica salvo em tools/manuais_texto/<id>.txt
# (copiado do Drive pela API; atualizar o .txt quando o arquivo mudar).
TEXT_DIR = Path(__file__).resolve().parent / "manuais_texto"

HEAD = re.compile(r"^(\d+(\.\d+)*[.)]?\s+)?(objetivos?|escopo|considera[cç][oõ]es gerais|defini[cç][oõ]es|gloss[aá]rio|descri[cç][aã]o|"
                  r"responsabilidades|pap[eé]is|refer[eê]ncias|procedimento|etapas?|fluxo|controles?|anexos?|hist[oó]rico|"
                  r"indicadores|kpis?|slas?|exce[cç][oõ]es|evid[eê]ncias?|conclus[aã]o|introdu[cç][aã]o|scope|purpose)\b", re.I)
CRED = re.compile(r"^\s*(senha|password|pass|pwd|usu[aá]rio|user(name)?|login|host|servidor|porta|port|token|api[ _-]?key|"
                  r"chave( de api)?|secret)\s*[:=]", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
GENERIC_MAIL = re.compile(r"^(fisia|pagamentos|faturamento|tesouraria|contasapagar|br\.logistics|vektor|importacao|comex|sac)@", re.I)


def clean(text: str) -> str:
    lines = []
    for line in str(text).splitlines():
        if CRED.search(line):
            lines.append("[informação de acesso removida]")
            continue
        lines.append(EMAIL.sub(lambda m: m.group(0) if GENERIC_MAIL.match(m.group(0)) else "[e-mail]", line))
    return "\n".join(lines)


def docx_blocks(path: Path) -> list[str]:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc = docx.Document(str(path))
    out = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, doc)
            text = p.text.strip()
            if text:
                style = (p.style.name or "").lower() if p.style is not None else ""
                out.append(("# " if style.startswith(("heading", "título", "titulo")) else "") + text)
        elif tag == "tbl":
            for row in Table(child, doc).rows:
                cells, seen = [], set()
                for cell in row.cells:
                    t = " ".join(cell.text.split())
                    if t and t not in seen:
                        seen.add(t)
                        cells.append(t)
                if cells:
                    out.append(" | ".join(cells))
    return out


def pdf_blocks(path: Path) -> list[str]:
    from pypdf import PdfReader
    out = []
    for i, page in enumerate(PdfReader(str(path)).pages, 1):
        text = (page.extract_text() or "").strip()
        if text:
            out.append(f"# Página {i}")
            out.extend(line.strip() for line in text.splitlines() if line.strip())
    return out


def pptx_blocks(path: Path) -> list[str]:
    from pptx import Presentation
    out = []
    for i, slide in enumerate(Presentation(str(path)).slides, 1):
        texts = [line.strip() for shape in slide.shapes if shape.has_text_frame
                 for line in shape.text_frame.text.splitlines() if line.strip()]
        if texts:
            out.append(f"# Slide {i} – {texts[0][:70]}")
            out.extend(texts[1:])
    return out


def text_blocks(file_id: str) -> list[str]:
    path = TEXT_DIR / f"{file_id}.txt"
    return [line.rstrip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sections(blocks: list[str]) -> list[dict[str, str]]:
    result, title, buf = [], "Início", []
    for block in blocks:
        plain = block.lstrip("# ").strip()
        is_head = block.startswith("# ") or (len(plain) <= 70 and HEAD.match(plain) and not plain.endswith(".")) \
            or (len(plain) <= 60 and plain.isupper() and len(plain.split()) <= 7)
        if is_head:
            if buf:
                result.append({"titulo": title, "texto": clean("\n".join(buf))})
            title, buf = plain[:90], []
        else:
            buf.append(plain)
    if buf:
        result.append({"titulo": title, "texto": clean("\n".join(buf))})
    total, kept = 0, []
    for s in result:
        if total >= LIMIT:
            break
        s["texto"] = s["texto"][:LIMIT - total]
        total += len(s["texto"])
        kept.append(s)
    return kept


def author(path: Path, blocks: list[str]) -> str:
    """Quem elaborou o documento: 'Elaborador: Nome' (inclusive no cabecalho do Word), quadro Elaborador | Avaliador |
    Aprovador, 'Autor: Nome', autor da versao mais recente no quadro de versoes ou quem assinou em 'Emitido por'."""
    texts, tables = list(blocks), []
    if path.suffix.lower() == ".docx":
        import docx
        d = docx.Document(str(path))
        for sec in d.sections:
            for part in (sec.header, sec.first_page_header):
                texts = [p.text for p in part.paragraphs if p.text.strip()] + texts
                for t in part.tables:
                    texts = [" | ".join(" ".join(c.text.split()) for c in r.cells) for r in t.rows] + texts
        tables = [[[" ".join(c.text.split()) for c in r.cells] for r in t.rows] for t in d.tables]
    text = "\n".join(texts)
    for pattern, flags in [(r"Elaborador(?:a)?\s*\|\s*Avaliador(?:a)?(?:\s*\|\s*Aprovador(?:a)?)?\s*\n\s*([^|\n]{3,90})", re.I),
                           (r"\bElaborad(?:or|ora|o por)\s*:\s*([^|\n]{3,90}?)(?=\s+Aprovad|\s+Avaliad|\s*\||\s*$|\n)", re.I | re.M),
                           (r"\bAutor(?:a)?\s*:\s*([^|\n]{3,90}?)(?=\s+Revis|\s*\||\s*$|\n)", re.M)]:
        for found in re.finditer(pattern, text, flags):
            name = person(found.group(1))
            if name:
                return name
    for rows in tables:
        head = [slug(c) for c in rows[0]] if rows else []
        col = next((i for i, h in enumerate(head) if h.startswith(("author", "autor", "elaborad"))), None)
        if col is not None and any(h.startswith(("version", "versao", "revisao", "data", "date")) for h in head):
            names = [r[col] for r in rows[1:] if len(r) > col and r[col].strip()]
            if names:
                return ", ".join(filter(None, (person(n) for n in names[-1].split(",")))) or ""
        for i, row in enumerate(rows[:-1]):
            if row and slug(row[0]).startswith("emitido-por"):
                name = person(re.sub(r"(?i)data:.*$", "", rows[i + 1][0]).replace("Assinatura:", "").replace("assinatura:", ""))
                if name:
                    return name
    return ""


def person(value: str) -> str:
    """Nome de pessoa: sem o cargo depois do nome, com iniciais maiusculas; vazio se nao parecer nome."""
    name = re.split(r"\s+(?:Gerente|Diretor|Diretora|Coord\w*|Analista|Especialista|Supervisor\w*|Time|L[ií]der|Head)\b",
                    " ".join(str(value).replace("/", " ").split()))[0].strip(" .-–:")
    words = name.split()
    if not 2 <= len(words) <= 6 or re.search(r"\d", name):
        return ""
    return " ".join(w if w.lower() in {"de", "da", "do", "dos", "das", "e"} else w[0].upper() + w[1:] for w in words)


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60]


def main() -> int:
    if not MANIFEST.is_file() or not ROOT.is_dir():
        print("Configure NEXXUS_MANUALS_MANIFEST e NEXXUS_MANUALS_ROOT antes de executar.")
        return 2
    manuais, faltam = [], []
    try:  # manual que sumiu do Drive fica como estava na versao anterior (nunca some da base sem decisao)
        previous = {m["id"]: m for m in json.loads(OUT.read_text(encoding="utf-8")).get("manuais", [])}
    except (OSError, ValueError):
        previous = {}
    for titulo, revisao, tipo, unidades, rel, file_id in MANUAIS:
        path = ROOT / rel
        suffix = path.suffix.lower()
        if not path.exists():
            faltam.append(rel)
            if slug(titulo) in previous:
                manuais.append(previous[slug(titulo)])
            continue
        blocks = (pdf_blocks(path) if suffix == ".pdf" else pptx_blocks(path) if suffix == ".pptx"
                  else text_blocks(file_id) if suffix in GOOGLE_LINK else docx_blocks(path))
        secs = sections(blocks)
        code = re.match(r"^((ID|Ação|POP|FISIA|SOP do despachante PR-DESEMB)[^–]*)–", titulo)
        manuais.append({"id": slug(titulo), "titulo": titulo, "codigo": code.group(1).strip() if code else "",
                        "autor": author(path, blocks) if suffix in {".pdf", ".docx"} else "", "revisao": revisao,
                        "tipo": tipo, "unidades": unidades, "area": os.environ.get("NEXXUS_MANUALS_AREA", "Área configurada"),
                        "link": GOOGLE_LINK.get(suffix, D).format(file_id), "origem": "Acervo configurado › " + " › ".join(rel.split("/")[:-1]),
                        "secoes": secs, "caracteres": sum(len(s["texto"]) for s in secs)})
        print(f"  {manuais[-1]['caracteres']:6d}  {len(secs):3d} seções  {titulo}")
    data = {"gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "observacao": "Manuais e procedimentos oficiais EM VIGOR da Logística Internacional (só a versão mais recente "
                          "de cada um). Credenciais e e-mails pessoais removidos. Gerado por tools/build_manuais.py.",
            "manuais": manuais}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(manuais)} manuais, {OUT.stat().st_size // 1024} KB -> {OUT}")
    if faltam:
        print("NÃO ENCONTRADOS:", *faltam, sep="\n  ")
    leaks = [m["titulo"] for m in manuais for s in m["secoes"] if re.search(r"(senha|password)[ \t]*[:=][ \t]*(?!\[)\S{4,}", s["texto"], re.I)]
    if leaks:
        print("ATENÇÃO, possível senha restante em:", leaks)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
