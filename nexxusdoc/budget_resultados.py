"""Resultados realizados do Budget (Log. Internacional): leitura das bases de fechamento.

Le dois tipos de arquivo, sempre pelos rotulos das abas e das linhas:
  - bridge de custo ("Bridge Custo <mes> - Fisia/Zelus"): abas "LOG. INTL PXQ - <operacao> (<periodo>)" e
    "Bridges - Units&Custos <periodo>";
  - Ferramenta de Controle ("Orcamento FISIA (Nike) - 2026 - Ferramenta de Controle"): abas "Bridges - Units&Custos",
    "Outlook - Units&Custos", "Masc. - Breakdown" e "Masc. - Custo" (base da PGL).

Regra central: nenhum resultado e estimado. O que nao esta no arquivo fica vazio; as conferencias so comparam numeros
que estao nas proprias bases e apontam o que nao fecha.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MES_NOME = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
TOL_REAIS = 5.0        # diferenca aceita nas conferencias (arredondamento das planilhas)
TOL_UNITS = 2.0


class BaseNaoReconhecida(ValueError):
    """O arquivo nao tem a estrutura de uma base de resultados conhecida."""


def _norm(v: Any) -> str:
    txt = unicodedata.normalize("NFKD", str(v or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", txt).strip()


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _txt(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _grid(ws) -> list[list[Any]]:
    return [list(r) for r in ws.iter_rows(values_only=True)]


def _cell(grid: list[list[Any]], r: int, c: int) -> Any:
    return grid[r][c] if 0 <= r < len(grid) and 0 <= c < len(grid[r]) else None


def _operacao(nome: str) -> str | None:
    n = _norm(nome)
    if "zelus" in n:  # a analise considera apenas a Fisia (pedido do usuario em 18/11/2026)
        return None
    if "nike" in n or "fisia" in n:
        return "fisia"
    return None


def _periodo(txt: str, ano: int | None) -> dict[str, Any] | None:
    """'Out/26' -> mes; 'YTD/26' -> acumulado; '3o Tri/26' -> trimestre. O Excel exportado do Google corta o nome da aba
    em 31 caracteres e tira a barra ('... (Out', '... (3o '): nesse caso o ano vem da aba 'Bridges - Units&Custos Out26'."""
    n = _norm(txt).rstrip(") ").strip()
    m = re.search(r"/?(\d{2})$", n) if not re.fullmatch(r"\do?", n) else None
    if m:
        ano = 2000 + int(m.group(1))
        n = n[: m.start()].strip()
    if ano is None:
        return None
    aa = str(ano)[2:]
    if n in MESES:
        mes = MESES.index(n) + 1
        return {"tipo": "mes", "chave": "mes", "rotulo": f"{MES_NOME[mes - 1]}/{aa}", "ano": ano, "mes": mes}
    if n == "ytd":
        return {"tipo": "ytd", "chave": "ytd", "rotulo": f"Acumulado/{aa}", "ano": ano}
    m = re.match(r"(\d)o?( tri.*)?$", n)
    if m:
        return {"tipo": "tri", "chave": f"tri{m.group(1)}", "rotulo": f"{m.group(1)}º trimestre/{aa}", "ano": ano}
    return None

# ---------------------------------------------------------------- bridge de custo
def _ponte(grid: list[list[Any]], inicio: int) -> list[dict[str, Any]]:
    itens: list[dict[str, Any]] = []
    for r in range(inicio + 1, min(inicio + 20, len(grid))):
        rot, val = _txt(_cell(grid, r, 0)), _num(_cell(grid, r, 1))
        if not rot:
            break
        itens.append({"rotulo": rot, "valor": val})
        if _norm(rot) == "actual":
            break
    return itens


def _abertura(grid: list[list[Any]], r0: int, c0: int) -> dict[str, Any]:
    linhas, total = [], None
    for r in range(r0 + 1, min(r0 + 16, len(grid))):
        rot = _txt(_cell(grid, r, c0))
        if not rot:
            break
        v = lambda d: _num(_cell(grid, r, c0 + d))
        item = {"rotulo": rot, "cpu_budget": v(2 - 1), "cpu_actual": v(2), "units_budget": v(3), "units_actual": v(4),
                "budget": v(7), "actual": v(8), "variacao": v(9), "impacto_volume": v(10), "impacto_preco": v(12), "impacto_total": v(13)}
        if _norm(rot) == "total":
            total = item
            break
        linhas.append(item)
    return {"linhas": linhas, "total": total}


def _ler_aba_ponte(grid: list[list[Any]]) -> dict[str, Any]:
    pos_ab = [(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if _norm(v) == "abertura"]
    pos_pt = [r for r, row in enumerate(grid) if row and _norm(row[0]) == "label"]
    if not pos_ab or not pos_pt:
        raise BaseNaoReconhecida("aba sem a abertura ou sem a ponte")
    cambio: dict[str, Any] = {}
    meses: dict[str, float | None] = {}
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            n = _norm(v)
            if n in ("fx budget", "fx actual", "efeito fx"):
                cambio[n.replace(" ", "_")] = _num(_cell(grid, r, c + 1))
            elif n in MESES and c > 15:
                meses[n] = _num(_cell(grid, r, c + 1))
    saida = {"real": _abertura(grid, *pos_ab[0]), "cambio_budget": _abertura(grid, *pos_ab[1]) if len(pos_ab) > 1 else None,
             "ponte_custo": _ponte(grid, pos_pt[0]), "ponte_cpu": _ponte(grid, pos_pt[1]) if len(pos_pt) > 1 else [],
             "cambio": cambio, "cambio_mensal": meses}
    return saida


def _secoes_bridges(grid: list[list[Any]], c0: int = 0) -> dict[str, Any]:
    """Blocos da aba 'Bridges - Units&Custos': units, custos, CPU e indicadores (colunas a partir de c0)."""
    def bloco(titulos: tuple[str, ...], ini: int = 0) -> tuple[list[dict[str, Any]], int]:
        for r in range(ini, len(grid)):
            if _norm(_cell(grid, r, c0)) in titulos and _norm(_cell(grid, r, c0 + 1)) == "budget":
                linhas = []
                k = r + 1
                while k < len(grid) and _txt(_cell(grid, k, c0)):
                    rot = _txt(_cell(grid, k, c0))
                    linhas.append({"rotulo": rot, "budget": _num(_cell(grid, k, c0 + 1)), "forecast": _num(_cell(grid, k, c0 + 2)),
                                   "actual": _num(_cell(grid, k, c0 + 3))})
                    if _norm(rot) == "total":
                        break
                    k += 1
                return linhas, k
        return [], ini
    units, p = bloco(("total units",))
    custos, p = bloco(("despesa",), p)
    cpu, p = bloco(("cpu", "custo total"), p)
    ind, p = bloco(("indicador",), p)
    return {"units": units, "custos": custos, "cpu": cpu, "indicadores": ind}


def _total(linhas: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((x for x in linhas if _norm(x["rotulo"]) == "total"), None)


def ler_bridge(wb) -> list[dict[str, Any]]:
    grupos: dict[str, dict[str, Any]] = {}
    ignoradas: list[str] = []
    aba_b = next((ws for ws in wb.worksheets if _norm(ws.title).startswith("bridges - units")), None)
    m_ano = re.search(r"[A-Za-z]{3}/?(\d{2})\s*$", aba_b.title) if aba_b is not None else None
    ano = 2000 + int(m_ano.group(1)) if m_ano else None
    for ws in wb.worksheets:
        m = re.fullmatch(r"LOG\. INTL PXQ - (.+?) \((.*)", ws.title.strip())
        per = _periodo(m.group(2), ano) if m else None
        op = _operacao(m.group(1)) if m else None
        if not (m and per and op):
            if not _norm(ws.title).startswith("bridges - units"):
                ignoradas.append(ws.title)
            continue
        g = grupos.setdefault(op, {"tipo": "bridge", "operacao": op, "periodos": {}, "abas": []})
        dados = _ler_aba_ponte(_grid(ws))
        dados.update(rotulo=per["rotulo"], aba=ws.title, oculta=ws.sheet_state != "visible")
        g["periodos"][per["chave"]] = dados
        g["abas"].append(ws.title)
        if per["tipo"] == "mes":
            g["competencia"] = f"{per['ano']}-{per['mes']:02d}"
    if not grupos:
        if any("zelus" in _norm(ws.title) for ws in wb.worksheets):
            raise BaseNaoReconhecida("o MBR considera apenas a Fisia")
        raise BaseNaoReconhecida("nenhuma aba 'LOG. INTL PXQ - <operação> (<período>)'")
    saida = []

    for g in grupos.values():
        if "competencia" not in g:
            raise BaseNaoReconhecida("a bridge não tem a aba do mês")
        if aba_b is not None:
            g["detalhe_mes"] = _secoes_bridges(_grid(aba_b))
            g["abas"].append(aba_b.title)
        g["abas_ignoradas"] = ignoradas
        saida.append(g)
    return saida


# ---------------------------------------------------------------- Ferramenta de Controle
_OUT_TOTAIS = {"total units budget": ("units", "budget"), "total units forecast": ("units", "forecast"), "total units actual": ("units", "actual"),
               "total conteineres budget": ("conteineres", "budget"), "total conteineres forecast": ("conteineres", "forecast"),
               "total conteineres actual": ("conteineres", "actual"), "custo total budget": ("custo", "budget"),
               "custo total forecast": ("custo", "forecast"), "custo total actual": ("custo", "actual")}


def _ler_outlook(grid: list[list[Any]], nomes: list[str]) -> dict[str, Any]:
    serie = lambda r: [_num(_cell(grid, r, c)) or 0.0 for c in range(2, 14)]
    out: dict[str, Any] = {"units": {}, "conteineres": {}, "custo": {}, "linhas": {"budget": {}, "forecast": {}, "actual": {}},
                           "units_modal": {"budget": {}, "forecast": {}, "actual": {}}}
    cen, cen_u, alvo = None, None, {_norm(n) for n in nomes}
    for r in range(len(grid)):
        n = _norm(_cell(grid, r, 1))
        if n in _OUT_TOTAIS:
            grupo, c = _OUT_TOTAIS[n]
            out[grupo][c] = serie(r)
            cen, cen_u = c if grupo == "custo" else None, c if grupo == "units" else None
        elif cen_u and n in ("frete maritimo", "frete aereo"):
            out["units_modal"][cen_u].setdefault("Frete Marítimo" if n == "frete maritimo" else "Frete Aéreo", serie(r))
        elif cen and n in alvo:
            # o Outlook repete o nome no grupo e no detalhe (Bunker, Marinha Mercante...): vale a ultima, que e o detalhe
            out["linhas"][cen][next(x for x in nomes if _norm(x) == n)] = serie(r)
    for g in ("units", "conteineres", "custo"):
        if set(out[g]) != {"budget", "forecast", "actual"}:
            raise BaseNaoReconhecida("aba Outlook sem Budget, Forecast e Actual")
    return out


def _ler_pgl(ws) -> dict[str, Any] | None:
    linhas = ws.iter_rows(values_only=True)
    cab = [_txt(x) for x in next(linhas)]
    pos = {n: i for i, n in reversed(list(enumerate(cab)))}
    if "PROCESSO" not in pos or "VIA_DE_TRANSPORTE" not in pos:
        return None
    dados = [r for r in linhas if r[pos["PROCESSO"]] not in (None, "")]
    val = lambda r, n: (_num(r[pos[n]]) or 0.0) if n in pos else 0.0
    soma = lambda n, rs=dados: sum(val(r, n) for r in rs)
    mar = [r for r in dados if _norm(r[pos["VIA_DE_TRANSPORTE"]]).startswith("maritimo")]
    bio = [r for r in mar if val(r, "ECODELIV_USD") > 0]
    return {"processos": len(dados), "processos_maritimos": len(mar), "processos_aereos": len(dados) - len(mar), "units": soma("QTD_PARES_PECAS"),
            "bunker": [{"rotulo": "Bunker", "brl": soma("BUNKER_R$"), "usd": soma("BUNKER_USD")},
                       {"rotulo": "Fossil", "brl": soma("FOSSIL_R$"), "usd": soma("FOSSIL_USD")},
                       {"rotulo": "Transpter (taxas de origem)", "brl": soma("TRANSPTER_R$"), "usd": soma("TRANSPTER_USD")},
                       {"rotulo": "Biocombustível (Ecodeliv)", "brl": soma("ECODELIV_R$"), "usd": soma("ECODELIV_USD")}],
            "processos_com_bio": len(bio), "bio_usd_por_processo": soma("ECODELIV_USD", bio) / len(bio) if bio else None}


def ler_ferramenta(wb) -> list[dict[str, Any]]:
    nomes = {_norm(ws.title): ws for ws in wb.worksheets}
    ws_b, ws_o = nomes.get("bridges - units&custos"), nomes.get("outlook - units&custos")
    if ws_b is None or ws_o is None:
        raise BaseNaoReconhecida("faltam as abas 'Bridges - Units&Custos' e 'Outlook - Units&Custos'")
    grid_b = _grid(ws_b)
    ytd, mes = _secoes_bridges(grid_b, 10), _secoes_bridges(grid_b, 19)
    if not mes["custos"] or not ytd["custos"]:
        raise BaseNaoReconhecida("aba Bridges sem os blocos do mês e do acumulado")
    rotulos = [x["rotulo"] for x in mes["custos"] if _norm(x["rotulo"]) != "total"]
    out = _ler_outlook(_grid(ws_o), rotulos)
    fechados = [i for i, v in enumerate(out["custo"]["actual"]) if v > 0]
    if not fechados:
        raise BaseNaoReconhecida("a Ferramenta não tem mês realizado")
    ult = fechados[-1]
    ano = next((v.year for row in ws_o.iter_rows(min_row=30, max_row=32, values_only=True) for v in row if hasattr(v, "year")), None)
    if ano is None:
        raise BaseNaoReconhecida("não foi possível identificar o ano na aba Outlook")
    # total "Actual vs. Forecast" como esta escrito na Ferramenta (so para conferir com a diferenca dos totais)
    avf: dict[str, float | None] = {}
    cab = next((r for r in range(len(grid_b)) if _norm(_cell(grid_b, r, 19)) == "despesa"), None)
    if cab is not None:
        fim = next((r for r in range(cab, len(grid_b)) if _norm(_cell(grid_b, r, 19)) == "total"), None)
        if fim is not None:
            avf = {"mes": _num(_cell(grid_b, fim, 26)), "ytd": _num(_cell(grid_b, fim, 17))}
    breakdown = None
    ws_d = nomes.get("masc. - breakdown")
    if ws_d is not None:
        for row in ws_d.iter_rows(values_only=True):
            if len(row) > 2 and _norm(row[1]) == "spend total":
                breakdown = _num(row[2])
    ws_c = nomes.get("masc. - custo")
    return [{"tipo": "ferramenta", "operacao": "fisia", "competencia": f"{ano}-{ult + 1:02d}", "mes_fechado": ult,
             "mes": mes, "ytd": ytd, "outlook": out, "spend_total": breakdown, "avf_escrito": avf,
             "pgl": _ler_pgl(ws_c) if ws_c is not None else None, "abas": [ws.title for ws in wb.worksheets]}]


def ler_arquivo(caminho: Any) -> list[dict[str, Any]]:
    """Identifica o arquivo pela estrutura das abas e devolve as bases lidas; recusa o que nao reconhece."""
    import openpyxl  # so ao ler um arquivo, para o servidor subir rapido
    wb = openpyxl.load_workbook(caminho, data_only=True)
    try:
        titulos = [_norm(ws.title) for ws in wb.worksheets]
        if "outlook - units&custos" in titulos and "bridges - units&custos" in titulos:
            bases = ler_ferramenta(wb)
        elif any(t.startswith("log. intl pxq") for t in titulos):
            bases = ler_bridge(wb)
        else:
            raise BaseNaoReconhecida("não é uma bridge de custo nem a Ferramenta de Controle")
    finally:
        wb.close()
    for b in bases:
        b["conferencias"] = conferir(b)
    return bases


# ---------------------------------------------------------------- conferencias
def _chk(nome: str, ok: bool, detalhe: str = "", nivel: str = "") -> dict[str, Any]:
    return {"nome": nome, "ok": bool(ok), "nivel": nivel or ("ok" if ok else "atencao"), "detalhe": detalhe}


def _brl(v: float | None) -> str:
    if v is None:
        return "-"
    return ("-" if v < 0 else "") + "R$ " + f"{abs(v):,.0f}".replace(",", ".")


def conferir(b: dict[str, Any]) -> list[dict[str, Any]]:
    return _conferir_bridge(b) if b["tipo"] == "bridge" else _conferir_ferramenta(b)


def _conferir_bridge(b: dict[str, Any]) -> list[dict[str, Any]]:
    res = []
    for p in b["periodos"].values():
        tot = p["real"]["total"] or {}
        soma = sum((x["valor"] or 0) for x in p["ponte_custo"] if _norm(x["rotulo"]) not in ("budget", "actual"))
        dif = (soma - ((tot.get("actual") or 0) - (tot.get("budget") or 0)) / 1e6) * 1e6
        res.append(_chk(f"{p['rotulo']}: a ponte fecha do Budget ao Actual", abs(dif) <= TOL_REAIS, f"diferença de {_brl(dif)}"))
        fim = next((x["valor"] for x in p["ponte_custo"] if _norm(x["rotulo"]) == "actual"), None)
        if fim is not None and abs(fim * 1e6 - (tot.get("actual") or 0)) > 100:
            res.append(_chk(f"{p['rotulo']}: rótulo ACTUAL da ponte", False,
                            f"a planilha mostra {_brl(fim * 1e6)} no fim da ponte, mas o custo realizado é {_brl(tot.get('actual'))}. Aqui vale o custo realizado"))
        s_b = sum(x["budget"] or 0 for x in p["real"]["linhas"])
        s_a = sum(x["actual"] or 0 for x in p["real"]["linhas"])
        res.append(_chk(f"{p['rotulo']}: os grupos somam o total", abs(s_b - (tot.get("budget") or 0)) <= TOL_REAIS and abs(s_a - (tot.get("actual") or 0)) <= TOL_REAIS))
        faltam = [m.capitalize() for m in MESES if m in p["cambio_mensal"] and not p["cambio_mensal"][m]]
        if p["cambio_mensal"] and faltam:
            res.append(_chk(f"{p['rotulo']}: câmbio de todos os meses", False, f"sem câmbio em {', '.join(faltam)}: a média do acumulado considera só os demais meses"))
    det = b.get("detalhe_mes") or {}
    mes = b["periodos"].get("mes")
    if det.get("custos") and mes:
        tc, tu = _total(det["custos"]) or {}, _total(det["units"]) or {}
        tm = mes["real"]["total"] or {}
        ok = abs((tc.get("budget") or 0) - (tm.get("budget") or 0)) <= TOL_REAIS and abs((tc.get("actual") or 0) - (tm.get("actual") or 0)) <= TOL_REAIS
        res.append(_chk("Mês: detalhe por despesa igual à ponte", ok))
        res.append(_chk("Mês: units do detalhe iguais às da ponte", abs((tu.get("actual") or 0) - (tm.get("units_actual") or 0)) <= TOL_UNITS))
        lin = [x for x in det["custos"] if _norm(x["rotulo"]) != "total"]
        res.append(_chk("Mês: as despesas somam o total", abs(sum(x["actual"] or 0 for x in lin) - (tc.get("actual") or 0)) <= TOL_REAIS))
        if lin and all(abs((x["forecast"] or 0) - (x["budget"] or 0)) < 0.5 for x in lin):
            res.append(_chk("Mês: Forecast próprio", False, "o Forecast é igual ao Budget em todas as despesas: a base não traz uma previsão diferente do orçamento"))
    return res


def _conferir_ferramenta(b: dict[str, Any]) -> list[dict[str, Any]]:
    res = []
    o, u = b["outlook"], b["mes_fechado"]
    ate = lambda s: sum(s[: u + 1])
    ty = _total(b["ytd"]["custos"]) or {}
    tm = _total(b["mes"]["custos"]) or {}
    for c, nome in (("budget", "Budget"), ("forecast", "Forecast"), ("actual", "Actual")):
        res.append(_chk(f"Acumulado: {nome} do Outlook igual ao da aba Bridges", abs(ate(o["custo"][c]) - (ty.get(c) or 0)) <= TOL_REAIS,
                        f"{_brl(ate(o['custo'][c]))} × {_brl(ty.get(c))}"))
    lin = [x for x in b["mes"]["custos"] if _norm(x["rotulo"]) != "total"]
    res.append(_chk("Mês: as despesas somam o total", abs(sum(x["actual"] or 0 for x in lin) - (tm.get("actual") or 0)) <= TOL_REAIS))
    if b.get("spend_total") is not None:
        res.append(_chk("Mês: Spend Total do Breakdown igual ao Actual", abs(b["spend_total"] - (tm.get("actual") or 0)) <= TOL_REAIS))
    tu = _total(b["mes"]["units"]) or {}
    if b.get("pgl"):
        res.append(_chk("Mês: units da base da PGL iguais ao Actual", abs(b["pgl"]["units"] - (tu.get("actual") or 0)) <= TOL_UNITS,
                        f"{b['pgl']['processos']} processos"))
    avf, dif_m = b.get("avf_escrito") or {}, (tm.get("actual") or 0) - (tm.get("forecast") or 0)
    if avf.get("mes") is not None and abs(avf["mes"] - dif_m) > TOL_REAIS:
        res.append(_chk("Mês: total 'Actual vs. Forecast' da Ferramenta", False,
                        f"a Ferramenta mostra {_brl(avf['mes'])}, mas Actual menos Forecast dá {_brl(dif_m)} (o total não soma todas as linhas). Aqui vale a diferença dos totais"))
    dif_y = (ty.get("actual") or 0) - (ty.get("forecast") or 0)
    if avf.get("ytd") is not None and abs(avf["ytd"] - dif_y) > TOL_REAIS:
        res.append(_chk("Acumulado: total 'Actual vs. Forecast' da Ferramenta", False,
                        f"a Ferramenta mostra {_brl(avf['ytd'])}, mas Actual menos Forecast dá {_brl(dif_y)}. Aqui vale a diferença dos totais"))
    if abs(o["custo"]["forecast"][u] - o["custo"]["actual"][u]) > TOL_REAIS:
        res.append(_chk("Forecast do ano", False, f"o Forecast de {MES_NOME[u].lower()} ({_brl(o['custo']['forecast'][u])}) ainda não foi trocado pelo realizado ({_brl(o['custo']['actual'][u])}): o total anual do Forecast fica desatualizado"))
    return res


def cruzar(bridge: dict[str, Any], ferramenta: dict[str, Any]) -> list[dict[str, Any]]:
    """Compara a bridge com a Ferramenta de Controle da mesma competencia."""
    res = []
    for chave, bloco, nome in (("mes", "mes", "Mês"), ("ytd", "ytd", "Acumulado")):
        per = bridge["periodos"].get(chave)
        if not per:
            continue
        t, u, f = per["real"]["total"] or {}, _total(ferramenta[bloco]["units"]) or {}, _total(ferramenta[bloco]["custos"]) or {}
        res.append(_chk(f"{nome}: Budget da bridge igual ao da Ferramenta", abs((t.get("budget") or 0) - (f.get("budget") or 0)) <= TOL_REAIS, f"{_brl(t.get('budget'))} × {_brl(f.get('budget'))}"))
        res.append(_chk(f"{nome}: Actual da bridge igual ao da Ferramenta", abs((t.get("actual") or 0) - (f.get("actual") or 0)) <= TOL_REAIS, f"{_brl(t.get('actual'))} × {_brl(f.get('actual'))}"))
        res.append(_chk(f"{nome}: units da bridge iguais às da Ferramenta", abs((t.get("units_actual") or 0) - (u.get("actual") or 0)) <= TOL_UNITS))
    return res


# ---------------------------------------------------------------- dados prontos para a tela e a apresentacao
_TRI = {"tri1": (0, 3), "tri2": (3, 6), "tri3": (6, 9), "tri4": (9, 12)}
_ORDEM = {"mes": 0, "ytd": 1, "tri1": 2, "tri2": 3, "tri3": 4, "tri4": 5}


def _resumo(chave: str, per: dict[str, Any], bridge: dict[str, Any], ferr: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Budget, Forecast e Actual do periodo. Forecast so quando a base traz; sem base fica None (nunca estimado)."""
    t = per["real"]["total"] or {}
    r = {"budget": t.get("budget"), "actual": t.get("actual"), "forecast": None, "units_budget": t.get("units_budget"), "units_actual": t.get("units_actual"),
         "units_forecast": None, "cpu_budget": t.get("cpu_budget"), "cpu_actual": t.get("cpu_actual"), "cpu_forecast": None, "fonte_forecast": ""}
    bloco = bridge.get("detalhe_mes") if chave == "mes" else ferr["ytd"] if chave == "ytd" and ferr else None
    if bloco and bloco.get("custos"):
        tc, tu, tp = _total(bloco["custos"]) or {}, _total(bloco["units"]) or {}, _total(bloco["cpu"]) or {}
        r.update(forecast=tc.get("forecast"), units_forecast=tu.get("forecast"), cpu_forecast=tp.get("forecast"), fonte_forecast="base",
                 dif_forecast=(tc.get("actual") or 0) - (tc.get("forecast") or 0) if tc.get("forecast") is not None else None)
    elif chave in _TRI and ferr:
        i, j = _TRI[chave]
        c, u = sum(ferr["outlook"]["custo"]["forecast"][i:j]), sum(ferr["outlook"]["units"]["forecast"][i:j])
        r.update(forecast=c, units_forecast=u, cpu_forecast=c / u if u else None, fonte_forecast="outlook")
    return r, bloco


def montar_operacao(op: str, nome: str, bridge: dict[str, Any] | None, ferr: dict[str, Any] | None) -> dict[str, Any]:
    saida: dict[str, Any] = {"operacao": op, "nome": nome, "periodos": [], "proximo": None, "mensal": None, "pgl": None, "conferencias": [],
                             "tem_bridge": bool(bridge), "tem_ferramenta": bool(ferr)}
    if bridge:
        for chave in sorted(bridge["periodos"], key=lambda k: _ORDEM.get(k, 9)):
            per = bridge["periodos"][chave]
            resumo, bloco = _resumo(chave, per, bridge, ferr)
            saida["periodos"].append({"chave": chave, "rotulo": per["rotulo"], "oculta": per.get("oculta"), "resumo": resumo,
                                      "ponte": [x for x in per["ponte_custo"] if _norm(x["rotulo"]) not in ("budget", "actual")],
                                      "ponte_cpu": [x for x in per["ponte_cpu"] if _norm(x["rotulo"]) not in ("budget", "actual")],
                                      "real": per["real"], "cambio_budget": per["cambio_budget"], "cambio": per["cambio"], "detalhe": bloco})
        saida["conferencias"] += bridge.get("conferencias") or []
    if ferr:
        o, u = ferr["outlook"], ferr["mes_fechado"]
        saida["pgl"] = ferr.get("pgl")
        saida["conferencias"] += ferr.get("conferencias") or []
        saida["mensal"] = {"rotulos": [m.capitalize() for m in MESES], "fechado": u, "custo": o["custo"], "units": o["units"], "conteineres": o["conteineres"]}
        if u < 11:
            i = u + 1
            ordem = [x["rotulo"] for x in ferr["mes"]["custos"] if _norm(x["rotulo"]) != "total"]
            saida["proximo"] = {"rotulo": MES_NOME[i], "units_budget": o["units"]["budget"][i], "units_forecast": o["units"]["forecast"][i],
                                "budget": o["custo"]["budget"][i], "forecast": o["custo"]["forecast"][i],
                                "linhas": [{"rotulo": n, "budget": o["linhas"]["budget"].get(n, [0] * 12)[i], "forecast": o["linhas"]["forecast"].get(n, [0] * 12)[i]} for n in ordem]}
    if bridge and ferr:
        saida["conferencias"] += cruzar(bridge, ferr)
    return saida
