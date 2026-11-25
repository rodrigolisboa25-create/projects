"""Pagina Custos (24/11/2026, pedido do usuario): custo de importacao por processo a partir das MIROs de debito posterior.

A PGL salva em Sua Area > PGL S/4HANA > Layouts - MIRO de Deb. Post. > <MES> (pastas de mes reaproveitadas a cada ano)
um CSV por MIRO, ja no layout de subida no SAP (ZDMM_DEBITO_POST):
- "MIRO DE IMPOSTOS - <BL> - WFADIM...-1.csv": sai no registro da DI. Frete internacional e taxas do agente (fornecedor
  122546 = PGL), II + 1% de COFINS (150950) e Taxa Siscomex (150951). Atribuicao = numero da DI.
- "MIRO DE DESPESAS - <BL> - WFADIM...-1.csv": sai na programacao de entrega (vespera). Armazenagem, frete rodoviario,
  ajudantes, honorarios de desembaraco, CE Mercante etc. (122546).
- "-2", "-3": reemissao completa da mesma MIRO; vale a de numero maior.
Uma linha por item de pedido para cada rubrica (Texto). Rateio da PGL (conferido em 23/11/2026 em ~60 processos):
frete, taxas do agente e despesas pelo PESO BRUTO do item; II/1% COFINS, Siscomex, dumping e multa pelo VALOR.
Impostos recuperaveis (PIS, COFINS, ICMS) NAO entram nesses layouts: vao pela contabilizacao diaria em Layouts - Impostos
(fornecedor 150949, contas a recuperar). So Fisia (empresa 0001).
O n8n (fluxo apartado "NexxusDoc - Custos") le os layouts novos e grava nexxusdoc_custos_n8n.json; o historico (2025 em
diante) veio de uma carga unica com este modulo. A mesma leitura esta em JavaScript no fluxo.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime, timedelta
from typing import Any

DESDE = "2025-01-01"
PGL, II, SISCOMEX = "122546", "150950", "150951"
# Colunas do layout (posicao fixa; o cabecalho tem "Empresa" e "Codigo Imposto (IVA)" repetidos)
COLUNAS = ["Referencia do Documento ", "Invoice Ind.", "Tipo de Documento", "Data da fatura", "Data do lancamento",
           "Empresa", "Fornecedor", "Moeda", "Taxa de Cambio", "Montante da NF", "Data base calc. do venc.",
           "Dias de desconto 1", "Dias de desconto 2", "Txt. Cabecalho", "Atribuicao", "Texto", "Invoice Status",
           "Num. de Itens MIRO", "Num. da PO", "Item da PO", "Debito Posterior", "Codigo Imposto (IVA)", "Montante do Item",
           "Qtd. do Item", "Unid. medida do Item", "Condicao de pagamento", "Num. seq. de entr. dos impostos",
           "Conta Razao ref. ao imposto", "Montante do imposto", "DB CR IND", "Empresa", "Codigo Imposto (IVA)"]
GRUPOS = {  # ordem de exibicao, nome, cor: tons sobrios (pedido do usuario, sem rosa nem cores vivas), validados para
    # daltonismo na ordem do custo logistico (frete, porto, armazenagem, transporte, desembaraco, seguro)
    "frete": ("Frete internacional", "#34679E"), "impostos": ("Impostos (II, Siscomex)", "#4A5560"),
    "porto": ("Porto e terminal", "#B0603F"), "armazenagem": ("Armazenagem", "#14998A"),
    "transporte": ("Transporte até o CD", "#B8892C"), "desembaraco": ("Desembaraço e serviços", "#7C6CB0"),
    "seguro": ("Seguro", "#5E8C2C"), "outros": ("Outros", "#8A8F8C"),
}
# Rubricas mais comuns (codigo da coluna Texto). As demais caem no grupo pelo nome (rubrica_grupo).
RUBRICAS = {
    "PGTOFRETE": ("Frete internacional", "frete"), "PGTOBUNKER": ("Bunker", "frete"), "PGTOFOSSIL": ("Fossil Fuel", "frete"),
    "PGTOTXADD FRET": ("Taxa adicional de frete", "frete"), "PGTOECODELIV": ("Eco Delivery", "frete"),
    "PGTOCAPATAZIAS": ("Capatazias", "porto"), "PGTOCEMERCANTE": ("CE Mercante / AFRMM", "porto"),
    "PGTOJUROSMMERC": ("Juros Marinha Mercante", "porto"), "PGTODEMURRAGE": ("Demurrage", "porto"),
    "DEBITOII/1% Cof": ("II + 1% COFINS", "impostos"), "DEBITOTX. SISC.": ("Taxa Siscomex", "impostos"),
    "DEBITODUMPING": ("Direito antidumping", "impostos"), "DEBITOMULTA": ("Multa", "impostos"),
    "PGTOARMAZ": ("Armazenagem", "armazenagem"), "PGTOARMAZDSA": ("Armazenagem DSA", "armazenagem"),
    "PGTOFRETEROD": ("Frete rodoviário", "transporte"), "PGTOFRETRODCPL": ("Frete rodoviário complementar", "transporte"),
    "PGTOAJDESCARGA": ("Ajudantes de descarga", "transporte"), "PGTOTRAVAELET": ("Trava eletrônica", "transporte"),
    "PGTODESEMB": ("Honorários de desembaraço", "desembaraco"), "PGTOCOORDENA": ("Coordenação", "desembaraco"),
    "PGTOSERVADM": ("Serviço administrativo", "desembaraco"), "PGTOSERVLI": ("Serviço de LI", "desembaraco"),
    "PGTOFLOWLS": ("Flowls", "desembaraco"), "PGTOSEGURO": ("Seguro", "seguro"), "PGTOADMSEG": ("Administração do seguro", "seguro"),
}
VALOR_BASE = ("impostos",)  # grupos rateados pelo valor da mercadoria; o resto pelo peso bruto


def rubrica_grupo(codigo: str) -> str:
    c = re.sub(r"^(PGTO|PREST(A[CÇ][AÃ]O)?|ANTECIPA[CÇ][AÃ]O|D[EÉ]BITO)\s*", "", (codigo or "").upper())
    for k, (_, g) in RUBRICAS.items():
        if re.sub(r"^(PGTO|DEBITO)", "", k) == c:
            return g
    if re.search(r"FRETE ?ROD|FRETROD|FRETENACIO|AJDESC|TRAVA|MOTO|TTMS", c):
        return "transporte"
    if "ARMAZ" in c:
        return "armazenagem"
    if re.search(r"II|SISC|DUMPING|MULTA", c) and "SERV" not in c:
        return "impostos"
    if re.search(r"CAPATAZ|MERC|DEMURR|INSPE|MOVCARGA|TRANSPTER|FOTOGRAF", c):
        return "porto"
    if re.search(r"FRETE|BUNKER|FOSSIL|BL|DELIV|CONSOL|COLLECT|CHC|DOC FEE|IOF", c):
        return "frete"
    if "SEGUR" in c:
        return "seguro"
    if re.search(r"DESEMB|SERV|COORD|FLOWLS|SISTEMA|ADM|CARTA|DESP|JURO", c):
        return "desembaraco"
    return "outros"


def rubrica_nome(codigo: str) -> str:
    if codigo in RUBRICAS:
        return RUBRICAS[codigo][0]
    c = re.sub(r"^(PGTO|PREST|DEBITO|D[EÉ]BITO)\s*", "", codigo or "").strip()
    return c.capitalize() if c else "Sem rubrica"


def _num(v: str) -> float:
    v = (v or "").strip().strip('"').replace(" ", "")
    if not v:
        return 0.0
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return 0.0


def _data(v: str) -> str:
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", (v or "").strip().strip('"'))
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def _texto(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", "replace")


def tipo_do_nome(nome: str) -> str:
    m = re.match(r"[\s_]*MIRO[\s_]+DE[\s_]+(IMPOSTOS|DESPESAS|FRETE)", (nome or "").upper())
    return m.group(1).lower() if m else "outro"


def ler_layout(raw: bytes | str, nome: str) -> dict[str, Any] | None:
    """Um CSV de MIRO -> resumo: rubricas (total, fornecedor, cabecalho, atribuicao, vencimento), itens por pedido."""
    txt = raw if isinstance(raw, str) else _texto(raw)
    linhas = [l for l in txt.splitlines() if l.strip()]
    if len(linhas) < 2:
        return None
    rub: dict[str, dict[str, Any]] = {}
    itens: dict[str, dict[str, Any]] = {}
    ref = emp = data = ""
    for l in linhas[1:]:
        c = [v.strip().strip('"').strip() for v in l.split(";")]
        if len(c) < 24:
            continue
        ref, emp, data = ref or c[0], emp or c[5], data or _data(c[3])
        cod = c[15] or "(sem texto)"
        r = rub.setdefault(cod, {"fornecedor": c[6], "cabecalho": c[13], "atribuicao": c[14], "nf": 0.0, "_refs": set(),
                                 "venc": _data(c[10]), "total": 0.0, "itens": 0})
        if c[0] not in r["_refs"]:  # um arquivo pode juntar duas MIROs (referencias diferentes)
            r["_refs"].add(c[0])
            r["nf"] += _num(c[9])
        v = _num(c[22])
        r["total"] += v
        r["itens"] += 1
        k = f"{c[18]}/{c[19].lstrip('0') or c[19]}"
        it = itens.setdefault(k, {"po": c[18], "item": c[19], "qtd": _num(c[23]), "unid": c[24], "valores": {}})
        it["valores"][cod] = round(it["valores"].get(cod, 0.0) + v, 2)
    if not rub:
        return None
    for r in rub.values():
        r.pop("_refs", None)
        r["total"] = round(r["total"], 2)
        r["nf"] = round(r["nf"], 2)
    nm = (nome or "").upper()
    wf = re.search(r"WFADIM\d{8,9}", nm)
    ver = re.search(r"-(\d{1,2})(?:\s|\.CSV|$)", re.sub(r"\.CSV$", "", nm) + " ")
    return {"nome": nome, "tipo": tipo_do_nome(nome), "versao": int(ver.group(1)) if ver else 1,
            "wfadim": wf.group(0) if wf else "", "ref": ref, "empresa": emp, "data": data,
            "rubricas": rub, "itens": list(itens.values())}


def compacto(a: dict[str, Any]) -> dict[str, Any]:
    """Resumo guardado (historico e n8n): sem os itens, com o total por pedido (PO) e grupo de rubrica."""
    pos: dict[str, dict[str, Any]] = {}
    for it in a.get("itens") or []:
        p = pos.setdefault(it["po"], {"qtd": 0.0, "itens": 0, "g": {}})
        p["itens"] += 1
        p["qtd"] += it.get("qtd") or 0
        for cod, v in it["valores"].items():
            g = rubrica_grupo(cod)
            p["g"][g] = round(p["g"].get(g, 0.0) + v, 2)
    out = {k: v for k, v in a.items() if k != "itens"}
    out["pos"] = pos
    out["n_itens"] = len(a.get("itens") or [])
    return out


def consolidar(arquivos: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Layouts lidos -> processos (chave WFADIM, ou a referencia). Por tipo vale a maior versao (empate: o mais novo)."""
    por: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for a in arquivos:
        if not a or (a.get("empresa") and a["empresa"] not in ("0001", "")):
            continue
        chave = a.get("wfadim") or re.sub(r"[^A-Z0-9]", "", (a.get("ref") or "").upper())
        if chave:
            por.setdefault(chave, {}).setdefault(a["tipo"], []).append(a)
    out = {}
    for chave, tipos in por.items():
        vale = {t: max(v, key=lambda a: (a.get("versao") or 1, a.get("mod") or "")) for t, v in tipos.items()}
        rub: dict[str, dict[str, Any]] = {}
        for t, a in sorted(vale.items(), key=lambda kv: kv[1].get("mod") or ""):
            for cod, r in a["rubricas"].items():
                rub[cod] = {**r, "tipo": t, "arquivo": a["nome"], "grupo": rubrica_grupo(cod), "nome": rubrica_nome(cod)}
        grupos: dict[str, float] = {}
        for r in rub.values():
            grupos[r["grupo"]] = round(grupos.get(r["grupo"], 0.0) + r["total"], 2)
        refs = sorted({a.get("ref") for v in tipos.values() for a in v if a.get("ref")})
        datas = {t: a.get("data") for t, a in vale.items()}
        di = next((r["atribuicao"] for r in rub.values() if r["fornecedor"] in (II, SISCOMEX) and r.get("atribuicao")), "")
        out[chave] = {
            "chave": chave, "wfadim": chave if chave.startswith("WFADIM") else "", "ref": refs[0] if refs else "",
            "refs": refs, "di": di, "data_impostos": datas.get("impostos") or datas.get("frete") or "",
            "data_despesas": datas.get("despesas") or "", "data": max([d for d in datas.values() if d] or [""]),
            "tem_impostos": "impostos" in vale or "frete" in vale, "tem_despesas": "despesas" in vale,
            "rubricas": rub, "grupos": grupos, "total": round(sum(grupos.values()), 2),
            "arquivos": sorted(({"nome": a["nome"], "tipo": a["tipo"], "versao": a.get("versao") or 1, "mod": a.get("mod") or "",
                                 "drive_id": a.get("drive_id", ""), "vale": a is vale.get(a["tipo"]), "data": a.get("data") or ""}
                                for v in tipos.values() for a in v), key=lambda x: (x["tipo"], x["versao"])),
            "pedidos": _pedidos(vale.values()),
            "itens": max((a.get("n_itens") or len(a.get("itens") or []) for a in vale.values()), default=0),
        }
    return out


def _pedidos(arqs) -> list[dict[str, Any]]:
    """Custo por pedido (PO FISIA) somando os layouts que valem: quantidade (a maior entre eles) e grupos."""
    acc: dict[str, dict[str, Any]] = {}
    for a in arqs:
        pos = a.get("pos") or compacto(a)["pos"]
        for po, p in pos.items():
            d = acc.setdefault(po, {"po": po, "qtd": 0.0, "itens": 0, "grupos": {}, "total": 0.0})
            d["qtd"] = max(d["qtd"], p["qtd"])
            d["itens"] = max(d["itens"], p["itens"])
            for g, v in p["g"].items():
                d["grupos"][g] = round(d["grupos"].get(g, 0.0) + v, 2)
    for d in acc.values():
        d["total"] = round(sum(d["grupos"].values()), 2)
    return sorted(acc.values(), key=lambda d: -d["total"])


# ---------------------------------------------------------------------------
# Montagem do layout (mesmo formato da PGL, pronto para a ZDMM_DEBITO_POST)
# ---------------------------------------------------------------------------
def _br(v: float) -> str:
    """Como a PGL escreve: virgula decimal e sem zeros a direita (202,2 ; 553)."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def _dt(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def ratear(total: float, pesos: list[float]) -> list[float]:
    """Divide em centavos proporcionalmente aos pesos; a sobra do arredondamento vai para o maior item."""
    soma = sum(pesos)
    if not pesos:
        return []
    if soma <= 0:
        pesos, soma = [1.0] * len(pesos), float(len(pesos))
    partes = [round(total * p / soma, 2) for p in pesos]
    dif = round(total - sum(partes), 2)
    if dif:
        i = max(range(len(pesos)), key=lambda j: pesos[j])
        partes[i] = round(partes[i] + dif, 2)
    return partes


def montar_layout(tipo: str, ref: str, itens: list[dict[str, Any]], valores: dict[str, float], data_doc: date,
                  di: str = "", vencimento_frete_dias: int = 15,
                  manual: dict[str, list[float]] | None = None, atribuicao: str = "1") -> tuple[str, list[dict[str, Any]]]:
    """itens: [{po, item, qtd, peso, valor}]; valores: {codigo_rubrica: total}. Devolve (csv, resumo por rubrica).
    manual: {codigo: [valor de cada item]} substitui o rateio (II e antidumping saem da DI, pela aliquota de cada NCM).
    tipo impostos: rubricas da PGL saem como "Frete" (vencimento + 15 dias) e 15095x como "Impostos"; atribuicao = DI nas duas;
    tipo despesas: "Despesas", atribuicao "1" ou o numero que a PGL usa (as duas formas aparecem em 2026), vencimento na data."""
    out = io.StringIO()
    out.write(";".join(COLUNAS) + "\n")
    resumo = []
    manual = manual or {}
    for cod in list(manual):
        if cod not in valores:
            valores = {**valores, cod: 0}
    for cod, total in valores.items():
        grupo = rubrica_grupo(cod)
        imposto = grupo == "impostos"
        forn = (SISCOMEX if re.search(r"SISC|DUMPING", cod.upper()) else II) if imposto else PGL  # como em 2026
        lista = manual.get(cod)
        if lista and len(lista) == len(itens):
            partes = [round(float(v or 0), 2) for v in lista]
            total, base_nome = round(sum(partes), 2), "informado por item"
        else:
            total = round(float(total or 0), 2)
            base = [float(i.get("valor") or 0) if imposto else float(i.get("peso") or 0) for i in itens]
            partes, base_nome = ratear(total, base), ("valor" if imposto else "peso bruto")
        if total <= 0:
            continue
        if tipo == "impostos":
            cab, atrib = ("Impostos", di) if imposto else ("Frete", di)
            venc = data_doc if imposto else data_doc + timedelta(days=vencimento_frete_dias)
        else:
            cab, atrib, venc = "Despesas", (atribuicao or "1"), data_doc
        seq = 0
        for it, v in zip(itens, partes):
            if v <= 0:  # a PGL nao escreve item sem valor na rubrica; o numero do item na MIRO conta so as linhas escritas
                continue
            seq += 1
            linha = [ref, "X", "CA", _dt(data_doc), _dt(data_doc), "0001", forn, "BRL", "1", _br(total), _dt(venc), "", "",
                     cab, atrib, cod, "5", str(seq), str(it["po"]), str(it["item"]), "X", "I0", _br(v),
                     _br(float(it.get("qtd") or 0)), it.get("unid") or "CDA", "", "", "", "0" if imposto else "", "", "", ""]
            out.write(";".join(linha) + "\n")
        resumo.append({"codigo": cod, "nome": rubrica_nome(cod), "fornecedor": forn, "total": total,
                       "base": base_nome, "itens": seq, "partes": partes})
    return out.getvalue(), resumo


def itens_da_proforma(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Planilha proforma do sistema -> itens de pedido (PO FISIA + item) com quantidade, peso bruto e valor."""
    acc: dict[tuple[str, str], dict[str, Any]] = {}
    for lin in (doc or {}).get("linhas", []):
        c = lin.get("c") or {}
        po, it = str(c.get("po_fisia") or "").strip(), str(c.get("it_fisia") or "").strip()
        if not po or not it:
            continue
        ncm = re.sub(r"\D", "", str(c.get("ncm") or ""))
        a = acc.setdefault((po, it), {"po": po, "item": it, "qtd": 0.0, "peso": 0.0, "valor": 0.0,
                                      "unid": "PAR" if ncm.startswith("64") else "CDA"})  # calcado (NCM 64) em pares
        try:
            q = float(c.get("qtd") or 0)
            a["qtd"] += q
            a["peso"] += float(c.get("peso_bruto") or 0)
            a["valor"] += q * float(c.get("preco") or 0)
        except (TypeError, ValueError):
            continue
    return sorted(acc.values(), key=lambda a: (a["po"], int(re.sub(r"\D", "", a["item"]) or 0)))


def itens_do_layout(a: dict[str, Any]) -> list[dict[str, Any]]:
    """Base de itens a partir de um layout lido por inteiro (ler_layout): o peso sai da soma das rubricas da PGL por item
    (frete, capatazias e despesas sao repartidos pelo peso bruto, entao a proporcao e a mesma) e o valor do Siscomex (pelo
    valor da mercadoria). Serve para montar a MIRO de despesas a partir da de impostos do mesmo processo."""
    out = []
    for it in a.get("itens") or []:
        pgl = sum(v for c, v in it["valores"].items() if rubrica_grupo(c) != "impostos")
        sisc = sum(v for c, v in it["valores"].items() if "SISC" in c.upper())
        out.append({"po": it["po"], "item": it["item"], "qtd": it["qtd"], "unid": it.get("unid") or "CDA", "peso": pgl, "valor": sisc})
    # Participacao de cada item em % (o rateio so depende da proporcao)
    for k in ("peso", "valor"):
        soma = sum(i[k] for i in out)
        for i in out:
            i[k] = round(i[k] / soma * 100, 6) if soma else 0.0
    return out


def hoje() -> date:
    return datetime.now().date()
