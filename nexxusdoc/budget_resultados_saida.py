"""Budget > MBR: arquivos para baixar (apresentacao em PowerPoint e base usada em Excel).

Tudo sai dos dados ja lidos das bases (budget_resultados.montar_operacao); nada e estimado aqui. O PowerPoint usa so formas e
textos editaveis, em Arial.
"""
from __future__ import annotations

import io
import unicodedata
from pathlib import Path
from typing import Any

MES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
ROT = {"BUNKER": "Bunker", "VOLUME": "Volume", "O. DESPESAS": "Outras despesas", "MARITIMO": "Marítimo", "ARMAZENAGEM": "Armazenagem", "RODOVIÁRIO": "Rodoviário",
       "V. CAMBIAL": "Câmbio", "FRETE AÉREO": "Frete aéreo", "SEGURO": "Seguro", "BUDGET": "Budget", "ACTUAL": "Actual"}
BG, INK, SOFT, FAINT, LINE, LIME, UP, DOWN = "06211A", "F2F6E8", "B9C9BD", "7F978B", "2C4A3D", "C6E84F", "FF8F87", "6FE39A"
G_UP, G_DOWN, G_END = ("FF7A6E", "C9302C"), ("5BE08A", "12A150"), ("6FB1FF", "2459BC")
PX = 6350  # 1 px do quadro de 1920 x 1080 em EMU


def _nf(v: float | None, d: int = 0) -> str:
    txt = f"{float(v or 0):,.{d}f}"
    return txt.replace(",", "§").replace(".", ",").replace("§", ".")


def _sg(v: float) -> str:
    return "+" if v > 0 else "-" if v < 0 else ""


def _din(v: float) -> str:
    a = abs(v)
    return f"R$ {_nf(a / 1e6, 2)} milhões" if a >= 999500 else f"R$ {_nf(a / 1e3)} mil"


def _abr(v: float) -> str:
    a = abs(v)
    return f"R$ {_nf(a / 1e6, 2)} mi" if a >= 999500 else f"R$ {_nf(a / 1e3)} mil"


def _pc(a: float, b: float) -> str:
    if not b:
        return "-"
    x = a / b - 1
    return f"{_sg(x)}{_nf(abs(x) * 100, 1)}%"


def _lado(v: float) -> str:
    return "acima" if v > 0 else "abaixo"


def _sem(txt: str) -> str:
    return unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode().lower().strip()


def _quebra(txt: str, maximo: int) -> list[str]:
    out, atual = [], ""
    for w in txt.split():
        if atual and len(f"{atual} {w}") > maximo:
            out.append(atual)
            atual = w
        else:
            atual = f"{atual} {w}".strip()
    return out + ([atual] if atual else [])


class _Tela:
    """Desenho no quadro de 1920 x 1080."""

    def __init__(self, prs: Any):
        from pptx.dml.color import RGBColor
        self.rgb = RGBColor.from_string
        self.s = prs.slides.add_slide(prs.slide_layouts[6])
        fill = self.s.background.fill
        fill.solid()
        fill.fore_color.rgb = self.rgb(BG)

    def caixa(self, x: float, y: float, w: float, h: float, cor: str | None = None, grad: tuple[str, str] | None = None, borda: str | None = None, raio: float = 0, forma: Any = None) -> Any:
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.util import Emu, Pt
        tipo = forma or (MSO_SHAPE.ROUNDED_RECTANGLE if raio else MSO_SHAPE.RECTANGLE)
        sh = self.s.shapes.add_shape(tipo, Emu(int(x * PX)), Emu(int(y * PX)), Emu(int(max(w, 1) * PX)), Emu(int(max(h, 1) * PX)))
        if raio and not forma:
            sh.adjustments[0] = min(0.5, raio / max(min(w, h), 1))
        sh.shadow.inherit = False
        if grad:
            sh.fill.gradient()
            sh.fill.gradient_angle = 270
            sh.fill.gradient_stops[0].color.rgb = self.rgb(grad[0])
            sh.fill.gradient_stops[1].color.rgb = self.rgb(grad[1])
        elif cor:
            sh.fill.solid()
            sh.fill.fore_color.rgb = self.rgb(cor)
        else:
            sh.fill.background()
        if borda:
            sh.line.color.rgb = self.rgb(borda)
            sh.line.width = Pt(1)
        else:
            sh.line.fill.background()
        return sh

    def texto(self, x: float, y: float, w: float, h: float, txt: str, tam: float, cor: str = INK, negrito: bool = False, alinha: str = "l", meio: bool = False) -> Any:
        from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
        from pptx.util import Emu, Pt
        tb = self.s.shapes.add_textbox(Emu(int(x * PX)), Emu(int(y * PX)), Emu(int(w * PX)), Emu(int(h * PX)))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE if meio else MSO_ANCHOR.TOP
        for i, parte in enumerate(str(txt).split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[alinha]
            r = p.add_run()
            r.text = parte
            r.font.name = "Arial"
            r.font.size = Pt(round(tam * 0.5, 1))
            r.font.bold = negrito
            r.font.color.rgb = self.rgb(cor)
        return tb

    def linha(self, x1: float, y1: float, x2: float, y2: float, cor: str = LINE, larg: float = 1, tracejada: bool = False) -> None:
        from pptx.enum.dml import MSO_LINE
        from pptx.enum.shapes import MSO_CONNECTOR
        from pptx.util import Emu, Pt
        c = self.s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Emu(int(x1 * PX)), Emu(int(y1 * PX)), Emu(int(x2 * PX)), Emu(int(y2 * PX)))
        c.line.color.rgb = self.rgb(cor)
        c.line.width = Pt(larg * 0.75)
        if tracejada:
            c.line.dash_style = MSO_LINE.DASH

    def topo(self, kick: str, titulo: str, sub: str = "") -> None:
        self.texto(84, 56, 1750, 28, kick.upper(), 19, LIME, True)
        self.texto(84, 88, 1750, 72, titulo, 52, INK, True)
        if sub:
            self.texto(84, 160, 1750, 40, sub, 26, SOFT)

    def rodape(self, mes: str, ano: str, n: int, total: int) -> None:
        self.texto(84, 1024, 1000, 24, f"Logística Internacional · MBR {mes} {ano}", 16, FAINT)
        self.texto(1636, 1024, 200, 24, f"{n} / {total}", 16, FAINT, alinha="r")


def _bridge(t: _Tela, p: dict[str, Any], destaques: dict[str, str], ox: float, oy: float, W: float, H: float) -> None:
    r = p["resumo"]
    it: list[dict[str, Any]] = [{"t": "BUDGET", "v": r["budget"], "end": True}] + [{"t": x["rotulo"], "v": (x["valor"] or 0) * 1e6} for x in p["ponte"]] + [{"t": "ACTUAL", "v": r["actual"], "end": True}]
    acc = topo = r["budget"]
    for x in it:
        if not x.get("end"):
            x["a"] = acc
            acc += x["v"]
            x["b"] = acc
            topo = max(topo, x["a"], x["b"])
    T, B = 104, 78
    y = lambda v: oy + H - B - (v / (topo * 1.02)) * (H - B - T)
    pw, bw, d = W / len(it), W / len(it) * .6, 2 if topo >= 1e6 else 3
    t.linha(ox, y(0), ox + W, y(0), "4A6355", 1.2)
    for i, x in enumerate(it):
        cx, x0, fim = ox + pw * i + pw / 2, ox + pw * i + (pw - bw) / 2, x.get("end")
        if fim:
            t0, h, grad, txt, cor = y(x["v"]), y(0) - y(x["v"]), G_END, _nf(x["v"] / 1e6, d), INK
        else:
            zero = abs(x["v"]) / 1e6 < 10 ** -d / 2
            t0, h = y(max(x["a"], x["b"])), max(5, abs(y(x["a"]) - y(x["b"])))
            grad, cor = (G_UP, UP) if x["v"] > 0 else (G_DOWN, DOWN)
            txt = ("" if zero else _sg(x["v"])) + _nf(abs(x["v"]) / 1e6, d)
        t.caixa(x0, t0, bw, h, grad=grad, raio=4)
        t.texto(cx - pw / 2, t0 - 40, pw, 34, txt, 27 if fim else 24, cor, True, "c")
        t.texto(cx - pw / 2, y(0) + 12, pw, 54, ROT.get(x["t"], x["t"]).replace(" ", "\n"), 16.5, SOFT, True, "c")
        nota = None if fim else destaques.get(_sem(ROT.get(x["t"], x["t"]))) or destaques.get(_sem(x["t"]))
        if nota:
            lin = _quebra(nota, 12)
            larg, tam = pw * .92, min(18, (pw * .92 - 14) / (max(len(w) for w in lin) * .6))
            alt = len(lin) * tam * 1.25 + 16
            by = t0 + h + 14
            if by + alt > y(0) - 6:
                by = t0 - 50 - alt
            t.caixa(cx - larg / 2, by, larg, alt, "0A2A20", borda="E8EEDB", raio=4)
            t.texto(cx - larg / 2, by, larg, alt, "\n".join(lin), tam, INK, alinha="c", meio=True)
        if i < len(it) - 1:
            nv = x["v"] if fim else x["b"]
            t.linha(x0 + bw, y(nv), x0 + pw, y(nv), "4F6A5B", 1, True)
    # traco que liga o Budget ao Actual, com a diferenca total no meio
    dt, xa, xb, yb, gap = r["actual"] - r["budget"], ox + pw / 2, ox + pw * (len(it) - 1) + pw / 2, oy + 24, 104
    xm = (xa + xb) / 2
    t.linha(xa, y(r["budget"]) - 46, xa, yb, "E8EEDB", 2)
    t.linha(xa, yb, xm - gap, yb, "E8EEDB", 2)
    t.linha(xm + gap, yb, xb, yb, "E8EEDB", 2)
    t.linha(xb, yb, xb, y(r["actual"]) - 56, "E8EEDB", 2)
    from pptx.enum.shapes import MSO_SHAPE
    t.caixa(xb - 8, y(r["actual"]) - 57, 16, 13, "E8EEDB", forma=MSO_SHAPE.ISOSCELES_TRIANGLE).rotation = 180
    t.texto(xm - gap, yb - 20, gap * 2, 40, f"{_sg(dt)}{_nf(abs(dt) / 1e6, 3)}MM", 31, UP if dt > 0 else DOWN, True, "c", True)


def _metrica(t: _Tela, x: float, y: float, nome: str, valor: str, sub: str, on: bool = False) -> float:
    t.texto(x, y, 360, 22, nome.upper(), 17, LIME if on else FAINT, True)
    t.texto(x, y + 25, 360, 54, valor, 43, LIME if on else INK, True)
    if sub:
        t.texto(x, y + 80, 360, 26, sub, 18, SOFT)
    return y + (120 if sub else 96)


def _mini(t: _Tela, x: float, y: float, itens: list[tuple[str, str, str]]) -> None:
    for i, (nome, valor, cor) in enumerate(itens):
        t.texto(x + i * 122, y, 118, 20, nome.upper(), 15, FAINT, True)
        t.texto(x + i * 122, y + 24, 118, 34, valor, 25, cor, True)


def _slide_res(prs: Any, op: dict[str, Any], p: dict[str, Any], D: dict[str, Any], mes: str, ano: str) -> _Tela:
    t = _Tela(prs)
    r, ytd, nome = p["resumo"], p["chave"] == "ytd", op["nome"].split(" ")[0]
    d = r["actual"] - r["budget"]
    tit = f"No acumulado, {nome} está {_din(d)} {_lado(d)} do Budget" if ytd else f"{nome} fechou {mes} {_din(d)} {_lado(d)} do Budget"
    xs = [(ROT.get(x["rotulo"], x["rotulo"]).lower(), (x["valor"] or 0) * 1e6) for x in p["ponte"]]
    menor, maior, sub = min(xs, key=lambda a: a[1]), max(xs, key=lambda a: a[1]), []
    if menor[1] < 0:
        sub.append(f"maior redução em {menor[0]} ({_sg(menor[1])}{_din(menor[1])})")
    if maior[1] > 0:
        sub.append(f"maior aumento em {maior[0]} ({_sg(maior[1])}{_din(maior[1])})")
    texto_sub = "; ".join(sub)
    t.topo(f"{op['nome']} · " + (f"Acumulado {ano}" if ytd else f"{mes.capitalize()} {ano}"), tit, texto_sub[:1].upper() + texto_sub[1:] + ".")
    chave = f"{op['operacao']}|{D['competencia']}|{p['chave']}"
    notas = (D.get("comentarios") or {}).get(chave, [])[:3]
    destaques = {_sem(x.split(":", 1)[0]): x.split(":", 1)[1].strip() for x in (D.get("comentarios") or {}).get(f"{chave}|destaques", []) if ":" in x}
    base = 1006 - len(notas) * 36 - (16 if notas else 0)
    _bridge(t, p, destaques, 84, 212, 1300, base - 212)
    if notas:
        t.linha(84, base + 4, 1384, base + 4)
        for i, n in enumerate(notas):
            yy = base + 16 + i * 36
            from pptx.enum.shapes import MSO_SHAPE
            t.caixa(84, yy + 9, 9, 9, LIME, forma=MSO_SHAPE.OVAL)
            t.texto(106, yy, 1278, 32, n, 21, "E3EBDC")
    t.linha(1436, 212, 1436, 1000)
    y = 300 if has_fc(r) else 360
    x = 1480
    y = _metrica(t, x, y, "Budget", _abr(r["budget"]), f"{_nf(r['units_budget'])} units · CPU R$ {_nf(r['cpu_budget'], 2)}")
    if has_fc(r):
        y = _metrica(t, x, y + 14, "Forecast", _abr(r["forecast"]), f"{_nf(r['units_forecast'])} units · CPU R$ {_nf(r['cpu_forecast'], 2)}")
    y = _metrica(t, x, y + 14, "Actual", _abr(r["actual"]), f"{_nf(r['units_actual'])} units · CPU R$ {_nf(r['cpu_actual'], 2)}", True)
    cpu, fx = r["cpu_actual"] - r["cpu_budget"], (p.get("cambio") or {}).get("fx_actual")
    itens = [("Volume", _pc(r["units_actual"], r["units_budget"]), INK), ("CPU", _pc(r["cpu_actual"], r["cpu_budget"]), UP if cpu > 0 else DOWN)]
    if fx is not None:
        itens.append(("Câmbio", _nf(fx, 2), INK))
    _mini(t, x, y + 18, itens)
    return t


def has_fc(r: dict[str, Any]) -> bool:
    return r.get("forecast") is not None


def _slide_fc(prs: Any, op: dict[str, Any], f: dict[str, Any], ano: str) -> _Tela:
    t = _Tela(prs)
    nome, mes = op["nome"].split(" ")[0], f["rotulo"].lower()
    du, dc = f["units_forecast"] - f["units_budget"], f["forecast"] - f["budget"]
    t.topo(f"{op['nome']} · Forecast {f['rotulo']} {ano}", f"{nome} deve fechar {mes} {_din(dc)} {_lado(dc)} do Budget",
           f"Forecast de {_nf(f['units_forecast'])} units, {_nf(abs(du))} {'a menos' if du < 0 else 'a mais'} que o Budget.")
    ls = sorted([{"r": l["rotulo"], "d": l["forecast"] - l["budget"]} for l in f["linhas"] if abs(l["forecast"] - l["budget"]) >= .5], key=lambda a: -abs(a["d"]))
    top, resto = ls[:6], ls[6:]
    if resto:
        top.append({"r": "Demais despesas", "d": sum(x["d"] for x in resto), "dem": True})
    maximo = max(abs(x["d"]) for x in top) or 1
    y0 = 385
    t.texto(84, y0 - 54, 900, 34, "O que muda em relação ao Budget", 24, SOFT, True)
    xt, wt = 420, 760
    t.linha(xt + wt / 2, y0 - 8, xt + wt / 2, y0 + len(top) * 62 - 16)
    for i, x in enumerate(top):
        yy, w = y0 + i * 62, abs(x["d"]) / maximo * wt / 2
        t.texto(84, yy, 330, 36, x["r"], 25, SOFT if x.get("dem") else INK, meio=True)
        t.caixa(xt + wt / 2 - w if x["d"] < 0 else xt + wt / 2, yy, max(w, 4), 36, grad=G_UP if x["d"] > 0 else G_DOWN, raio=4)
        t.texto(1190, yy, 194, 36, f"{_sg(x['d'])}R$ {_nf(abs(x['d']) / 1e3)} mil", 25, UP if x["d"] > 0 else DOWN, True, "r", True)
    t.linha(1436, 212, 1436, 1000)
    y = _metrica(t, 1480, 400, "Budget", _abr(f["budget"]), f"{_nf(f['units_budget'])} units")
    y = _metrica(t, 1480, y + 14, "Forecast", _abr(f["forecast"]), f"{_nf(f['units_forecast'])} units", True)
    _mini(t, 1480, y + 18, [("Custo", _pc(f["forecast"], f["budget"]), UP if dc > 0 else DOWN), ("Units", _pc(f["units_forecast"], f["units_budget"]), INK)])
    return t


def gerar_pptx(D: dict[str, Any]) -> bytes:
    from pptx import Presentation
    from pptx.util import Emu
    op = D["operacoes"][0]
    ano, mes = D["competencia"][:4], MES[int(D["competencia"][5:])]
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(1920 * PX), Emu(1080 * PX)
    per = {p["chave"]: p for p in op["periodos"]}
    m, y = per["mes"], per.get("ytd")
    def abertura(titulo: str, sub: str) -> None:
        t = _Tela(prs)
        for i, h in enumerate([150, 250, 215, 330, 285, 410, 370, 500, 450, 610]):
            c = tuple(int(int(BG[k:k + 2], 16) + (int(LIME[k:k + 2], 16) - int(BG[k:k + 2], 16)) * (.22 + i * .05)) for k in (0, 2, 4))
            t.caixa(920 + i * 100, 1080 - h, 68, h, grad=("%02X%02X%02X" % c, BG), raio=5)
        t.texto(120, 410, 1500, 34, "GRUPO SBF · MBR LOGÍSTICA", 23, LIME, True)
        t.texto(120, 462, 1700, 140, titulo, 112, INK, True)
        t.texto(120, 616, 1500, 50, sub, 34, SOFT)

    abertura(f"Resultados de {mes}", f"Logística Internacional · {op['nome']} · {ano}")
    # resumo
    t = _Tela(prs)
    dm, dy = m["resumo"]["actual"] - m["resumo"]["budget"], (y["resumo"]["actual"] - y["resumo"]["budget"]) if y else None
    nome = op["nome"].split(" ")[0]
    t.topo(f"Resumo executivo · {mes.capitalize()} {ano}", f"{nome} segue abaixo do Budget no mês e no acumulado" if dm < 0 and dy is not None and dy < 0 else f"Resultado de {mes} da {nome}")
    for i, (rot, d, p) in enumerate([(mes.capitalize(), dm, m)] + ([("Acumulado", dy, y)] if y else [])):
        yy = 340 + i * 260
        t.texto(84, yy, 780, 40, rot, 30, LIME, True)
        t.texto(84, yy + 44, 780, 110, f"{_sg(d)}{_din(d).replace(' milhões', ' mi')}", 84, UP if d > 0 else DOWN, True)
        t.texto(84, yy + 156, 780, 36, f"{_pc(p['resumo']['actual'], p['resumo']['budget'])} em relação ao Budget", 24, SOFT)
    t.linha(960, 212, 960, 980)
    cel = lambda p, c: _abr(p["resumo"][c]) if p and p["resumo"].get(c) is not None else "-"
    linhas = [("Budget", cel(m, "budget"), cel(y, "budget"), False), ("Forecast", cel(m, "forecast"), cel(y, "forecast"), False), ("Actual", cel(m, "actual"), cel(y, "actual"), True),
              ("Units Actual", _nf(m["resumo"]["units_actual"]), _nf(y["resumo"]["units_actual"]) if y else "-", False),
              ("CPU Actual", f"R$ {_nf(m['resumo']['cpu_actual'], 2)}", f"R$ {_nf(y['resumo']['cpu_actual'], 2)}" if y else "-", False)]
    t.texto(1320, 352, 240, 24, mes.upper(), 17, FAINT, True, "r")
    t.texto(1596, 352, 240, 24, "ACUMULADO", 17, FAINT, True, "r")
    t.linha(1000, 388, 1836, 388)
    for i, (rot, a, b, on) in enumerate(linhas):
        yy = 402 + i * 86
        t.texto(1000, yy, 320, 58, rot, 29, LIME if on else SOFT, on, meio=True)
        t.texto(1320, yy, 240, 58, a, 29, LIME if on else INK, on, "r", True)
        t.texto(1596, yy, 240, 58, b, 29, LIME if on else INK, on, "r", True)
        if i < len(linhas) - 1:
            t.linha(1000, yy + 72, 1836, yy + 72)
    _slide_res(prs, op, m, D, mes, ano)
    if y:
        _slide_res(prs, op, y, D, mes, ano)
    if op.get("proximo"):
        _slide_fc(prs, op, op["proximo"], ano)
    abertura("Fim", f"Logística Internacional · {op['nome']} · {mes} {ano}")
    total = len(prs.slides._sldIdLst)
    for i, sl in enumerate(prs.slides):
        if 0 < i < total - 1:
            tela = _Tela.__new__(_Tela)
            from pptx.dml.color import RGBColor
            tela.rgb, tela.s = RGBColor.from_string, sl
            tela.rodape(mes, ano, i + 1, total)
    saida = io.BytesIO()
    prs.save(saida)
    return saida.getvalue()


# ---------------------------------------------------------------- base usada em Excel
def gerar_excel(D: dict[str, Any], arquivos: list[dict[str, Any]], pgl_original: Path | None) -> Any:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    op = D["operacoes"][0]
    wb = Workbook()
    wb.remove(wb.active)

    def aba(nome: str, cab: list[str], linhas: list[list[Any]], fmt: dict[int, str] | None = None) -> None:
        ws = wb.create_sheet(nome)
        ws.append(cab)
        for row in linhas:
            ws.append(row)
        for c in ws[1]:
            c.fill, c.font, c.alignment = PatternFill("solid", fgColor="0D4A26"), Font(bold=True, color="FFFFFF"), Alignment(vertical="center", wrap_text=True)
        ws.row_dimensions[1].height = 32
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for i, nome_c in enumerate(cab, 1):
            maior = max([len(str(nome_c))] + [len(str(r[i - 1])) for r in linhas[:300] if i <= len(r) and isinstance(r[i - 1], str)])
            ws.column_dimensions[get_column_letter(i)].width = min(46, max(13, maior + 2))
            if fmt and i in fmt:
                for cel in ws[get_column_letter(i)][1:]:
                    cel.number_format = fmt[i]

    R, N, C, P = "#,##0.00", "#,##0", "0.000", "0.0%"
    dif = lambda a, b: a - b if a is not None and b is not None else None
    var = lambda a, b: a / b - 1 if a is not None and b else None
    lin = []
    for p in op["periodos"]:
        r, c = p["resumo"], p.get("cambio") or {}
        lin.append([p["rotulo"], r["budget"], r["forecast"], r["actual"], dif(r["actual"], r["budget"]), var(r["actual"], r["budget"]), dif(r["actual"], r["forecast"]), var(r["actual"], r["forecast"]),
                    r["units_budget"], r["units_forecast"], r["units_actual"], r["cpu_budget"], r["cpu_forecast"], r["cpu_actual"], c.get("fx_budget"), c.get("fx_actual"), c.get("efeito_fx")])
    aba("Resumo", ["Período", "Budget (R$)", "Forecast (R$)", "Actual (R$)", "Actual vs Budget (R$)", "Actual vs Budget (%)", "Actual vs Forecast (R$)", "Actual vs Forecast (%)", "Units Budget", "Units Forecast", "Units Actual",
                   "CPU Budget", "CPU Forecast", "CPU Actual", "Câmbio Budget", "Câmbio Actual", "Efeito do câmbio (R$)"], lin,
        {2: R, 3: R, 4: R, 5: R, 6: P, 7: R, 8: P, 9: N, 10: N, 11: N, 12: C, 13: C, 14: C, 15: "0.00", 16: "0.00", 17: R})
    lin = []
    for p in op["periodos"]:
        lin.append([p["rotulo"], "Budget", p["resumo"]["budget"]])
        lin += [[p["rotulo"], ROT.get(x["rotulo"], x["rotulo"]), (x["valor"] or 0) * 1e6] for x in p["ponte"]]
        lin.append([p["rotulo"], "Actual", p["resumo"]["actual"]])
    aba("Bridge", ["Período", "Fator", "Valor (R$)"], lin, {3: R})
    lin = []
    for p in op["periodos"]:
        for nome_c, bloco in (("Câmbio real", p["real"]), ("Câmbio do Budget", p.get("cambio_budget"))):
            for x in ((bloco or {}).get("linhas") or []) + ([bloco["total"]] if bloco and bloco.get("total") else []):
                lin.append([p["rotulo"], nome_c, x["rotulo"], x["cpu_budget"], x["cpu_actual"], x["budget"], x["actual"], x["variacao"], x["impacto_volume"], x["impacto_preco"]])
    aba("Abertura por grupo", ["Período", "Câmbio", "Grupo", "CPU Budget", "CPU Actual", "Budget (R$)", "Actual (R$)", "Variação (R$)", "Impacto de volume (R$)", "Impacto de preço (R$)"], lin,
        {4: C, 5: C, 6: R, 7: R, 8: R, 9: R, 10: R})
    lin = []
    for p in op["periodos"]:
        for chave, nome_c in (("custos", "Custo (R$)"), ("cpu", "CPU (R$)"), ("units", "Units"), ("indicadores", "Indicadores")):
            for x in ((p.get("detalhe") or {}).get(chave) or []):
                lin.append([p["rotulo"], nome_c, x["rotulo"], x["budget"], x["forecast"], x["actual"]])
    aba("Detalhe por despesa", ["Período", "Tipo", "Linha", "Budget", "Forecast", "Actual"], lin, {4: "#,##0.000", 5: "#,##0.000", 6: "#,##0.000"})
    m = op.get("mensal")
    if m:
        fim = m["fechado"]
        lin = [[t, m["custo"]["budget"][i], m["custo"]["forecast"][i], m["custo"]["actual"][i] if i <= fim else None, m["units"]["budget"][i], m["units"]["forecast"][i], m["units"]["actual"][i] if i <= fim else None,
                m["conteineres"]["budget"][i], m["conteineres"]["forecast"][i], m["conteineres"]["actual"][i] if i <= fim else None] for i, t in enumerate(m["rotulos"])]
        aba("Evolução mensal", ["Mês", "Custo Budget (R$)", "Custo Forecast (R$)", "Custo Actual (R$)", "Units Budget", "Units Forecast", "Units Actual", "Contêineres Budget", "Contêineres Forecast", "Contêineres Actual"], lin,
            {2: R, 3: R, 4: R, 5: N, 6: N, 7: N, 8: N, 9: N, 10: N})
    f = op.get("proximo")
    if f:
        lin = [[l["rotulo"], l["budget"], l["forecast"], l["forecast"] - l["budget"]] for l in f["linhas"]] + [["Total", f["budget"], f["forecast"], f["forecast"] - f["budget"]]]
        aba(f"Forecast {f['rotulo']}"[:31], ["Despesa", "Budget (R$)", "Forecast (R$)", "Diferença (R$)"], lin, {2: R, 3: R, 4: R})
    aba("Conferência das bases", ["Situação", "Conferência", "Detalhe"], [["Fecha" if c["ok"] else "Atenção", c["nome"], c["detalhe"]] for c in op["conferencias"]])
    aba("Arquivos de origem", ["Arquivo", "Tipo", "Enviado por", "Enviado em", "Em uso"], [[a["nome"], a["tipo_rotulo"], a.get("por"), a.get("em"), "Sim" if a["em_uso"] else "Não"] for a in arquivos])
    if pgl_original and pgl_original.is_file():
        org = load_workbook(pgl_original, data_only=True, read_only=True)
        try:
            fonte = next((ws for ws in org.worksheets if _sem(ws.title).replace(" ", "") == "masc.-custo"), None)
            if fonte is not None:
                linhas = [list(r) for r in fonte.iter_rows(values_only=True)]
                cab = [str(x or "") for x in linhas[0]]
                pos = cab.index("PROCESSO")
                aba("Base PGL (processos)", cab, [r for r in linhas[1:] if r[pos] not in (None, "")])
        finally:
            org.close()
    return wb
