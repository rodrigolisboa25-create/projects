"""Resultados > Apresentacao Final: Orcamento x Forecast do ano anterior, por processo e por cenario de frete maritimo.

Forecast do ano anterior = 10+2 da Ferramenta de Controle mais recente (Actual dos meses fechados + Forecast dos demais).
Os cenarios usam so as duas tarifas maritimas do proprio orcamento e sao recalculados pelo motor (budget_engine): nenhum
numero e digitado aqui. Bridge com o metodo das planilhas: volume = (U1 - U0) x CPU0; preco = C1 - C0 x U1 / U0; nos grupos em
dolar o preco fica a cambio constante e a diferenca vai para a variacao cambial.
"""
from __future__ import annotations

import copy
from typing import Any

import budget_engine as E

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
LINHAS = {"frete_maritimo": ["Frete Marítimo"], "frete_aereo": ["Frete Aéreo"], "bunker": ["Bunker", "Biocombustível"], "capatazias": ["Capatazias"],
          "afrmm": ["Marinha Mercante", "Taxa Siscomex"], "armazenagem": ["Armazenagem Santos"], "despachante": ["Desembaraço DI", "Carta Protesto"],
          "sistemas": ["Licença de Importação/Classificação NCM", "Serviço de Desenvolvimento", "DUIMP", "Flowls", "TTMS"], "in_house": ["In-House"],
          "demurrage": ["Demurrage"], "multa": ["Multa"], "seguro": ["Seguro Internacional"],
          "rodoviario": ["Santos - Extrema", "Santos - Louveira", "Escolta Armada", "Trava Ciltronics", "Estadia de Veículo", "Depot (Devolução)", "Horas Paradas", "Ajudante"]}
NOMES = {"rodoviario": "Frete rodoviário", "seguro": "Seguro internacional", "bunker": "Bunker + biocombustível", "afrmm": "Marinha Mercante + Siscomex", "sistemas": "Sistemas e desenvolvimento"}
GRUPOS = {"BUNKER": ["bunker"], "O. DESPESAS": ["capatazias", "afrmm", "despachante", "sistemas", "in_house", "demurrage", "multa"], "MARITIMO": ["frete_maritimo"],
          "ARMAZENAGEM": ["armazenagem"], "RODOVIÁRIO": ["rodoviario"], "FRETE AÉREO": ["frete_aereo"], "SEGURO": ["seguro"]}
ORDEM = ["BUNKER", "VOLUME", "O. DESPESAS", "MARITIMO", "ARMAZENAGEM", "RODOVIÁRIO", "V. CAMBIAL", "FRETE AÉREO", "SEGURO"]  # mesma ordem do MBR
GRUPOS_USD = {"BUNKER", "MARITIMO", "SEGURO"}  # grupos com tarifa em dolar no orcamento
ROTULO = {"BUNKER": "Bunker", "MARITIMO": "Marítimo", "ARMAZENAGEM": "Armazenagem", "RODOVIÁRIO": "Rodoviário", "FRETE AÉREO": "Frete aéreo"}


class BaseIncompleta(ValueError):
    """Faltam dados para montar a apresentacao."""


def _br(v: float, d: int = 2) -> str:
    return f"{v:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def _sn(v: float, d: int = 2) -> str:
    return ("+" if v > 0 else "-" if v < 0 else "") + _br(abs(v), d)


def _dez_mais(ferr: dict[str, Any], actual: list[float], forecast: list[float]) -> list[float]:
    fim = ferr["mes_fechado"]
    return [(actual[m] if m <= fim else forecast[m]) or 0.0 for m in range(12)]


def _serie(ferr: dict[str, Any], nomes: list[str]) -> list[float]:
    o, zero = ferr["outlook"]["linhas"], [0.0] * 12
    total = [0.0] * 12
    for n in nomes:
        s = _dez_mais(ferr, o["actual"].get(n) or zero, o["forecast"].get(n) or zero)
        total = [a + b for a, b in zip(total, s)]
    return total


def forecast_ano_anterior(ferr: dict[str, Any]) -> dict[str, Any]:
    """Forecast do ano anterior (Actual dos meses fechados + Forecast dos demais): fonte unica do Painel, do Comparativo e da Apresentacao Final."""
    o, fim = ferr["outlook"], ferr["mes_fechado"]
    return {"rubricas": {k: _serie(ferr, ns) for k, ns in LINHAS.items()}, "rod_santos": _serie(ferr, ["Santos - Extrema"]),
            "units": _dez_mais(ferr, o["units"]["actual"], o["units"]["forecast"]), "conteineres": _dez_mais(ferr, o["conteineres"]["actual"], o["conteineres"]["forecast"]),
            "base": f"{fim + 1}+{11 - fim}", "rotulo": f"{fim + 1}+{11 - fim} de {E.MESES_LONGOS[fim].lower()}", "competencia": ferr.get("competencia")}


def aplicar_forecast(params: dict[str, Any], ferr: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Copia das premissas com o Forecast do ano anterior trocado pelo da Ferramenta. A versao guardada e o Budget nao mudam."""
    try:
        ano = int(params.get("ano"))
    except (TypeError, ValueError):
        return params, None
    if not ferr or not (ferr.get("outlook") or {}).get("linhas") or str(ferr.get("competencia") or "")[:4] != str(ano - 1):
        return params, None
    fc = forecast_ano_anterior(ferr)
    if not sum(fc["units"]) or not sum(sum(v) for v in fc["rubricas"].values()):
        return params, None
    p = copy.deepcopy(params)
    ant = p["anterior"] if isinstance(p.get("anterior"), dict) else {}
    p["anterior"] = ant
    for k, serie in fc["rubricas"].items():
        ant.setdefault(k, {})["forecast"] = sum(serie)
    vol = p["volume_anterior"] if isinstance(p.get("volume_anterior"), dict) else {}
    vol["f"] = sum(fc["units"]); vol.pop("forecast", None); p["volume_anterior"] = vol
    am = p["anterior_mensal"] if isinstance(p.get("anterior_mensal"), dict) else {}
    am["forecast"] = {**fc["rubricas"], "rod_santos": fc["rod_santos"]}
    am["units_forecast"], am["cntr_forecast"] = fc["units"], fc["conteineres"]
    p["anterior_mensal"] = am
    return p, {"base": fc["base"], "rotulo": fc["rotulo"], "competencia": fc["competencia"]}


def _fx_ano_anterior(bridge: dict[str, Any] | None) -> float | None:
    per = ((bridge or {}).get("periodos") or {}).get("ytd") or {}
    fx = (per.get("cambio") or {}).get("fx_actual")
    return float(fx) if fx else None


def _bridge(c0: dict[str, float], c1: dict[str, float], u0: float, u1: float, fx0: float | None, fx1: float) -> list[dict[str, Any]]:
    tot0 = sum(c0.values())
    valores = {"VOLUME": (u1 - u0) * tot0 / u0, "V. CAMBIAL": 0.0}
    for g, ks in GRUPOS.items():
        a, b = sum(c0[k] for k in ks), sum(c1[k] for k in ks)
        constante = b / fx1 * fx0 if fx0 and g in GRUPOS_USD else b
        valores[g] = constante - a * u1 / u0
        valores["V. CAMBIAL"] += b - constante
    return [{"t": t, "v": valores[t]} for t in ORDEM]


def _cenarios(params: dict[str, Any], forecast: float) -> list[dict[str, Any]]:
    t = params["tarifas"]
    t1, t2, mes = t["frete_maritimo_1"]["base"], t["frete_maritimo_2"]["base"], int(t["frete_maritimo_2"]["mes"])
    ate, desde = MESES[max(mes - 2, 0)].lower(), MESES[min(mes - 1, 11)].lower()
    planos = [("Cenário 1", f"USD {_br(t1, 0)} o ano todo", {"frete_maritimo_2": t1}, False),
              ("Cenário 2", f"USD {_br(t1, 0)} até {ate} e USD {_br(t2, 0)} desde {desde}", {}, True),
              ("Cenário 3", f"USD {_br(t2, 0)} o ano todo", {"frete_maritimo_1": t2}, False)]
    saida = []
    for nome, tarifa, muda, aprovado in planos:
        p = copy.deepcopy(params)
        for k, v in muda.items():
            p["tarifas"][k]["base"] = v
        r = E.calcular(p)
        rub = {c["k"]: c["atual"] for c in r["comparativo"]}
        tot = r["kpi"]["total"]
        a, b = p["tarifas"]["frete_maritimo_1"]["base"], p["tarifas"]["frete_maritimo_2"]["base"]
        saida.append({"nome": nome, "tarifa": tarifa, "aprovado": aprovado, "tarifas": [b if m + 1 >= mes else a for m in range(12)], "total": tot, "var": tot - forecast, "var_pct": tot / forecast - 1 if forecast else 0,
                      "cpu": r["kpi"]["custo_unit"], "maritimo": rub["frete_maritimo"], "afrmm": rub["afrmm"], "demais": tot - rub["frete_maritimo"] - rub["afrmm"], "mensal": r["mensal"]["total"]})
    return saida


def montar(versao: dict[str, Any], ferr: dict[str, Any], bridge: dict[str, Any] | None) -> dict[str, Any]:
    params = versao["params"]
    r = E.calcular(params)
    comp = {c["k"]: c for c in r["comparativo"]}
    o, fim = ferr["outlook"], ferr["mes_fechado"]
    if not o.get("linhas"):
        raise BaseIncompleta("a Ferramenta de Controle não traz o Outlook por despesa")
    fc = forecast_ano_anterior(ferr)
    series = fc["rubricas"]
    c0 = {k: sum(v) for k, v in series.items()}
    c1 = {k: comp[k]["atual"] for k in LINHAS}
    mensal0 = [sum(series[k][m] for k in LINHAS) for m in range(12)]
    custo0 = sum(_dez_mais(ferr, o["custo"]["actual"], o["custo"]["forecast"]))
    tot0, tot1 = sum(c0.values()), r["kpi"]["total"]
    u0, u1 = sum(fc["units"]), r["kpi"]["units"]
    if not u0 or not tot0:
        raise BaseIncompleta("a Ferramenta de Controle está sem custo ou sem units")
    n0, n1 = sum(fc["conteineres"]), r["kpi"]["conteineres"]
    e, t = params["escalares"], params["tarifas"]
    fx0, fx1 = _fx_ano_anterior(bridge), e["cambio_usd_brl"]
    barras = _bridge(c0, c1, u0, u1, fx0, fx1)
    val = {x["t"]: x["v"] for x in barras}
    share_arm = e.get("pct_armazenagem_no_total") or 0.0  # armazenagem fixada em % do orcamento total (19/11/2026)
    pendente = not 0 < share_arm < 1 and t["arm_cif_maior_acima10"]["base"] == 0 and t["arm_cif_menor_acima10"]["base"] == 0
    processos = [{"k": k, "l": NOMES.get(k, comp[k]["l"]), "forecast": c0[k], "orcamento": c1[k], "var": c1[k] - c0[k], "pct": c1[k] / c0[k] - 1 if c0[k] else None,
                  "cpu_f": c0[k] / u0, "cpu_o": c1[k] / u1, "explica": comp[k]["explica"], "pendente": k == "armazenagem" and pendente}
                 for k in LINHAS if abs(c0[k]) >= .5 or abs(c1[k]) >= .5]
    processos.sort(key=lambda x: -x["orcamento"])
    modal = o.get("units_modal") or {}
    aereo1 = sum(r["mensal"]["units_aereo"])
    aereo0 = sum(_dez_mais(ferr, (modal.get("actual") or {}).get("Frete Aéreo") or [0.0] * 12, (modal.get("forecast") or {}).get("Frete Aéreo") or [0.0] * 12)) if modal else None
    cen = _cenarios(params, tot0)
    t1, t2 = t["frete_maritimo_1"]["base"], t["frete_maritimo_2"]["base"]
    por_100 = (cen[2]["total"] - cen[0]["total"]) / (t2 - t1) * 100 if t2 != t1 else 0.0
    ate, desde = MESES[max(int(t["frete_maritimo_2"]["mes"]) - 2, 0)].lower(), MESES[min(int(t["frete_maritimo_2"]["mes"]) - 1, 11)].lower()
    extra = {"MARITIMO": f"tarifa de USD {_br(t1, 0)} até {ate} e USD {_br(t2, 0)} a partir de {desde}.",
             "BUNKER": f"USD {_br(t['bunker']['base'], 0)} por contêiner e {_br(e['pct_conteineres_biocombustivel'] * 100, 0)}% dos contêineres com biocombustível.",
             "ARMAZENAGEM": "faixa acima de 10 dias ainda sem tarifa no orçamento." if pendente else
             f"{_br(share_arm * 100, 1)}% do orçamento total." if 0 < share_arm < 1 else "tarifas por faixa de permanência.",
             "RODOVIÁRIO": "reajuste das tarifas pelo IPCA e ajudantes.", "FRETE AÉREO": f"modal aéreo com {_br(e['pct_modal_aereo'] * 100)}% das units."}
    def cpu_txt(g: str) -> str:
        a, b = sum(c0[k] for k in GRUPOS[g]) / u0, sum(c1[k] for k in GRUPOS[g]) / u1
        return f"CPU de R$ {_br(a)} para R$ {_br(b)}; {extra[g]}"
    top = ["MARITIMO"] + sorted((g for g in extra if g != "MARITIMO"), key=lambda g: -abs(val[g]))[:2]  # o frete maritimo e o tema da apresentacao
    cpu0, cpu1 = tot0 / u0, tot1 / u1
    comentarios = [{"k": f"{_sn(val[g] / 1e6)} - {ROTULO[g]}:", "t": cpu_txt(g)} for g in top]
    comentarios.append({"k": f"{_sn(val['VOLUME'] / 1e6)} - Volume:", "t": f"{_br(abs(u1 - u0) / 1e6)} MM de units {'a mais' if u1 >= u0 else 'a menos'} ({_sn((u1 / u0 - 1) * 100, 1)}%)."})
    comentarios.append({"k": f"{_sn(cpu1 - cpu0)} - CPU:", "t": f"de R$ {_br(cpu0)} para R$ {_br(cpu1)} ({_sn((cpu1 / cpu0 - 1) * 100, 1)}%)."})
    if fx0:
        comentarios.append({"k": "FX -", "t": f"Forecast 26 (média do Actual) {_br(fx0)} vs Orçamento 27 {_br(fx1)}."})
    atencao = []
    arm = next((x for x in processos if x["k"] == "armazenagem"), None)
    if 0 < share_arm < 1 and arm:
        atencao.append({"n": f"R$ {_br(arm['orcamento'] / 1e6)} MM", "t": "Armazenagem em % do orçamento",
                        "d": f"Fixada em {_br(share_arm * 100, 1)}% do orçamento total. O Forecast 26 traz R$ {_br(arm['forecast'] / 1e6)} MM."})
    elif pendente and arm:
        atencao.append({"n": f"R$ {_br(arm['orcamento'] / 1e6)} MM", "t": "Armazenagem acima de 10 dias sem tarifa",
                        "d": f"{_br(e['pct_processos_armazenagem_acima_10_dias'] * 100, 0)}% dos processos ficam nessa faixa. O Forecast 26 traz R$ {_br(arm['forecast'] / 1e6)} MM: o total de 2027 tende a subir quando a tarifa for definida."})
    if t1:
        atencao.append({"n": f"{_sn((t2 / t1 - 1) * 100, 0)}%", "t": f"Tarifa marítima muda em {desde}", "d": f"De USD {_br(t1, 0)} para USD {_br(t2, 0)} por contêiner. Entre os cenários, o total varia R$ {_br(abs(cen[2]['total'] - cen[0]['total']) / 1e6)} MM."})
    atencao.append({"n": f"{_sn((u1 / u0 - 1) * 100, 1)}%", "t": "Volume de units", "d": f"{_br(u1 / 1e6, 1)} MM de units contra {_br(u0 / 1e6, 1)} MM no Forecast 26, com impacto de {'+' if val['VOLUME'] >= 0 else '-'}R$ {_br(abs(val['VOLUME']) / 1e6)} MM no custo."})
    if fx0:
        efeito = "reduz" if val["V. CAMBIAL"] < 0 else "aumenta"
        atencao.append({"n": f"R$ {_br(fx1)}", "t": "Câmbio do orçamento", "d": f"{'Abaixo' if fx1 < fx0 else 'Acima'} da média de R$ {_br(fx0)} do Actual de jan a {MESES[fim].lower()}/26: a diferença {efeito} o custo em R$ {_br(abs(val['V. CAMBIAL']) / 1e6)} MM."})
    chaves = ["frete_maritimo", "bunker", "rodoviario", "frete_aereo"]
    por_k = {x["k"]: x for x in processos}
    fretes = [por_k[k] for k in chaves if k in por_k]
    conferencia = []
    if abs(tot0 - custo0) > 5:
        conferencia.append(f"as despesas somam R$ {_br(tot0)} e o total da Ferramenta é R$ {_br(custo0)}")
    if abs(sum(x["v"] for x in barras) - (tot1 - tot0)) > 1:
        conferencia.append("a Bridge não fecha")
    return {"ano": params["ano"], "ano_anterior": params["ano"] - 1, "base": f"{fim + 1}+{11 - fim}", "periodo": f"Actual de jan a {MESES[fim].lower()} + Forecast dos demais meses",
            "versao": {"nome": versao.get("nome"), "ciclo": versao.get("ciclo")},
            "resumo": {"forecast": tot0, "orcamento": tot1, "var": tot1 - tot0, "var_pct": tot1 / tot0 - 1, "units_f": u0, "units_o": u1, "var_units": u1 - u0, "var_units_pct": u1 / u0 - 1,
                       "cpu_f": cpu0, "cpu_o": cpu1, "cntr_f": n0, "cntr_o": n1, "fx_f": fx0, "fx_o": fx1},
            "units": {"maritimo_f": u0 - aereo0 if aereo0 is not None else None, "aereo_f": aereo0, "maritimo_o": u1 - aereo1, "aereo_o": aereo1},
            "bridge": barras, "comentarios": comentarios, "processos": processos, "fretes": fretes, "total_fretes": {"f": sum(x["forecast"] for x in fretes), "o": sum(x["orcamento"] for x in fretes)},
            "cenarios": cen, "por_100": por_100, "amplitude": cen[2]["total"] - cen[0]["total"], "mes_tarifa": int(t["frete_maritimo_2"]["mes"]), "tarifa_1": t1, "tarifa_2": t2,
            "mensal": {"rotulos": MESES, "forecast": mensal0}, "afrmm_f": c0["afrmm"], "maritimo_f": c0["frete_maritimo"], "demais_f": tot0 - c0["afrmm"] - c0["frete_maritimo"],
            "armazenagem_pendente": pendente, "atencao": atencao, "conferencia": conferencia}
