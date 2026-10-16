"""Visuais inseridos pelo Optimus na Visão e relatórios ("Inserir visuais").

O usuário descreve em português o gráfico que quer; o Optimus (n8n) devolve só uma especificação (tipo, dimensão,
medida, filtros, top) — nunca números. O sistema valida a especificação contra as listas abaixo, calcula os dados na
Base de Estoque da competência (com os mesmos filtros da página) e a página desenha com as MESMAS funções dos gráficos
que já existem, no mesmo card. Os visuais ficam antes de "Evolução do Aging por Material" e entram no HTML e no PDF.

Regras: os gráficos que já existem na página não são alterados; um pedido igual a um gráfico existente não cria
outro (a página leva até ele); cada usuário vê os visuais que inseriu e pode removê-los.
Sem o Optimus (VPN desligada, n8n fora do ar), ``local_interpret`` entende os pedidos simples por palavras-chave.
"""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from datetime import datetime
from typing import Any

from .db import connect
from .inventory import NO_FILTER, _natural_key, aging_race, ensure_inventory_schema, overview_filter_sql
from .presentation_data import DIMENSIONS, MEASURES, _label_sql

# Tipo → estilo da página que ele reproduz. "fixed" = medida fixa do estilo; "series" = usa a segunda dimensão.
TYPES: dict[str, dict[str, Any]] = {
    "barras": {"label": "Barras horizontais", "like": "Valor por centro / Origem do material", "span": 6},
    "barras_quantidade": {"label": "Barras com valor e quantidade", "like": "Local de estoque", "span": 6,
                          "fixed": "fiscal_value"},
    "colunas": {"label": "Colunas com variação vs competência anterior", "like": "Division Description", "span": 6},
    "colunas_agrupadas": {"label": "Barras agrupadas (2 séries)", "like": "Lifecycle × Aging", "span": 6, "series": True},
    "matriz": {"label": "Matriz (mapa de calor com totais)", "like": "Aging for Season", "span": 6, "series": True},
    "evolucao": {"label": "Evolução mês a mês (valor e quantidade)", "like": "Evolução da posição de estoque", "span": 6,
                 "fixed": "fiscal_value", "no_dimension": True},
    "risco_aging": {"label": "Barras empilhadas por faixa de aging", "like": "Risco de obsolescência", "span": 6,
                    "fixed": "fiscal_value"},
    "pareto": {"label": "Pareto do PMM", "like": "PMM analítico", "span": 6, "fixed": "pmm"},
    "pizza": {"label": "Pizza 3D", "like": "Composição do custo fiscal", "span": 6},
    "dispersao": {"label": "Dispersão valor × quantidade", "like": "Dispersão do estoque livre", "span": 12,
                  "fixed": "fiscal_value"},
    "corrida": {"label": "Corrida do aging por material (animada)", "like": "Evolução do Aging por Material", "span": 12,
                "fixed": "aging_days", "no_dimension": True},
    "linhas": {"label": "Linhas", "like": "linha da Evolução da posição (uma ou várias séries)", "span": 6,
               "series_optional": True},
    "tabela": {"label": "Tabela ranking", "like": "tabela (valor, quantidade e aging médio)", "span": 6},
}
# Medidas dos visuais: as das apresentações + aging médio em dias (ponderado pela quantidade livre), para "maior aging".
_AGING_DAYS = ("coalesce(sum(case when unrestricted_quantity>0 then aging_days*unrestricted_quantity end)"
               "/nullif(sum(case when unrestricted_quantity>0 and aging_days is not null then unrestricted_quantity end),0),"
               "avg(aging_days),0)")
VISUAL_MEASURES: dict[str, tuple[str, str, str, bool]] = {**MEASURES, "aging_days": (_AGING_DAYS, "days", "Aging médio (dias)", False)}
BRL_MEASURES = {key for key, value in VISUAL_MEASURES.items() if value[1] == "brl" and value[3]}
# Material pela descrição (Texto breve material), mais legível que o código; "material" continua sendo o código.
VISUAL_DIMENSIONS = {**{key: value for key, value in DIMENSIONS.items() if key != "period"},
                     "material_name": ("material_description", "Material (descrição)")}
MAX_TOP = 30
MAX_VISUALS = 24

# Gráficos que já existem na página: dimensões, medidas e o estilo nativo de cada um (não podem ser alterados).
BUILTINS: list[dict[str, Any]] = [
    {"id": "chart-lifecycle-aging", "title": "Lifecycle × Aging", "dims": [{"lifecycle", "aging"}],
     "measures": {"fiscal_value"}, "type": "colunas_agrupadas"},
    {"id": "matrix-aging-season", "title": "Aging for Season", "dims": [{"year", "season"}], "measures": {"fiscal_value"},
     "type": "matriz"},
    {"id": "chart-division", "title": "Division Description", "dims": [{"division"}],
     "measures": {"fiscal_value", "free_quantity"}, "type": "colunas"},
    {"id": "chart-locations", "title": "Local de estoque", "dims": [{"location"}], "measures": {"fiscal_value", "free_quantity"},
     "type": "barras_quantidade"},
    {"id": "chart-plants", "title": "Valor por centro", "dims": [{"plant"}], "measures": {"fiscal_value"}, "type": "barras"},
    {"id": "chart-origins", "title": "Origem do material", "dims": [{"origin"}], "measures": {"fiscal_value"}, "type": "barras"},
    {"id": "chart-trend", "title": "Evolução da posição de estoque", "dims": [{"period"}],
     "measures": {"fiscal_value", "free_quantity"}, "type": "evolucao"},
    {"id": "chart-division-aging", "title": "Risco de obsolescência", "dims": [{"division", "aging"}],
     "measures": {"fiscal_value"}, "type": "risco_aging"},
    {"id": "chart-pmm-pareto", "title": "PMM analítico", "dims": [{"period"}, {"division"}, {"plant"}, {"location"}, {"season"}],
     "measures": {"pmm"}, "type": "pareto"},
    {"id": "chart-cost-composition", "title": "Composição do custo fiscal", "dims": [set()],
     "measures": {"fob", "import_tax", "other_costs"}, "type": "pizza"},
    {"id": "chart-stock-scatter", "title": "Dispersão do estoque livre",
     "dims": [{"period"}, {"division"}, {"plant"}, {"location"}, {"season"}], "measures": {"scatter"}, "type": "dispersao"},
    {"id": "chart-material-race", "title": "Evolução do Aging por Material", "dims": [set()], "measures": {"aging_days"},
     "type": "corrida"},
]


# ------------------------------------------------------------------ especificação


def _clean_filters(raw: Any) -> dict[str, list[str]]:
    filters: dict[str, list[str]] = {}
    for key, values in (raw.items() if isinstance(raw, dict) else []):
        key = str(key).strip().lower()
        if key not in VISUAL_DIMENSIONS:
            continue
        values = values if isinstance(values, list) else [values]
        chosen = list(dict.fromkeys(str(value).strip()[:80] for value in values if str(value or "").strip()))[:20]
        if chosen:
            filters[key] = chosen
    return filters


def clean_spec(raw: Any) -> dict[str, Any]:
    """Valida a especificação (do Optimus ou do intérprete local). ValueError com o motivo em linguagem simples."""
    if not isinstance(raw, dict):
        raise ValueError("Especificação do gráfico inválida.")
    kind = str(raw.get("type") or "").strip().lower()
    if kind not in TYPES:
        raise ValueError("Tipo de gráfico desconhecido. Tipos possíveis: " + ", ".join(t["label"] for t in TYPES.values()) + ".")
    info = TYPES[kind]
    spec: dict[str, Any] = {"type": kind}
    if not info.get("no_dimension"):
        dimension = str(raw.get("dimension") or "").strip().lower()
        if dimension not in VISUAL_DIMENSIONS:
            raise ValueError("Diga por qual informação agrupar (ex.: divisão, centro, local, season, ano, aging, lifecycle, origem).")
        spec["dimension"] = dimension
    series = str(raw.get("series") or "").strip().lower()
    if info.get("series") or (info.get("series_optional") and series and series not in ("null", "none")):
        if series not in VISUAL_DIMENSIONS or series == spec.get("dimension"):
            raise ValueError("Esse estilo cruza duas informações: diga também a segunda (ex.: divisão × season).")
        spec["series"] = series
    measure = info.get("fixed") or str(raw.get("measure") or "fiscal_value").strip().lower()
    if not info.get("fixed"):
        if measure not in VISUAL_MEASURES:
            raise ValueError("Medida desconhecida. Use valor fiscal, quantidade livre, materiais, PMM, aging médio, acima de 12 meses etc.")
        if kind in ("colunas_agrupadas", "matriz") and measure not in BRL_MEASURES:
            raise ValueError("Esse estilo mostra valores em R$: escolha uma medida em reais (ex.: valor fiscal, acima de 12 meses).")
        if kind == "pizza" and not VISUAL_MEASURES[measure][3]:
            raise ValueError("A pizza mostra partes de um total: escolha uma medida que soma (ex.: valor fiscal, quantidade).")
    spec["measure"] = measure
    # Top por outra medida (ex.: os 5 materiais de maior aging, mostrando o valor fiscal).
    rank_by = str(raw.get("rank_by") or "").strip().lower()
    if rank_by in VISUAL_MEASURES and rank_by != measure and not info.get("fixed"):
        spec["rank_by"] = rank_by
    try:
        top = int(raw.get("top") or 12)
    except (TypeError, ValueError):
        top = 12
    spec["top"] = max(2, min(MAX_TOP, top))
    filters = _clean_filters(raw.get("filters"))
    if filters:
        spec["filters"] = filters
    title = re.sub(r"\s+", " ", str(raw.get("title") or "")).strip()[:80]
    spec["title"] = title or describe(spec)
    return spec


def describe(spec: dict[str, Any]) -> str:
    kind = spec["type"]
    if kind == "evolucao":
        text = "Evolução do valor fiscal e da quantidade livre"
    elif kind == "corrida":
        text = "Corrida do aging por material"
    elif kind == "dispersao":
        text = f"Dispersão valor × quantidade por {VISUAL_DIMENSIONS[spec['dimension']][1]}"
    elif kind == "risco_aging":
        text = f"Faixas de aging por {VISUAL_DIMENSIONS[spec['dimension']][1]}"
    elif kind == "tabela":
        rank = VISUAL_MEASURES[spec.get("rank_by") or spec["measure"]][2].lower()
        text = f"Top {spec['top']} {VISUAL_DIMENSIONS[spec['dimension']][1]} por {rank}"
    else:
        text = f"{VISUAL_MEASURES[spec['measure']][2]} por {VISUAL_DIMENSIONS[spec['dimension']][1]}"
        if spec.get("series"):
            text += f" × {VISUAL_DIMENSIONS[spec['series']][1]}"
    if spec.get("filters"):
        text += " · " + "; ".join(f"{VISUAL_DIMENSIONS[key][1]}: {', '.join(values[:3])}" for key, values in spec["filters"].items())
    return text[:80]


def subtitle(spec: dict[str, Any]) -> str:
    info = TYPES[spec["type"]]
    parts = [info["label"].lower()]
    if spec["type"] not in ("evolucao", "corrida", "risco_aging", "dispersao", "pareto", "tabela"):
        parts.append(VISUAL_MEASURES[spec["measure"]][2].lower())
    if spec.get("rank_by"):  # "top 5 por aging médio (dias)"
        parts.append(f"top {spec['top']} por {VISUAL_MEASURES[spec['rank_by']][2].lower()}")
    elif spec["type"] not in ("evolucao", "matriz", "colunas_agrupadas", "pizza", "linhas") and not info.get("no_dimension"):
        parts.append(f"top {spec['top']}")
    return " · ".join(parts)


def _identity(spec: dict[str, Any]) -> str:
    keys = ("type", "dimension", "series", "measure", "rank_by", "filters")
    return json.dumps({key: spec.get(key) for key in keys}, sort_keys=True, ensure_ascii=False)


def find_duplicate(spec: dict[str, Any], existing: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pedido igual a um gráfico da página (ou a um visual já inserido)? Devolve onde ele está."""
    for item in existing:
        if _identity(item["spec"]) == _identity(spec):
            return {"kind": "custom", "target": f"visual-{item['id']}", "title": item["spec"]["title"], "same_type": True}
    if spec.get("filters"):
        return None  # recorte novo (ex.: valor por centro só de Footwear): não existe na página
    kind = spec["type"]
    dims = {"period"} if kind == "evolucao" else set() if kind == "corrida" else {spec["dimension"], *(
        [spec["series"]] if spec.get("series") else [])} | ({"aging"} if kind == "risco_aging" else set())
    measure = "scatter" if kind == "dispersao" else spec["measure"]
    for builtin in BUILTINS:
        if dims in builtin["dims"] and (measure in builtin["measures"] or kind == builtin["type"] == "corrida"):
            return {"kind": "builtin", "target": builtin["id"], "title": builtin["title"], "same_type": kind == builtin["type"]}
    return None


# ------------------------------------------------------------------ disposição na página (lado a lado)

# Estilos que, sozinhos de ponta a ponta, ficam esticados: o Optimus sugere um par para colocar ao lado.
POOR_FULL_WIDTH = {"pizza", "barras", "barras_quantidade", "pareto", "colunas", "matriz", "colunas_agrupadas"}


def is_wide(spec: dict[str, Any], data: dict[str, Any] | None) -> bool:
    """Ocupa a linha inteira por natureza (dispersão, corrida, matriz com muitas colunas, muitas colunas com variação)."""
    data = data or {}
    return (TYPES[spec["type"]]["span"] == 12
            or (spec["type"] == "matriz" and len(data.get("columns") or []) > 3)
            or (spec["type"] == "colunas" and len(data.get("items") or []) > 7)
            or (spec["type"] == "linhas" and len(data.get("x") or []) > 8))


def needs_partner(spec: dict[str, Any], wide: bool, existing_wide: list[bool]) -> bool:
    """O novo visual ficaria sozinho na linha (número par de visuais de meia largura antes dele) e esticado."""
    halves = sum(1 for flag in existing_wide if not flag)
    return not wide and halves % 2 == 0 and spec["type"] in POOR_FULL_WIDTH


def complements(spec: dict[str, Any], existing: list[dict[str, Any]], limit: int = 2) -> list[dict[str, Any]]:
    """Gráficos que completam a informação do pedido, para ficarem lado a lado (mesma dimensão e filtros)."""
    dimension = spec.get("dimension")
    if not dimension:
        return []
    base = {"dimension": dimension, **({"filters": spec["filters"]} if spec.get("filters") else {})}
    candidates = [
        {"type": "barras", "measure": "free_quantity"}, {"type": "pizza", "measure": "fiscal_value"},
        {"type": "risco_aging"}, {"type": "pareto"}, {"type": "barras", "measure": "over_12_value"},
        {"type": "barras", "measure": "materials"}, {"type": "barras", "measure": "fiscal_value"},
    ]
    chosen: list[dict[str, Any]] = []
    for extra in candidates:
        try:
            candidate = clean_spec({**base, **extra})
        except ValueError:
            continue
        if (candidate["type"], candidate["measure"]) == (spec["type"], spec["measure"]):
            continue
        if any(c["type"] == candidate["type"] for c in chosen) or find_duplicate(candidate, existing + [{"id": "novo", "spec": spec}]):
            continue
        chosen.append(candidate)
        if len(chosen) == limit:
            break
    return chosen


# ------------------------------------------------------------------ dados


def _filters_sql(spec: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses, params = [], []
    for key, values in (spec.get("filters") or {}).items():
        clauses.append(f"{_label_sql(VISUAL_DIMENSIONS[key][0])} in ({','.join('?' * len(values))})")
        params.extend(values)
    return "".join(f" and {clause}" for clause in clauses), params


def dataset(settings: Any, period: str, spec: dict[str, Any], page_filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dados no formato da função de desenho do estilo (os mesmos dos gráficos da página)."""
    kind, top = spec["type"], spec["top"]
    own_where, own_params = _filters_sql(spec)
    page_where, page_params = overview_filter_sql(page_filters)
    where, params = own_where + page_where, [*own_params, *page_params]
    if kind == "corrida":
        return aging_race(settings, period, page_filters, top=min(top, 15), extra=(own_where, own_params))
    expression, unit = VISUAL_MEASURES[spec["measure"]][0], VISUAL_MEASURES[spec["measure"]][1]
    rank = VISUAL_MEASURES[spec.get("rank_by") or spec["measure"]][0]  # quem entra no top (ex.: maior aging médio)
    with connect(settings.path("database")) as connection:
        ensure_inventory_schema(connection)
        if kind == "evolucao":
            rows = connection.execute(
                f"""select period, count(*), coalesce(sum(unrestricted_quantity),0), coalesce(sum(fiscal_total_amount),0)
                      from inventory_rows where period <= ? {where} group by period order by period desc limit 18""",
                [period, *params]).fetchall()
            return {"items": [{"period": str(r[0]), "rows": int(r[1]), "quantity": float(r[2] or 0),
                               "fiscal_value": float(r[3] or 0), "pmm": float(r[3] or 0) / float(r[2]) if r[2] else 0.0}
                              for r in reversed(rows)]}
        label = _label_sql(VISUAL_DIMENSIONS[spec["dimension"]][0])
        if kind == "linhas":
            # Eixo X = dimensão (todos os valores, em ordem natural); uma linha por série (top N pelo critério pedido).
            if spec.get("series"):
                series_sql = _label_sql(VISUAL_DIMENSIONS[spec["series"]][0])
                chosen = [str(r[0]) for r in connection.execute(
                    f"select {series_sql}, {rank} from inventory_rows where period=? {where} group by 1 order by 2 desc limit ?",
                    [period, *params, min(top, 10)]).fetchall()]
                if not chosen:
                    return {"x": [], "series": [], "format": "brl"}
                cells = connection.execute(
                    f"""select {label}, {series_sql}, {expression} from inventory_rows
                         where period=? {where} and {series_sql} in ({','.join('?' * len(chosen))}) group by 1, 2""",
                    [period, *params, *chosen]).fetchall()
            else:
                chosen = [VISUAL_MEASURES[spec["measure"]][2]]
                cells = [(a, chosen[0], v) for a, v in connection.execute(
                    f"select {label}, {expression} from inventory_rows where period=? {where} group by 1", [period, *params]).fetchall()]
            xs = sorted({str(a) for a, _, _ in cells}, key=lambda v: (v != "<2022", _natural_key(v)))[:24]
            lookup = {(str(a), str(b)): float(v or 0) for a, b, v in cells}
            return {"x": xs, "measure": VISUAL_MEASURES[spec["measure"]][2], "dimension": VISUAL_DIMENSIONS[spec["dimension"]][1],
                    "format": {"num": "num", "pct": "pct", "days": "days"}.get(unit, "brl"),
                    "series": [{"label": s, "values": [lookup.get((x, s)) for x in xs]} for s in chosen]}
        if kind == "tabela":
            rows = connection.execute(
                f"""select {label}, count(*), coalesce(sum(unrestricted_quantity),0), coalesce(sum(fiscal_total_amount),0),
                           {VISUAL_MEASURES['aging_days'][0]}, {expression}, {rank}
                      from inventory_rows where period=? {where} group by 1 order by 7 desc limit ?""",
                [period, *params, top]).fetchall()
            return {"dimension": VISUAL_DIMENSIONS[spec["dimension"]][1], "measure": VISUAL_MEASURES[spec["measure"]][2],
                    "measure_format": {"num": "num", "pct": "pct", "days": "days"}.get(unit, "brl"), "measure_key": spec["measure"],
                    "rank_by": VISUAL_MEASURES[spec.get("rank_by") or spec["measure"]][2],
                    "rank_key": {"fiscal_value": "fiscal_value", "free_quantity": "quantity", "aging_days": "aging_days"}.get(
                        spec.get("rank_by") or spec["measure"], "value"),
                    "rows": [{"label": str(r[0]), "rows": int(r[1]), "quantity": float(r[2] or 0), "fiscal_value": float(r[3] or 0),
                              "aging_days": float(r[4] or 0), "value": float(r[5] or 0)} for r in rows]}
        if kind in ("colunas_agrupadas", "matriz", "risco_aging"):
            other = "aging_bucket" if kind == "risco_aging" else VISUAL_DIMENSIONS[spec["series"]][0]
            measure = "coalesce(sum(fiscal_total_amount),0)" if kind == "risco_aging" else expression
            totals = connection.execute(
                f"select {label}, {rank if spec.get('rank_by') else measure} from inventory_rows where period=? {where} group by 1 order by 2 desc limit ?",
                [period, *params, top]).fetchall()
            chosen = [str(r[0]) for r in totals]
            if not chosen:
                return {"rows": [], "columns": [], "values": [], "series": []}
            cells = connection.execute(
                f"""select {label}, {_label_sql(other)}, {measure} from inventory_rows
                     where period=? {where} and {label} in ({','.join('?' * len(chosen))}) group by 1, 2""",
                [period, *params, *chosen]).fetchall()
            lookup = {(str(a), str(b)): float(v or 0) for a, b, v in cells}
            columns = sorted({str(b) for _, b, _ in cells}, key=_natural_key)
            if kind == "colunas_agrupadas":  # 2 séries (as de maior valor), como Active × Inactive
                weight = {c: sum(lookup.get((r, c), 0.0) for r in chosen) for c in columns}
                columns = sorted(sorted(columns, key=lambda c: -weight[c])[:2], key=_natural_key)
                rows_sorted = sorted(chosen, key=_natural_key)
                return {"columns": rows_sorted, "toneByIndex": True, "axisLabel": f"{VISUAL_MEASURES[spec['measure']][2]} (R$)",
                        "ariaLabel": spec["title"],
                        "series": [{"label": c, "values": [lookup.get((r, c), 0.0) for r in rows_sorted]} for c in columns]}
            rows_sorted = chosen if kind == "risco_aging" else sorted(chosen, key=_natural_key)
            if kind == "matriz":
                columns = columns[:14]
            values = [[lookup.get((r, c), 0.0) for c in columns] for r in rows_sorted]
            return {"rows": rows_sorted, "columns": columns, "values": values,
                    "series": [{"label": r, "values": values[i]} for i, r in enumerate(rows_sorted)]}
        rows = connection.execute(
            f"""select {label}, count(*), coalesce(sum(unrestricted_quantity),0), coalesce(sum(fiscal_total_amount),0),
                       {expression}, {rank}
                  from inventory_rows where period=? {where} group by 1 order by 6 desc limit ?""",
            [period, *params, top]).fetchall()
        items = [{"label": str(r[0]), "rows": int(r[1]), "quantity": float(r[2] or 0), "fiscal_value": float(r[3] or 0),
                  "value": float(r[4] or 0)} for r in rows]
        for item in items:
            item["pmm"] = item["fiscal_value"] / item["quantity"] if item["quantity"] else 0.0
        result: dict[str, Any] = {"items": items, "format": {"num": "num", "pct": "pct", "days": "days"}.get(unit, "brl")}
        if kind == "pizza":
            total = float(connection.execute(f"select {expression} from inventory_rows where period=? {where}",
                                             [period, *params]).fetchone()[0] or 0)
            shown = items[:6]
            rest = total - sum(item["value"] for item in shown)
            pie = [{"label": item["label"], "value": item["value"]} for item in shown]
            if rest > 0.005 * max(total, 1):
                pie.append({"label": "Outros", "value": rest})
            return {"items": pie, "format": "num" if unit == "num" else "brl", "shareLabel": "do total"}
        if kind == "colunas" and spec["measure"] in BRL_MEASURES:
            previous = connection.execute("select max(period) from inventory_rows where period < ?", [period]).fetchone()[0]
            if previous:
                before = dict(connection.execute(
                    f"select {label}, {expression} from inventory_rows where period=? {where} group by 1",
                    [previous, *params]).fetchall())
                result["previous_period"] = str(previous)
                result["variance"] = [{"label": item["label"], "current_value": item["value"],
                                       "previous_value": float(before.get(item["label"]) or 0),
                                       "difference": item["value"] - float(before.get(item["label"]) or 0),
                                       "variation_pct": (100 * (item["value"] - float(before[item["label"]])) / abs(float(before[item["label"]]))
                                                         if before.get(item["label"]) else None)} for item in items]
        return result


# ------------------------------------------------------------------ armazenamento (por usuário)


# Visuais da equipe: a mesma lista para todos que acessam o sistema (inserir e remover: só administradores).
# Cada máquina guarda a lista no banco local; a ponte do Drive (Estoque_Cont\visuais\alteracoes\<COMPUTADOR>.json)
# leva as alterações às outras máquinas — vale a mais recente de cada visual, e a remoção também viaja (deleted).
BRIDGE_FOLDER = "visuais"
JOURNAL_FOLDER = "alteracoes"
STATE_KEY = "custom_visuals_state"
FORMAT_VERSION = 1


def ensure_schema(connection: Any) -> None:
    connection.execute(
        """create table if not exists custom_visuals (
               visual_id varchar primary key, owner varchar not null, spec_json varchar not null,
               created_at timestamp not null default current_timestamp)"""
    )
    connection.execute("alter table custom_visuals add column if not exists changed_at varchar")
    connection.execute("alter table custom_visuals add column if not exists deleted boolean default false")


def _entries(connection: Any) -> dict[str, dict[str, Any]]:
    ensure_schema(connection)
    rows = connection.execute(
        "select visual_id, owner, spec_json, created_at, changed_at, coalesce(deleted,false) from custom_visuals").fetchall()
    return {str(r[0]): {"owner": r[1], "spec": r[2], "created_at": str(r[3]), "changed_at": r[4] or str(r[3]),
                        "deleted": bool(r[5])} for r in rows}


def _mark_changed(connection: Any) -> None:
    state = {"publisher": True, "pending_publish": True}
    connection.execute(
        """insert into system_settings(setting_key, setting_value, updated_at) values (?, ?, current_timestamp)
           on conflict(setting_key) do update set setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
        [STATE_KEY, json.dumps(state)])


def list_visuals(settings: Any, owner: str | None = None) -> list[dict[str, Any]]:
    """Visuais da equipe (todos os ativos, na ordem em que foram inseridos). ``owner`` é ignorado (compatibilidade)."""
    with connect(settings.path("database")) as connection:
        entries = _entries(connection)
    result = []
    for visual_id, entry in sorted(entries.items(), key=lambda item: item[1]["created_at"]):
        if entry["deleted"]:
            continue
        try:
            spec = clean_spec(json.loads(entry["spec"]))
        except (ValueError, TypeError):
            continue
        result.append({"id": visual_id, "spec": spec, "created_at": entry["created_at"], "created_by": entry["owner"]})
    return result


def add_visual(settings: Any, owner: str, spec: dict[str, Any]) -> dict[str, Any]:
    if len(list_visuals(settings)) >= MAX_VISUALS:
        raise ValueError(f"Limite de {MAX_VISUALS} visuais inseridos. Remova algum antes de inserir outro.")
    visual_id = uuid.uuid4().hex[:12]
    now = datetime.now()
    with connect(settings.path("database")) as connection:
        ensure_schema(connection)
        connection.execute(
            "insert into custom_visuals(visual_id, owner, spec_json, created_at, changed_at, deleted) values (?,?,?,?,?,false)",
            [visual_id, owner.lower(), json.dumps(spec, ensure_ascii=False), now, now.isoformat(timespec="seconds")])
        _mark_changed(connection)
    return {"id": visual_id, "spec": spec}


def delete_visual(settings: Any, owner: str | None, visual_id: str) -> bool:
    """Remove (para todos) — a rota é exclusiva de administradores. A marca de remoção vai para as outras máquinas."""
    with connect(settings.path("database")) as connection:
        ensure_schema(connection)
        found = connection.execute("select count(*) from custom_visuals where visual_id=? and not coalesce(deleted,false)",
                                   [visual_id]).fetchone()[0]
        if found:
            connection.execute("update custom_visuals set deleted=true, changed_at=? where visual_id=?",
                               [datetime.now().isoformat(timespec="seconds"), visual_id])
            _mark_changed(connection)
    return bool(found)


def sync_visuals(settings: Any, root: Any) -> dict[str, Any]:
    """Publica a lista desta máquina (se ela alterou algo) e aplica as alterações mais novas das outras."""
    import os
    from pathlib import Path

    from .access_sync import _read_json, machine_file_name, machine_name, utc_now

    folder = Path(root) / BRIDGE_FOLDER / JOURNAL_FOLDER
    with connect(settings.path("database")) as connection:
        local = _entries(connection)
        row = connection.execute("select setting_value from system_settings where setting_key=?", [STATE_KEY]).fetchone()
    state = json.loads(row[0]) if row and row[0] else {}
    published = False
    if state.get("publisher") and local:
        target = folder / machine_file_name(settings)
        current = _read_json(target)
        if not current or current.get("entries") != local:
            folder.mkdir(parents=True, exist_ok=True)
            partial = folder / f".{target.name}.parcial"
            partial.write_text(json.dumps({"format": FORMAT_VERSION, "machine": machine_name(settings), "updated_at": utc_now(),
                                           "entries": local}, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(partial, target)
            published = True
    received = 0
    if folder.is_dir():
        newest: dict[str, dict[str, Any]] = {}
        for path in sorted(folder.glob("*.json")):
            payload = _read_json(path)
            if not payload or int(payload.get("format", 0) or 0) > FORMAT_VERSION or not isinstance(payload.get("entries"), dict):
                continue
            for key, entry in payload["entries"].items():
                if isinstance(entry, dict) and (key not in newest or str(entry.get("changed_at") or "") > str(newest[key].get("changed_at") or "")):
                    newest[key] = entry
        with connect(settings.path("database")) as connection:
            ensure_schema(connection)
            for key, entry in newest.items():
                mine = local.get(key)
                if mine is None or str(entry.get("changed_at") or "") > str(mine.get("changed_at") or ""):
                    connection.execute("delete from custom_visuals where visual_id=?", [key])
                    connection.execute(
                        "insert into custom_visuals(visual_id, owner, spec_json, created_at, changed_at, deleted) values (?,?,?,?,?,?)",
                        [key, str(entry.get("owner") or ""), str(entry.get("spec") or "{}"), str(entry.get("created_at") or utc_now())[:19],
                         str(entry.get("changed_at") or ""), bool(entry.get("deleted"))])
                    received += 1
            if published:
                connection.execute("update system_settings set setting_value=? where setting_key=?",
                                   [json.dumps({**state, "pending_publish": False}), STATE_KEY])
    return {"published": published, "received": received}


# ------------------------------------------------------------------ Optimus (n8n) e intérprete local


def catalog(options: dict[str, Any]) -> dict[str, Any]:
    """O que o agente pode usar: tipos, dimensões, medidas, valores de filtro da competência e gráficos existentes."""
    values = {d["key"]: [v["value"] for v in d["values"]][:40] for d in options.get("dimensions", [])}
    return {
        "types": {key: f"{info['label']} (estilo de '{info['like']}')" + (" — precisa de duas dimensões" if info.get("series") else "")
                  + (" — sem dimensão" if info.get("no_dimension") else "") for key, info in TYPES.items()},
        "dimensions": {key: label for key, (_column, label) in VISUAL_DIMENSIONS.items()},
        "measures": {key: value[2] for key, value in VISUAL_MEASURES.items()},
        "filter_values": values,
        "existing_charts": {b["id"]: b["title"] for b in BUILTINS},
    }


def agent_prompt(cat: dict[str, Any], history: list[dict[str, str]], message: str, period: str) -> str:
    turns = "\n".join(f"{'Usuário' if t.get('role') == 'user' else 'Optimus'}: {str(t.get('text') or '')[:400]}"
                      for t in history[-6:])
    return (
        "Tarefa do sistema Estoque Contábil (não é conversa livre): o usuário quer INSERIR um gráfico na página "
        f"Visão e relatórios (competência {period}). Converta o pedido numa especificação. Você NÃO calcula nem inventa "
        "números: o sistema calcula na Base de Estoque. Responda SOMENTE com um JSON entre [[VISUAL]] e [[/VISUAL]], "
        "num destes formatos:\n"
        '1) criar: {"action":"create","reply":"frase curta dizendo o que será inserido","spec":{"type":"<tipo>",'
        '"dimension":"<dimensão>","series":"<segunda dimensão ou null>","measure":"<medida>","rank_by":"<medida do top ou null>",'
        '"top":12,"filters":{"<dimensão>":["valor exato da lista"]},"title":"título curto"}}\n'
        '2) perguntar (só se faltar algo essencial): {"action":"ask","reply":"pergunta curta","options":["opção","opção"]}\n'
        '3) o mesmo gráfico já existe na página (mesmos dados, sem filtro novo): {"action":"exists","builtin":"<id>","reply":"..."}\n'
        '4) impossível com estes dados: {"action":"unsupported","reply":"explique em uma frase"}\n'
        "Regras: use só as chaves do catálogo; filtros só com valores exatos da lista; tipo não pedido → escolha o "
        "estilo mais adequado; 'evolucao' e 'corrida' não têm dimensão; 'colunas_agrupadas' e 'matriz' precisam de "
        "dimension e series diferentes; os gráficos existentes não podem ser alterados. "
        "Gráfico de linhas → type 'linhas': dimension = eixo X (ex.: year, aging, season), series = uma linha por item "
        "(ex.: material_name), measure = eixo Y. Tabela/ranking/lista → type 'tabela' (mostra valor, quantidade e aging médio). "
        "'top N … com maior aging', 'mais antigos', 'mais tempo em estoque' → rank_by 'aging_days' (aging médio em dias); "
        "'top N … de maior valor' → rank_by 'fiscal_value'; o top vale para a series (linhas) ou para a dimension (demais). "
        "Materiais → use 'material_name' (descrição), não 'material' (código), salvo se pedirem o código. "
        "Prefira criar a perguntar ou recusar: só responda unsupported quando não houver nenhum tipo do catálogo que sirva.\n"
        f"Catálogo: {json.dumps(cat, ensure_ascii=False)}\n"
        + (f"Conversa até aqui:\n{turns}\n" if turns else "")
        + f"Pedido atual: {message[:600]}"
    )


def parse_agent_reply(text: str) -> dict[str, Any]:
    match = re.search(r"\[\[VISUAL\]\](.*?)\[\[/VISUAL\]\]", text, re.S)
    raw = match.group(1) if match else text
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("O Optimus não devolveu a especificação do gráfico.")
    data = json.loads(raw[start:end + 1])
    if not isinstance(data, dict) or data.get("action") not in ("create", "ask", "exists", "unsupported"):
        raise ValueError("Resposta do Optimus fora do formato.")
    return data


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if unicodedata.category(c) != "Mn")


_TYPE_WORDS = [
    ("corrida", ["corrida", "race", "animad"]), ("dispersao", ["dispers", "scatter", "bolha"]), ("pareto", ["pareto"]),
    ("pizza", ["pizza", "rosca", "donut", "setor", "pie"]), ("matriz", ["matriz", "mapa de calor", "heatmap", "tabela cruzada"]),
    ("tabela", ["tabela", "ranking", "lista"]), ("linhas", ["grafico de linha", "de linhas", "em linhas", "em linha"]),
    ("risco_aging", ["risco", "obsolesc"]), ("evolucao", ["evolucao", "mes a mes", "historic", "tendencia", "ao longo"]),
    ("colunas_agrupadas", ["agrupad", "lado a lado"]), ("barras_quantidade", ["valor e quantidade", "quantidade e valor"]),
    ("colunas", ["coluna"]), ("barras", ["barra"]),
]
_DIMENSION_WORDS = [
    ("style_color", ["estilo-cor", "estilo cor"]), ("style", ["estilo"]), ("division", ["divis", "categoria"]),
    ("plant", ["centro", "planta"]), ("location", ["local", "deposito", "loja"]), ("season_year", ["season/colecao"]),
    ("season", ["season", "estacao"]), ("year", ["year", "ano da colecao", "por ano", "ano"]),
    ("aging", ["aging", "faixa", "idade"]), ("lifecycle", ["lifecycle", "ciclo de vida"]),
    ("origin", ["origem"]), ("status", ["status"]), ("type", ["tipo de estoque"]), ("material", ["codigo do material", "sku"]),
    ("material_name", ["materia", "produto"]),  # "materia" cobre material e materiais
]
_RANK_AGING = ["maior aging", "maiores aging", "aging medio", "mais antigo", "mais tempo", "dias em estoque"]
_MEASURE_WORDS = [
    ("pmm", ["pmm", "preco medio", "custo medio"]), ("over_12_pct", ["% acima de 12", "percentual acima de 12"]),
    ("over_12_value", ["acima de 12", "mais de 12 meses"]), ("futures_value", ["futures"]), ("fob", ["fob"]),
    ("import_tax", ["imposto de importacao", " ii "]), ("blocked_quantity", ["bloquead"]),
    ("materials", ["quantos materiais", "numero de materiais", "materiais distintos", "qtd de materiais"]),
    ("free_quantity", ["quantidade", "unidades", "pecas", "qtd"]), ("rows", ["linhas da base", "registros"]),
    ("company_value", ["vlr tot emp", "valor empresa"]), ("commercial_value", ["valor comercial", "total cc"]),
]


def _position(text: str, word: str) -> int:
    """Posição da palavra (ou do começo de palavra, ex.: "divis" em "divisão") no texto; -1 se não houver."""
    match = re.search(rf"(?<![a-z0-9]){re.escape(word.strip())}", text) if word.strip() else None
    return match.start() if match else -1


def local_interpret(message: str, options: dict[str, Any]) -> dict[str, Any]:
    """Intérprete por palavras-chave (sem Optimus): entende pedidos simples como "pizza do valor por season"."""
    text = f" {_fold(message)} "
    kind = next((key for key, words in _TYPE_WORDS if any(_position(text, w) >= 0 for w in words)), None)
    found: list[tuple[int, str]] = []
    for key, words in _DIMENSION_WORDS:
        positions = [p for p in (_position(text, w) for w in words) if p >= 0]
        if positions and not any(key in ("style", "season") and other in ("style_color", "season_year") for _, other in found):
            found.append((min(positions), key))
    dims = [key for _, key in sorted(found)]
    rank_by = "aging_days" if any(_position(text, w) >= 0 for w in _RANK_AGING) else None
    if rank_by:  # "maior aging" é critério do top, não a dimensão "faixa de aging"
        dims = [d for d in dims if d != "aging"] or dims
    measure = next((key for key, words in _MEASURE_WORDS if any(_position(text, w) >= 0 for w in words)), "fiscal_value")
    top = re.search(r"top\s*(\d{1,2})|(\d{1,2})\s*(?:maiores|principais|primeiros)", text)
    filters: dict[str, list[str]] = {}
    for dimension in options.get("dimensions", []):
        for item in dimension["values"]:
            value = str(item["value"])
            folded = _fold(value)
            if len(folded) >= 2 and folded != "nao informado" and re.search(rf"(?<![\w-]){re.escape(folded)}(?![\w-])", text):
                if dimension["key"] not in dims[:1]:
                    filters.setdefault(dimension["key"], []).append(value)
    dims = [d for d in dims if d not in filters or d == (dims[0] if dims else None)]
    if kind is None:
        kind = "evolucao" if not dims and "evolu" in text else "colunas_agrupadas" if len(dims) >= 2 else "barras"
    if kind in ("colunas_agrupadas", "matriz") and len(dims) < 2:
        kind = "barras" if dims else kind
    if kind == "barras" and measure == "pmm":
        kind = "pareto"
    raw = {"type": kind, "dimension": dims[0] if dims else None, "series": dims[1] if len(dims) > 1 else None,
           "measure": measure, "rank_by": rank_by, "filters": filters,
           "top": int(next(g for g in top.groups() if g)) if top else 12}
    spec = clean_spec(raw)
    return {"action": "create", "reply": f"Vou inserir: {spec['title']}.", "spec": spec}
