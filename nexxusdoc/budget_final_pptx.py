"""Resultados > Apresentacao Final em PowerPoint: os mesmos slides da versao em HTML, com formas e textos editaveis.

Todo numero vem de budget_final.montar; nada e calculado de novo aqui alem de somas para os textos.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from budget_resultados_saida import PX, _nf, _sg, _Tela

INK, SOFT, FAINT, LINE, LIME, VERDE, UP, DW = "EDFFD4", "BCD2B4", "8BA88A", "2E6B49", "B5FF20", "005E28", "FF8F87", "6FE39A"
G_UP, G_DW, G_END, G_BASE, G_LIME, G_CINZA = ("FF7A6E", "C9302C"), ("5BE08A", "12A150"), ("6FB1FF", "2459BC"), ("1F6B40", "3C9A62"), ("B5FF20", "7DBB12"), ("D5E4C8", "7E9A80")
ROT = {"BUNKER": "Bunker", "VOLUME": "Volume", "O. DESPESAS": "Outras despesas", "MARITIMO": "Marítimo", "ARMAZENAGEM": "Armazenagem", "RODOVIÁRIO": "Rodoviário",
       "V. CAMBIAL": "Câmbio", "FRETE AÉREO": "Frete aéreo", "SEGURO": "Seguro"}
TOTAL = 9


def mm(v: float, d: int = 2) -> str:
    return _nf(abs(v) / 1e6, d)


def din(v: float) -> str:
    a = abs(v)
    return f"R$ {_nf(a / 1e6, 2)} {'milhão' if a < 1995000 else 'milhões'}" if a >= 999500 else f"R$ {_nf(a / 1e3)} mil"


def abr(v: float) -> str:
    a = abs(v)
    return f"R$ {_nf(a / 1e6, 2)} MM" if a >= 999500 else f"R$ {_nf(a / 1e3)} mil"


def pc(v: float | None) -> str:
    return "-" if v is None else f"{_sg(v)}{_nf(abs(v) * 100, 1)}%"


def cor(v: float | None) -> str:
    return UP if (v or 0) > 0 else DW if (v or 0) < 0 else INK


class Tela(_Tela):
    def __init__(self, prs: Any):
        super().__init__(prs)
        fill = self.s.background.fill
        fill.gradient()
        fill.gradient_angle = 300
        fill.gradient_stops[0].color.rgb = self.rgb("03492A")
        fill.gradient_stops[1].color.rgb = self.rgb("02351D")

    def forte(self, x: float, y: float, w: float, h: float, txt: str, tam: float, c: str, entre: float | None = None) -> None:
        for p in self.texto(x, y, w, h, txt, tam, c).text_frame.paragraphs:
            if entre:
                p.line_spacing = entre
            for r in p.runs:
                r.font.name = "Arial Black"

    def foto(self, arq: Path, x: float, y: float, w: float, h: float) -> None:
        from pptx.util import Emu
        self.s.shapes.add_picture(str(arq), Emu(int(x * PX)), Emu(int(y * PX)), Emu(int(w * PX)), Emu(int(h * PX)))

    def barra(self, x: float, y: float, w: float, h: float, grad: tuple[str, str]) -> Any:
        sh = self.caixa(x, y, max(w, 3), h, grad=grad, raio=4)
        sh.fill.gradient_angle = 0
        return sh


def transicao(t: Tela) -> None:
    from lxml import etree
    t.s._element.append(etree.fromstring('<p:transition xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" spd="med"><p:fade/></p:transition>'))


def capa(prs: Any, pasta: Path, linhas: list[str], sub: str = "") -> None:
    t = Tela(prs)
    t.foto(pasta / "capa_fundo.png", 0, 0, 1920, 1080)
    y0 = 361 if len(linhas) > 1 else 426
    t.forte(166, y0, 1600, 270, "\n".join(linhas), 128, LIME, .84)
    if sub:
        t.forte(169, 654, 1500, 60, sub, 44, INK)
    t.foto(pasta / "logo_capa.png", 1692, 980, 166, 36)
    transicao(t)


def slide(prs: Any, pasta: Path, n: int, sub2: str, lead: str, sub: str, D: dict[str, Any]) -> Tela:
    t = Tela(prs)
    t.caixa(36, 29, 1848, 155, VERDE, raio=13)
    t.forte(86, 42, 1290, 70, "OPS. FISIA: LOG. INTERNACIONAL", 58, LIME)
    t.forte(86, 112, 1500, 58, sub2, 46, INK)
    t.foto(pasta / "logo_marcas.png", 1391, 43, 474, 60)
    t.texto(55, 200, 1810, 50, lead, 41, INK, True)
    if sub:
        t.texto(55, 251, 1810, 32, sub, 24, SOFT)
    t.texto(55, 1046, 1200, 22, f"Logística Internacional · Orçamento {D['ano']} x Forecast {D['ano_anterior']}", 17, FAINT)
    t.texto(1665, 1046, 200, 22, f"{n} / {TOTAL}", 17, FAINT, alinha="r")
    transicao(t)
    return t


def metrica(t: Tela, y: float, nome: str, valor: str, resto: str = "", on: bool = False, c: str | None = None, ultima: bool = False) -> float:
    x = 1510
    t.texto(x, y, 355, 22, nome.upper(), 16.5, LIME if on else FAINT, True)
    t.texto(x, y + 26, 355, 52, valor, 42 if len(valor) <= 13 else 33, c or (LIME if on else INK), True)
    if resto:
        t.texto(x, y + 80, 355, 26, resto, 19, SOFT)
    fim = y + 118
    if not ultima:
        t.linha(x, fim, 1865, fim, LINE)
    return fim + 18


def trilho(t: Tela) -> None:
    t.linha(1475, 300, 1475, 1030, LINE)


def s_bridge(prs: Any, pasta: Path, D: dict[str, Any]) -> None:
    r, xs = D["resumo"], [(ROT.get(x["t"], x["t"]), x["v"]) for x in D["bridge"]]
    ma, me = max(xs, key=lambda a: a[1]), min(xs, key=lambda a: a[1])
    t = slide(prs, pasta, 2, "ORÇAMENTO 27 X FORECAST 26: BRIDGE", f"O orçamento de {D['ano']} fica {din(r['var'])} {'acima' if r['var'] > 0 else 'abaixo'} do Forecast de {D['ano_anterior']}",
              f"Maior aumento em {ma[0].lower()} (+{din(ma[1])}) e maior redução em {me[0].lower()} (-{din(me[1])}). Valores em R$ milhões.", D)
    it: list[dict[str, Any]] = [{"t": f"Forecast\n{D['ano_anterior']}", "v": r["forecast"], "end": True}] + [{"t": ROT.get(x["t"], x["t"]).replace(" ", "\n"), "k": x["t"], "v": x["v"]} for x in D["bridge"]] + [{"t": f"Orçamento\n{D['ano']}", "v": r["orcamento"], "end": True}]
    acc, topo = r["forecast"], max(r["forecast"], r["orcamento"])
    for x in it:
        if not x.get("end"):
            x["a"], acc = acc, acc + x["v"]
            x["b"] = acc
            topo = max(topo, x["a"], x["b"])
    ox, oy, W, H, T, B = 55, 292, 1390, 566, 110, 68
    y = lambda v: oy + H - B - v / (topo * 1.02) * (H - B - T)  # noqa: E731
    pw, bw = W / len(it), W / len(it) * .62
    notas = {"VOLUME": f"{_sg(r['var_units'])}{mm(r['var_units'])} MM units\n{pc(r['var_units_pct'])}"}
    if D.get("armazenagem_pendente"):
        notas["ARMAZENAGEM"] = "Acima de 10\ndias sem tarifa"
    t.linha(ox, y(0), ox + W, y(0), "5F8A70", 1.2)
    for i, x in enumerate(it):
        cx, x0 = ox + pw * i + pw / 2, ox + pw * i + (pw - bw) / 2
        if x.get("end"):
            t0, h, g, txt, c = y(x["v"]), y(0) - y(x["v"]), G_END, mm(x["v"]), INK
        else:
            t0, h = y(max(x["a"], x["b"])), max(5, abs(y(x["a"]) - y(x["b"])))
            g, c, txt = (G_UP, UP, f"+{mm(x['v'])}") if x["v"] > 0 else (G_DW, DW, f"-{mm(x['v'])}")
        t.caixa(x0, t0, bw, h, grad=g, raio=4)
        t.texto(cx - pw / 2, t0 - 38, pw, 32, txt, 29 if x.get("end") else 25, c, True, "c")
        t.texto(cx - pw / 2, y(0) + 10, pw, 50, x["t"], 18, SOFT, True, "c")
        nota = notas.get(x.get("k"))
        if nota:
            t.caixa(cx - pw * .49, t0 + h + 12, pw * .98, 58, "024526", borda=INK, raio=4)
            t.texto(cx - pw * .49, t0 + h + 12, pw * .98, 58, nota, 16, INK, alinha="c", meio=True)
        if i < len(it) - 1:
            nv = x["v"] if x.get("end") else x["b"]
            t.linha(x0 + bw, y(nv), x0 + pw, y(nv), "6E9A80", 1, True)
    dt, xa, xb, yb, gap = r["var"], ox + pw / 2, ox + pw * (len(it) - 1) + pw / 2, oy + 24, 98
    xm = (xa + xb) / 2
    for a, b, c, d in ((xa, y(r["forecast"]) - 44, xa, yb), (xa, yb, xm - gap, yb), (xm + gap, yb, xb, yb), (xb, yb, xb, y(r["orcamento"]) - 54)):
        t.linha(a, b, c, d, INK, 2)
    from pptx.enum.shapes import MSO_SHAPE
    t.caixa(xb - 8, y(r["orcamento"]) - 55, 16, 13, INK, forma=MSO_SHAPE.ISOSCELES_TRIANGLE).rotation = 180
    t.texto(xm - gap, yb - 20, gap * 2, 40, f"{_sg(dt)}{mm(dt)}MM", 34, cor(dt), True, "c", True)
    t.linha(55, 866, 1445, 866, LINE)
    for i, c in enumerate(D["comentarios"][:3]):
        yy = 880 + i * 49
        t.caixa(55, yy + 9, 10, 10, LIME, forma=MSO_SHAPE.OVAL)
        t.texto(78, yy, 1367, 44, f"{c['k']} {c['t']}", 20, "DCEBD0")
    trilho(t)
    p = metrica(t, 430, f"Forecast {D['ano_anterior']} · {D['base']}", abr(r["forecast"]), f"{_nf(r['units_f'])} units · CPU R$ {_nf(r['cpu_f'], 2)}")
    p = metrica(t, p, f"Orçamento {D['ano']}", abr(r["orcamento"]), f"{_nf(r['units_o'])} units · CPU R$ {_nf(r['cpu_o'], 2)}", True)
    for i, (n, v, c) in enumerate((("Volume", pc(r["var_units_pct"]), INK), ("CPU", pc(r["cpu_o"] / r["cpu_f"] - 1), cor(r["cpu_o"] - r["cpu_f"])), ("Câmbio", _nf(r["fx_o"], 2), INK))):
        t.texto(1510 + i * 120, p, 116, 20, n.upper(), 15, FAINT, True)
        t.texto(1510 + i * 120, p + 24, 116, 34, v, 26, c, True)


def s_processos(prs: Any, pasta: Path, D: dict[str, Any]) -> None:
    r, ps = D["resumo"], D["processos"]
    ups, dws = sorted(ps, key=lambda p: -p["var"])[:2], sorted(ps, key=lambda p: p["var"])[:2]
    nome = lambda p: p["l"].split(" + ")[0].lower()  # noqa: E731
    lead = f"{nome(ups[0]).capitalize()} e {nome(ups[1])} puxam o aumento; {nome(dws[0])} e {nome(dws[1])} reduzem"
    t = slide(prs, pasta, 3, "ORÇAMENTO 27 X FORECAST 26: PROCESSOS", lead, f"Forecast {D['ano_anterior']} ({D['base']}) e Orçamento {D['ano']} em R$ milhões, com a variação de cada processo.", D)
    a1, a2 = str(D["ano_anterior"])[2:], str(D["ano"])[2:]
    for x, w, txt, al in ((55, 315, "PROCESSO", "l"), (370, 110, f"FCST {a1}", "r"), (490, 110, f"ORÇ {a2}", "r"), (615, 580, "VARIAÇÃO", "c"), (1205, 135, "R$ MIL", "r"), (1345, 100, "%", "r")):
        t.texto(x, 306, w, 24, txt, 15.5, FAINT, True, al)
    t.linha(55, 336, 1445, 336, LINE)
    maximo, mid = max(abs(p["var"]) for p in ps) or 1, 905
    rh = 45
    t.linha(mid, 344, mid, 344 + rh * len(ps), LINE)
    for i, p in enumerate(ps):
        y, v, w = 344 + i * rh, p["var"], abs(p["var"]) / maximo * 288
        t.texto(55, y, 315, rh, p["l"] + (" *" if p.get("pendente") else ""), 22, INK, meio=True)
        t.texto(370, y, 110, rh, mm(p["forecast"]), 22, SOFT, alinha="r", meio=True)
        t.texto(490, y, 110, rh, mm(p["orcamento"]), 22, SOFT, alinha="r", meio=True)
        t.barra(mid if v > 0 else mid - w, y + 9, w, 27, G_UP if v > 0 else G_DW)
        t.texto(1205, y, 135, rh, f"{_sg(v)}{_nf(abs(v) / 1e3)}", 22, cor(v), True, "r", True)
        t.texto(1345, y, 100, rh, pc(p["pct"]), 22, cor(v), True, "r", True)
    if D.get("armazenagem_pendente"):
        t.texto(55, 344 + rh * len(ps) + 12, 1390, 26, f"* Faixa acima de 10 dias ainda sem tarifa: o total de {D['ano']} tende a subir quando ela for definida.", 19, SOFT)
    trilho(t)
    y = metrica(t, 440, "Custo total", f"{_sg(r['var'])}{abr(r['var'])}", f"{pc(r['var_pct'])} sobre o Forecast {D['ano_anterior']}", True, cor(r["var"]))
    y = metrica(t, y, "Units", f"{_sg(r['var_units'])}{mm(r['var_units'])} MM", f"{_nf(r['units_o'])} em {D['ano']} · {pc(r['var_units_pct'])}")
    dc = r["cntr_o"] - r["cntr_f"]
    metrica(t, y, "Contêineres", f"{_sg(dc)}{_nf(abs(dc))}", f"{_nf(r['cntr_o'])} em {D['ano']} · {_nf(r['cntr_f'])} em {D['ano_anterior']}", ultima=True)


def s_fretes(prs: Any, pasta: Path, D: dict[str, Any]) -> None:
    tf, d, part = D["total_fretes"], D["total_fretes"]["o"] - D["total_fretes"]["f"], D["total_fretes"]["o"] / D["resumo"]["orcamento"]
    aereo = next((f for f in D["fretes"] if f["k"] == "frete_aereo"), None)
    t = slide(prs, pasta, 4, "ORÇAMENTO 27 X FORECAST 26: FRETES", f"Os quatro fretes somam {din(tf['o'])}, {_nf(part * 100)}% do orçamento de {D['ano']}",
              f"Alta de {din(d)} sobre o Forecast {D['ano_anterior']}" + (", mesmo com a redução do frete aéreo" if aereo and aereo["var"] < 0 else "") + ". Valores em R$ milhões.", D)
    maximo = max(max(f["forecast"], f["orcamento"]) for f in D["fretes"]) or 1
    for i, f in enumerate(D["fretes"]):
        x, y = 55 + (i % 2) * 725, 306 + (i // 2) * 366
        t.texto(x, y, 385, 40, f["l"], 28, INK, True)
        t.texto(x + 385, y - 3, 280, 42, f"{_sg(f['var'])}{abr(f['var'])}  {pc(f['pct'])}", 28, cor(f["var"]), True, "r")
        for k, (nome, v, g) in enumerate(((f"Forecast {D['ano_anterior']}", f["forecast"], ("5E7A66", "9DB5A2")), (f"Orçamento {D['ano']}", f["orcamento"], ("7DBB12", "B5FF20")))):
            yy = y + 56 + k * 50
            t.texto(x, yy, 165, 34, nome, 19, SOFT, meio=True)
            t.barra(x + 172, yy + 4, v / maximo * 400, 26, g)
            t.texto(x + 580, yy, 85, 34, mm(v), 22, INK, True, "r", True)
        t.texto(x, y + 166, 665, 110, f"CPU de R$ {_nf(f['cpu_f'], 2)} para R$ {_nf(f['cpu_o'], 2)}. {f['explica']}", 19, SOFT)
    t.linha(55, 656, 1445, 656, LINE)
    trilho(t)
    y = metrica(t, 440, "Participação", f"{_nf(part * 100)}%", "do orçamento", True)
    y = metrica(t, y, f"Fretes em {D['ano']}", abr(tf["o"]), f"Forecast {D['ano_anterior']}: {abr(tf['f'])}")
    metrica(t, y, "Variação", f"{_sg(d)}{abr(d)}", f"{pc(tf['o'] / tf['f'] - 1 if tf['f'] else 0)} sobre o Forecast", c=cor(d), ultima=True)


def s_cenarios(prs: Any, pasta: Path, D: dict[str, Any]) -> None:
    C, r, F = D["cenarios"], D["resumo"], D["resumo"]["forecast"]
    t = slide(prs, pasta, 5, f"CENÁRIOS DE FRETE MARÍTIMO {D['ano']}", f"A tarifa marítima leva o orçamento de {abr(C[0]['total'])} a {abr(C[2]['total'])}",
              f"Só a tarifa marítima muda entre os cenários. Valores em R$ milhões, comparados ao Forecast {D['ano_anterior']}.", D)
    maximo = max([c["total"] for c in C] + [F])
    x0, wb, yh, rh = 480, 520, 338, 132
    t.barra(55, 303, 20, 20, G_BASE)
    t.texto(85, 299, 260, 28, f"Até o Forecast {D['ano_anterior']}", 19, SOFT, meio=True)
    t.barra(345, 303, 20, 20, G_UP)
    t.texto(375, 299, 290, 28, f"Acima do Forecast {D['ano_anterior']}", 19, SOFT, meio=True)
    t.linha(675, 300, 675, 326, INK, 1.5, True)
    t.texto(690, 299, 400, 28, f"Forecast {D['ano_anterior']}: {abr(F)}", 19, SOFT, meio=True)
    for x, w, txt, al in ((70, 400, "CENÁRIO E TARIFA POR CONTÊINER", "l"), (x0, wb, "CUSTO DO ANO", "l"), (1015, 115, "TOTAL", "r"), (1145, 135, "VARIAÇÃO", "r"), (1295, 90, "CPU", "r")):
        t.texto(x, yh, w, 24, txt, 14.5, FAINT, True, al)
    t.linha(55, yh + 32, 1445, yh + 32, LINE)
    linhas = [(f"Forecast {D['ano_anterior']}", f"{D['base']}: Actual e Forecast do ano", F, None, None, r["cpu_f"], False)] + [(c["nome"], c["tarifa"], c["total"], c["var"], c["var_pct"], c["cpu"], c["aprovado"]) for c in C]
    for i, (nome, txt, tot, v, pct, cpu, ap) in enumerate(linhas):
        y = yh + 40 + i * rh
        if ap:
            t.caixa(55, y + 4, 1390, rh - 8, "0E5A30", raio=12)
        t.texto(70, y + 30, 400, 40, nome + ("  ·  APROVADO" if ap else ""), 28, LIME if ap else INK, True)
        t.texto(70, y + 74, 405, 30, txt, 19, SOFT)
        base, ex = min(tot, F) / maximo * wb, max(tot - F, 0) / maximo * wb
        t.barra(x0, y + 44, base, 54, G_BASE)
        if ex:
            t.barra(x0 + base, y + 44, ex, 54, G_UP)
        t.texto(1015, y, 115, rh, mm(tot), 34, LIME if ap else INK, True, "r", True)
        if v is None:
            t.texto(1145, y, 135, rh, "Base", 21, INK, alinha="r", meio=True)
        else:
            t.texto(1145, y + 40, 135, 36, f"{_sg(v)}{mm(v)}", 29, cor(v), True, "r")
            t.texto(1145, y + 78, 135, 26, pc(pct), 19, cor(v), alinha="r")
        t.texto(1295, y, 90, rh, _nf(cpu, 2), 25, INK, True, "r", True)
    xf = x0 + F / maximo * wb
    t.linha(xf, yh + 40, xf, yh + 40 + rh * 4, INK, 1.5, True)
    trilho(t)
    y = metrica(t, 540, "Entre os cenários 1 e 3", abr(D["amplitude"]), "Diferença no custo do ano", True)
    metrica(t, y, "Cada USD 100 por contêiner", abr(D["por_100"]), "No ano todo", ultima=True)


def s_impacto(prs: Any, pasta: Path, D: dict[str, Any]) -> None:
    C, r = D["cenarios"], D["resumo"]
    t = slide(prs, pasta, 6, "CENÁRIOS DE FRETE: IMPACTO POR PROCESSO", "Só o frete marítimo e a Marinha Mercante mudam entre os cenários",
              f"Os demais processos ficam em {din(C[1]['demais'])} nos três cenários. Valores em R$ milhões; à direita, total e variação sobre o Forecast.", D)
    G = (("1F6B40", "35905A"), ("7DBB12", "B5FF20"), ("CFE6B4", "EDFFD4"))
    for i, (nome, g) in enumerate(zip(("Demais processos", "Frete marítimo", "Marinha Mercante + Siscomex"), G)):
        x = 55 + i * 250
        t.barra(x, 342, 20, 20, g)
        t.texto(x + 30, 338, 340, 28, nome, 19, SOFT, meio=True)
    maximo = max([c["total"] for c in C] + [r["forecast"]])
    linhas = [(f"Forecast {D['ano_anterior']}", f"{D['base']}: Actual e Forecast do ano", D["demais_f"], D["maritimo_f"], D["afrmm_f"], r["forecast"], None, False)] + [(c["nome"], c["tarifa"], c["demais"], c["maritimo"], c["afrmm"], c["total"], c["var"], c["aprovado"]) for c in C]
    for i, (nome, tarifa, a, b, c, tot, v, aprovado) in enumerate(linhas):
        y = 385 + i * 158
        t.texto(55, y + 26, 300, 34, nome + ("  ·  APROVADO" if aprovado else ""), 24, LIME if aprovado else INK, True)
        t.texto(55, y + 64, 295, 60, tarifa, 18, SOFT)
        x = 365.0
        for val, g, esc, d in ((a, G[0], INK, 2), (b, G[1], "00331A", 2), (c, G[2], "00331A", 1)):
            w = val / maximo * 745
            t.barra(x, y + 40, w - 3, 76, g)
            t.texto(x, y + 40, w - 3, 76, _nf(val / 1e6, d), 21 if d == 2 else 17, esc, True, "c", True)
            x += w
        t.texto(1120, y, 150, 156, mm(tot), 31, INK, True, "r", True)
        t.texto(1285, y, 160, 156, "base" if v is None else f"{_sg(v)}{mm(v)}", 24, cor(v) if v is not None else INK, True, "r", True)
        if i < 3:
            t.linha(55, y + 157, 1445, y + 157, LINE)
    trilho(t)
    y = metrica(t, 440, "Frete marítimo", f"R$ {mm(C[0]['maritimo'])} a {mm(C[2]['maritimo'])} MM", "Do Cenário 1 ao Cenário 3", True)
    y = metrica(t, y, "Marinha Mercante + Siscomex", f"R$ {mm(C[0]['afrmm'])} a {mm(C[2]['afrmm'])} MM", "Acompanha o frete")
    cp = [c["cpu"] for c in C]
    metrica(t, y, "CPU", f"R$ {_nf(min(cp), 2)} a {_nf(max(cp), 2)}", f"Forecast {D['ano_anterior']}: R$ {_nf(r['cpu_f'], 2)}", ultima=True)


def s_mensal(prs: Any, pasta: Path, D: dict[str, Any]) -> None:
    C, F, rot = D["cenarios"], D["mensal"]["forecast"], D["mensal"]["rotulos"]
    ap = next(c for c in C if c["aprovado"])["mensal"]
    acima, ix = sum(1 for a, b in zip(ap, F) if a > b), D["mes_tarifa"] - 1
    t = slide(prs, pasta, 7, "CENÁRIOS DE FRETE: EVOLUÇÃO MENSAL", f"O orçamento aprovado fica acima do Forecast {D['ano_anterior']} em {acima} dos 12 meses",
              f"Custo de cada mês em R$ milhões; o traço claro marca o Forecast {D['ano_anterior']}. A partir de {rot[ix].lower()}, o Cenário 2 iguala o Cenário 3.", D)
    sers = [(f"Forecast {D['ano_anterior']}", D["resumo"]["forecast"], F, G_CINZA, INK, D["base"])]
    for c, g, tx in zip(C, (G_END, G_LIME, G_UP), ("8FC3FF", LIME, "FF9F98")):
        sers.append((c["nome"], c["total"], c["mensal"], g, tx, "ORÇAMENTO APROVADO" if c["aprovado"] else f"USD {_nf(c['tarifas'][0])} O ANO TODO"))
    L, W, top, rh = 275, 1170, 334, 174
    cw, bw = W / 12, W / 12 * .6
    maximo, hm = max(max(s[2]) for s in sers), rh - 62
    for k, r in enumerate(rot):
        t.texto(L + cw * k, 302, cw, 24, r, 18, FAINT, alinha="c")
    for n, (nome, total, serie, g, tx, tag) in enumerate(sers):
        y0, base = top + rh * n, top + rh * n + rh - 10
        t.linha(55, y0, 1445, y0, LINE)
        t.linha(L, base, L + W, base, "5F8A70")
        t.texto(55, y0 + 38, 215, 32, nome, 25, INK, True)
        t.texto(55, y0 + 72, 215, 28, f"R$ {mm(total)} MM", 22, tx, True)
        t.texto(55, y0 + 102, 215, 22, tag, 12.5, SOFT, True)
        for k, v in enumerate(serie):
            cx, h = L + cw * k + cw / 2, v / maximo * hm
            topo = base - h
            ref = base - F[k] / maximo * hm if n else None
            t.caixa(cx - bw / 2, topo, bw, h, grad=g, raio=3)
            if ref is not None:
                t.linha(cx - bw / 2 - 6, ref, cx + bw / 2 + 6, ref, INK, 2.6)
            ly = (ref if ref is not None and ref < topo and topo - ref < 28 else topo) - 28
            t.texto(cx - cw / 2, ly, cw, 24, mm(v), 18.5, tx, True, "c")
    trilho(t)
    def sem(a: int, b: int) -> tuple[str, str]:
        o, f = sum(ap[a:b]), sum(F[a:b])
        return abr(o), f"Forecast {D['ano_anterior']}: {abr(f)} · {pc(o / f - 1 if f else 0)}"
    y = metrica(t, 440, "1º semestre do orçamento", *sem(0, 6), True)
    y = metrica(t, y, "2º semestre do orçamento", *sem(6, 12))
    p = ap.index(max(ap))
    metrica(t, y, "Mês de maior custo", f"{rot[p]} · {abr(ap[p])}", "No orçamento aprovado", ultima=True)


def s_atencao(prs: Any, pasta: Path, D: dict[str, Any]) -> None:
    t = slide(prs, pasta, 8, f"ORÇAMENTO {D['ano']}: PONTOS DE ATENÇÃO", f"O que pode mudar o orçamento de {D['ano']}", "", D)
    for i, a in enumerate(D["atencao"][:4]):
        x, y = 55 + (i % 2) * 930, 300 + (i // 2) * 372
        t.texto(x, y, 880, 76, a["n"], 62, LIME, True)
        t.texto(x, y + 84, 880, 42, a["t"], 32, INK, True)
        t.texto(x, y + 134, 880, 150, a["d"], 25, SOFT)
    t.linha(55, 656, 1865, 656, LINE)


def gerar(D: dict[str, Any], pasta: Path) -> bytes:
    from pptx import Presentation
    from pptx.util import Emu
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(1920 * PX), Emu(1080 * PX)
    capa(prs, pasta, ["LOG.", "INTERNACIONAL"], f"ORÇAMENTO {D['ano']} X FORECAST {D['ano_anterior']}")
    for f in (s_bridge, s_processos, s_fretes, s_cenarios, s_impacto, s_mensal, s_atencao):
        f(prs, pasta, D)
    capa(prs, pasta, ["FIM"])
    saida = io.BytesIO()
    prs.save(saida)
    return saida.getvalue()
