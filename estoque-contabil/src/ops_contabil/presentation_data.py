"""Dados livres das apresentações do Optimus: qualquer recorte da Base de Estoque, inclusive projeção.

O agente descreve O QUE quer ver (dimensão, medida, filtros, top, projeção) num objeto ``data``; o sistema valida
contra as listas abaixo, consulta ``inventory_rows`` (as mesmas linhas da Visão e relatórios, sem filtros da página)
e devolve os itens do gráfico. Nenhum número vem do texto do agente.

Projeção: tendência linear (mínimos quadrados) da medida nas competências carregadas até a da apresentação,
estendida pelos meses pedidos (1 a 6). É uma estimativa e aparece marcada como tal no slide.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .db import connect
from .inventory import ensure_inventory_schema

# id → (coluna, rótulo). "period" = série mensal das competências carregadas.
DIMENSIONS: dict[str, tuple[str, str]] = {
    "period": ("period", "Competência"),
    "division": ("division_description", "Division Description"),
    "location": ("location_group", "Local de estoque"),
    "plant": ("plant", "Centro"),
    "status": ("operation_status", "STATUS OPERAÇÃO"),
    "lifecycle": ("lifecycle_description", "Lifecycle"),
    "aging": ("aging_bucket", "Faixa de aging"),
    "season": ("season", "Season"),
    "year": ("historical_year_bucket", "Coleção (ano)"),
    "season_year": ("season_year", "Season/Coleção"),
    "origin": ("material_origin", "Origem do material"),
    "type": ("inventory_type", "Tipo"),
    "style": ("style", "Estilo"),
    "style_color": ("style_color", "Estilo-Cor"),
    "material": ("material", "Material"),
}
_OVER_12 = "left(cast(aging_bucket as varchar), 2) in ('5)','6)','7)','8)')"
_FUTURES = "left(cast(aging_bucket as varchar), 2) = '0)'"
# id → (expressão SQL, unidade, rótulo, aditiva: participação % faz sentido)
MEASURES: dict[str, tuple[str, str, str, bool]] = {
    "fiscal_value": ("coalesce(sum(fiscal_total_amount),0)", "brl", "Valor fiscal", True),
    "company_value": ("coalesce(sum(company_total_amount),0)", "brl", "Vlr Tot Emp", True),
    "commercial_value": ("coalesce(sum(commercial_total_amount),0)", "brl", "Vlr Total CC", True),
    "free_quantity": ("coalesce(sum(unrestricted_quantity),0)", "num", "Utilização livre (unidades)", True),
    "blocked_quantity": ("coalesce(sum(blocked_quantity),0)", "num", "Bloqueado (unidades)", True),
    "materials": ("count(distinct material)", "num", "Materiais", False),
    "rows": ("count(*)", "num", "Linhas da base", True),
    "pmm": ("coalesce(sum(fiscal_total_amount)/nullif(sum(unrestricted_quantity),0),0)", "brl", "PMM", False),
    "over_12_value": (f"coalesce(sum(case when {_OVER_12} then fiscal_total_amount end),0)", "brl",
                      "Acima de 12 meses", True),
    "over_12_pct": (f"coalesce(100*sum(case when {_OVER_12} then fiscal_total_amount end)"
                    f"/nullif(sum(case when not {_FUTURES} then fiscal_total_amount end),0),0)", "pct",
                    "% acima de 12 meses do recebido", False),
    "futures_value": (f"coalesce(sum(case when {_FUTURES} then fiscal_total_amount end),0)", "brl", "Futures", True),
    "fob": ("coalesce(sum(fob_amount),0)", "brl", "FOB", True),
    "import_tax": ("coalesce(sum(import_tax_amount),0)", "brl", "II", True),
    "other_costs": ("coalesce(sum(other_costs_amount),0)", "brl", "Outros custos", True),
}
MAX_PROJECTION = 6
MAX_HISTORY = 18
PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")


def _label_sql(column: str) -> str:
    return f"coalesce(nullif(trim(cast(\"{column}\" as varchar)), ''), 'Não informado')"


def _int(value: Any, low: int, high: int, default: int | None) -> int | None:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def clean_query(raw: Any) -> dict[str, Any] | None:
    """Valida o pedido do agente; None quando não dá para montar o gráfico (dimensão ou medida desconhecida)."""
    if not isinstance(raw, dict):
        return None
    dimension = str(raw.get("dimension") or raw.get("dim") or "").strip().lower()
    measure = str(raw.get("measure") or raw.get("metric") or "fiscal_value").strip().lower()
    projection = _int(raw.get("projection") or raw.get("forecast"), 0, MAX_PROJECTION, 0) or 0
    if projection and not dimension:
        dimension = "period"
    if dimension not in DIMENSIONS or measure not in MEASURES:
        return None
    query: dict[str, Any] = {"dimension": dimension, "measure": measure}
    filters = {}
    for key, values in (raw.get("filters") or {}).items() if isinstance(raw.get("filters"), dict) else []:
        key = str(key).strip().lower()
        if key in DIMENSIONS and key != "period":
            values = values if isinstance(values, list) else [values]
            chosen = [str(value).strip()[:80] for value in values if str(value or "").strip()][:20]
            if chosen:
                filters[key] = chosen
    if filters:
        query["filters"] = filters
    if dimension == "period":
        query["periods"] = _int(raw.get("periods") or raw.get("history"), 2, MAX_HISTORY, 6)
        if projection:
            query["projection"] = projection
    else:
        query["top"] = _int(raw.get("top"), 1, 20, 12)
        if raw.get("compare") in (True, "true", "sim", 1, "1"):
            query["compare"] = True
    title = re.sub(r"\s+", " ", str(raw.get("title") or "")).strip()[:80]
    if title:
        query["title"] = title
    return query


def query_key(query: dict[str, Any]) -> str:
    return json.dumps(query, sort_keys=True, ensure_ascii=False)


def describe(query: dict[str, Any]) -> str:
    """Nome do gráfico: "Valor fiscal por Division Description (projeção de 3 meses)"."""
    if query.get("title"):
        return query["title"]
    measure = MEASURES[query["measure"]][2]
    if query["dimension"] == "period":
        text = f"Evolução: {measure.lower()}"
        if query.get("projection"):
            text = f"{measure} com projeção de {query['projection']} {'mês' if query['projection'] == 1 else 'meses'}"
    else:
        text = f"{measure} por {DIMENSIONS[query['dimension']][1]}"
    if query.get("filters"):
        text += " · " + "; ".join(f"{DIMENSIONS[key][1]}: {', '.join(values[:3])}" for key, values in query["filters"].items())
    return text


def _where(query: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses, params = [], []
    for key, values in (query.get("filters") or {}).items():
        clauses.append(f"{_label_sql(DIMENSIONS[key][0])} in ({','.join('?' * len(values))})")
        params.extend(values)
    return ("".join(f" and {clause}" for clause in clauses), params)


def _next_period(period: str, months: int) -> str:
    year, month = map(int, period.split("-"))
    index = year * 12 + month - 1 + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def linear_projection(values: list[float], months: int) -> tuple[list[float], float]:
    """Tendência linear (mínimos quadrados) estendida por ``months`` meses; nunca abaixo de zero."""
    n = len(values)
    mean_x, mean_y = (n - 1) / 2, sum(values) / n
    spread = sum((x - mean_x) ** 2 for x in range(n)) or 1
    slope = sum((x - mean_x) * (y - mean_y) for x, y in enumerate(values)) / spread
    return [max(0.0, mean_y + slope * (n - 1 + step - mean_x)) for step in range(1, months + 1)], slope


def dataset(settings: Any, period: str, query: dict[str, Any]) -> dict[str, Any]:
    """Itens do gráfico livre: [{label, value, share?, variation?, projected?}] + unidade, nome e nota de método."""
    if not PERIOD_RE.match(period):
        raise ValueError("Competência inválida.")
    expression, unit, measure_label, additive = MEASURES[query["measure"]]
    where, params = _where(query)
    result: dict[str, Any] = {"title": describe(query), "unit": unit, "measure": measure_label,
                              "dimension": DIMENSIONS[query["dimension"]][1], "items": [], "note": ""}
    with connect(settings.path("database")) as connection:
        ensure_inventory_schema(connection)
        if query["dimension"] == "period":
            rows = connection.execute(
                f"""select period, {expression} from inventory_rows where period <= ? {where}
                    group by period order by period desc limit ?""",
                [period, *params, query.get("periods", 6)],
            ).fetchall()
            history = [(str(row[0]), float(row[1] or 0)) for row in reversed(rows)]
            result["items"] = [{"label": label, "period": label, "value": value} for label, value in history]
            months = int(query.get("projection") or 0)
            if months and len(history) >= 2:
                projected, slope = linear_projection([value for _, value in history], months)
                last = history[-1][0]
                result["items"] += [{"label": _next_period(last, step), "period": _next_period(last, step), "value": value,
                                     "projected": True} for step, value in enumerate(projected, 1)]
                result["projection"] = {"months": months, "basis": [label for label, _ in history], "slope": slope}
                result["note"] = (f"Projeção = tendência linear das {len(history)} competências carregadas "
                                  f"({history[0][0]} a {last}); estimativa, não é número contábil.")
            elif months:
                result["note"] = "Projeção indisponível: é preciso ter pelo menos duas competências carregadas."
        else:
            column = DIMENSIONS[query["dimension"]][0]
            rows = connection.execute(
                f"""select {_label_sql(column)} as label, {expression} as value from inventory_rows
                    where period = ? {where} group by 1 order by 2 desc limit ?""",
                [period, *params, query.get("top", 12)],
            ).fetchall()
            total = 0.0
            if additive:
                total = float(connection.execute(
                    f"select {expression} from inventory_rows where period = ? {where}", [period, *params]).fetchone()[0] or 0)
            items = [{"label": str(row[0]), "value": float(row[1] or 0)} for row in rows]
            for item in items:
                if additive and total:
                    item["share"] = round(100 * item["value"] / total, 1)
            if query.get("compare"):
                previous = connection.execute("select max(period) from inventory_rows where period < ?", [period]).fetchone()[0]
                if previous:
                    before = dict(connection.execute(
                        f"""select {_label_sql(column)}, {expression} from inventory_rows where period = ? {where} group by 1""",
                        [previous, *params]).fetchall())
                    for item in items:
                        old = float(before.get(item["label"]) or 0)
                        item["variation"] = round(100 * (item["value"] - old) / old, 1) if old else None
                    result["previous_period"] = str(previous)
            result["items"] = items
            result["total"] = total if additive else None
    return result
