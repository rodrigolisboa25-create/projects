"""Budget > MBR: alterar valores pela base em Excel.

A base baixada traz a aba "Editar valores" (custo por despesa, units, conteineres e cambio, mes a mes). Ao reenviar o arquivo,
so as celulas que mudaram entram: o sistema soma a diferenca nos periodos atingidos e refaz totais, CPU, abertura por grupo e
Bridge com as mesmas formulas das planilhas de bridge. O que nao mudou continua exatamente como foi lido das bases.
"""
from __future__ import annotations

import copy
import json
from typing import Any

import budget_resultados as BR

ABA = "Editar valores"
MARCA = "_mbr"
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
CENARIOS = {"actual": "Actual", "forecast": "Forecast", "budget": "Budget"}
CUSTO, UNITS, CNTR, FX = "Custo (R$)", "Units", "Contêineres", "Câmbio (USD)"
MODAIS = ("Frete Marítimo", "Frete Aéreo")
_GRUPO = {"frete maritimo": "maritimo", "bunker": "bunker", "biocombustivel": "bunker", "frete aereo": "frete aereo", "seguro internacional": "seguro internacional",
          "armazenagem santos": "armazenagem", "santos - extrema": "rodoviario", "santos - louveira": "rodoviario", "escolta armada": "rodoviario",
          "trava ciltronics": "rodoviario", "estadia de veiculo": "rodoviario", "horas paradas": "rodoviario", "ajudante": "rodoviario"}
_USD = ("maritimo", "bunker", "frete aereo", "seguro internacional")  # so estes grupos sofrem efeito do cambio


def _grupo(linha: str) -> str:
    return _GRUPO.get(BR._norm(linha), "outras despesas")


def _fx_meses(bridge: dict[str, Any], ferr: dict[str, Any]) -> list[float | None]:
    mapa = (bridge["periodos"].get("ytd") or {}).get("cambio_mensal") or {}
    vals = [mapa.get(m.lower()) or None for m in MESES]
    mes = bridge["periodos"].get("mes")
    if mes and vals[ferr["mes_fechado"]] is None:
        vals[ferr["mes_fechado"]] = (mes.get("cambio") or {}).get("fx_actual")
    return vals


def grade(bridge: dict[str, Any], ferr: dict[str, Any]) -> list[dict[str, Any]]:
    """Linhas da aba Editar valores, sempre a partir dos dados em uso."""
    o, fim, linhas = ferr["outlook"], ferr["mes_fechado"], []
    ordem = [x["rotulo"] for x in ferr["mes"]["custos"] if BR._norm(x["rotulo"]) != "total"]

    def add(tipo: str, cen: str, linha: str, vals: list[Any]) -> None:
        ed = [cen != "actual" or i <= fim for i in range(12)]
        linhas.append({"tipo": tipo, "cen": cen, "linha": linha, "valores": [v if ed[i] else None for i, v in enumerate(vals)], "editavel": ed})
    for cen in CENARIOS:
        for n in ordem:
            add(CUSTO, cen, n, o["linhas"][cen].get(n) or [0.0] * 12)
    for cen in CENARIOS:
        modal = (o.get("units_modal") or {}).get(cen) or {}
        for m in MODAIS:
            if m in modal:  # base lida antes de existir esta abertura nao oferece a linha (nunca parte de zero)
                add(UNITS, cen, m, modal[m])
        add(CNTR, cen, "Quantidade de contêineres", o["conteineres"][cen])
    add(FX, "actual", "Câmbio Actual", _fx_meses(bridge, ferr))
    return linhas


def escrever_aba(wb: Any, bridge: dict[str, Any], ferr: dict[str, Any], marca: dict[str, Any], titulo: str) -> None:
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    ws = wb.create_sheet(ABA, 0)
    ws["A1"], ws["A1"].font = titulo, Font(bold=True, size=14, color="0D4A26")
    ws["A2"] = "Altere as células amarelas, salve e envie este arquivo em Enviar arquivos. O sistema lê só esta aba e refaz totais, CPU, Bridge, gráficos e apresentação."
    ws["A2"].font = Font(color="44544A")
    cab = ["Tipo", "Cenário", "Linha"] + MESES
    linha_cab = 4
    for c, t in enumerate(cab, 1):
        cel = ws.cell(linha_cab, c, t)
        cel.fill, cel.font, cel.alignment = PatternFill("solid", fgColor="0D4A26"), Font(bold=True, color="FFFFFF"), Alignment(horizontal="left" if c < 4 else "right", vertical="center")
    amarelo, cinza, fina = PatternFill("solid", fgColor="FFF6C9"), PatternFill("solid", fgColor="E7EAE6"), Side(style="thin", color="D9DDD6")
    fmt = {CUSTO: "#,##0.00", UNITS: "#,##0", CNTR: "#,##0", FX: "0.0000"}
    r = linha_cab
    for g in grade(bridge, ferr):
        r += 1
        ws.cell(r, 1, g["tipo"]), ws.cell(r, 2, CENARIOS[g["cen"]]), ws.cell(r, 3, g["linha"])
        for i in range(12):
            cel = ws.cell(r, 4 + i, g["valores"][i])
            cel.number_format, cel.border = fmt[g["tipo"]], Border(left=fina, right=fina, top=fina, bottom=fina)
            cel.fill = amarelo if g["editavel"][i] else cinza
    for c, larg in ((1, 14), (2, 11), (3, 40)):
        ws.column_dimensions[get_column_letter(c)].width = larg
    for c in range(4, 16):
        ws.column_dimensions[get_column_letter(c)].width = 14
    ws.freeze_panes = ws.cell(linha_cab + 1, 4)
    ws.auto_filter.ref = f"A{linha_cab}:{get_column_letter(15)}{r}"
    m = wb.create_sheet(MARCA)
    m["A1"] = json.dumps({"tipo": "base_mbr", "versao": 1, **marca})
    m.sheet_state = "hidden"
    for aba in wb.worksheets:  # planilha sem protecao nem senha (pedido do usuario): quem confere o que vale e o envio
        aba.sheet_view.tabSelected = aba is ws  # duas abas selecionadas fariam o Excel digitar nas duas
    wb.active = 0


def ler_planilha(caminho: Any) -> dict[str, Any] | None:
    """Devolve a aba Editar valores da base baixada do MBR; None quando o arquivo e outro tipo de planilha."""
    import openpyxl
    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    try:
        if MARCA not in wb.sheetnames:
            return None
        try:
            marca = json.loads(next(wb[MARCA].iter_rows(values_only=True))[0])
        except (StopIteration, TypeError, ValueError):
            return None
        if marca.get("tipo") != "base_mbr":
            return None
        saida: dict[str, Any] = {"marca": marca, "linhas": {}, "erros": []}
        if ABA not in wb.sheetnames:
            saida["erros"].append(f"a aba {ABA} não está no arquivo")
            return saida
        cen_inv = {v: k for k, v in CENARIOS.items()}
        cab = False
        for n, row in enumerate(wb[ABA].iter_rows(values_only=True), 1):
            row = list(row) + [None] * 15
            if not cab:
                cab = row[0] == "Tipo" and row[1] == "Cenário"
                if cab and [str(x) for x in row[3:15]] != MESES:
                    saida["erros"].append("as colunas dos meses foram alteradas")
                    return saida
                continue
            if row[0] in (None, "") and row[2] in (None, ""):
                continue
            cen = cen_inv.get(str(row[1]))
            if cen is None:
                saida["erros"].append(f"linha {n}: cenário não reconhecido")
                continue
            vals: list[float | None] = []
            for i, v in enumerate(row[3:15]):
                if v in (None, ""):
                    vals.append(None)
                elif isinstance(v, bool) or not isinstance(v, (int, float)):
                    saida["erros"].append(f"célula {'DEFGHIJKLMNO'[i]}{n} ({row[2]}, {MESES[i]}): use apenas número")
                    vals.append(None)
                else:
                    vals.append(float(v))
            saida["linhas"][(str(row[0]), cen, str(row[2]))] = vals
        if not cab:
            saida["erros"].append(f"o cabeçalho da aba {ABA} foi alterado")
        return saida
    finally:
        wb.close()


def _meses(chave: str, fim: int) -> list[int]:
    if chave == "mes":
        return [fim]
    if chave == "ytd":
        return list(range(fim + 1))
    i, j = BR._TRI.get(chave, (0, 0))
    return list(range(i, j))


def recalcular_periodo(p: dict[str, Any]) -> None:
    """Refaz abertura, efeito do cambio e Bridge do periodo, com as formulas da planilha de bridge."""
    cam, real, cb = p.get("cambio") or {}, p["real"], p.get("cambio_budget")
    fxb, fxa = cam.get("fx_budget"), cam.get("fx_actual")
    t = real["total"]
    ub, ua = t["units_budget"] or 0, t["units_actual"] or 0

    def calc(tab: dict[str, Any]) -> dict[str, dict[str, Any]]:
        soma = {"budget": 0.0, "actual": 0.0, "variacao": 0.0, "impacto_volume": 0.0, "impacto_preco": 0.0, "impacto_total": 0.0}
        idx = {}
        for x in tab["linhas"]:
            cb_, ca = x["budget"] / ub if ub else 0.0, x["actual"] / ua if ua else 0.0
            x.update(units_budget=ub, units_actual=ua, cpu_budget=cb_, cpu_actual=ca, variacao=x["actual"] - x["budget"], impacto_volume=(ua - ub) * cb_, impacto_preco=(ca - cb_) * ua)
            x["impacto_total"] = x["impacto_volume"] + x["impacto_preco"]
            for k in soma:
                soma[k] += x[k]
            idx[BR._norm(x["rotulo"])] = x
        tab["total"].update(soma, units_budget=ub, units_actual=ua, cpu_budget=soma["budget"] / ub if ub else 0.0, cpu_actual=soma["actual"] / ua if ua else 0.0)
        return idx
    ir = calc(real)
    ic = ir
    if cb:
        for x in cb["linhas"]:
            g = BR._norm(x["rotulo"])
            x["budget"], x["actual"] = ir[g]["budget"], ir[g]["actual"] / fxa * fxb if g in _USD and fxa else ir[g]["actual"]
        cb["total"].update(units_budget=ub, units_actual=ua)
        ic = calc(cb)
    efeito = sum(ir[g]["impacto_preco"] - ic[g]["impacto_preco"] for g in _USD if g in ir)
    cam["efeito_fx"] = efeito
    preco = lambda tab, g: tab[g]["impacto_preco"] if g in tab else 0.0
    valores = {"budget": t["budget"], "bunker": preco(ic, "bunker"), "volume": t["impacto_volume"], "o. despesas": preco(ir, "outras despesas"), "maritimo": preco(ic, "maritimo"),
               "armazenagem": preco(ir, "armazenagem"), "rodoviario": preco(ir, "rodoviario"), "v. cambial": efeito, "frete aereo": preco(ic, "frete aereo"), "seguro": preco(ic, "seguro internacional")}
    soma = 0.0
    for x in p["ponte_custo"]:
        n = BR._norm(x["rotulo"])
        if n == "actual":
            x["valor"] = soma / 1e6
        elif n in valores:
            x["valor"] = valores[n] / 1e6
            soma += valores[n]
    cpu = {"armazenagem": preco(ir, "armazenagem"), "bunker": preco(ir, "bunker"), "o. despesas": preco(ir, "outras despesas"), "frete": preco(ir, "maritimo") + preco(ir, "frete aereo"), "rodoviario": preco(ir, "rodoviario")}
    for x in p.get("ponte_cpu") or []:
        n = BR._norm(x["rotulo"])
        x["valor"] = t["cpu_budget"] if n == "budget" else t["cpu_actual"] if n == "actual" else cpu.get(n, 0.0) / ua if ua else 0.0


def _recalc_bloco(bl: dict[str, Any], meses: list[int], dc: dict[str, Any], du: dict[str, Any], dn: dict[str, Any]) -> None:
    custos = {BR._norm(x["rotulo"]): x for x in bl["custos"]}
    units = {BR._norm(x["rotulo"]): x for x in bl["units"]}
    cpu = {BR._norm(x["rotulo"]): x for x in bl.get("cpu") or []}
    ind = {BR._norm(x["rotulo"]): x for x in bl.get("indicadores") or []}
    for cen in CENARIOS:
        mudou, tot_c, tot_u = set(), 0.0, 0.0
        for n, serie in dc[cen].items():
            d = sum(serie[m] for m in meses)
            x = custos.get(BR._norm(n))
            if d and x:
                x[cen] = (x.get(cen) or 0.0) + d
                tot_c += d
                mudou.add(BR._norm(n))
        for n, serie in du[cen].items():
            d = sum(serie[m] for m in meses)
            x = units.get(BR._norm(n))
            if d and x:
                x[cen] = (x.get(cen) or 0.0) + d
                tot_u += d
        d_n = sum(dn[cen][m] for m in meses)
        if tot_c and "total" in custos:
            custos["total"][cen] = (custos["total"].get(cen) or 0.0) + tot_c
        if tot_u and "total" in units:
            units["total"][cen] = (units["total"].get(cen) or 0.0) + tot_u
        ut = (units.get("total") or {}).get(cen) or 0.0
        if ut and (mudou or tot_u):
            for n, x in cpu.items():
                if (tot_u or n in mudou or n == "total") and n in custos:
                    x[cen] = (custos[n].get(cen) or 0.0) / ut
        q, por = ind.get("quantidade de conteineres"), ind.get("units por conteiner")
        if q and d_n:
            q[cen] = (q.get(cen) or 0.0) + d_n
        if por and q and (d_n or tot_u) and q.get(cen):
            por[cen] = ((units.get("frete maritimo") or {}).get(cen) or 0.0) / q[cen]


def _num_br(v: float | None, tipo: str) -> str:
    if v is None:
        return "vazio"
    d = {CUSTO: 2, FX: 4}.get(tipo, 0)
    txt = f"{v:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"R$ {txt}" if tipo == CUSTO else txt


def aplicar(bridge: dict[str, Any], ferr: dict[str, Any], lida: dict[str, Any]) -> dict[str, Any]:
    """Aplica na copia das bases o que mudou na planilha. Nao grava nada."""
    atual = {(g["tipo"], g["cen"], g["linha"]): g for g in grade(bridge, ferr)}
    erros, avisos, mud = list(lida["erros"]), [], []
    brancos = 0
    for chave, vals in lida["linhas"].items():
        g = atual.get(chave)
        if g is None:
            erros.append(f"linha não reconhecida: {chave[2]} ({CENARIOS.get(chave[1], chave[1])})")
            continue
        tipo = chave[0]
        for m, novo in enumerate(vals):
            velho = g["valores"][m]
            if novo is None:
                brancos += velho is not None
                continue
            if not g["editavel"][m]:
                avisos.append(f"{CENARIOS[g['cen']]} de {MESES[m]} ignorado: o mês ainda não fechou")
                continue
            if tipo in (UNITS, CNTR) and novo < 0:
                erros.append(f"{g['linha']} de {MESES[m]}: o valor não pode ser negativo")
            elif tipo == FX and novo <= 0:
                erros.append(f"câmbio de {MESES[m]}: o valor precisa ser maior que zero")
            elif velho is None or abs(novo - velho) >= (1e-6 if tipo == FX else .005):
                mud.append((tipo, g["cen"], g["linha"], m, velho, novo))
    if brancos:
        avisos.append(f"{brancos} célula(s) em branco mantiveram o valor atual")
    saida = {"erros": erros, "avisos": sorted(set(avisos)), "alteracoes": [f"{CENARIOS[c]} · {l} · {MESES[m]}: {_num_br(v, t)} → {_num_br(n, t)}" for t, c, l, m, v, n in mud], "bridge": None, "ferramenta": None}
    if erros or not mud:
        return saida
    b, f = copy.deepcopy(bridge), copy.deepcopy(ferr)
    o, fim = f["outlook"], f["mes_fechado"]
    dc = {c: {} for c in CENARIOS}
    du = {c: {} for c in CENARIOS}
    dn = {c: [0.0] * 12 for c in CENARIOS}
    fx_mud: dict[int, float] = {}
    for tipo, cen, linha, m, velho, novo in mud:
        d = novo - (velho or 0.0)
        if tipo == CUSTO:
            dc[cen].setdefault(linha, [0.0] * 12)[m] += d
            o["linhas"][cen].setdefault(linha, [0.0] * 12)[m] = novo
            o["custo"][cen][m] += d
        elif tipo == UNITS:
            du[cen].setdefault(linha, [0.0] * 12)[m] += d
            o.setdefault("units_modal", {}).setdefault(cen, {}).setdefault(linha, [0.0] * 12)[m] = novo
            o["units"][cen][m] += d
        elif tipo == CNTR:
            dn[cen][m] += d
            o["conteineres"][cen][m] = novo
        else:
            fx_mud[m] = novo
    for chave, p in b["periodos"].items():
        for m, v in fx_mud.items():
            if chave == "ytd" or MESES[m].lower() in (p.get("cambio_mensal") or {}):
                p.setdefault("cambio_mensal", {})[MESES[m].lower()] = v
    fx_todos = _fx_meses(b, f)
    for m, v in fx_mud.items():
        fx_todos[m] = v
    for chave, p in b["periodos"].items():
        ms = _meses(chave, fim)
        muda_fx = any(m in fx_mud for m in ms)
        mexeu = muda_fx
        for cen, campo in (("budget", "budget"), ("actual", "actual")):
            por_grupo: dict[str, float] = {}
            for n, serie in dc[cen].items():
                d = sum(serie[m] for m in ms)
                if d:
                    por_grupo[_grupo(n)] = por_grupo.get(_grupo(n), 0.0) + d
            for x in p["real"]["linhas"]:
                d = por_grupo.get(BR._norm(x["rotulo"]), 0.0)
                if d:
                    x[campo] += d
                    mexeu = True
            d_u = sum(serie[m] for serie in du[cen].values() for m in ms)
            if d_u:
                p["real"]["total"][f"units_{campo}"] = (p["real"]["total"].get(f"units_{campo}") or 0.0) + d_u
                mexeu = True
        if muda_fx:
            vals = [fx_todos[m] for m in ms if fx_todos[m]]
            p.setdefault("cambio", {})["fx_actual"] = sum(vals) / len(vals)
        if mexeu:
            recalcular_periodo(p)
    if b.get("detalhe_mes"):
        _recalc_bloco(b["detalhe_mes"], [fim], dc, du, dn)
    _recalc_bloco(f["mes"], [fim], dc, du, dn)
    _recalc_bloco(f["ytd"], list(range(fim + 1)), dc, du, dn)
    d_a, d_f = [sum(s[m] for s in dc["actual"].values()) for m in range(12)], [sum(s[m] for s in dc["forecast"].values()) for m in range(12)]
    if f.get("spend_total") is not None:
        f["spend_total"] += d_a[fim]
    avf = f.get("avf_escrito") or {}  # o total escrito na Ferramenta acompanha a alteracao: a diferenca que ja existia continua aparecendo
    if avf.get("mes") is not None:
        avf["mes"] += d_a[fim] - d_f[fim]
    if avf.get("ytd") is not None:
        avf["ytd"] += sum(d_a[: fim + 1]) - sum(d_f[: fim + 1])
    b["conferencias"], f["conferencias"] = BR.conferir(b), BR.conferir(f)
    saida.update(bridge=b, ferramenta=f)
    return saida


def efeitos(antes: dict[str, Any], depois: dict[str, Any]) -> list[str]:
    """Principais numeros que mudam na pagina, para a previa do envio."""
    saida = []
    reais = lambda v: _num_br(round(v), CUSTO)[:-3]
    per = {p["chave"]: p for p in antes["periodos"]}
    for p in depois["periodos"]:
        a = per.get(p["chave"])
        for campo, nome in (("budget", "Budget"), ("forecast", "Forecast"), ("actual", "Actual")):
            v0, v1 = (a or {}).get("resumo", {}).get(campo), p["resumo"].get(campo)
            if v0 is not None and v1 is not None and abs(v1 - v0) >= .5:
                saida.append(f"{nome} de {p['rotulo']}: {reais(v0)} → {reais(v1)}")
    f0, f1 = antes.get("proximo"), depois.get("proximo")
    if f0 and f1 and abs(f1["forecast"] - f0["forecast"]) >= .5:
        saida.append(f"Forecast de {f1['rotulo'].lower()}: {reais(f0['forecast'])} → {reais(f1['forecast'])}")
    return saida
