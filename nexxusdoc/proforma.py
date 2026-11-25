"""Planilha proforma online da pagina Embarques (23/11/2026, pedido do usuario).

Cada proforma (uma por processo/BL) fica num arquivo da pasta compartilhada (embarques/proformas/<pid>.json) e e
editada pela tela como uma planilha. O sistema monta a proforma sozinho a partir de:
  1. TCCIs da pasta do processo (PDF da Nike: PO FISIA, PO Nike e item, material, faixa de tamanho, quantidade, preco,
     valor, pesos, fabrica e endereco);
  2. base da "Ferramenta de Analise" da equipe (a copia mais recente de "2. PROforma S4 - Ferramenta de Analise - *.xlsx"
     em Sua Area > Controle de Conferencia - BL > 1. PLATAFORMAS), guardada em Parquet e consultada com DuckDB:
     aba TCCI (relatorio do SAP: linha por tamanho), aba LIs (relatorio de LI da PGL: NCM, descricao, peso liquido,
     fabricante e endereco, LI e situacao no DECEX) e aba OTR 1998 (conteiner por PO Nike/item);
  3. BL do processo (conteiner quando a OTR nao traz).
Nada e estimado: o que nenhuma fonte traz fica vazio para a pessoa preencher. Cada celula guarda a origem.
Quando o relatorio de LI da PGL tiver fonte propria, ele entra no lugar da aba LIs (mesmas colunas).
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import embarques

# Colunas da proforma (mesma ordem do modelo da equipe, linha 17 da aba Proforma)
COLUNAS = [
    {"k": "po_fisia", "l": "PO FISIA", "t": "txt", "w": 104},
    {"k": "it_fisia", "l": "it FISIA", "t": "txt", "w": 64},
    {"k": "po_nike", "l": "PO Nike", "t": "txt", "w": 104},
    {"k": "it_nike", "l": "It Nike", "t": "txt", "w": 62},
    {"k": "material", "l": "Material code", "t": "txt", "w": 132},
    {"k": "ncm", "l": "HTS Code", "t": "txt", "w": 92},
    {"k": "descricao", "l": "Product Description", "t": "txt", "w": 300},
    {"k": "qtd", "l": "Quantity", "t": "num", "d": 0, "w": 84},
    {"k": "peso_liq", "l": "Net Weight", "t": "num", "d": 3, "w": 96},
    {"k": "peso_bruto", "l": "Gross Weight", "t": "num", "d": 3, "w": 100},
    {"k": "preco", "l": "UNIT $", "t": "num", "d": 2, "w": 86},
    {"k": "total", "l": "Total $", "t": "num", "d": 2, "w": 108, "calc": True},
    {"k": "fabricante", "l": "Factory Name", "t": "txt", "w": 220},
    {"k": "endereco", "l": "Factory Address", "t": "txt", "w": 280},
    {"k": "tcci", "l": "TCCI Number", "t": "txt", "w": 110},
    {"k": "tcci_data", "l": "TCCI Billing dt.", "t": "data", "w": 104},
    {"k": "cntr", "l": "Cntr. ID", "t": "txt", "w": 118},
    {"k": "flag_preco", "l": "Flag Alt. Preço", "t": "txt", "w": 96},
    {"k": "flag_qtd", "l": "Flag. Alt. Qtd.", "t": "txt", "w": 96},
]
CHAVES = [c["k"] for c in COLUNAS]
EDITAVEIS = [c["k"] for c in COLUNAS if not c.get("calc")]
NUMERICAS = {c["k"] for c in COLUNAS if c["t"] == "num"}
OBRIGATORIAS = ("po_fisia", "material", "ncm", "descricao", "qtd", "preco", "fabricante")
ORIGENS = {"tcci": "TCCI da pasta (PDF)", "sap": "Ferramenta: aba TCCI (SAP)", "li": "Ferramenta: aba LIs (relatório de LI)",
           "li_produto": "Ferramenta: aba LIs, mesmo produto em outro pedido", "otr": "Ferramenta: aba OTR 1998",
           "bl": "BL da pasta", "rateio": "Peso da TCCI rateado pela quantidade", "pasta": "Proforma salva na pasta do processo",
           "manual": "Digitado na planilha"}
FERRAMENTA_GLOB = "2. PROforma S4 - Ferramenta de An*lise - *.xlsx"


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:  # 1.234,56 (Brasil) ou 1,234.56 (EUA): o ultimo separador e o decimal
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _txt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, datetime):
        return v.date().isoformat()
    return re.sub(r"\s+", " ", str(v)).strip()[:400]


def _item(v: Any) -> str:
    """Item de pedido sem zeros a esquerda ('000040' -> '40'), como a planilha usa na chave PO+item."""
    s = _txt(v)
    return str(int(s)) if s.isdigit() else s


# ---------------------------------------------------------------------------
# TCCI (PDF da Nike) com o detalhe que a proforma precisa
# ---------------------------------------------------------------------------
def ler_tcci_detalhe(text: str) -> dict[str, Any] | None:
    base = embarques.ler_fatura_nike(text)
    if not base:
        return None
    item = embarques._find(r"PO Line Item Seq\.#:\s*(\d+)", text)
    linhas = []
    bloco = re.search(r"Number of Cartons:\s*\d+\s*\n(.*?)\n-{10,}", text, re.S)
    for m in re.finditer(r"^\s*(\S+)\s+([\d.]+)\s+([\d.,]+)\s+([\d.,]+)\s*$", bloco.group(1) if bloco else "", re.M):
        linhas.append({"tamanho": m.group(1), "qtd": embarques.num_eu(m.group(2)), "preco": embarques.num_eu(m.group(3)),
                       "valor": embarques.num_eu(m.group(4))})
    endereco = ""
    fab = re.search(r"Manufacturing Factory:\s*\n(.*?)\nPage \d", text, re.S)
    if fab:
        partes = [p.strip() for p in fab.group(1).splitlines() if p.strip()]
        nome = base.get("fabricante", "")
        # tira as linhas do nome (1 ou 2) e junta o endereco
        usadas = 0
        acc = ""
        for p in partes:
            if nome and (acc + " " + p).strip().casefold() in nome.casefold() or (not acc and nome.casefold().startswith(p.casefold())):
                acc = (acc + " " + p).strip()
                usadas += 1
                continue
            break
        endereco = ", ".join(partes[usadas or 1:])[:240]
    return {**base, "item": _item(item), "linhas": linhas, "endereco": endereco}


def tccis_do_processo(pasta: Path, arquivos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Le de novo as TCCIs da pasta (zip e PDF) com o detalhe; fatura repetida (zip e PDF solto) conta uma vez."""
    out: dict[str, dict[str, Any]] = {}
    for f in arquivos:
        if f.get("tipo") not in {"tcci", "ci"}:
            continue
        full = pasta / f["rel"]
        try:
            if full.suffix.lower() == ".zip":
                z = zipfile.ZipFile(io.BytesIO(full.read_bytes()))
                textos = [embarques._pdf_text(z.read(n), 3) for n in z.namelist() if n.lower().endswith(".pdf") and z.getinfo(n).file_size < 20_000_000]
            elif full.suffix.lower() == ".pdf" and full.stat().st_size < 25_000_000:
                textos = [embarques._pdf_text(full.read_bytes(), 3)]
            else:
                continue
        except Exception:  # noqa: BLE001 - arquivo quebrado ou fora do Drive: segue com os outros
            continue
        for t in textos:
            try:
                d = ler_tcci_detalhe(t)
            except Exception:  # noqa: BLE001
                d = None
            if d and d.get("fatura"):
                out[d["fatura"]] = d
    return sorted(out.values(), key=lambda d: (d.get("po") or "", d.get("item") or "", d.get("fatura") or ""))


# ---------------------------------------------------------------------------
# Base da Ferramenta de Analise (Parquet + DuckDB)
# ---------------------------------------------------------------------------
ABAS = {
    # aba: (arquivo parquet, {coluna da planilha (letra): nome})
    "LIs": ("lis", {"E": "po_fisia", "F": "it_fisia", "H": "po_nike", "I": "it_nike", "L": "peso_bruto", "R": "material",
                    "S": "descricao", "T": "ncm", "V": "qtd", "W": "peso_liq", "AA": "fabricante", "AB": "endereco",
                    "AC": "pais", "AE": "li", "AG": "li_registro", "AI": "li_deferimento", "AJ": "li_situacao",
                    "AL": "li_vencimento", "O": "modal", "M": "tipo"}),
    "TCCI": ("tcci", {"B": "dt_entrada", "C": "data_doc", "D": "po_fisia", "E": "it_fisia", "F": "tcci", "G": "material",
                      "H": "qtd", "J": "valor", "K": "moeda"}),
    "OTR 1998": ("otr", {"E": "po_item", "G": "bol", "H": "po_nike", "I": "po_fisia", "J": "it_nike", "K": "material",
                         "O": "modal", "R": "cntr", "AN": "tcci", "AO": "tcci_data"}),
}


def _col_idx(letra: str) -> int:
    n = 0
    for ch in letra:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


class Base:
    """Copia em Parquet das abas LIs, TCCI e OTR 1998 da Ferramenta mais recente (refeita quando sai uma copia nova)."""

    def __init__(self, ferramentas: Path, destino: Path, log: Callable[[str], None] = print) -> None:
        self.ferramentas, self.destino, self.log = ferramentas, destino, log
        self.lock = threading.Lock()
        self.estado: dict[str, Any] = {"rodando": False}
        self._visto = 0.0

    def ferramenta_atual(self) -> Path | None:
        try:
            arqs = [p for p in self.ferramentas.glob(FERRAMENTA_GLOB) if not p.name.startswith("~$")]
        except OSError:
            return None
        return max(arqs, key=lambda p: p.stat().st_mtime) if arqs else None

    def meta(self) -> dict[str, Any]:
        try:
            return json.loads((self.destino / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def pronta(self) -> bool:
        return all((self.destino / f"{a}.parquet").is_file() for a, _ in ABAS.values())

    def status(self) -> dict[str, Any]:
        m = self.meta()
        atual = self.ferramenta_atual()
        nova = bool(atual and (not m or m.get("arquivo") != atual.name or abs(m.get("mtime", 0) - atual.stat().st_mtime) > 1))
        return {"pronta": self.pronta(), "arquivo": m.get("arquivo", ""), "gerada_em": m.get("gerada_em", ""),
                "linhas": m.get("linhas", {}), "rodando": bool(self.estado.get("rodando")), "etapa": self.estado.get("etapa", ""),
                "erro": self.estado.get("erro", ""), "nova_disponivel": nova, "atual": atual.name if atual else "",
                "pasta_ok": self.ferramentas.is_dir()}

    def talvez_atualizar(self) -> None:
        """Na abertura da planilha (no maximo a cada 10 min): copia nova da Ferramenta = base refeita em segundo plano."""
        if time.time() - self._visto < 600 or self.estado.get("rodando"):
            return
        self._visto = time.time()
        if self.status().get("nova_disponivel"):
            threading.Thread(target=self.gerar, daemon=True, name="nexus-proforma-base").start()

    def gerar(self) -> dict[str, Any]:
        if not self.lock.acquire(blocking=False):
            return {"feito": False, "motivo": "A base já está sendo atualizada."}
        try:
            import duckdb
            import openpyxl
            atual = self.ferramenta_atual()
            if not atual:
                raise RuntimeError("A Ferramenta de Análise não foi encontrada em Controle de Conferência - BL › 1. PLATAFORMAS.")
            self.estado.update(rodando=True, etapa="abrindo a Ferramenta", erro="")
            t0 = time.time()
            mtime = atual.stat().st_mtime
            import shutil
            import tempfile
            tmpdir = Path(tempfile.mkdtemp(prefix="nexus_pf_"))
            copia = tmpdir / "ferramenta.xlsx"
            shutil.copy2(atual, copia)  # copia local: o Drive nao fica preso e a leitura e mais rapida
            wb = openpyxl.load_workbook(copia, read_only=True, data_only=True)
            linhas: dict[str, int] = {}
            self.destino.mkdir(parents=True, exist_ok=True)
            con = duckdb.connect()
            try:
                for aba, (nome, cols) in ABAS.items():
                    self.estado["etapa"] = f"lendo a aba {aba}"
                    ws = wb[aba]
                    idx = {k: _col_idx(k) for k in cols}
                    csv_path = tmpdir / f"{nome}.csv"
                    n = 0
                    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
                        w = csv.writer(fh)
                        w.writerow(list(cols.values()))
                        for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
                            vals = [(row[j] if j < len(row) else None) for j in idx.values()]
                            if not any(v not in (None, "") for v in vals):
                                continue
                            out = []
                            for nomecol, v in zip(cols.values(), vals):
                                if isinstance(v, str) and v.startswith("#"):  # #N/A, #REF! das formulas
                                    v = None
                                if isinstance(v, datetime):
                                    v = v.date().isoformat()
                                if nomecol in {"it_fisia", "it_nike"}:
                                    v = _item(v)
                                out.append("" if v is None else _txt(v) if not isinstance(v, (int, float)) or nomecol in {
                                    "po_fisia", "po_nike", "po_item", "tcci", "ncm", "it_fisia", "it_nike"} else v)
                            w.writerow(out)
                            n += 1
                    destino = self.destino / f"{nome}.parquet"
                    tmp_parquet = tmpdir / f"{nome}.parquet"
                    con.execute(f"COPY (SELECT * FROM read_csv('{csv_path.as_posix()}', header=true, all_varchar=true)) "
                                f"TO '{tmp_parquet.as_posix()}' (FORMAT parquet)")
                    shutil.copy2(tmp_parquet, destino.with_suffix(".tmp"))
                    os.replace(destino.with_suffix(".tmp"), destino)
                    linhas[aba] = n
            finally:
                con.close()
                wb.close()
                shutil.rmtree(tmpdir, ignore_errors=True)
            meta = {"arquivo": atual.name, "mtime": mtime, "gerada_em": _agora(), "linhas": linhas, "segundos": round(time.time() - t0)}
            (self.destino / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            self.log(f"Proforma: base da Ferramenta atualizada ({atual.name}, {linhas}) em {meta['segundos']} s")
            return {"feito": True, **meta}
        except Exception as exc:  # noqa: BLE001 - o erro aparece na tela
            self.estado["erro"] = str(exc)[:300]
            self.log(f"Proforma: falha na base da Ferramenta: {exc!r}")
            return {"feito": False, "motivo": str(exc)[:300]}
        finally:
            self.estado.update(rodando=False, etapa="")
            self.lock.release()

    def consultar(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        if not self.pronta():
            return []
        import duckdb
        con = duckdb.connect()
        try:
            for _, (nome, _c) in ABAS.items():
                con.execute(f"CREATE VIEW {nome} AS SELECT * FROM read_parquet('{(self.destino / (nome + '.parquet')).as_posix()}')")
            cur = con.execute(sql, params or [])
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            con.close()


# ---------------------------------------------------------------------------
# Montagem automatica
# ---------------------------------------------------------------------------
def _linha(valores: dict[str, Any], origem: dict[str, str]) -> dict[str, Any]:
    c = {k: valores.get(k) for k in EDITAVEIS}
    for k in NUMERICAS:
        c[k] = _num(c.get(k))
    for k in EDITAVEIS:
        if k not in NUMERICAS:
            c[k] = _txt(c.get(k))
    return {"id": uuid.uuid4().hex[:12], "rev": 1, "c": c, "o": {k: v for k, v in origem.items() if c.get(k) not in (None, "")}}


def montar(resumo: dict[str, Any], tccis: list[dict[str, Any]], base: Base, bl_dados: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Linhas da proforma + relatorio do que veio de cada fonte."""
    rel = {"faturas": len(tccis), "pela_sap": 0, "pela_tcci": 0, "sem_li": 0, "avisos": []}
    numeros = [t["fatura"] for t in tccis]
    sap: dict[str, list[dict[str, Any]]] = {}
    lis: dict[str, dict[str, Any]] = {}
    lis_mat: dict[str, dict[str, Any]] = {}
    prod: dict[str, dict[str, Any]] = {}
    otr: dict[str, dict[str, Any]] = {}
    if base.pronta() and numeros:
        for r in base.consultar("SELECT * FROM tcci WHERE tcci IN (SELECT unnest(?))", [numeros]):
            sap.setdefault(r["tcci"], []).append(r)
        pos = sorted({t.get("po_cliente") for t in tccis if t.get("po_cliente")} | {r["po_fisia"] for v in sap.values() for r in v})
        if pos:
            for r in base.consultar("SELECT * FROM lis WHERE po_fisia IN (SELECT unnest(?))", [pos]):
                lis[f"{r['po_fisia']}|{r['it_fisia']}"] = r
                lis_mat.setdefault(f"{r['po_fisia']}|{(r.get('material') or '')[:10]}", r)
        # Mesmo produto em outro pedido: NCM, descricao (com a composicao) e peso liquido por unidade sao do produto
        mats = sorted({r["material"] for v in sap.values() for r in v if r.get("material")})
        estilos = sorted({(m or "")[:10] for m in mats} | {(t.get("material") or "")[:10] for t in tccis if t.get("material")})
        if estilos:
            for r in base.consultar("SELECT * FROM lis WHERE (material IN (SELECT unnest(?)) OR substr(material, 1, 10) IN (SELECT unnest(?))) "
                                    "AND ncm IS NOT NULL ORDER BY li_registro DESC NULLS LAST", [mats or [""], estilos]):
                prod.setdefault(r["material"], r)
                prod.setdefault((r["material"] or "")[:10], r)
        chaves = [f"{t.get('po')}{t.get('item')}" for t in tccis if t.get("po") and t.get("item")]
        if chaves:
            for r in base.consultar("SELECT * FROM otr WHERE po_item IN (SELECT unnest(?))", [chaves]):
                otr[r["po_item"]] = r
    elif not base.pronta():
        rel["avisos"].append("A base da Ferramenta de Análise ainda não foi carregada: NCM, descrição e abertura por tamanho ficam em branco.")
    cntr_bl = (bl_dados or {}).get("conteineres") or []
    linhas: list[dict[str, Any]] = []
    for t in tccis:
        po_item = f"{t.get('po')}{t.get('item')}"
        cntr = (otr.get(po_item) or {}).get("cntr") if resumo.get("modal") != "Aéreo" else ""
        cntr_o = "otr" if cntr else ""
        if not cntr and resumo.get("modal") != "Aéreo" and len(cntr_bl) == 1:
            cntr, cntr_o = cntr_bl[0], "bl"
        comum = {"po_nike": t.get("po"), "it_nike": t.get("item"), "tcci": t.get("fatura"), "tcci_data": t.get("data"),
                 "fabricante": t.get("fabricante"), "endereco": t.get("endereco"), "cntr": cntr}
        o_comum = {"po_nike": "tcci", "it_nike": "tcci", "tcci": "tcci", "tcci_data": "tcci", "fabricante": "tcci", "endereco": "tcci", "cntr": cntr_o}
        partes = []
        if sap.get(t["fatura"]):
            rel["pela_sap"] += 1
            for r in sap[t["fatura"]]:
                q = _num(r.get("qtd"))
                v = _num(r.get("valor"))
                partes.append(({"po_fisia": r.get("po_fisia"), "it_fisia": r.get("it_fisia"), "material": r.get("material"), "qtd": q,
                                "preco": round(v / q, 6) if v is not None and q else None},
                               {"po_fisia": "sap", "it_fisia": "sap", "material": "sap", "qtd": "sap", "preco": "sap"}))
        else:
            rel["pela_tcci"] += 1
            for ln in t.get("linhas") or [{"tamanho": "", "qtd": t.get("quantidade"), "preco": None, "valor": t.get("valor")}]:
                q = ln.get("qtd")
                preco = ln.get("preco") if ln.get("preco") is not None else (round(ln["valor"] / q, 6) if ln.get("valor") is not None and q else None)
                partes.append(({"po_fisia": t.get("po_cliente"), "material": t.get("material") + (f" ({ln['tamanho']})" if ln.get("tamanho") else ""),
                                "qtd": q, "preco": preco},
                               {"po_fisia": "tcci", "material": "tcci", "qtd": "tcci", "preco": "tcci"}))
        qtd_fat = sum((p[0].get("qtd") or 0) for p in partes) or None
        for valores, origem in partes:
            valores, origem = {**comum, **valores}, {**o_comum, **origem}
            li = lis.get(f"{valores.get('po_fisia')}|{_item(valores.get('it_fisia'))}") if valores.get("it_fisia") else None
            li = li or lis_mat.get(f"{valores.get('po_fisia')}|{(valores.get('material') or '')[:10]}")
            q = valores.get("qtd")
            mat = valores.get("material") or ""
            if li:  # LI do proprio pedido e item
                for k in ("ncm", "descricao"):
                    if li.get(k):
                        valores[k], origem[k] = li[k], "li"
                if li.get("fabricante"):
                    valores["fabricante"], origem["fabricante"] = li["fabricante"], "li"
                if li.get("endereco"):
                    valores["endereco"], origem["endereco"] = li["endereco"], "li"
                pl, ql = _num(li.get("peso_liq")), _num(li.get("qtd"))
                if pl is not None and ql and q is not None and valores.get("it_fisia"):
                    valores["peso_liq"], origem["peso_liq"] = round(pl * q / ql, 3), "li"
            else:
                pr = prod.get(mat) or prod.get(mat[:10])
                if pr:  # LI do mesmo produto em outro pedido
                    rel["pelo_produto"] = rel.get("pelo_produto", 0) + 1
                    for k in ("ncm", "descricao"):
                        if pr.get(k):
                            valores[k], origem[k] = pr[k], "li_produto"
                    pl, ql = _num(pr.get("peso_liq")), _num(pr.get("qtd"))
                    if pl is not None and ql and q is not None and pr.get("material") == mat:
                        valores["peso_liq"], origem["peso_liq"] = round(pl / ql * q, 3), "li_produto"
                else:
                    rel["sem_li"] += 1
            # Pesos da TCCI rateados pela quantidade (bruto sempre; liquido so quando a LI nao trouxe)
            if qtd_fat and q is not None:
                if t.get("peso_bruto") is not None:
                    valores["peso_bruto"], origem["peso_bruto"] = round(t["peso_bruto"] * q / qtd_fat, 3), "rateio"
                if valores.get("peso_liq") is None and t.get("peso_liquido") is not None:
                    valores["peso_liq"], origem["peso_liq"] = round(t["peso_liquido"] * q / qtd_fat, 3), "rateio"
            linhas.append(_linha(valores, origem))
    if rel.get("pelo_produto"):
        rel["avisos"].append(f"{rel['pelo_produto']} linha(s) com NCM e descrição da LI do mesmo produto em outro pedido (o pedido não está mais na base).")
    if rel["sem_li"]:
        rel["avisos"].append(f"{rel['sem_li']} linha(s) sem dado de LI na base: NCM e descrição ficam para preencher.")
    if rel["pela_tcci"] and base.pronta():
        rel["avisos"].append(f"{rel['pela_tcci']} fatura(s) ainda não estão na base da Ferramenta: linhas montadas pela própria TCCI (por faixa de tamanho).")
    return linhas, rel


def da_pasta(data: bytes) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Linhas e cabecalho da proforma que a equipe ja salvou na pasta (Excel no modelo da Ferramenta)."""
    import openpyxl
    embarques_rot = {embarques.norm(c["l"]).strip(): c["k"] for c in COLUNAS}
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        cab: dict[str, str] = {}
        cols: dict[int, str] = {}
        linhas = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i > 5000:
                break
            if not cols:
                for j, v in enumerate(row):
                    rot = embarques.norm(v).strip() if isinstance(v, str) else ""
                    if rot in {"invoice no:", "exp no:", "inv date:", "bl no:"} and j + 1 < len(row):
                        cab[{"invoice no:": "invoice", "exp no:": "exp", "inv date:": "data", "bl no:": "bl"}[rot]] = _txt(row[j + 1])
                        if rot == "bl no:" and j + 2 < len(row) and row[j + 2] in ("VL", "AF"):
                            cab["modal"] = row[j + 2]
                labels = [embarques.norm(c).strip() if isinstance(c, str) else "" for c in row]
                if "po fisia" in labels and "quantity" in labels:
                    cols = {j: embarques_rot[lab] for j, lab in enumerate(labels) if lab in embarques_rot}
                continue
            vals = {k: row[j] for j, k in cols.items() if j < len(row)}
            if not isinstance(vals.get("qtd"), (int, float)):
                continue
            vals.pop("total", None)
            if vals.get("it_fisia") is not None:
                vals["it_fisia"] = _item(vals["it_fisia"])
            if vals.get("it_nike") is not None:
                vals["it_nike"] = _item(vals["it_nike"])
            linhas.append(_linha(vals, {k: "pasta" for k in vals}))
        return linhas, cab
    finally:
        wb.close()


# ---------------------------------------------------------------------------
# Arquivo da proforma
# ---------------------------------------------------------------------------
class Proformas:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta
        self.lock = threading.Lock()

    def _path(self, pid: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{16}", pid):
            raise ValueError("Processo inválido.")
        return self.pasta / f"{pid}.json"

    def ler(self, pid: str) -> dict[str, Any] | None:
        try:
            return json.loads(self._path(pid).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def gravar(self, doc: dict[str, Any]) -> None:
        path = self._path(doc["pid"])
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, path)

    def lista(self) -> list[dict[str, Any]]:
        out = []
        for p in sorted(self.pasta.glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            out.append({"pid": d["pid"], "processo": d.get("processo", ""), "op": d.get("op", ""), "linhas": len(d.get("linhas", [])),
                        "qtd": sum((ln["c"].get("qtd") or 0) for ln in d.get("linhas", [])),
                        "pendentes": pendencias(d)["total"], "alterado_em": d.get("alterado_em", ""), "alterado_por": d.get("alterado_por", ""),
                        "criado_por": d.get("criado_por", "")})
        return sorted(out, key=lambda x: x["alterado_em"], reverse=True)

    def excluir(self, pid: str, destino: Path) -> None:
        path = self._path(pid)
        destino.mkdir(parents=True, exist_ok=True)
        os.replace(path, destino / f"{pid}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")


def total(c: dict[str, Any]) -> float | None:
    q, p = c.get("qtd"), c.get("preco")
    return round(q * p, 2) if q is not None and p is not None else None


def pendencias(doc: dict[str, Any]) -> dict[str, Any]:
    falta = {k: 0 for k in OBRIGATORIAS}
    for ln in doc.get("linhas", []):
        for k in OBRIGATORIAS:
            if ln["c"].get(k) in (None, ""):
                falta[k] += 1
    return {"por_coluna": {k: v for k, v in falta.items() if v}, "total": sum(falta.values())}


def aplicar(doc: dict[str, Any], ops: list[dict[str, Any]], quem: str) -> dict[str, Any]:
    """Aplica operacoes da tela. Celula: {tipo:'cel', linha, col, valor, rev}; inserir: {tipo:'ins', apos, n, valores?};
    excluir: {tipo:'del', ids}; cabecalho: {tipo:'cab', campo, valor}. Conflito (linha mudou desde a versao que a
    pessoa via) volta em 'conflitos' com a linha atual; o resto e aplicado."""
    linhas = doc["linhas"]
    pos = {ln["id"]: i for i, ln in enumerate(linhas)}
    conflitos, novas, mudou = [], [], False
    for op in ops[:5000]:
        t = op.get("tipo")
        if t == "cel":
            i = pos.get(op.get("linha"))
            col = op.get("col")
            if i is None or col not in EDITAVEIS:
                continue
            ln = linhas[i]
            # Outra pessoa mudou ESTA celula depois da versao que a tela via: recusa e devolve a linha atual
            if isinstance(op.get("rev"), int) and ln.get("u", {}).get(col, 0) > op["rev"] and ln.get("w", {}).get(col) != quem:
                conflitos.append(ln)
                continue
            v = op.get("valor")
            v = _num(v) if col in NUMERICAS else _txt(v)
            if col == "tcci_data" and v and re.fullmatch(r"\d{2}/\d{2}/\d{4}", v):
                d, m, a = v.split("/")
                v = f"{a}-{m}-{d}"
            if ln["c"].get(col) == v:
                continue
            ln["c"][col] = v
            ln["rev"] += 1
            ln.setdefault("u", {})[col] = ln["rev"]
            ln.setdefault("w", {})[col] = quem
            if v in (None, ""):
                ln.get("o", {}).pop(col, None)
            else:
                ln.setdefault("o", {})[col] = "manual"
            mudou = True
        elif t == "ins":
            n = max(1, min(int(op.get("n") or 1), 500))
            valores = op.get("valores") or []
            i = pos.get(op.get("apos"), len(linhas) - 1) + 1 if op.get("apos") else (0 if op.get("inicio") else len(linhas))
            criadas = []
            for k in range(n):
                vals = valores[k] if k < len(valores) and isinstance(valores[k], dict) else {}
                ln = _linha({c: vals.get(c) for c in EDITAVEIS}, {c: "manual" for c in vals})
                if op.get("ids") and k < len(op["ids"]) and re.fullmatch(r"[a-f0-9]{12}", str(op["ids"][k])):
                    ln["id"] = op["ids"][k]
                criadas.append(ln)
            linhas[i:i] = criadas
            novas.extend(criadas)
            pos = {ln["id"]: j for j, ln in enumerate(linhas)}
            mudou = True
        elif t == "del":
            ids = set(op.get("ids") or [])
            antes = len(linhas)
            linhas[:] = [ln for ln in linhas if ln["id"] not in ids]
            pos = {ln["id"]: j for j, ln in enumerate(linhas)}
            mudou = mudou or len(linhas) != antes
        elif t == "cab" and op.get("campo") in {"invoice", "exp", "data", "bl", "modal"}:
            v = _txt(op.get("valor"))[:60]
            if doc["cab"].get(op["campo"]) != v:
                doc["cab"][op["campo"]] = v
                mudou = True
    if mudou:
        doc["versao"] = doc.get("versao", 0) + 1
        doc["alterado_em"], doc["alterado_por"] = _agora(), quem
    return {"conflitos": conflitos, "novas": novas, "mudou": mudou}


def para_tela(doc: dict[str, Any]) -> dict[str, Any]:
    for ln in doc.get("linhas", []):
        ln["c"]["total"] = total(ln["c"])
    return {**doc, "pendencias": pendencias(doc)}


def resumo_numeros(doc: dict[str, Any]) -> dict[str, Any]:
    """Totais da proforma com DuckDB (mesmo padrao da planilha do Estoque Contabil: soma das colunas numericas)."""
    import duckdb
    con = duckdb.connect()
    try:
        con.execute("CREATE TABLE p (qtd DOUBLE, peso_liq DOUBLE, peso_bruto DOUBLE, preco DOUBLE, tcci VARCHAR, ncm VARCHAR)")
        rows = [(ln["c"].get("qtd"), ln["c"].get("peso_liq"), ln["c"].get("peso_bruto"), ln["c"].get("preco"),
                 ln["c"].get("tcci") or None, ln["c"].get("ncm") or None) for ln in doc.get("linhas", [])]
        if rows:
            con.executemany("INSERT INTO p VALUES (?, ?, ?, ?, ?, ?)", rows)
        r = con.execute("SELECT count(*), sum(qtd), sum(peso_liq), sum(peso_bruto), sum(round(qtd * preco, 2)), "
                        "count(DISTINCT tcci), count(DISTINCT ncm) FROM p").fetchone()
        return {"linhas": r[0], "qtd": r[1], "peso_liq": r[2], "peso_bruto": r[3], "total": r[4], "tccis": r[5], "ncms": r[6]}
    finally:
        con.close()


def excel(doc: dict[str, Any]) -> Any:
    """Excel no layout da proforma da equipe (cabecalho nas linhas 4 a 14, colunas na linha 17, dados a partir da 18)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    wb = Workbook()
    ws = wb.active
    ws.title = "Proforma"
    cab = doc.get("cab", {})
    ws["D4"] = "PROFORMA FISIA"
    ws["D4"].font = Font(bold=True, size=16)
    for r, (rot, val) in enumerate((("Invoice No:", cab.get("invoice") or "Mixed Files"), ("EXP No:", cab.get("exp") or "-"),
                                     ("Inv Date:", cab.get("data") or datetime.now().strftime("%d/%m/%Y")), ("BL No:", cab.get("bl") or "")), start=4):
        ws.cell(r, 16, rot).font = Font(bold=True)
        ws.cell(r, 17, val)
    ws.cell(7, 18, cab.get("modal") or "")
    linhas = doc.get("linhas", [])
    soma_q = sum((ln["c"].get("qtd") or 0) for ln in linhas)
    soma_v = round(sum((total(ln["c"]) or 0) for ln in linhas), 2)
    ws.cell(12, 15, "Quantity").font = Font(bold=True)
    ws.cell(12, 16, "Grand Total $").font = Font(bold=True)
    ws.cell(13, 10, "Totals:").font = Font(bold=True)
    ws.cell(13, 15, soma_q)
    ws.cell(13, 16, soma_v)
    ws.cell(14, 15, "Prs/Pcs")
    ws.cell(14, 16, "(Currency: USD)")
    head = [c["l"] for c in COLUNAS]
    fill = PatternFill("solid", fgColor="003D18")
    fino = Side(style="thin", color="BFCFBF")
    for j, h in enumerate(head, start=4):
        cell = ws.cell(17, j, h)
        cell.font, cell.fill = Font(bold=True, color="FFFFFF"), fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for i, ln in enumerate(linhas, start=18):
        c = ln["c"]
        ws.cell(i, 1, f"{c.get('po_fisia') or ''}{c.get('it_fisia') or ''}")
        ws.cell(i, 2, f"{c.get('po_fisia') or ''}{c.get('it_fisia') or ''}{c.get('tcci') or ''}{c.get('material') or ''}")
        ws.cell(i, 3, f"{c.get('po_nike') or ''}{c.get('it_nike') or ''}")
        for j, col in enumerate(COLUNAS, start=4):
            v = total(c) if col["k"] == "total" else c.get(col["k"])
            if col["t"] == "data" and v:
                try:
                    v = datetime.strptime(v, "%Y-%m-%d")
                except ValueError:
                    pass
            cell = ws.cell(i, j, v if v not in ("",) else None)
            cell.border = Border(top=fino, bottom=fino, left=fino, right=fino)
            if col["t"] == "num":
                cell.number_format = "#,##0" if col.get("d") == 0 else "#,##0.000" if col.get("d") == 3 else "#,##0.00"
            elif col["t"] == "data" and isinstance(v, datetime):
                cell.number_format = "dd/mm/yyyy"
    for j, col in enumerate(COLUNAS, start=4):
        ws.column_dimensions[ws.cell(17, j).column_letter].width = max(10, min(48, col["w"] / 7))
    for letra in ("A", "B", "C"):
        ws.column_dimensions[letra].hidden = True
    ws.freeze_panes = "D18"
    ws.auto_filter.ref = f"D17:{ws.cell(17, 3 + len(COLUNAS)).column_letter}{max(18, 17 + len(linhas))}"
    return wb
