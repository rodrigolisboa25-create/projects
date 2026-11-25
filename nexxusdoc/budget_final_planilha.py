"""Planilha oficial da Apresentacao Final (19/11/2026, pedido do usuario: "precisa ter todos os dados que compoem a
apresentacao", para enviar a gerente junto com os slides). Os numeros sao os mesmos da apresentacao (budget_final.montar):
nada e recalculado aqui."""
from __future__ import annotations

import io
from typing import Any

VERDE, CLARO = "003D18", "E6F2DA"


def gerar(D: dict[str, Any]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    BRL, PCT, NUM, USD, CPU = '"R$" #,##0.00', "0.0%", "#,##0", '"USD" #,##0.00', '"R$" #,##0.0000'
    thin = Side(style="thin", color="C9D9BD")
    a0, a1 = D["ano_anterior"], D["ano"]
    fc, orc = f"Forecast {a0} ({D['base']})", f"Orçamento {a1}"
    book = Workbook()

    def aba(nome: str, titulo: str, sub: str = ""):
        ws = book.active if book.active.title == "Sheet" else book.create_sheet()
        ws.title = nome
        ws["A1"] = titulo
        ws["A1"].font = Font(bold=True, size=14, color=VERDE)
        ws["A2"] = sub or f"{orc} × {fc} · {D['periodo']} · versão do orçamento: {D['versao'].get('nome', '')}"
        ws["A2"].font = Font(italic=True, size=9, color="555555")
        ws.sheet_view.showGridLines = False
        return ws

    def tabela(ws, linha: int, cab: list[str], rows: list[list[Any]], fmts: list[str | None], larg: list[int] | None = None) -> int:
        for j, c in enumerate(cab, 1):
            cell = ws.cell(linha, j, c)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=VERDE)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for i, r in enumerate(rows, 1):
            for j, v in enumerate(r, 1):
                cell = ws.cell(linha + i, j, v)
                cell.border = Border(bottom=thin)
                if fmts[j - 1] and isinstance(v, (int, float)):
                    cell.number_format = fmts[j - 1]
                if i % 2 == 0:
                    cell.fill = PatternFill("solid", fgColor="F5FAF0")
                if isinstance(v, str) and len(v) > 40:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
        for j, w in enumerate(larg or [], 1):
            ws.column_dimensions[get_column_letter(j)].width = w
        return linha + len(rows) + 2

    r, u = D["resumo"], D["units"]
    # 1. Resumo
    ws = aba("Resumo", f"Apresentação Final · {orc} × {fc}")
    var = lambda a, b: [a, b, b - a, (b / a - 1) if a else None]  # noqa: E731
    lin = tabela(ws, 4, ["Indicador", fc, orc, "Variação", "Variação %"], [
        ["Custo total (R$)", *var(r["forecast"], r["orcamento"])],
        ["Units (total)", *var(r["units_f"], r["units_o"])],
        ["Units marítimo", *var(u.get("maritimo_f") or 0, u.get("maritimo_o") or 0)],
        ["Units aéreo", *var(u.get("aereo_f") or 0, u.get("aereo_o") or 0)],
        ["Contêineres", *var(r["cntr_f"], r["cntr_o"])],
        ["Custo por unit (R$)", *var(r["cpu_f"], r["cpu_o"])],
        ["Câmbio (R$ por US$)", *var(r["fx_f"], r["fx_o"])],
    ], [None, "#,##0.0000", "#,##0.0000", "#,##0.0000", PCT], [34, 22, 22, 18, 14])
    for row in range(5, 12):  # formato por linha (R$, unidades, CPU, cambio)
        f = {5: BRL, 6: NUM, 7: NUM, 8: NUM, 9: NUM, 10: CPU, 11: "#,##0.00"}[row]
        for col in (2, 3, 4):
            ws.cell(row, col).number_format = f
    ws.cell(lin, 1, "Base do Forecast").font = Font(bold=True)
    ws.cell(lin, 2, f"{D['base']}: {D['periodo']}")
    ws.cell(lin + 1, 1, "Versão do orçamento").font = Font(bold=True)
    ws.cell(lin + 1, 2, D["versao"].get("nome", ""))
    # 2. Bridge
    ws = aba("Bridge", f"Bridge do {fc} ao {orc} (R$)")
    rows = [[fc, r["forecast"]]] + [[b["t"].title(), b["v"]] for b in D["bridge"]] + [[orc, r["orcamento"]]]
    lin = tabela(ws, 4, ["Etapa", "Valor (R$)"], rows, [None, BRL], [34, 22])
    ws.cell(lin, 1, "Comentários da apresentação").font = Font(bold=True, color=VERDE)
    tabela(ws, lin + 1, ["Destaque", "Texto"], [[c["k"], c["t"]] for c in D["comentarios"]], [None, None], [34, 90])
    # 3. Processos e 4. Fretes
    cab = ["Processo", f"{fc} (R$)", f"{orc} (R$)", "Variação (R$)", "Variação %", f"CPU {a0} (R$)", f"CPU {a1} (R$)", "O que explica"]
    fm = [None, BRL, BRL, BRL, PCT, CPU, CPU, None]
    larg = [30, 20, 20, 18, 12, 14, 14, 70]
    ws = aba("Processos", "Custo por processo")
    lin = tabela(ws, 4, cab, [[p["l"], p["forecast"], p["orcamento"], p["var"], p["pct"], p["cpu_f"], p["cpu_o"],
                                p["explica"] + (" (faixa acima de 10 dias sem tarifa)" if p.get("pendente") else "")] for p in D["processos"]], fm, larg)
    ws.cell(lin, 1, "Total").font = Font(bold=True)
    for col, k in ((2, "forecast"), (3, "orcamento"), (4, "var")):
        ws.cell(lin, col, sum(p[k] for p in D["processos"])).number_format = BRL
    ws = aba("Fretes", "Fretes")
    lin = tabela(ws, 4, cab, [[p["l"], p["forecast"], p["orcamento"], p["var"], p["pct"], p["cpu_f"], p["cpu_o"], p["explica"]] for p in D["fretes"]], fm, larg)
    tf = D.get("total_fretes") or {}
    ws.cell(lin, 1, "Total de fretes").font = Font(bold=True)
    ws.cell(lin, 2, tf.get("f")).number_format = BRL
    ws.cell(lin, 3, tf.get("o")).number_format = BRL
    # 5. Cenarios
    ws = aba("Cenários", "Cenários de frete marítimo (tarifa por contêiner)")
    lin = tabela(ws, 4, ["Cenário", "Tarifa", "Aprovado", f"Total {a1} (R$)", f"Variação × {fc} (R$)", "Variação %", "CPU (R$)",
                         "Frete marítimo (R$)", "AFRMM + Siscomex (R$)", "Demais custos (R$)"],
                 [[c["nome"], c["tarifa"], "Sim" if c.get("aprovado") else "Não", c["total"], c["var"], c["var_pct"], c["cpu"],
                   c["maritimo"], c["afrmm"], c["demais"]] for c in D["cenarios"]],
                 [None, None, None, BRL, BRL, PCT, CPU, BRL, BRL, BRL], [14, 34, 10, 20, 22, 12, 12, 20, 20, 20])
    ws.cell(lin, 1, "Cada USD 100 na tarifa por contêiner").font = Font(bold=True)
    ws.cell(lin, 4, D["por_100"]).number_format = BRL
    ws.cell(lin + 1, 1, "Diferença entre o cenário mais barato e o mais caro").font = Font(bold=True)
    ws.cell(lin + 1, 4, D["amplitude"]).number_format = BRL
    ws.cell(lin + 2, 1, "Frete marítimo, AFRMM e demais custos no Forecast").font = Font(bold=True)
    for col, k in ((8, "maritimo_f"), (9, "afrmm_f"), (10, "demais_f")):
        ws.cell(lin + 2, col, D.get(k)).number_format = BRL
    meses = D["mensal"]["rotulos"]
    lin = tabela(ws, lin + 5, ["Tarifa por contêiner (USD)"] + meses, [[c["nome"]] + c["tarifas"] for c in D["cenarios"]], [None] + [USD] * 12)
    # 6. Mensal
    ws = aba("Mensal", "Custo mês a mês (R$)")
    rows = [[fc] + D["mensal"]["forecast"] + [sum(D["mensal"]["forecast"])]]
    rows += [[f"{c['nome']} ({c['tarifa']})"] + c["mensal"] + [sum(c["mensal"])] for c in D["cenarios"]]
    tabela(ws, 4, ["Série"] + meses + ["Total"], rows, [None] + [BRL] * 13, [44] + [15] * 13)
    # 7. Pontos de atencao
    ws = aba("Pontos de atenção", "Pontos de atenção")
    tabela(ws, 4, ["Número", "Ponto", "Detalhe"], [[a["n"], a["t"], a["d"]] for a in D["atencao"]], [None, None, None], [16, 40, 100])
    if D.get("conferencia"):
        ws2 = aba("Conferência", "Conferência dos números")
        tabela(ws2, 4, ["Item", "Detalhe"], [[str(c.get("t") or c.get("item") or ""), str(c.get("d") or c.get("detalhe") or "")] for c in D["conferencia"]],
               [None, None], [40, 100])
    # 8. Fontes
    ws = aba("Fontes", "De onde vêm os números")
    tabela(ws, 4, ["Item", "Fonte"], [
        [orc, f"Versão \"{D['versao'].get('nome', '')}\" do orçamento na página Resultados do NexxusDoc."],
        [fc, f"Ferramenta de Controle mais recente enviada na aba MBR: {D['periodo']} ({D['base']})."],
        ["Bridge", "Volume = variação de units × custo por unit do Forecast; preço = diferença restante; grupos em dólar a câmbio constante, com a diferença na variação cambial."],
        ["Cenários", "Recalculados pelo motor do orçamento trocando só as tarifas de frete marítimo; demais premissas iguais ao orçamento."],
    ], [None, None], [24, 120])
    for w in book.worksheets:
        for row in w.iter_rows():
            for cell in row:
                if cell.data_type == "f":  # nada vira formula (texto que comeca com '=')
                    cell.data_type = "s"
    buf = io.BytesIO()
    book.save(buf)
    return buf.getvalue()
