"""Apresentações animadas do Optimus (HTML único, offline), sobre o html-ppt-skill (MIT, ver presentation_assets).

Divisão de trabalho:
- o AGENTE decide o conteúdo: roteiro, títulos-mensagem, textos de insight e quais gráficos/indicadores entram
  (um "spec" JSON com layouts deste catálogo);
- o SISTEMA valida o spec e desenha cada slide com os números reais da competência (os mesmos da Visão e
  relatórios), gráficos em SVG animados e o runtime de navegação embutido. Nenhum número de gráfico, KPI ou
  tabela vem do texto do agente.

Cada apresentação fica em %LOCALAPPDATA%/OpsContabil/presentations/<id>/ com versões (v1, v2...) do spec e do
HTML; o download sai em HTML único ou ZIP.
"""

from __future__ import annotations

import html
import io
import json
import re
import unicodedata
import uuid
import zipfile
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any

ASSETS = Path(__file__).with_name("presentation_assets")
FX_MODULES = ("_util", "constellation", "gradient-blob", "data-stream", "orbit-ring", "particle-burst")
THEMES: dict[str, str] = {
    "estoque-contabil": "azul-marinho do Estoque Contábil, acentos ciano/lilás/laranja (padrão)",
    "tokyo-night": "escuro técnico",
    "corporate-clean": "claro corporativo",
    "minimal-white": "claro minimalista",
    "arctic-cool": "claro azul frio",
    "aurora": "escuro com gradiente aurora",
    "pitch-deck-vc": "executivo de alto contraste",
    "swiss-grid": "suíço tipográfico",
    "editorial-serif": "editorial com serifa",
    "nord": "escuro nórdico",
    "catppuccin-mocha": "escuro suave",
}
DEFAULT_THEME = "estoque-contabil"
LAYOUTS = ("cover", "agenda", "section", "kpis", "chart", "flow", "bullets", "columns", "table", "highlight", "closing")
FLOWS: dict[str, str] = {
    "aging_flow": "Fluxo do valor fiscal: Futures × recebido → até 12 meses × acima de 12 meses → Active × Inactive (animado e clicável)",
}
CHARTS: dict[str, str] = {
    "lifecycle_aging": "Lifecycle × Aging (valor por faixa de aging, Active/Inactive)",
    "aging_season": "Aging for Season (ano × season)",
    "division": "Division Description (valor e variação)",
    "risk": "Risco de obsolescência (% recebido com mais de 12 meses por divisão)",
    "location": "Local de estoque",
    "evolution": "Evolução da posição de estoque (valor e PMM por competência)",
    "pmm_division": "PMM analítico por divisão",
    "cost": "Composição do custo fiscal (FOB, II, Outros)",
    "origin": "Origem do material",
}
KPIS: dict[str, str] = {
    "fiscal_value": "Valor fiscal",
    "free_quantity": "Utilização livre",
    "materials": "Materiais",
    "pmm": "Média PMM",
    "coverage": "Cobertura All Brazil",
    "over_12_months": "Estoque com mais de 12 meses",
}
TABLES: dict[str, str] = {
    "division": "Divisões: valor, participação, variação e PMM",
    "location": "Locais de estoque: valor e participação",
    "aging": "Faixas de aging: valor, participação, Active e Inactive",
}
MAX_SLIDES = 16
MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
          "novembro", "dezembro")
MONTHS_SHORT = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


# ------------------------------------------------------------------ formatação


def _num(value: float, digits: int = 0) -> str:
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


# Formato dos números do slide sendo desenhado (pedido de revisão): {"format": "short"|"full", "decimals": 0-2}.
# Muda só a forma de escrever; o valor é sempre o do sistema.
NUMBER_FMT: ContextVar[dict[str, Any]] = ContextVar("NUMBER_FMT", default={})


def brl(value: float) -> str:
    opts = NUMBER_FMT.get()
    if opts.get("format") == "full":
        return f"R$ {_num(value, opts.get('decimals', 0 if abs(value) >= 1000 else 2))}"
    amount = abs(value)
    for limit, suffix, digits in ((1e9, "bi", 2), (1e6, "mi", 1), (1e3, "mil", 1)):
        if amount >= limit:
            return f"R$ {_num(value / limit, opts.get('decimals', digits))} {suffix}"
    return f"R$ {_num(value, opts.get('decimals', 2))}"


def pct(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "—"
    return (f"{value:+.1f}" if signed else f"{value:.1f}").replace(".", ",") + "%"


def period_label(period: str) -> str:
    year, month = period.split("-")
    return f"{MONTHS[int(month) - 1]}/{year}"


def period_short(period: str) -> str:
    year, month = period.split("-")
    return f"{MONTHS_SHORT[int(month) - 1]}/{year[2:]}"


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _brand(text: str) -> str:
    """A empresa nas apresentações é a Fisia (o agente às vezes escreve Grupo SBF)."""
    for article, female in (("do", "da"), ("no", "na"), ("pelo", "pela"), ("ao", "à"), ("o", "a")):  # concordância
        text = re.sub(rf"\b{article}\s+Grupo\s+SBF\b", f"{female} Fisia", text, flags=re.I)
    return re.sub(r"\bSBF\b", "Fisia", re.sub(r"\bGrupo\s+SBF\b", "Fisia", text, flags=re.I))


def _clip(value: Any, limit: int) -> str:
    text = _brand(re.sub(r"\s+", " ", str(value or "")).strip())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


# ------------------------------------------------------------------ catálogo para o agente


def catalog() -> dict[str, Any]:
    return {
        "layouts": {
            "cover": "capa: kicker, title, subtitle, tags (até 4 rótulos curtos)",
            "agenda": "roteiro: title, items (3 a 6 tópicos)",
            "kpis": "indicadores: title, kpis (2 a 4 ids de kpis), insight",
            "chart": "gráfico do sistema: title (frase-mensagem), chart (id), insight, points (até 3 frases curtas)",
            "bullets": "lista numerada: title, lead (frase de apoio), items (até 5)",
            "columns": "3 colunas: title, columns [{label, title, text}] (até 3)",
            "table": "tabela do sistema: title, table (id), insight",
            "highlight": "número de destaque: title, kpi (id) ou statement (frase curta), caption",
            "section": "abertura de capítulo com número grande: title, lede (1 frase)",
            "flow": "fluxograma animado e clicável do sistema: title, flow (id de flows), insight",
            "closing": "encerramento: title, subtitle",
        },
        "charts": CHARTS,
        "kpis": KPIS,
        "tables": TABLES,
        "flows": FLOWS,
        "themes": list(THEMES),
    }


# ------------------------------------------------------------------ spec: validação e padrão


def _items(value: Any, limit: int, size: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clip(item, size) for item in value if str(item or "").strip()][:limit]


# Forma editável pelo agente (nunca os valores). Cores: #hex, rgb() ou nomes abaixo; tamanhos em escala 0,5–2,5.
COLOR_NAMES = {
    "destaque": "var(--accent)", "accent": "var(--accent)", "accent-2": "var(--accent-2)", "accent-3": "var(--accent-3)",
    "texto": "var(--text-1)", "text": "var(--text-1)", "suave": "var(--text-3)", "fundo": "var(--bg)",
    "branco": "#ffffff", "white": "#ffffff", "preto": "#0b1220", "black": "#0b1220", "laranja": "#f58634", "orange": "#f58634",
    "azul": "#3b82f6", "blue": "#3b82f6", "azul-claro": "#6dd8ff", "azul-escuro": "#0b2545", "marinho": "#0b2545",
    "verde": "#22c55e", "green": "#22c55e", "vermelho": "#ef4444", "red": "#ef4444", "amarelo": "#facc15", "yellow": "#facc15",
    "roxo": "#a78bfa", "lilas": "#a6a0ff", "purple": "#a78bfa", "cinza": "#94a3b8", "gray": "#94a3b8", "rosa": "#f472b6",
    "verde-claro": "#86efac", "verde-escuro": "#15803d", "verde-agua": "#5eead4", "laranja-claro": "#fdba74",
    "laranja-escuro": "#c2410c", "vermelho-claro": "#fca5a5", "vermelho-escuro": "#b91c1c", "amarelo-claro": "#fde68a",
    "roxo-claro": "#c4b5fd", "roxo-escuro": "#6d28d9", "cinza-claro": "#cbd5e1", "cinza-escuro": "#475569",
    "rosa-claro": "#f9a8d4", "dourado": "#eab308", "ciano": "#22d3ee", "turquesa": "#2dd4bf", "magenta": "#d946ef",
    "light-green": "#86efac", "lightgreen": "#86efac", "dark-green": "#15803d", "light-blue": "#6dd8ff", "dark-blue": "#0b2545",
    "navy": "#0b2545", "gold": "#eab308", "pink": "#f472b6", "cyan": "#22d3ee", "teal": "#2dd4bf",
}
# Paleta dos botões do painel "Ajustar com o Optimus" (escolha sem precisar adivinhar o nome da cor).
PALETTE_CHOICES = (("Laranja", "#f58634"), ("Verde", "#22c55e"), ("Verde claro", "#86efac"), ("Azul", "#3b82f6"),
                   ("Azul claro", "#6dd8ff"), ("Azul escuro", "#0b2545"), ("Roxo", "#a78bfa"), ("Vermelho", "#ef4444"),
                   ("Amarelo", "#facc15"), ("Cinza", "#94a3b8"), ("Branco", "#ffffff"))
STYLE_PROPS = ("color", "background", "border", "bold", "italic", "size", "hidden", "highlight")
DEFAULT_KIND = {"aging_season": "matrix", "evolution": "columns", "cost": "donut"}  # demais: barras
CHART_OPTS = ("type", "sort", "top", "only", "hide", "highlight", "values", "share", "variation", "color", "colors", "series")
NUMBER_OPTS = ("format", "decimals")
TARGET_RE = re.compile(r"^[a-z]+(:[^\"'<>\\{}]{1,80})?$")


def _color(value: Any) -> str | None:
    text = refkey(value).replace(" ", "-").replace("_", "-")
    if text in COLOR_NAMES:
        return COLOR_NAMES[text]
    if text.replace("-", "") in COLOR_NAMES:  # "verdeclaro", "azulescuro"
        return COLOR_NAMES[text.replace("-", "")]
    raw = str(value or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", raw):
        return raw.lower()
    match = re.fullmatch(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(,\s*(0|1|0?\.\d+)\s*)?\)", raw)
    if match and all(int(match.group(i)) <= 255 for i in (1, 2, 3)):
        return raw.replace(" ", "")
    return None


def _flag(value: Any) -> bool:
    return value is True or str(value).strip().lower() in ("true", "1", "sim", "yes")


def clean_style(props: Any) -> dict[str, Any]:
    if not isinstance(props, dict):
        return {}
    clean: dict[str, Any] = {}
    for key in ("color", "background", "border"):
        if key in props and _color(props[key]):
            clean[key] = _color(props[key])
    for key in ("bold", "italic", "hidden", "highlight"):
        if key in props:
            clean[key] = _flag(props[key])
    if "size" in props:
        try:
            clean["size"] = round(min(2.5, max(0.5, float(props["size"]))), 2)
        except (TypeError, ValueError):
            pass
    return clean


def clean_styles(styles: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(styles, dict):
        return {}
    clean = {}
    for target, props in list(styles.items())[:60]:
        key = refkey(target)
        if TARGET_RE.match(key) and clean_style(props):
            clean[key] = clean_style(props)
    return clean


def clean_chart_opts(opts: Any) -> dict[str, Any]:
    if not isinstance(opts, dict):
        return {}
    clean: dict[str, Any] = {}
    if opts.get("type") in (*CHART_TYPES, "matrix"):
        clean["type"] = opts["type"]
    if opts.get("sort") in ("desc", "asc", "label"):
        clean["sort"] = opts["sort"]
    try:
        if opts.get("top"):
            clean["top"] = max(1, min(20, int(opts["top"])))
    except (TypeError, ValueError):
        pass
    for key in ("only", "hide", "highlight"):
        if isinstance(opts.get(key), list):
            clean[key] = [_clip(item, 60) for item in opts[key] if str(item or "").strip()][:20]
    for key in ("values", "share", "variation"):
        if key in opts:
            clean[key] = _flag(opts[key])
    if _color(opts.get("color")):
        clean["color"] = _color(opts["color"])
    for key in ("colors", "series"):  # colors: por item (rótulo); series: por série (Active, Inactive...)
        if isinstance(opts.get(key), dict):
            colors = {_clip(label, 60): _color(color) for label, color in list(opts[key].items())[:20] if _color(color)}
            if colors:
                clean[key] = colors
    return clean


def rejected_colors(op: dict[str, Any]) -> list[dict[str, Any]]:
    """Cores de uma operação que o sistema não reconheceu (viram botões de paleta no painel)."""
    found, values = [], op.get("set") if isinstance(op.get("set"), dict) else {}
    for key in ("color", "background", "border"):
        if values.get(key) not in (None, "") and not _color(values[key]):
            found.append({"op": op, "field": key, "value": str(values[key])[:40]})
    for key in ("colors", "series"):
        for label, color in (values.get(key) or {}).items() if isinstance(values.get(key), dict) else []:
            if not _color(color):
                found.append({"op": op, "field": f"{key}.{label}", "value": str(color)[:40]})
    return found


def color_choices(rejected: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Botões de cor para refazer a operação recusada com uma cor válida (aplicada direto pelo sistema)."""
    if not rejected:
        return None
    first = rejected[0]
    options = []
    for name, hex_color in PALETTE_CHOICES:
        op = json.loads(json.dumps(first["op"]))
        if "." in first["field"]:
            key, label = first["field"].split(".", 1)
            op["set"][key][label] = hex_color
        else:
            op["set"][first["field"]] = hex_color
        options.append({"label": name, "color": hex_color, "patch": {"ops": [op]}})
    return {"title": f"Não reconheci a cor “{first['value']}”. Escolha uma:", "options": options}


def clean_number_opts(opts: Any) -> dict[str, Any]:
    if not isinstance(opts, dict):
        return {}
    clean: dict[str, Any] = {}
    if opts.get("format") in ("short", "full"):
        clean["format"] = opts["format"]
    try:
        if opts.get("decimals") is not None:
            clean["decimals"] = max(0, min(2, int(opts["decimals"])))
    except (TypeError, ValueError):
        pass
    return clean


def normalize_spec(spec: Any, facts: dict[str, Any]) -> dict[str, Any]:
    """Valida o spec do agente: só layouts, gráficos, KPIs e tabelas do catálogo; textos escapados e limitados."""
    if not isinstance(spec, dict):
        raise ValueError("O roteiro da apresentação precisa ser um objeto JSON.")
    period = facts["period"]
    theme = str(spec.get("theme") or DEFAULT_THEME)
    clean: dict[str, Any] = {
        "title": _clip(spec.get("title") or f"Posição contábil do estoque · {period_label(period)}", 90),
        "subtitle": _clip(spec.get("subtitle") or "Visão e relatórios", 120),
        "theme": theme if theme in THEMES else DEFAULT_THEME,
        "slides": [],
    }
    for key, cleaner in (("styles", clean_styles), ("number_opts", clean_number_opts)):  # valem para todos os slides
        if cleaner(spec.get(key)):
            clean[key] = cleaner(spec.get(key))
    for raw in spec.get("slides") or []:
        if not isinstance(raw, dict) or raw.get("layout") not in LAYOUTS:
            continue
        slide: dict[str, Any] = {"layout": raw["layout"], "kicker": _clip(raw.get("kicker"), 48),
                                 "title": _clip(raw.get("title"), 110), "notes": _clip(raw.get("notes"), 1200)}
        layout = slide["layout"]
        if layout == "cover":
            slide.update(subtitle=_clip(raw.get("subtitle"), 180), tags=_items(raw.get("tags"), 4, 28))
        elif layout == "agenda":
            slide.update(items=_items(raw.get("items"), 6, 90))
        elif layout == "kpis":
            ids = [item for item in (raw.get("kpis") or []) if item in KPIS][:4]
            slide.update(kpis=ids or ["fiscal_value", "free_quantity", "pmm", "materials"], insight=_clip(raw.get("insight"), 220))
        elif layout == "chart":
            if raw.get("chart") not in CHARTS:
                continue
            slide.update(chart=raw["chart"], insight=_clip(raw.get("insight"), 260), points=_items(raw.get("points"), 3, 140))
        elif layout == "bullets":
            slide.update(lead=_clip(raw.get("lead"), 200), items=_items(raw.get("items"), 5, 150))
        elif layout == "columns":
            columns = [
                {"label": _clip(col.get("label"), 30), "title": _clip(col.get("title"), 60), "text": _clip(col.get("text"), 220)}
                for col in (raw.get("columns") or []) if isinstance(col, dict)
            ][:3]
            if not columns:
                continue
            slide.update(columns=columns)
        elif layout == "table":
            if raw.get("table") not in TABLES:
                continue
            slide.update(table=raw["table"], insight=_clip(raw.get("insight"), 220))
        elif layout == "section":
            slide.update(lede=_clip(raw.get("lede") or raw.get("subtitle"), 200))
        elif layout == "flow":
            if raw.get("flow") not in FLOWS:
                continue
            slide.update(flow=raw["flow"], insight=_clip(raw.get("insight"), 260))
        elif layout == "highlight":
            slide.update(kpi=raw.get("kpi") if raw.get("kpi") in KPIS else None,
                         statement=_clip(raw.get("statement"), 40), caption=_clip(raw.get("caption"), 200))
        elif layout == "closing":
            slide.update(subtitle=_clip(raw.get("subtitle"), 180))
        if not slide["title"] and layout not in ("highlight",):
            continue
        for key, cleaner in (("styles", clean_styles), ("number_opts", clean_number_opts), ("chart_opts", clean_chart_opts)):
            if cleaner(raw.get(key)) and (key != "chart_opts" or layout == "chart"):
                slide[key] = cleaner(raw.get(key))
        if slide.get("chart_opts", {}).get("type") == DEFAULT_KIND.get(slide.get("chart"), "bars"):
            slide["chart_opts"].pop("type")  # "trocar" para o tipo que já é o padrão não é mudança
            if not slide["chart_opts"]:
                slide.pop("chart_opts")
        clean["slides"].append(slide)
    slides = [s for s in clean["slides"] if s["layout"] not in ("cover", "closing")][: MAX_SLIDES - 2]
    cover = next((s for s in clean["slides"] if s["layout"] == "cover"), None) or {
        "layout": "cover", "kicker": f"ESTOQUE CONTÁBIL · {period_label(period).upper()}", "title": clean["title"],
        "subtitle": clean["subtitle"], "tags": [], "notes": ""}
    closing = next((s for s in clean["slides"] if s["layout"] == "closing"), None) or {
        "layout": "closing", "kicker": "", "title": "", "subtitle": clean["title"], "notes": ""}
    year, month = period.split("-")
    closing["title"] = f"Fisia - {month}/{year}"  # sempre assim no último slide (competência da apresentação)
    clean["slides"] = [cover, *slides, closing]
    if len(clean["slides"]) < 3:
        raise ValueError("O roteiro precisa de pelo menos um slide de conteúdo.")
    return clean


def chart_story(chart: str, facts: dict[str, Any]) -> tuple[str, str, list[str]]:
    """Título-mensagem, insight e tópicos de um gráfico escritos só com os fatos (sem o agente)."""
    k, charts = facts["kpis"], facts["charts"]
    variation = k.get("variation_pct_vs_previous") or {}
    previous = f" vs {period_short(facts['previous_period'])}" if facts.get("previous_period") else ""
    risk = charts["Risco de obsolescência"]
    total_risk = risk["all_divisions_total"]
    if chart == "lifecycle_aging":
        aging = charts["Lifecycle × Aging"]["by_aging_bucket"]
        if not aging:
            return "Aging do estoque", "", []
        heaviest = max(aging, key=lambda item: item["value"])
        return (f"A faixa {_bucket(heaviest)} concentra {pct(heaviest['share_pct'])} do valor",
                f"Estoque recebido com mais de 12 meses: {brl(total_risk['over_12_months_value'])} "
                f"({pct(total_risk['over_12_months_pct_of_received'])} do recebido).",
                [f"{_bucket(item)}: {brl(item['value'])} ({pct(item['share_pct'])})"
                 for item in sorted(aging, key=lambda item: item["value"], reverse=True)[:3]])
    if chart == "aging_season":
        years = sorted(charts["Aging for Season"]["by_year"], key=lambda item: item["value"], reverse=True)
        cells = charts["Aging for Season"].get("largest_cells") or []
        return (f"A coleção {years[0]['year']} responde por {pct(years[0]['share_pct'])} do valor" if years else "Coleções e seasons",
                f"Maior célula: {cells[0]['season']} {cells[0]['year']} com {brl(cells[0]['value'])} ({pct(cells[0]['share_pct'])})." if cells else "",
                [f"{c['season']} {c['year']}: {brl(c['value'])}" for c in cells[1:3]])
    if chart == "division":
        divisions = charts["Division Description"]
        if not divisions:
            return "Divisões", "", []
        return (f"{divisions[0]['division']} responde por {pct(divisions[0]['share_pct'])} do valor",
                "Variação contra a competência anterior ao lado de cada divisão." if previous else "",
                [f"{item['division']}: {brl(item['value'])}" + (f" ({pct(item['variation_pct_vs_previous'], True)}{previous})"
                                                                 if item["variation_pct_vs_previous"] is not None else "")
                 for item in divisions[:3]])
    if chart == "risk":
        riskiest = max(risk["by_division"], key=lambda item: item["over_12_months_pct_of_received"]) if risk["by_division"] else None
        return (f"{riskiest['division']} tem o maior peso acima de 12 meses" if riskiest else "Risco de obsolescência",
                f"Total acima de 12 meses: {brl(total_risk['over_12_months_value'])} em todas as divisões "
                f"({pct(total_risk['over_12_months_pct_of_received'])} do recebido).",
                [f"{item['division']}: {pct(item['over_12_months_pct_of_received'])} do recebido" for item in risk["by_division"][:3]])
    if chart == "pmm_division":
        pmm = charts["PMM analítico"]
        ordered = sorted(pmm["by_division"], key=lambda item: item["pmm"], reverse=True)
        return (f"PMM da competência em {brl(pmm['pmm'])}" + (f" ({pct(pmm['variation_pct_vs_previous'], True)}{previous})"
                                                               if pmm["variation_pct_vs_previous"] is not None else ""),
                f"{ordered[0]['division']} tem o maior PMM: {brl(ordered[0]['pmm'])}." if ordered else "",
                [f"{item['division']}: {brl(item['pmm'])}" for item in ordered[1:3]])
    if chart == "location":
        locations = charts["Local de estoque"]
        return (f"{locations[0]['location']} concentra {pct(locations[0]['share_pct'])} do valor" if locations else "Locais de estoque",
                f"Os dois maiores locais somam {pct(sum(item['share_pct'] for item in locations[:2]))} do valor fiscal." if len(locations) > 1 else "",
                [f"{item['location']}: {brl(item['value'])}" for item in locations[:3]])
    if chart == "evolution":
        trend = charts["Evolução da posição de estoque"]
        return ("Evolução da posição de estoque",
                f"Variação do valor fiscal{previous}: {pct(variation.get('fiscal_value'), True)}; PMM {pct(variation.get('pmm'), True)}."
                if variation.get("fiscal_value") is not None else "",
                [f"{period_short(item['period'])}: {brl(item['fiscal_value'])}" for item in trend[-3:]])
    if chart == "cost":
        cost = charts["Composição do custo fiscal"]
        return (f"FOB responde por {pct(cost['fob_pct'])} do custo fiscal",
                f"Imposto de importação em {pct(cost['ii_pct'])} e outros custos em {pct(cost['others_pct'])}.", [])
    if chart == "origin":
        origins = charts["Origem do material"]
        return (f"{_clip(origins[0]['origin'], 40)} soma {pct(origins[0]['share_pct'])} do valor" if origins else "Origem do material",
                "", [f"{_clip(item['origin'], 40)}: {brl(item['value'])}" for item in origins[:3]])
    return CHARTS.get(chart, ""), "", []


def flow_story(facts: dict[str, Any]) -> str:
    aging = facts["charts"]["Lifecycle × Aging"]["by_aging_bucket"]
    total = sum(item["value"] for item in aging) or 1
    futures = sum(item["value"] for item in aging if item["bucket"].startswith("0)"))
    over = sum(item["value"] for item in aging if item["bucket"][:2] in ("5)", "6)", "7)", "8)"))
    return (f"Futures somam {brl(futures)} ({pct(100 * futures / total)}); do recebido, {brl(over)} "
            f"({pct(100 * over / ((total - futures) or 1))}) têm mais de 12 meses. Clique nos blocos para ver o detalhe.")


def attention_columns(facts: dict[str, Any]) -> list[dict[str, str]]:
    charts = facts["charts"]
    risk = charts["Risco de obsolescência"]
    riskiest = max(risk["by_division"], key=lambda item: item["over_12_months_pct_of_received"]) if risk["by_division"] else None
    inactive = {item["label"]: item for item in charts["Lifecycle × Aging"]["by_lifecycle"]}.get("Inactive")
    unmapped = charts.get("Centros sem local no Mapping") or []
    return [
        {"label": "Obsolescência", "title": f"{brl(risk['all_divisions_total']['over_12_months_value'])} acima de 12 meses",
         "text": f"{pct(risk['all_divisions_total']['over_12_months_pct_of_received'])} do estoque já recebido"
                 + (f"; maior peso em {riskiest['division']} ({pct(riskiest['over_12_months_pct_of_received'])})." if riskiest else ".")},
        {"label": "Lifecycle", "title": f"Inactive em {pct(inactive['share_pct'])} do valor" if inactive else "Lifecycle",
         "text": f"{pct(inactive['over_12_months_pct_of_received'])} do Inactive recebido tem mais de 12 meses ({brl(inactive['value'])})."
                 if inactive else "Sem estoque Inactive na competência."},
        {"label": "Mapping", "title": f"{len(unmapped)} centro(s) sem local" if unmapped else "Locais mapeados",
         "text": ("Cadastre no Mapping: " + ", ".join(f"{item['plant']} ({brl(item['value'])})" for item in unmapped[:3]) + ".")
                 if unmapped else "Todos os centros da competência têm local no Mapping."},
    ]


def auto_texts(spec: dict[str, Any], facts: dict[str, Any]) -> None:
    """Completa com os fatos os textos que o agente não devolveu (nunca sobrescreve o que ele escreveu)."""
    k, period = facts["kpis"], facts["period"]
    sections = [s.get("title") for s in spec["slides"] if s.get("layout") == "section" and s.get("title")]
    topics = sections or [re.sub(r"^\s*\d{1,2}\s*/\s*", "", s.get("kicker") or "").strip().capitalize()
                          for s in spec["slides"] if s.get("layout") not in ("cover", "agenda", "closing") and s.get("kicker")]
    for slide in spec["slides"]:
        layout = slide.get("layout")
        if layout == "cover":
            if not slide.get("subtitle"):
                slide["subtitle"] = f"Principais indicadores da competência {period_label(period)}."
            if not slide.get("tags"):
                slide["tags"] = ["Visão e relatórios", "Aging", "PMM", "Divisões"]
        elif layout == "agenda" and not slide.get("items"):
            slide["items"] = list(dict.fromkeys(t for t in topics if t))[:6] or ["Visão geral", "Aging", "Divisões", "Pontos de atenção"]
        elif layout == "kpis" and not slide.get("insight"):
            slide["insight"] = (f"{_num(k['materials'])} materiais na competência; cobertura All Brazil de "
                                f"{pct(k['all_brazil_coverage_pct'])}.")
        elif layout == "chart" and slide.get("chart") in CHARTS:
            story = dict(zip(("title", "insight", "points"), chart_story(slide["chart"], facts)))
            for name, value in story.items():
                if not slide.get(name):
                    slide[name] = value
        elif layout == "flow" and not slide.get("insight"):
            slide["insight"] = flow_story(facts)
        elif layout == "columns" and not slide.get("columns"):
            slide["columns"] = attention_columns(facts)
        elif layout == "highlight" and not slide.get("caption") and slide.get("kpi") in KPIS:
            slide["caption"] = kpi_value(slide["kpi"], facts)[1]
        elif layout == "closing" and not slide.get("subtitle"):
            slide["subtitle"] = f"Estoque Contábil · competência {period_label(period)}"
        elif layout == "table" and not slide.get("insight") and slide.get("table") == "division":
            slide["insight"] = chart_story("division", facts)[1]


def default_spec(facts: dict[str, Any]) -> dict[str, Any]:
    """Roteiro montado pelo sistema (quando o agente não responde): mesmos gráficos, textos só com fatos do evento."""
    k, period = facts["kpis"], facts["period"]
    variation = k.get("variation_pct_vs_previous") or {}
    risk = facts["charts"]["Risco de obsolescência"]["all_divisions_total"]
    chart = lambda chart_id, theme: {"layout": "chart", "kicker": theme, "chart": chart_id}  # noqa: E731
    slides = [
        {"layout": "cover", "kicker": f"POSIÇÃO CONTÁBIL · {period_label(period).upper()}", "title": "Estoque Fisia",
         "tags": ["Visão e relatórios", "Aging", "PMM", "Divisões"]},
        {"layout": "agenda", "kicker": "ROTEIRO", "title": "O que esta apresentação cobre"},
        {"layout": "kpis", "kicker": "VISÃO GERAL",
         "title": f"Valor fiscal de {brl(k['fiscal_value'])}" + (f", {pct(variation.get('fiscal_value'), True)} no mês"
                                                                if variation.get("fiscal_value") is not None else ""),
         "kpis": ["fiscal_value", "free_quantity", "pmm", "over_12_months"]},
        {"layout": "section", "kicker": "AGING", "title": "Aging e lifecycle",
         "lede": "Onde está o valor fiscal: o que ainda não chegou, o recente e o que passou de 12 meses."},
        {"layout": "flow", "kicker": "AGING", "flow": "aging_flow",
         "title": f"{pct(risk['over_12_months_pct_of_received'])} do estoque recebido passou de 12 meses"},
        chart("lifecycle_aging", "AGING"),
        chart("aging_season", "COLEÇÕES"),
        {"layout": "section", "kicker": "DIVISÕES", "title": "Divisões, PMM e locais",
         "lede": "Quem concentra o valor, o custo médio por unidade e onde o estoque está."},
        chart("division", "DIVISÕES"),
        chart("risk", "RISCO"),
        chart("pmm_division", "PMM"),
        chart("evolution", "EVOLUÇÃO"),
        chart("location", "LOCAIS"),
        {"layout": "columns", "kicker": "ATENÇÃO", "title": "Pontos de atenção da competência"},
        {"layout": "closing", "title": "Obrigado."},
    ]
    spec = {"title": f"Posição contábil do estoque · {period_label(period)}", "subtitle": "Visão e relatórios",
            "theme": DEFAULT_THEME, "slides": slides}
    auto_texts(spec, facts)
    number_kickers(spec)
    return spec


# ------------------------------------------------------------------ agente: prompt e leitura


def _bucket(item: dict[str, Any]) -> str:
    return item["bucket"].split(") ", 1)[-1]


def facts_brief(facts: dict[str, Any]) -> str:
    """Fatos da competência em linhas curtas e já formatadas (R$ 1,37 bi; 3,9%) para o prompt do agente.

    O gateway do n8n corta a resposta em ~20 s: o JSON completo dos fatos deixava o pedido lento demais."""
    k, charts = facts["kpis"], facts["charts"]
    variation = k.get("variation_pct_vs_previous") or {}
    previous = facts.get("previous_period")
    vs = f" vs {period_short(previous)}" if previous else ""
    change = lambda key: f" ({pct(variation.get(key), True)}{vs})" if variation.get(key) is not None else ""  # noqa: E731
    risk = charts["Risco de obsolescência"]
    pmm = charts["PMM analítico"]
    pmm_div = {item["division"]: item["pmm"] for item in pmm["by_division"]}
    season = charts["Aging for Season"]
    cost = charts["Composição do custo fiscal"]
    lines = [
        f"Competência {period_label(facts['period'])}" + (f"; anterior {period_label(previous)}" if previous else ""),
        f"KPIs: valor fiscal {brl(k['fiscal_value'])}{change('fiscal_value')}; utilização livre {_num(k['free_quantity'])}"
        f"{change('free_quantity')}; materiais {_num(k['materials'])}; PMM {brl(k['pmm'])}{change('pmm')}; cobertura All Brazil "
        f"{pct(k['all_brazil_coverage_pct'])}; acima de 12 meses {brl(risk['all_divisions_total']['over_12_months_value'])} "
        f"({pct(risk['all_divisions_total']['over_12_months_pct_of_received'])} do recebido)",
        "Aging (faixa: valor, % do total, Active/Inactive): " + "; ".join(
            f"{_bucket(item)} {brl(item['value'])} {pct(item['share_pct'])} A {brl(item['by_lifecycle'].get('Active', 0))}"
            f"/I {brl(item['by_lifecycle'].get('Inactive', 0))}" for item in charts["Lifecycle × Aging"]["by_aging_bucket"]),
        "Lifecycle: " + "; ".join(f"{item['label']} {brl(item['value'])} ({pct(item['share_pct'])}), acima de 12 meses "
                                  f"{pct(item['over_12_months_pct_of_received'])} do recebido"
                                  for item in charts["Lifecycle × Aging"]["by_lifecycle"]),
        "Coleção (ano): " + "; ".join(f"{item['year']} {brl(item['value'])} ({pct(item['share_pct'])})" for item in season["by_year"]),
        "Maiores células season×ano: " + "; ".join(f"{c['season']} {c['year']} {brl(c['value'])} ({pct(c['share_pct'])})"
                                                   for c in season.get("largest_cells") or []),
        "Divisões (valor, %, variação, PMM, acima de 12 meses % do recebido): " + "; ".join(
            f"{item['division']} {brl(item['value'])} {pct(item['share_pct'])} {pct(item['variation_pct_vs_previous'], True)} "
            f"PMM {brl(pmm_div.get(item['division'], 0))} {pct(r['over_12_months_pct_of_received'])}"
            for item, r in zip(charts["Division Description"], risk["by_division"])),
        "Locais: " + "; ".join(f"{item['location']} {brl(item['value'])} ({pct(item['share_pct'])})" for item in charts["Local de estoque"]),
        "Centros sem local no Mapping: " + ("; ".join(f"{item['plant']} {brl(item['value'])}" for item in charts.get("Centros sem local no Mapping") or []) or "nenhum"),
        "Origem: " + "; ".join(f"{item['origin']} {brl(item['value'])} ({pct(item['share_pct'])})" for item in charts["Origem do material"]),
        "Evolução (valor; PMM): " + "; ".join(
            f"{period_short(item['period'])} {brl(item['fiscal_value'])}; {brl(next((p['pmm'] for p in pmm['by_period'] if p['period'] == item['period']), 0))}"
            for item in charts["Evolução da posição de estoque"]),
        f"Custo fiscal: FOB {pct(cost['fob_pct'])}, II {pct(cost['ii_pct'])}, outros {pct(cost['others_pct'])}",
    ]
    return "\n".join(lines)


def compact_spec(spec: dict[str, Any]) -> str:
    """Roteiro atual sem roteiro de fala e sem campos vazios, em JSON minificado (pedido de revisão menor)."""
    slides = [{key: value for key, value in slide.items() if value not in ("", None, []) and key != "notes"} for slide in spec["slides"]]
    return json.dumps({"title": spec["title"], "subtitle": spec["subtitle"], "theme": spec["theme"], "slides": slides},
                      ensure_ascii=False, separators=(",", ":"))


# O gateway do n8n corta qualquer resposta em ~20 s e o agente leva ~9 s só para responder "OK": um roteiro inteiro
# (12 slides com textos) não cabe numa chamada. Por isso o trabalho do agente é dividido em respostas curtas:
#   1) estrutura (outline_prompt): layouts, títulos-mensagem e ids — uma chamada;
#   2) textos (details_prompt): insights, tópicos e colunas — várias chamadas em paralelo, poucos slides cada;
#   revisão (patch_prompt): só as operações que mudam (editar, incluir, excluir, mover, tema), não o roteiro todo.
# O que o agente não devolver a tempo o sistema completa com textos tirados dos fatos (auto_texts).

_RULES = ("Regras: pt-BR; a empresa é a Fisia (nunca escreva Grupo SBF); títulos em frase normal (nunca Title Case) com o "
          "achado do slide; números só dos FATOS e no formato deles (R$ 1,37 bi; 3,9%), nunca invente nem recalcule; sem emojis.")
_FIELDS = ("cover{subtitle,tags≤4} agenda{items 3-6} section{lede} kpis{insight} chart{insight,points≤3} flow{insight} "
           "highlight{caption} columns{columns≤3:[{label,title,text}]} bullets{lead,items≤5} table{insight} closing{subtitle}")
_JSON_ONLY = "Responda SOMENTE com JSON minificado entre [[DECK]] e [[/DECK]], sem texto fora e sem chamar ferramentas."
DETAIL_CHUNK = 2  # slides por chamada de textos (3 já beirava os 20 s do gateway)


def _ids_block() -> str:
    return (f"charts: {', '.join(CHARTS)}\nkpis: {', '.join(KPIS)}\ntables: {', '.join(TABLES)}\n"
            "flows: aging_flow (Futures/recebido → até/acima de 12 meses → Active/Inactive)\n"
            f"themes: {', '.join(THEMES)} (padrão {DEFAULT_THEME})\n")


def _request_block(request: str | None) -> str:
    if request:
        return f"[PEDIDO_DO_USUARIO]\n{request}\n[/PEDIDO_DO_USUARIO]\n"
    return "Conteúdo a seu critério: escolha os temas e gráficos mais relevantes.\n"


def outline_prompt(facts: dict[str, Any], request: str | None) -> str:
    """Etapa 1: só a estrutura (resposta curta)."""
    return (
        "[TAREFA_APRESENTACAO] etapa 1/2: ESTRUTURA\n"
        "Escolha a estrutura de uma apresentação executiva animada sobre a posição contábil do estoque. " + _JSON_ONLY + "\n"
        'Formato: {"title":..,"subtitle":..,"theme":..,"slides":[{"l":layout,"t":título,"k":"TEMA do kicker (1-2 palavras)",'
        '"id":id do chart/table/flow/kpi do highlight,"kpis":[ids, só no layout kpis]}]}\n'
        "Layouts: cover, agenda, section (abre um bloco), kpis (2-4), chart, flow, highlight (um kpi em destaque), "
        "columns (3 pontos de atenção ou próximos passos), bullets, table, closing.\n" + _ids_block() +
        "9 a 13 slides; cover primeiro e closing último; abra os blocos com section; use aging_flow ao falar de aging; "
        "varie os layouts. " + _RULES + "\n"
        f"[FATOS]\n{facts_brief(facts)}\n[/FATOS]\n" + _request_block(request) + "[/TAREFA_APRESENTACAO]"
    )


def _slide_line(number: int, slide: dict[str, Any]) -> str:
    ref = slide.get("chart") or slide.get("table") or slide.get("flow") or slide.get("kpi") or ",".join(slide.get("kpis") or [])
    return f"{number}: {slide['layout']}{' ' + ref if ref else ''} | {slide.get('title') or ''}"


def details_prompt(facts: dict[str, Any], slides: list[tuple[int, dict[str, Any]]], deck_title: str, request: str | None) -> str:
    """Etapa 2: textos de poucos slides (várias chamadas em paralelo)."""
    lines = "\n".join(_slide_line(number, slide) for number, slide in slides)
    return (
        "[TAREFA_APRESENTACAO] etapa 2/2: TEXTOS\n"
        f"Apresentação \"{deck_title}\". Escreva os textos dos slides abaixo. " + _JSON_ONLY + "\n"
        'Formato: {"<n>":{campos do layout}}. Campos: ' + _FIELDS + ". Seja breve: insight e lede com 1 frase de até 150 "
        "caracteres; points até 2, de até 60 caracteres; textos de columns até 120 caracteres. " + _RULES + "\n"
        f"[SLIDES]\n{lines}\n[/SLIDES]\n[FATOS]\n{facts_brief(facts)}\n[/FATOS]\n" + _request_block(request) +
        "[/TAREFA_APRESENTACAO]"
    )


def slide_targets(slide: dict[str, Any], facts: dict[str, Any]) -> str:
    """Endereços (alvos de estilo) de um slide, para o agente: "title, insight, bar:<rótulo> (Calçados, ...)"."""
    layout = slide["layout"]
    names = ["title", "kicker", "values"]
    if layout == "cover":
        names += ["subtitle", "tag:1-4", "logo"]
    elif layout in ("agenda", "bullets"):
        names += ["lead", f"item:1-{len(slide.get('items') or []) or 1}"] if layout == "bullets" else [f"item:1-{len(slide.get('items') or []) or 1}"]
    elif layout == "section":
        names += ["lede", "number"]
    elif layout == "kpis":
        names += [f"kpi:{kpi}" for kpi in slide.get("kpis") or []] + ["insight"]
    elif layout == "chart":
        names += ["insight", "point:1-3", "chart"]
        model = chart_model(slide["chart"], facts)
        if model["kind"] == "matrix" and (slide.get("chart_opts") or {}).get("type", "matrix") == "matrix":
            names += [f"cell:<ano>|<season> (anos {', '.join(y['year'] for y in model['years'])}; seasons {', '.join(model['seasons'])})",
                      "total:<ano>", "row:<ano>"]
        else:
            names.append(f"bar:<rótulo> ({', '.join(str(item['label']) for item in model['items'])})")
            if model["kind"] == "columns":
                names += ["line", "legend"]
    elif layout == "flow":
        names += ["insight", "node:<id> (total, futures, received, recent, old, recent_active, recent_inactive, old_active, old_inactive)"]
    elif layout == "columns":
        names.append(f"col:1-{len(slide.get('columns') or [])}")
    elif layout == "table":
        names += ["insight", "row:<primeira coluna>"]
    elif layout == "highlight":
        names += ["big", "caption"]
    elif layout == "closing":
        names += ["subtitle"]
    return ", ".join(names)


CHART_TYPE_LABELS = {"bars": "Barras", "columns": "Colunas", "donut": "Rosca", "table": "Tabela", "matrix": "Matriz"}
PICKS = ("color", "chart_type", "theme", "number_format", "slide", "options")


def _fill(value: Any, chosen: Any) -> Any:
    """Troca $VALUE pela escolha do usuário dentro da operação pendente."""
    if value == "$VALUE":
        return chosen
    if isinstance(value, str):
        return value.replace("$VALUE", str(chosen))
    if isinstance(value, dict):
        return {_fill(k, chosen): _fill(v, chosen) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, chosen) for v in value]
    return value


def ask_choices(ask: Any, spec: dict[str, Any]) -> dict[str, Any] | None:
    """Pergunta do agente com botões, só quando o pedido exige uma escolha (cor, tipo de gráfico, tema...).

    ask = {question, pick, op (operação com $VALUE no lugar do valor), options?}; cada botão leva a operação pronta,
    aplicada direto pelo sistema (sem nova chamada ao agente)."""
    if not isinstance(ask, dict) or ask.get("pick") not in PICKS:
        return None
    pick, op = ask["pick"], ask.get("op") if isinstance(ask.get("op"), dict) else None
    if pick == "color":
        values = [(name, value, value) for name, value in PALETTE_CHOICES]
    elif pick == "chart_type":  # sem o tipo que o gráfico já tem (trocar para o mesmo não muda nada)
        try:
            slide = spec["slides"][int(op["n"]) - 1] if op and str(op.get("n", "")).isdigit() else {}
        except (IndexError, ValueError):
            slide = {}
        current = (slide.get("chart_opts") or {}).get("type") or DEFAULT_KIND.get(slide.get("chart"), "bars")
        values = [(label, key, None) for key, label in CHART_TYPE_LABELS.items()
                  if key != current and (key != "matrix" or slide.get("chart") == "aging_season")]
    elif pick == "theme":
        values = [(THEMES[key].split(" (")[0].capitalize(), key, None) for key in THEMES if key != spec.get("theme")]
    elif pick == "number_format":
        values = [("Valor completo (R$ 1.371.344.911)", "full", None), ("Valor abreviado (R$ 1,37 bi)", "short", None)]
    elif pick == "slide":
        values = [(f"{i} · {_clip(s.get('title') or s['layout'], 40)}", i, None) for i, s in enumerate(spec["slides"], 1)]
    else:
        values = [(_clip(item.get("label"), 50), item.get("value"),
                   _color(item.get("value")) if isinstance(item.get("value"), str) else None)
                  for item in (ask.get("options") or []) if isinstance(item, dict) and item.get("label")][:10]
    options = []
    for label, value, swatch in values:
        if op is not None:
            patch = {"ops": [_fill(op, value)]}
        elif pick == "theme":
            patch = {"theme": value, "ops": []}
        else:
            continue
        options.append({"label": label, **({"color": swatch} if swatch else {}), "patch": patch})
    if not options:
        return None
    return {"title": _clip(ask.get("question") or "Escolha uma opção:", 200), "options": options}


def patch_prompt(facts: dict[str, Any], current: dict[str, Any], request: str, open_slide: int | None = None) -> str:
    """Revisão: o agente devolve só as operações (resposta curta), o sistema aplica no roteiro atual."""
    lines = "\n".join(f"{number}: " + json.dumps({key: value for key, value in slide.items()
                                                  if value not in ("", None, [], {}) and key not in ("notes", "chapter")},
                                                 ensure_ascii=False, separators=(",", ":"))
                      + f"\n   alvos: {slide_targets(slide, facts)}"
                      for number, slide in enumerate(current["slides"], 1))
    deck_level = {key: current[key] for key in ("styles", "number_opts") if current.get(key)}
    return (
        "[TAREFA_APRESENTACAO] REVISÃO\n"
        "Aplique a alteração pedida ao roteiro atual devolvendo SÓ o que muda. " + _JSON_ONLY + "\n"
        "Você pode mudar tudo na FORMA: textos, títulos, slides (incluir, excluir, mover), trocar/incluir/retirar gráficos, "
        "tabelas e KPIs, tema, cores, negrito, tamanho, destaque, ocultar elementos, tipo/ordem/top/filtro do gráfico e formato "
        "dos números. Os VALORES dos números vêm do sistema e NUNCA podem ser alterados nem digitados: se pedirem para mudar "
        "um valor, devolva ops vazio e explique em note. note = frase curta ao usuário sobre o que foi feito.\n"
        'Formato: {"title"?,"subtitle"?,"theme"?,"note"?,"ask"?,"ops":[...]}. Operações:\n'
        '{"op":"edit","n":3,"set":{campos do layout; layout/chart/table/kpis também}}\n'
        '{"op":"del","n":5} | {"op":"move","n":6,"after":2} | {"op":"add","after":4,"slide":{"layout":..,"kicker":"NN / TEMA","title":..,campos}}\n'
        '{"op":"style","n":6,"target":"cell:2026|FA","set":{"color":"#0b2545","background":"laranja","border":cor,"bold":true,'
        '"italic":true,"size":1.3,"hidden":true,"highlight":true,"reset":true}} (ou "targets":[...]; alvo "bar:*" = todos os '
        'itens; "values" = todos os números do slide)\n'
        '{"op":"chart","n":9,"set":{"type":"bars|columns|donut|table","sort":"desc|asc|label","top":3,"only":[rótulos],'
        '"hide":[rótulos],"highlight":[rótulos],"values":false,"share":true,"variation":true,"color":cor,"colors":{"rótulo":cor},'
        '"series":{"Active":cor},"reset":true}}\n'
        '{"op":"number","n":4,"set":{"format":"short|full","decimals":0-2,"reset":true}} (short = R$ 1,37 bi; full = R$ 1.371.344.910)\n'
        "Em style: color = cor do texto/número; background = cor da barra, fatia, célula ou card (\"barra de Calçados em laranja\" = "
        "background; \"número em laranja\" = color). Para pintar uma barra também serve chart colors; em gráfico com séries "
        "(Active/Inactive) use chart series {\"Active\":cor}.\n"
        "Se faltar uma escolha no pedido (ex.: \"mude a cor da barra\" sem dizer a cor, \"troque o gráfico\" sem dizer o tipo, "
        "\"mude o tema\", ou slide ambíguo), NÃO adivinhe: devolva ops vazio e "
        '"ask":{"question":"pergunta curta","pick":"color|chart_type|theme|number_format|slide|options","op":operação com '
        '"$VALUE" no lugar da escolha,"options":[{"label","value"}] só em pick options}. O sistema mostra botões e aplica a escolha. '
        f"Cores da paleta: {', '.join(name.lower() for name, _ in PALETTE_CHOICES)}. Slide: se o usuário disse o número, use-o; "
        "sem número, use o SLIDE_ABERTO; só pergunte o slide (pick slide) se não houver nenhum dos dois. Se faltar mais de uma "
        "escolha, pergunte uma só (a mais importante) e preencha o resto. Nunca \"troque\" para o mesmo tipo/cor que já está.\n"
        "n e after = números do ROTEIRO_ATUAL (after 0 = início); n = 0 em style/chart/number = todos os slides. Cores: #hex ou "
        f"{', '.join(k for k in COLOR_NAMES if '-' not in k or k.startswith('azul'))}. Campos por layout: kpis{{kpis,insight}} "
        "chart{chart,insight,points} flow{flow,insight} table{table,insight} highlight{kpi,caption} " + _FIELDS + "\n"
        + _ids_block() + _RULES + "\n"
        f'[ROTEIRO_ATUAL]\ntitle: {current["title"]} | subtitle: {current["subtitle"]} | theme: {current["theme"]}'
        + (f" | geral: {json.dumps(deck_level, ensure_ascii=False, separators=(',', ':'))}" if deck_level else "")
        + f"\n{lines}\n[/ROTEIRO_ATUAL]\n"
        + (f"[SLIDE_ABERTO]\n{open_slide} · {current['slides'][open_slide - 1].get('title') or ''} (é o slide que o usuário "
           f"está vendo: \"esse slide\", \"aqui\" ou pedido sem número de slide = {open_slide})\n[/SLIDE_ABERTO]\n"
           if open_slide and 1 <= open_slide <= len(current["slides"]) else "")
        + f"[ALTERACAO_PEDIDA]\n{request}\n[/ALTERACAO_PEDIDA]\n"
        f"[FATOS]\n{facts_brief(facts)}\n[/FATOS]\n[/TAREFA_APRESENTACAO]"
    )


def parse_agent_spec(text: str) -> dict[str, Any]:
    match = re.search(r"\[\[DECK\]\](.*?)\[\[/DECK\]\]", text, re.S)
    raw = match.group(1) if match else text
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("O agente não devolveu o roteiro em JSON.")
    return json.loads(raw[start: end + 1])


def outline_to_spec(outline: dict[str, Any]) -> dict[str, Any]:
    """Estrutura curta da etapa 1 → spec (ainda sem textos). Aceita também um roteiro completo (layout/title)."""
    slides = []
    for number, raw in enumerate(outline.get("slides") or [], 1):
        if not isinstance(raw, dict):
            continue
        if "layout" in raw:  # o agente já devolveu o slide completo
            slides.append(raw)
            continue
        layout, ref = raw.get("l"), raw.get("id")
        slide: dict[str, Any] = {"layout": layout, "title": raw.get("t"), "kicker": raw.get("k")}
        if layout == "chart":
            slide["chart"] = ref
        elif layout == "table":
            slide["table"] = ref
        elif layout == "flow":
            slide["flow"] = ref or "aging_flow"
        elif layout == "highlight":
            slide["kpi"] = ref
        elif layout == "kpis":
            slide["kpis"] = raw.get("kpis") or ([ref] if ref else [])
        slides.append(slide)
    return {"title": outline.get("title"), "subtitle": outline.get("subtitle"), "theme": outline.get("theme"), "slides": slides}


def number_kickers(spec: dict[str, Any]) -> None:
    """Kicker "NN / TEMA" = posição do slide (a mesma do rodapé "N / total"): "slide 7" é o 07 / … ."""
    chapter = 0
    for n, slide in enumerate(spec["slides"], 1):
        if slide["layout"] in ("cover", "closing"):
            continue
        if slide["layout"] == "section":  # número grande da abertura de capítulo: 01, 02…
            chapter += 1
            slide["chapter"] = f"{chapter:02d}"
        theme = re.sub(r"^\s*\d{1,2}\s*/\s*", "", slide.get("kicker") or "").strip().upper()
        slide["kicker"] = _clip(f"{n:02d} / {theme or slide['layout'].upper()}", 48)


DETAIL_FIELDS = {
    "cover": ("subtitle", "tags"), "agenda": ("items",), "section": ("lede",), "kpis": ("insight",),
    "chart": ("insight", "points"), "flow": ("insight",), "highlight": ("caption", "statement"),
    "columns": ("columns",), "bullets": ("lead", "items"), "table": ("insight",), "closing": ("subtitle",),
}


def merge_details(spec: dict[str, Any], details: dict[str, Any]) -> None:
    """Junta os textos da etapa 2 ({"<n>": {campos}}) aos slides, só nos campos do layout."""
    for key, fields in (details or {}).items():
        try:
            slide = spec["slides"][int(key) - 1]
        except (ValueError, IndexError, TypeError):
            continue
        if isinstance(fields, dict):
            for name in DETAIL_FIELDS.get(slide.get("layout"), ()):
                if fields.get(name):
                    slide[name] = fields[name]


def apply_patch(spec: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Aplica as operações da revisão ao roteiro atual (números = posições no roteiro atual)."""
    if isinstance(patch.get("slides"), list) and patch["slides"]:  # o agente devolveu o roteiro inteiro
        return patch
    result = json.loads(json.dumps(spec))
    for key in ("title", "subtitle", "theme"):
        if patch.get(key):
            result[key] = patch[key]
    rows: list[tuple[int | None, dict[str, Any]]] = list(enumerate(result["slides"], 1))
    position = lambda ref: None if ref is None else next((i for i, (n, _) in enumerate(rows) if n == ref), None)  # noqa: E731
    for op in patch.get("ops") or []:
        if not isinstance(op, dict):
            continue
        kind, ref = op.get("op"), op.get("n")
        try:
            ref = int(ref) if ref is not None else None
            after = int(op.get("after")) if op.get("after") is not None else None
        except (TypeError, ValueError):
            continue
        if kind in ("style", "chart", "number") and isinstance(op.get("set"), dict):
            # Forma (nunca valores): n = 0 vale para a apresentação toda; {"reset": true} volta ao padrão.
            targets = [slide for _, slide in rows] if ref == 0 else (
                [rows[position(ref)][1]] if ref is not None and position(ref) is not None else [])
            reset = _flag(op["set"].get("reset"))
            if kind == "style":
                names = op.get("targets") if isinstance(op.get("targets"), list) else [op.get("target")]
                owners = [result] if ref == 0 else targets
                for owner in owners:
                    styles = owner.setdefault("styles", {})
                    for name in [refkey(name) for name in names if name]:
                        if reset:
                            styles.pop(name, None)
                        else:
                            styles[name] = {**styles.get(name, {}), **clean_style(op["set"])}
            elif kind == "chart":
                for slide in targets:
                    if slide.get("layout") == "chart":
                        slide["chart_opts"] = {} if reset else {**slide.get("chart_opts", {}), **clean_chart_opts(op["set"])}
            else:
                for owner in ([result] if ref == 0 else targets):
                    owner["number_opts"] = {} if reset else {**owner.get("number_opts", {}), **clean_number_opts(op["set"])}
        elif kind == "edit" and isinstance(op.get("set"), dict) and position(ref) is not None:
            rows[position(ref)][1].update({k: v for k, v in op["set"].items() if k != "layout" or v in LAYOUTS})
        elif kind == "del" and position(ref) is not None:
            rows.pop(position(ref))
        elif kind in ("add", "move"):
            if kind == "add":
                if not isinstance(op.get("slide"), dict):
                    continue
                item: tuple[int | None, dict[str, Any]] = (None, op["slide"])
            else:
                if position(ref) is None:
                    continue
                item = rows.pop(position(ref))
            target = 0 if not after else (position(after) + 1 if position(after) is not None else len(rows))
            rows.insert(target, item)
    result["slides"] = [slide for _, slide in rows]
    return result


def _content(slide: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in slide.items() if key not in ("notes", "kicker", "chapter")}


def describe_changes(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """O que mudou de uma versão para outra (mostrado no painel "Ajustar com o Optimus"); vazio = nada mudou."""
    changes = []
    if old.get("theme") != new.get("theme"):
        changes.append(f"tema: {old.get('theme')} → {new.get('theme')}")
    if old.get("title") != new.get("title"):
        changes.append(f"título da apresentação: {new.get('title')}")
    if old.get("subtitle") != new.get("subtitle"):
        changes.append(f"subtítulo: {new.get('subtitle')}")
    before = [json.dumps(_content(s), sort_keys=True, ensure_ascii=False) for s in old["slides"]]
    after = [json.dumps(_content(s), sort_keys=True, ensure_ascii=False) for s in new["slides"]]
    added = [i for i, key in enumerate(after) if key not in before]
    removed = [i for i, key in enumerate(before) if key not in after]
    # Mesmo slide editado (mesma posição e layout): "slide N alterado"; o resto é inclusão/exclusão.
    edited = [i for i in added if i in removed and old["slides"][i]["layout"] == new["slides"][i]["layout"]]
    kinds = {"styles": "cores/estilo", "chart_opts": "gráfico", "number_opts": "formato dos números"}
    for key, label in (("styles", "cores/estilo"), ("number_opts", "formato dos números")):
        if (old.get(key) or {}) != (new.get(key) or {}):
            changes.append(f"{label} em todos os slides")
    for i in edited:
        a, b = _content(old["slides"][i]), _content(new["slides"][i])
        what = sorted({kinds.get(key, "conteúdo") for key in set(a) | set(b) if a.get(key) != b.get(key)})
        changes.append(f"slide {i + 1} ({_clip(new['slides'][i].get('title') or new['slides'][i]['layout'], 50)}): {', '.join(what)}")
    changes += [f"slide {i + 1} incluído ({new['slides'][i].get('title') or new['slides'][i]['layout']})" for i in added if i not in edited]
    changes += [f"slide removido ({old['slides'][i].get('title') or old['slides'][i]['layout']})" for i in removed if i not in edited]
    if not changes and before != after:
        changes.append("ordem dos slides alterada")
    return changes


# ------------------------------------------------------------------ gráficos (SVG animado, tokens do tema)
# Os VALORES vêm sempre dos fatos da competência. O agente só muda a forma (opções do gráfico, formato dos números e
# estilos por elemento): ver CHART_OPTS, NUMBER_OPTS, STYLE_PROPS e a revisão em apply_patch.


PALETTE = ("var(--accent)", "var(--accent-2)", "var(--accent-3)", "var(--good)", "var(--warn)", "var(--text-3)")
CATEGORY = ("var(--accent)", "var(--accent-2)", "var(--accent-3)", "var(--good)", "var(--warn)")  # uma cor por categoria
CHART_TYPES = ("bars", "columns", "donut", "table")


def refkey(value: Any) -> str:
    """Endereço de um elemento (data-ref) sem acento, minúsculo e com espaços simples: "bar:Calçados" = "bar:calcados"."""
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip().lower()


def _ref(value: str) -> str:
    return f' data-ref="{esc(refkey(value))}"'


def _fmt(value: float, unit: str) -> str:
    return brl(value) if unit == "brl" else pct(value) if unit == "pct" else _num(value)


def chart_model(chart: str, facts: dict[str, Any]) -> dict[str, Any]:
    """Itens de um gráfico (rótulo, valor e unidade) com os números do sistema; a forma é decidida em chart_html."""
    charts = facts["charts"]
    total = facts["kpis"]["fiscal_value"] or 1
    model: dict[str, Any] = {"kind": "bars", "row": 56, "share": True, "variation": False, "legend": None}
    if chart == "lifecycle_aging":
        aging = charts["Lifecycle × Aging"]["by_aging_bucket"]
        names = sorted({name for item in aging for name in item["by_lifecycle"]}, key=lambda name: (name != "Active", name))
        colors = {name: ("var(--accent)" if name == "Active" else "var(--accent-3)" if name == "Inactive" else "var(--text-3)") for name in names}
        model.update(row=50, legend=[(name, colors[name]) for name in names], items=[
            {"label": _bucket(item), "value": item["value"], "unit": "brl", "share": item["share_pct"],
             "segments": [(item["by_lifecycle"].get(name, 0.0), colors[name]) for name in names],
             "detail": lambda item=item: f"{_bucket(item)}: {brl(item['value'])} ({pct(item['share_pct'])} do valor fiscal) · "
                                         + " · ".join(f"{name} {brl(item['by_lifecycle'].get(name, 0.0))}" for name in names)}
            for item in aging])
    elif chart == "aging_season":
        season = charts["Aging for Season"]
        model.update(kind="matrix", seasons=[item["season"] for item in season["by_season"]], years=season["by_year"],
                     cells={(cell["year"], cell["season"]): cell["value"] for cell in season.get("all_cells") or []},
                     items=[{"label": item["year"], "value": item["value"], "unit": "brl", "share": item["share_pct"],
                             "detail": lambda item=item: f"Coleção {item['year']}: {brl(item['value'])} · {pct(item['share_pct'])} do valor fiscal"}
                            for item in season["by_year"]])
    elif chart == "division":
        pmm = {item["division"]: item["pmm"] for item in charts["PMM analítico"]["by_division"]}
        risk = {item["division"]: item for item in charts["Risco de obsolescência"]["by_division"]}
        vs = f" vs {period_short(facts['previous_period'])}" if facts.get("previous_period") else ""
        model.update(row=70, share=False, variation=True, items=[
            {"label": item["division"], "value": item["value"], "unit": "brl", "share": item["share_pct"],
             "variation": item["variation_pct_vs_previous"],
             "detail": lambda item=item: f"{item['division']}: {brl(item['value'])} ({pct(item['share_pct'])} do valor)"
                                         + (f" · {pct(item['variation_pct_vs_previous'], True)}{vs}" if item["variation_pct_vs_previous"] is not None else "")
                                         + f" · PMM {brl(pmm.get(item['division'], 0))}"
                                         + (f" · acima de 12 meses: {pct(risk[item['division']]['over_12_months_pct_of_received'])} do recebido"
                                            if item["division"] in risk else "")}
            for item in charts["Division Description"]])
    elif chart == "risk":
        model.update(row=70, share=False, items=[
            {"label": item["division"], "value": item["over_12_months_pct_of_received"], "unit": "pct",
             "extra": (item["over_12_months_value"], "brl"),
             "detail": lambda item=item: f"{item['division']}: {brl(item['over_12_months_value'])} acima de 12 meses = "
                                         f"{pct(item['over_12_months_pct_of_received'])} do recebido · Futures {pct(item['futures_pct'])} da divisão"}
            for item in charts["Risco de obsolescência"]["by_division"]])
    elif chart == "location":
        model.update(items=[{"label": item["location"], "value": item["value"], "unit": "brl", "share": item["share_pct"],
                             "detail": lambda item=item: f"{item['location']}: {brl(item['value'])} · {pct(item['share_pct'])} do valor fiscal"}
                            for item in charts["Local de estoque"]])
    elif chart == "pmm_division":
        model.update(row=70, share=False, items=[
            {"label": item["division"], "value": item["pmm"], "unit": "brl",
             "detail": lambda item=item: f"{item['division']}: PMM {brl(item['pmm'])} · utilização livre {_num(item['free_quantity'])} unidades"}
            for item in charts["PMM analítico"]["by_division"]])
    elif chart == "evolution":
        pmm = {item["period"]: item["pmm"] for item in charts["PMM analítico"]["by_period"]}
        model.update(kind="columns", share=False, line_name="PMM", items=[
            {"label": period_short(item["period"]), "value": item["fiscal_value"], "unit": "brl", "line": pmm.get(item["period"]),
             "detail": lambda item=item: f"{period_label(item['period'])}: valor fiscal {brl(item['fiscal_value'])} · utilização livre "
                                         f"{_num(item['free_quantity'])} · PMM {brl(pmm.get(item['period'], 0))}"}
            for item in charts["Evolução da posição de estoque"]])
    elif chart == "cost":
        cost = charts["Composição do custo fiscal"]
        parts = [("FOB", cost.get("fob_value", 0.0)), ("II", cost.get("ii_value", 0.0)), ("Outros custos", cost.get("others_value", 0.0))]
        whole = sum(value for _, value in parts) or 1
        model.update(kind="donut", items=[{"label": label, "value": value, "unit": "brl", "share": 100 * value / whole,
                                           "detail": lambda label=label, value=value: f"{label}: {brl(value)} · {pct(100 * value / whole)} do custo fiscal"}
                                          for label, value in parts])
    elif chart == "origin":
        model.update(row=60, items=[{"label": item["origin"], "value": item["value"], "unit": "brl", "share": item["share_pct"],
                                     "detail": lambda item=item: f"{item['origin']}: {brl(item['value'])} · {pct(item['share_pct'])} do valor fiscal"}
                                    for item in charts["Origem do material"]])
    else:
        model["items"] = []
    model["total"] = total
    return model


def _matches(label: str, wanted: list[str]) -> bool:
    key = refkey(label)
    return any(refkey(w) == key or (len(refkey(w)) >= 3 and refkey(w) in key) for w in wanted)


def _display(item: dict[str, Any], show_share: bool, show_variation: bool) -> str:
    parts = [_fmt(item["value"], item["unit"])]
    if item.get("extra"):
        parts.append(_fmt(*item["extra"]))
    if show_share and item.get("share") is not None:
        parts.append(pct(item["share"]))
    if show_variation and item.get("variation") is not None:
        parts.append(pct(item["variation"], True))
    return " · ".join(parts)


def chart_labels(chart: str, facts: dict[str, Any]) -> list[str]:
    return [str(item["label"]) for item in chart_model(chart, facts)["items"]]


def _hbars(items: list[dict[str, Any]], *, width: int = 1060, row: int = 46, label_w: int = 250,
           value_w: int = 220, legend: list[tuple[str, str]] | None = None) -> str:
    """Barras horizontais (simples ou empilhadas) com rótulo e valor; crescem ao entrar no slide."""
    if not items:
        return '<p class="dim">Sem dados para este gráfico.</p>'
    value_w = max(value_w, min(440, 11 * max(len(item["display"]) for item in items) + 24))
    track = width - label_w - value_w - 24
    peak = max((item["value"] for item in items), default=0) or 1
    height = row * len(items) + (34 if legend else 0)
    parts = [f'<svg class="hp-chart" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img">']
    if legend:
        x = label_w + 6
        for name, color in legend:
            parts.append(f'<rect x="{x}" y="4" width="14" height="14" rx="3" fill="{color}"/>'
                         f'<text x="{x + 20}" y="16" class="hp-legend">{esc(name)}</text>')
            x += 30 + 9 * len(name)
    top = 34 if legend else 0
    for index, item in enumerate(items):
        y = top + index * row
        delay = f"{0.12 + index * 0.07:.2f}s"
        # Cada barra é clicável: destaca a linha e mostra o detalhe (números do sistema) no painel do slide.
        parts.append(f'<g class="hp-pick hp-bar-row{" hp-hl" if item.get("hl") else ""}" tabindex="0" role="button"'
                     f'{_ref("bar:" + str(item["label"]))} data-detail="{esc(item.get("detail_text") or item["display"])}">'
                     f'<rect x="0" y="{y}" width="{width}" height="{row}" class="hp-hit"/>')
        parts.append(f'<text x="{label_w - 14}" y="{y + row / 2 + 6}" text-anchor="end" class="hp-label">{esc(_clip(item["label"], 28))}</text>')
        parts.append(f'<rect x="{label_w}" y="{y + 9}" width="{track}" height="{row - 18}" rx="7" class="hp-track"/>')
        segments = item.get("segments") or [(item["value"], item.get("color") or CATEGORY[index % len(CATEGORY)])]
        x = label_w
        for value, color in segments:
            w = max(0.0, track * value / peak)
            if w <= 0:
                continue
            parts.append(f'<rect x="{x:.1f}" y="{y + 9}" width="{w:.1f}" height="{row - 18}" rx="7" fill="{color}" '
                         f'class="hp-grow-x hp-seg" style="animation-delay:{delay}"/>')
            x += w
        parts.append(f'<text x="{label_w + track + 14}" y="{y + row / 2 + 6}" class="hp-value hp-fade" '
                     f'style="animation-delay:{delay}">{esc(item["display"])}</text></g>')
    parts.append("</svg>")
    return "".join(parts)


def _columns(items: list[dict[str, Any]], *, width: int = 1060, height: int = 470, line_name: str = "") -> str:
    """Colunas com linha opcional (ex.: PMM) desenhada por cima numa faixa própria; colunas clicáveis."""
    if not items:
        return '<p class="dim">Sem dados para este gráfico.</p>'
    peak = max(item["value"] for item in items) or 1
    slot = width / len(items)
    bar = min(110, slot * 0.46)
    base = height - 60
    band_top, band_bottom = 64, 120  # faixa da linha (acima das colunas)
    bars_top = 170
    parts = [f'<svg class="hp-chart" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img">',
             '<defs><linearGradient id="hpGrad" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--accent-2)"/>'
             '<stop offset="1" stop-color="var(--accent)"/></linearGradient></defs>',
             f'<line x1="0" y1="{base}" x2="{width}" y2="{base}" class="hp-axis"/>']
    lines = [item.get("line") for item in items]
    has_line = all(value is not None for value in lines) and len(items) > 1
    if has_line:
        low, high = min(lines), max(lines)
        span = (high - low) or 1
        points = [(slot * i + slot / 2, band_bottom - (band_bottom - band_top) * ((value - low) / span if high > low else .5))
                  for i, value in enumerate(lines)]
        path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points)
        parts.append(f'<g{_ref("legend")}><rect x="{width - 250}" y="4" width="14" height="14" rx="3" fill="url(#hpGrad)"/>'
                     f'<text x="{width - 230}" y="16" class="hp-legend">Valor fiscal</text>'
                     f'<line x1="{width - 112}" y1="11" x2="{width - 88}" y2="11" class="hp-line"/>'
                     f'<text x="{width - 80}" y="16" class="hp-legend">{esc(line_name)}</text></g>')
        parts.append(f'<g{_ref("line")}><path d="{path}" pathLength="1" class="hp-line hp-draw"/>')
        for index, ((x, y), item) in enumerate(zip(points, items)):
            delay = f"{0.9 + index * 0.18:.2f}s"
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" class="hp-dot hp-fade" style="animation-delay:{delay}"/>'
                         f'<text x="{x:.1f}" y="{y - 16:.1f}" text-anchor="middle" class="hp-line-label hp-fade" '
                         f'style="animation-delay:{delay}">{esc(f"{line_name} {brl(item["line"])}")}</text>')
        parts.append("</g>")
    narrow = slot < 170
    for index, item in enumerate(items):
        if narrow and item["display"]:
            item = {**item, "display": item["display"].split(" · ")[0].replace("R$ ", "")}
        h = max(2.0, (base - bars_top) * item["value"] / peak)
        x = slot * index + (slot - bar) / 2
        delay = f"{0.15 + index * 0.1:.2f}s"
        fill = item.get("color") or "url(#hpGrad)"
        parts.append(f'<g class="hp-pick hp-col-bar{" hp-hl" if item.get("hl") else ""}" tabindex="0" role="button"'
                     f'{_ref("bar:" + str(item["label"]))} data-detail="{esc(item.get("detail_text") or item["display"])}">'
                     f'<rect x="{slot * index:.1f}" y="{bars_top - 40}" width="{slot:.1f}" height="{base - bars_top + 80}" class="hp-hit"/>'
                     f'<rect x="{x:.1f}" y="{base - h:.1f}" width="{bar:.1f}" height="{h:.1f}" rx="8" fill="{fill}" '
                     f'class="hp-grow-y hp-seg" style="animation-delay:{delay}"/>'
                     f'<text x="{x + bar / 2:.1f}" y="{base - h - 12:.1f}" text-anchor="middle" class="hp-value hp-fade{" hp-value-sm" if narrow else ""}" '
                     f'style="animation-delay:{delay}">{esc(item["display"])}</text>'
                     f'<text x="{x + bar / 2:.1f}" y="{base + 34}" text-anchor="middle" class="hp-label">{esc(_clip(item["label"], 18))}</text></g>')
    parts.append("</svg>")
    return "".join(parts)


def _donut(items: list[dict[str, Any]]) -> str:
    items = items[:6]
    total = sum(item["value"] for item in items) or 1
    radius, circumference = 150, 2 * 3.14159265 * 150
    offset = 0.0
    rings, legend = [], []
    for index, item in enumerate(items):
        length = circumference * item["value"] / total
        color = item.get("color") or PALETTE[index]
        rings.append(f'<circle cx="210" cy="210" r="{radius}" fill="none" stroke="{color}" stroke-width="56" '
                     f'stroke-dasharray="{length:.1f} {circumference:.1f}" stroke-dashoffset="{-offset:.1f}" '
                     f'class="hp-ring" style="animation-delay:{0.2 + index * 0.15:.2f}s"/>')
        legend.append(f'<div class="hp-donut-key hp-pick{" hp-hl" if item.get("hl") else ""}" tabindex="0"{_ref("bar:" + str(item["label"]))} '
                      f'data-detail="{esc(item.get("detail_text") or item["display"])}"><i style="background:{color}"></i>'
                      f'<b title="{esc(item["label"])}">{esc(_clip(item["label"], 24))}</b><span>{pct(item["share"] if item.get("share") is not None else 100 * item["value"] / total)}</span>'
                      f'<small>{esc(item["display"]) if item.get("show_values", True) else ""}</small></div>')
        offset += length
    return ('<div class="hp-donut"><svg viewBox="0 0 420 420" width="360" height="360" role="img">'
            '<g transform="rotate(-90 210 210)">' + "".join(rings) + "</g></svg>"
            f'<div class="hp-donut-legend">{"".join(legend)}</div></div>')


def _item_table(items: list[dict[str, Any]], head: str) -> str:
    rows = "".join(f'<tr class="hp-fade hp-pick{" hp-hl" if item.get("hl") else ""}" tabindex="0" style="animation-delay:{0.08 + i * 0.05:.2f}s"'
                   f'{_ref("bar:" + str(item["label"]))} data-detail="{esc(item.get("detail_text") or item["display"])}">'
                   f'<td>{esc(item["label"])}</td><td>{esc(item["display"])}</td></tr>' for i, item in enumerate(items))
    return f'<table class="hp-table"><thead><tr><th>{esc(head)}</th><th>Valor</th></tr></thead><tbody>{rows}</tbody></table>'


def _matrix(model: dict[str, Any], items: list[dict[str, Any]]) -> str:
    cells, seasons, total = model["cells"], model["seasons"], model["total"]
    years = [year for year in model["years"] if any(refkey(item["label"]) == refkey(year["year"]) for item in items)]
    peak = max(cells.values(), default=0) or 1
    head = "".join(f"<th{_ref('season:' + season)}>{esc(season)}</th>" for season in seasons)
    rows = []
    for index, year in enumerate(years):
        tds = []
        for season in seasons:
            value = cells.get((year["year"], season), 0.0)
            alpha = int(10 + 70 * value / peak)
            detail = f"{season} {year['year']}: {brl(value)} · {pct(100 * value / (total or 1))} do valor fiscal" if value else ""
            hot = " hp-hot" if alpha >= 42 else ""  # célula de fundo claro: número escuro para não sumir
            tds.append(f'<td{_ref(f"cell:{year["year"]}|{season}")} style="background:color-mix(in srgb,var(--accent) {alpha}%,transparent)"'
                       + (f' class="hp-pick{hot}" tabindex="0" data-detail="{esc(detail)}"' if value else "")
                       + f'>{brl(value) if value else "—"}</td>')
        rows.append(f'<tr class="hp-fade" style="animation-delay:{0.1 + index * 0.06:.2f}s"{_ref("row:" + year["year"])}><th>{esc(year["year"])}</th>'
                    f'{"".join(tds)}<td class="hp-total"{_ref("total:" + year["year"])}>{brl(year["value"])}</td></tr>')
    return f'<table class="hp-matrix"><thead><tr><th>Ano</th>{head}<th>Total</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'


def chart_html(chart: str, facts: dict[str, Any], opts: dict[str, Any] | None = None) -> str:
    """Desenha o gráfico com os valores do sistema e as opções de forma (tipo, ordem, top, ocultar, destacar, cores)."""
    opts = opts or {}
    model = chart_model(chart, facts)
    items = [dict(item) for item in model["items"]]
    if opts.get("only"):
        items = [item for item in items if _matches(str(item["label"]), opts["only"])]
    if opts.get("hide"):
        items = [item for item in items if not _matches(str(item["label"]), opts["hide"])]
    if opts.get("sort") == "desc":
        items.sort(key=lambda item: -item["value"])
    elif opts.get("sort") == "asc":
        items.sort(key=lambda item: item["value"])
    elif opts.get("sort") == "label":
        items.sort(key=lambda item: refkey(item["label"]))
    if opts.get("top"):
        keep = {id(item) for item in sorted(items, key=lambda item: -item["value"])[: opts["top"]]}
        items = [item for item in items if id(item) in keep]
    show_share = opts.get("share", model["share"])
    show_variation = opts.get("variation", model["variation"])
    if opts.get("series") and model["legend"]:  # cor por série (Active/Inactive): segmentos e legenda
        series = {refkey(name): color for name, color in opts["series"].items()}
        recolor = {old: series.get(refkey(name), old) for name, old in model["legend"]}
        model = {**model, "legend": [(name, recolor[old]) for name, old in model["legend"]]}
        for item in items:
            if item.get("segments"):
                item["segments"] = [(value, recolor.get(color, color)) for value, color in item["segments"]]
    colors = {refkey(label): color for label, color in (opts.get("colors") or {}).items()}
    for item in items:
        item["display"] = _display(item, show_share, show_variation) if opts.get("values", True) else ""
        item["show_values"] = opts.get("values", True)
        item["detail_text"] = item["detail"]() if callable(item.get("detail")) else item.get("detail")
        item["hl"] = bool(opts.get("highlight")) and _matches(str(item["label"]), opts["highlight"])
        color = colors.get(refkey(item["label"])) or opts.get("color")
        if color:
            item["color"] = color
            item.pop("segments", None)  # cor escolhida: barra sólida (sem a divisão Active/Inactive)
    kind = opts.get("type") or model["kind"]
    if kind == "matrix" and model["kind"] != "matrix":
        kind = "bars"
    legend = model["legend"] if any(item.get("segments") for item in items) else None
    if kind == "matrix":
        return _matrix(model, items)
    if kind == "columns":
        return _columns(items, line_name=model.get("line_name", "") if model["kind"] == "columns" else "")
    if kind == "donut":
        for item in items:
            item["display"] = _display(item, False, show_variation) if opts.get("values", True) else ""
        return _donut(items)
    if kind == "table":
        return _item_table(items, CHARTS.get(chart, "").split(" (")[0])
    return _hbars(items, legend=legend, row=model["row"])

# Fluxo do aging (layout "flow"): blocos posicionados num quadro 1700×610, ligações em curva com espessura proporcional
# ao valor, desenhadas em sequência ao entrar no slide; blocos, ligações e etapas são clicáveis (detalhe embaixo).
FLOW_W, FLOW_H, FLOW_NODE_H = 1700, 610, 84


def flow_html(flow: str, facts: dict[str, Any]) -> str:
    aging = facts["charts"]["Lifecycle × Aging"]["by_aging_bucket"]
    total = facts["kpis"]["fiscal_value"] or 1
    group = lambda prefixes: [item for item in aging if item["bucket"][:2] in prefixes]  # noqa: E731
    futures, recent, old = group(("0)",)), group(("1)", "2)", "3)", "4)")), group(("5)", "6)", "7)", "8)"))
    value = lambda rows: sum(item["value"] for item in rows)  # noqa: E731
    life = lambda rows, name: sum(item["by_lifecycle"].get(name, 0.0) for item in rows)  # noqa: E731
    received = recent + old
    buckets = lambda rows: " · ".join(f"{_bucket(item)} {brl(item['value'])}" for item in rows)  # noqa: E731
    share = lambda part, whole: pct(100 * part / (whole or 1))  # noqa: E731
    k = facts["kpis"]
    tones = {"s1": "var(--accent)", "s2": "var(--accent-2)", "s3": "var(--accent-3)", "good": "var(--good)", "warn": "var(--warn)"}
    # id, etapa, x, y, largura, rótulo, valor, tom, detalhe
    nodes = [
        ("total", "s1", 30, 258, 340, "Valor fiscal", float(total), "s1",
         f"Valor fiscal da competência: {brl(total)} · {_num(k['materials'])} materiais · PMM {brl(k['pmm'])}"),
        ("futures", "s2", 450, 70, 340, "Futures", value(futures), "s2",
         f"Futures (ainda não recebido): {brl(value(futures))} = {share(value(futures), total)} do valor · "
         f"Active {brl(life(futures, 'Active'))} · Inactive {brl(life(futures, 'Inactive'))}"),
        ("received", "s2", 450, 380, 340, "Recebido", value(received), "s2",
         f"Recebido: {brl(value(received))} = {share(value(received), total)} do valor · até 12 meses "
         f"{share(value(recent), value(received))} e acima de 12 meses {share(value(old), value(received))} do recebido"),
        ("recent", "s3", 870, 300, 340, "Até 12 meses", value(recent), "s3", f"Até 12 meses: {buckets(recent)}"),
        ("old", "s3", 870, 470, 340, "Acima de 12 meses", value(old), "s3",
         f"Acima de 12 meses: {buckets(old)} · {share(value(old), value(received))} do recebido"),
        ("recent_active", "s4", 1290, 200, 380, "Até 12 m · Active", life(recent, "Active"), "good",
         f"Active até 12 meses: {brl(life(recent, 'Active'))} = {share(life(recent, 'Active'), value(recent))} da faixa"),
        ("recent_inactive", "s4", 1290, 300, 380, "Até 12 m · Inactive", life(recent, "Inactive"), "warn",
         f"Inactive até 12 meses: {brl(life(recent, 'Inactive'))} = {share(life(recent, 'Inactive'), value(recent))} da faixa"),
        ("old_active", "s4", 1290, 410, 380, "Acima 12 m · Active", life(old, "Active"), "good",
         f"Active acima de 12 meses: {brl(life(old, 'Active'))} = {share(life(old, 'Active'), value(old))} da faixa"),
        ("old_inactive", "s4", 1290, 510, 380, "Acima 12 m · Inactive", life(old, "Inactive"), "warn",
         f"Inactive acima de 12 meses: {brl(life(old, 'Inactive'))} = {share(life(old, 'Inactive'), value(old))} da faixa — maior risco"),
    ]
    links = [("total", "futures"), ("total", "received"), ("received", "recent"), ("received", "old"),
             ("recent", "recent_active"), ("recent", "recent_inactive"), ("old", "old_active"), ("old", "old_inactive")]
    stages = [("s1", 30, 340, "1 / VALOR FISCAL"), ("s2", 450, 340, "2 / ENTRADA"), ("s3", 870, 340, "3 / AGING"), ("s4", 1290, 380, "4 / LIFECYCLE")]
    stage_tone = {"s1": "s1", "s2": "s2", "s3": "s3", "s4": "good"}
    by_id = {node[0]: node for node in nodes}
    paths = []
    for index, (source, target) in enumerate(links):
        s, t = by_id[source], by_id[target]
        x1, y1 = s[2] + s[4], s[3] + FLOW_NODE_H / 2
        x2, y2 = t[2], t[3] + FLOW_NODE_H / 2
        mid = (x1 + x2) / 2
        d = f"M{x1} {y1:.0f} C{mid:.0f} {y1:.0f} {mid:.0f} {y2:.0f} {x2} {y2:.0f}"
        width = 2.5 + 24 * t[6] / total
        stage_delay = {"s2": 0.35, "s3": 1.0, "s4": 1.65}[t[1]]
        paths.append(
            f'<g class="hp-flow-link hp-pick" tabindex="0" role="button" data-from="{source}" data-to="{target}" '
            f'data-detail="{esc(t[5])}: {esc(brl(t[6]))} ({share(t[6], s[6])} de {esc(s[5].lower())})" '
            f'style="--tone:{tones[t[7]]};--w:{width:.1f}px;--delay:{stage_delay + index * 0.04:.2f}s">'
            f'<path d="{d}" pathLength="1" class="hp-flow-line"/><path d="{d}" pathLength="1" class="hp-flow-pulse"/>'
            f'<path d="{d}" class="hp-flow-hit"/></g>')
    blocks = []
    for node_id, stage, x, y, w, label, amount, tone, detail in nodes:
        blocks.append(
            f'<div class="hp-flow-node hp-pick {stage}" tabindex="0" role="button" data-node="{node_id}" data-stage="{stage}"{_ref("node:" + node_id)} '
            f'data-detail="{esc(detail)}" style="left:{x}px;top:{y}px;width:{w}px;--tone:{tones[tone]}">'
            f'<small>{esc(label)}</small><b data-count="{amount:.2f}" data-fmt="brl">{esc(brl(amount))}</b>'
            f'<span>{share(amount, total)} do valor fiscal</span></div>')
    heads = "".join(f'<button type="button" class="hp-flow-stage hp-pick" data-stage="{key}" '
                    f'data-detail="{esc(text.split(" / ")[1].capitalize())}: clique nos blocos ou nas ligações para ver os valores." '
                    f'style="left:{x}px;width:{w}px;--tone:{tones[stage_tone[key]]}">{esc(text)}</button>'
                    for key, x, w, text in stages)
    return (f'<div class="hp-flow hp-pickable" style="width:{FLOW_W}px;height:{FLOW_H}px">{heads}'
            f'<svg class="hp-flow-lines" viewBox="0 0 {FLOW_W} {FLOW_H}" width="{FLOW_W}" height="{FLOW_H}">{"".join(paths)}</svg>'
            f'{"".join(blocks)}</div>')


def kpi_value(kpi: str, facts: dict[str, Any]) -> tuple[str, str]:
    k = facts["kpis"]
    variation = k.get("variation_pct_vs_previous") or {}
    risk = facts["charts"]["Risco de obsolescência"]["all_divisions_total"]
    previous = f" vs {period_short(facts['previous_period'])}" if facts.get("previous_period") else ""
    if kpi == "fiscal_value":
        return brl(k["fiscal_value"]), (f"{pct(variation.get('fiscal_value'), True)}{previous}" if variation.get("fiscal_value") is not None else "Vlr Tot Fisc")
    if kpi == "free_quantity":
        return _num(k["free_quantity"]), (f"{pct(variation.get('free_quantity'), True)}{previous}" if variation.get("free_quantity") is not None else "unidades livres")
    if kpi == "materials":
        return _num(k["materials"]), "SKUs distintos"
    if kpi == "pmm":
        return brl(k["pmm"]), (f"{pct(variation.get('pmm'), True)}{previous}" if variation.get("pmm") is not None else "Vlr Tot Fisc ÷ quantidade livre")
    if kpi == "coverage":
        return pct(k["all_brazil_coverage_pct"]), "registros com Division"
    if kpi == "over_12_months":
        return brl(risk["over_12_months_value"]), f"{pct(risk['over_12_months_pct_of_received'])} do recebido"
    return "—", ""


def kpi_number(kpi: str, facts: dict[str, Any]) -> tuple[float, str] | None:
    """Valor numérico do KPI para a contagem animada (o texto final continua sendo o formatado pelo sistema)."""
    k = facts["kpis"]
    risk = facts["charts"]["Risco de obsolescência"]["all_divisions_total"]
    return {
        "fiscal_value": (k["fiscal_value"], "brl"), "free_quantity": (k["free_quantity"], "num"), "materials": (k["materials"], "num"),
        "pmm": (k["pmm"], "brl"), "coverage": (k["all_brazil_coverage_pct"], "pct"), "over_12_months": (risk["over_12_months_value"], "brl"),
    }.get(kpi)


def _counted(kpi: str, facts: dict[str, Any], text: str, tag: str = "b", cls: str = "", ref: str = "") -> str:
    number = kpi_number(kpi, facts)
    attrs = (f' class="{cls}"' if cls else "") + (_ref(ref) if ref else "")
    if number and number[0] is not None:
        opts = NUMBER_FMT.get()  # a contagem animada termina no mesmo formato pedido (abreviado/completo, casas)
        attrs += f' data-count="{float(number[0]):.2f}" data-fmt="{number[1]}"'
        attrs += (' data-full="1"' if opts.get("format") == "full" else "") + (
            f' data-dec="{opts["decimals"]}"' if opts.get("decimals") is not None else "")
    return f"<{tag}{attrs}>{esc(text)}</{tag}>"


def auto_notes(slide: dict[str, Any], facts: dict[str, Any]) -> str:
    """Roteiro de fala (modo apresentador, tecla S) montado com o texto do slide e os números do sistema."""
    layout = slide["layout"]
    parts = [slide.get("title") or ""]
    if layout == "kpis":
        parts += [f"{KPIS[kpi]}: {kpi_value(kpi, facts)[0]} ({kpi_value(kpi, facts)[1]})" for kpi in slide.get("kpis") or []]
    elif layout == "highlight" and slide.get("kpi"):
        parts.append(f"{KPIS[slide['kpi']]}: {kpi_value(slide['kpi'], facts)[0]}")
    elif layout == "flow":
        parts.append("Percorra o fluxo da esquerda para a direita: valor fiscal, Futures e recebido, faixas de 12 meses e lifecycle.")
    for key in ("subtitle", "lede", "insight", "lead", "caption"):
        if slide.get(key):
            parts.append(slide[key])
    parts += slide.get("points") or []
    parts += slide.get("items") or []
    parts += [f"{col['title']}: {col['text']}" for col in slide.get("columns") or []]
    return " ".join(part.rstrip(".") + "." for part in parts if part)


def table_html(table: str, facts: dict[str, Any]) -> str:
    charts = facts["charts"]
    if table == "division":
        pmm = {item["division"]: item["pmm"] for item in charts["PMM analítico"]["by_division"]}
        head, rows = ("Divisão", "Valor fiscal", "Participação", "Variação", "PMM"), [
            (item["division"], brl(item["value"]), pct(item["share_pct"]), pct(item["variation_pct_vs_previous"], True), brl(pmm.get(item["division"], 0)))
            for item in charts["Division Description"]]
    elif table == "location":
        head, rows = ("Local de estoque", "Valor fiscal", "Participação"), [
            (item["location"], brl(item["value"]), pct(item["share_pct"])) for item in charts["Local de estoque"]]
    else:
        aging = charts["Lifecycle × Aging"]["by_aging_bucket"]
        head, rows = ("Faixa de aging", "Valor fiscal", "Participação", "Active", "Inactive"), [
            (item["bucket"].split(") ", 1)[-1], brl(item["value"]), pct(item["share_pct"]),
             brl(item["by_lifecycle"].get("Active", 0)), brl(item["by_lifecycle"].get("Inactive", 0))) for item in aging]
    body = "".join(f'<tr class="hp-fade" style="animation-delay:{0.08 + i * 0.05:.2f}s"{_ref("row:" + str(row[0]))}>'
                   + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for i, row in enumerate(rows))
    return f'<table class="hp-table"><thead><tr>{"".join(f"<th>{esc(h)}</th>" for h in head)}</tr></thead><tbody>{body}</tbody></table>'


# ------------------------------------------------------------------ slides
# Cada elemento leva data-ref (endereço) para o agente poder mudar a forma: "title", "kpi:pmm", "bar:Calçados",
# "cell:2026|FA"... Os estilos pedidos viram regras CSS por slide (style_css).


def _slide(inner: str, index: int, total: int, footer: str, notes: str, extra_class: str = "", title: str = "") -> str:
    return (f'<section class="slide hp-slide {extra_class}" data-n="{index}" data-title="{esc(title)}">{inner}'
            f'<div class="deck-footer"><span class="hp-brand">{esc(footer)}</span>'
            f'<span class="slide-number" data-current="{index}" data-total="{total}"></span></div>'
            + (f'<div class="notes">{esc(notes)}</div>' if notes else "") + "</section>")


def _head(slide: dict[str, Any]) -> str:
    kicker = f'<p class="kicker hp-kicker" data-anim="fade-up"{_ref("kicker")}>{esc(slide["kicker"])}</p>' if slide.get("kicker") else ""
    return f'{kicker}<h2 class="h2 hp-title" data-anim="fade-up"{_ref("title")}>{esc(slide["title"])}</h2><div class="hp-rule"></div>'


FX_LAYER = '<div class="hp-fx" data-fx="constellation" aria-hidden="true"></div>'  # efeito do html-ppt (canvas), discreto
DETAIL_HINT = "Clique numa barra ou num bloco para ver o detalhe."


def _detail(text: str = "") -> str:
    return f'<p class="hp-detail" data-empty="{esc(text or DETAIL_HINT)}"{_ref("insight") if text else ""}>{esc(text or DETAIL_HINT)}</p>'


def _numbered(items: list[str]) -> str:
    return "".join(f'<li{_ref(f"item:{i}")}><b>{i:02d}</b><span>{esc(item)}</span></li>' for i, item in enumerate(items, 1))


def render_slide(slide: dict[str, Any], index: int, total: int, spec: dict[str, Any], facts: dict[str, Any]) -> str:
    # Formato dos números: o geral da apresentação e, por cima, o do slide (só a forma; valores do sistema).
    token = NUMBER_FMT.set({**(spec.get("number_opts") or {}), **(slide.get("number_opts") or {})})
    try:
        return _render_slide(slide, index, total, spec, facts)
    finally:
        NUMBER_FMT.reset(token)


def _render_slide(slide: dict[str, Any], index: int, total: int, spec: dict[str, Any], facts: dict[str, Any]) -> str:
    footer = f"ESTOQUE CONTÁBIL / {spec['subtitle'].upper()}"
    layout = slide["layout"]
    notes = slide.get("notes") or auto_notes(slide, facts)
    if layout == "cover":
        words = slide["title"].split()
        first, rest = (" ".join(words[:-1]), words[-1]) if len(words) > 1 else (slide["title"], "")
        tags = "".join(f"<span{_ref(f'tag:{i}')}>{esc(tag)}</span>" for i, tag in enumerate(slide.get("tags") or [], 1))
        inner = (
            FX_LAYER + '<div class="hp-cover">'
            f'<div><p class="kicker hp-kicker" data-anim="fade-up"{_ref("kicker")}>{esc(slide.get("kicker"))}</p><div class="hp-accent-rule"></div>'
            f'<h1 class="h1 hp-cover-title" data-anim="rise-in"{_ref("title")}>{esc(first)}<br><span data-anim="gradient-flow">{esc(rest)}</span></h1>'
            f'<p class="lede" data-anim="fade-up"{_ref("subtitle")}>{esc(slide.get("subtitle"))}</p>'
            f'<div class="hp-tags anim-stagger-list" data-anim-target>{tags}</div></div>'
            f'<div class="hp-brand-art" aria-hidden="true"{_ref("logo")}>{LOGO_SVG}</div></div>'
        )
        return _slide(inner, index, total, footer, notes, "hp-cover-slide", slide["title"])
    if layout == "agenda":
        return _slide(_head(slide) + f'<ol class="hp-agenda anim-stagger-list" data-anim-target>{_numbered(slide["items"])}</ol>',
                      index, total, footer, notes, title=slide["title"])
    if layout == "section":
        theme = re.sub(r"^\s*\d{1,2}\s*/\s*", "", slide.get("kicker") or "")
        inner = (f'<div class="hp-section"><div class="hp-section-num" aria-hidden="true"{_ref("number")}>{esc(slide.get("chapter") or "")}</div>'
                 f'<div class="hp-section-copy"><p class="kicker hp-kicker" data-anim="fade-right"{_ref("kicker")}>{esc(theme)}</p>'
                 f'<h2 class="hp-section-title" data-anim="blur-in"{_ref("title")}>{esc(slide["title"])}</h2><div class="hp-section-rule"></div>'
                 + (f'<p class="lede" data-anim="fade-up"{_ref("lede")}>{esc(slide.get("lede"))}</p>' if slide.get("lede") else "") + "</div></div>")
        return _slide(inner, index, total, footer, notes, "hp-section-slide", slide["title"])
    if layout == "kpis":
        cards = []
        for kpi in slide["kpis"]:
            value, sub = kpi_value(kpi, facts)
            size = min(62, int(62 * 10.5 / max(1, len(value))))  # valor completo (R$ 1.371.344.911) cabe no card
            cards.append(f'<div class="hp-kpi" style="--c:{CATEGORY[len(cards) % len(CATEGORY)]};--kfs:{size}px"{_ref("kpi:" + kpi)}><small>{esc(KPIS[kpi])}</small>'
                         f'{_counted(kpi, facts, value)}<span>{esc(sub)}</span></div>')
        insight = f'<p class="hp-insight" data-anim="fade-up"{_ref("insight")}>{esc(slide["insight"])}</p>' if slide.get("insight") else ""
        return _slide(_head(slide) + f'<div class="grid g{len(cards)} hp-kpis anim-stagger-list" data-anim-target>{"".join(cards)}</div>{insight}',
                      index, total, footer, notes, title=slide["title"])
    if layout == "chart":
        chart = chart_html(slide["chart"], facts, slide.get("chart_opts"))
        points = "".join(f"<li{_ref(f'point:{i}')}>{esc(point)}</li>" for i, point in enumerate(slide.get("points") or [], 1))
        if not slide.get("insight") and not points:  # sem texto de apoio: o gráfico ocupa a largura toda
            return _slide(_head(slide) + f'<div class="hp-chart-wide hp-pickable" data-anim="fade-up"{_ref("chart")}>{chart}</div>'
                          + _detail(), index, total, footer, notes, title=slide["title"])
        side = (f'<aside class="hp-side" data-anim="fade-left"><small>{esc(CHARTS[slide["chart"]].split(" (")[0])}</small>'
                + (f'<p{_ref("insight")}>{esc(slide["insight"])}</p>' if slide.get("insight") else "")
                + (f'<ul>{points}</ul>' if points else "") + _detail() + "</aside>")
        return _slide(_head(slide) + f'<div class="hp-chart-row"><div class="hp-chart-box hp-pickable" data-anim="fade-up"{_ref("chart")}>'
                      f'{chart}</div>{side}</div>', index, total, footer, notes, title=slide["title"])
    if layout == "flow":
        return _slide(_head(slide) + flow_html(slide["flow"], facts) + _detail(slide.get("insight") or ""),
                      index, total, footer, notes, "hp-flow-slide", slide["title"])
    if layout == "bullets":
        return _slide(_head(slide) + f'<div class="hp-bullets"><p class="hp-lead" data-anim="fade-up"{_ref("lead")}>{esc(slide.get("lead"))}</p>'
                      f'<ol class="anim-stagger-list" data-anim-target>{_numbered(slide["items"])}</ol></div>', index, total, footer, notes,
                      title=slide["title"])
    if layout == "columns":
        cols = "".join(f'<div class="hp-col" style="--c:{CATEGORY[i]}"{_ref(f"col:{i + 1}")}><div class="hp-col-num">{i + 1:02d}</div>'
                       f'<small>{esc(col["label"])}</small><h3>{esc(col["title"])}</h3><p>{esc(col["text"])}</p></div>'
                       for i, col in enumerate(slide["columns"]))
        return _slide(_head(slide) + f'<div class="hp-columns anim-stagger-list" data-anim-target>{cols}</div>', index, total, footer, notes, title=slide["title"])
    if layout == "table":
        insight = f'<p class="hp-insight" data-anim="fade-up"{_ref("insight")}>{esc(slide["insight"])}</p>' if slide.get("insight") else ""
        return _slide(_head(slide) + table_html(slide["table"], facts) + insight, index, total, footer, notes, title=slide["title"])
    if layout == "highlight":
        value = kpi_value(slide["kpi"], facts)[0] if slide.get("kpi") else slide.get("statement") or ""
        big = (_counted(slide["kpi"], facts, value, "div", "hp-big", "big") if slide.get("kpi")
               else f'<div class="hp-big"{_ref("big")}>{esc(value)}</div>')
        inner = (f'<div class="hp-highlight"><p class="kicker hp-kicker" data-anim="fade-up"{_ref("kicker")}>{esc(slide.get("kicker"))}</p>'
                 f'<div class="hp-big-wrap" data-anim="zoom-pop">{big}</div>'
                 f'<h2 class="h2" data-anim="fade-up"{_ref("title")}>{esc(slide.get("title"))}</h2>'
                 f'<p class="lede" data-anim="fade-up"{_ref("caption")}>{esc(slide.get("caption"))}</p></div>')
        return _slide(inner, index, total, footer, notes, "center tc hp-highlight-slide", slide.get("title") or value)
    inner = (FX_LAYER + f'<div class="hp-thanks"><h1 class="hp-thanks-title"{_ref("title")}>{esc(slide["title"])}</h1>'
             f'<div class="hp-thanks-rule"></div><p class="hp-thanks-sub"{_ref("subtitle")}>{esc(slide.get("subtitle"))}</p>'
             f'<p class="hp-source">Números da Base de Estoque da competência {esc(period_label(facts["period"]))} '
             f'(Visão e relatórios do Estoque Contábil).</p></div>')
    return _slide(inner, index, total, footer, notes, "hp-closing", slide["title"])


# Seletores dos números de um slide (alvo "values").
VALUE_SELECTORS = (".hp-value", ".hp-kpi b", ".hp-matrix td", ".hp-table td", ".hp-flow-node b", ".hp-big", ".hp-line-label",
                   ".hp-donut-key span", ".hp-donut-key small")


def _style_rules(scope: str, target: str, props: dict[str, Any]) -> str:
    """Regras CSS de um alvo: texto (HTML) e SVG (fill) tratados juntos; !important vence o estilo padrão e o inline."""
    if target == "values":
        bases = [f"{scope} {sel}" for sel in VALUE_SELECTORS]
    elif target.endswith(":*"):
        bases = [f'{scope} [data-ref^="{target[:-1]}"]']
    else:
        bases = [f'{scope} [data-ref="{target}"]']
    rules = []
    for base in bases:
        if props.get("hidden"):
            rules.append(f"{base}{{display:none!important}}")
            continue
        if props.get("color"):
            c = props["color"]
            rules.append(f"{base},{base} *{{color:{c}!important;-webkit-text-fill-color:{c}!important}}{base} text{{fill:{c}!important}}")
        if props.get("background"):
            c = props["background"]
            rules.append(f"{base}{{background:{c}!important}}{base} .hp-seg,{base} .hp-ring{{fill:{c}!important}}")
        if props.get("border"):
            c = props["border"]
            rules.append(f"{base}{{outline:3px solid {c}!important;outline-offset:3px}}{base} .hp-seg{{stroke:{c}!important;stroke-width:3px}}")
        if props.get("bold"):
            rules.append(f"{base},{base} *{{font-weight:800!important}}")
        if props.get("bold") is False:
            rules.append(f"{base},{base} *{{font-weight:400!important}}")
        if props.get("italic"):
            rules.append(f"{base},{base} *{{font-style:italic!important}}")
        if props.get("size"):
            k = props["size"]
            rules.append(f"{base}{{zoom:{k}}}{base} text{{font-size:{round(19 * k, 1)}px!important}}")
        if props.get("highlight"):
            rules.append(f"{base}{{box-shadow:0 0 0 3px var(--accent-3),0 0 26px color-mix(in srgb,var(--accent-3) 45%,transparent)!important;"
                         f"border-radius:8px}}{base} .hp-seg{{filter:drop-shadow(0 0 10px var(--accent-3))}}{base} text{{font-weight:800!important}}")
    return "".join(rules)


def style_css(spec: dict[str, Any]) -> str:
    """CSS dos estilos pedidos: geral (todos os slides) e por slide (data-n)."""
    rules = [_style_rules(".hp-slide", target, props) for target, props in (spec.get("styles") or {}).items()]
    for index, slide in enumerate(spec["slides"], 1):
        rules += [_style_rules(f'.hp-slide[data-n="{index}"]', target, props) for target, props in (slide.get("styles") or {}).items()]
    return "\n".join(rule for rule in rules if rule)


# Pilha de camadas do Estoque Contábil (capa): as três placas e as barras se montam ao entrar no slide.
# Mesmo desenho do logotipo do sistema (assets/estoque_contabil.svg), separado em camadas para a animação.
def _plate(cls: str, y: float, top: str, left: str, right: str) -> str:
    return (f'<g class="hp-layer {cls}"><path d="M32 {y}L47 {y + 7.5}L32 {y + 15}L17 {y + 7.5}Z" fill="{top}"/>'
            f'<path d="M17 {y + 7.5}L32 {y + 15}V{y + 18.5}L17 {y + 11}Z" fill="{left}"/>'
            f'<path d="M32 {y + 15}L47 {y + 7.5}V{y + 11}L32 {y + 18.5}Z" fill="{right}"/></g>')


LOGO_SVG = (
    '<svg class="hp-logo" viewBox="10 7 44 46" role="img" aria-label="Estoque Contábil">'
    + _plate("l1", 33.5, "#24589a", "#1b467d", "#143765")
    + _plate("l2", 25.5, "#4a8fd6", "#3a78bd", "#2d64a3")
    + _plate("l3", 17.5, "#9fd0ff", "#7db8f0", "#5e9fdc")
    + '<g class="hp-bars" fill="#ffffff" stroke="#0f2537" stroke-width=".8">'
    '<rect x="24" y="20" width="4.6" height="9" rx="1.2"/>'
    '<rect x="29.7" y="14" width="4.6" height="13.5" rx="1.2"/>'
    '<rect x="35.4" y="8.5" width="4.6" height="17.5" rx="1.2"/></g></svg>'
)


DECK_CSS = """
:root{--font-sans:'Segoe UI Variable Display','Segoe UI',Arial,sans-serif}
/* Base dos slides (modelo: deck de referência do usuário) — fundo com brilho radial e grade sutil */
.hp-slide{padding:82px 104px 96px;justify-content:center;background:radial-gradient(circle at 84% 11%,rgba(78,142,218,.13),transparent 31%),var(--bg)}
.hp-slide::before{content:'';position:absolute;inset:0;pointer-events:none;opacity:.14;background-image:linear-gradient(rgba(136,178,222,.22) 1px,transparent 1px),linear-gradient(90deg,rgba(136,178,222,.22) 1px,transparent 1px);background-size:80px 80px;-webkit-mask-image:linear-gradient(90deg,transparent,#000 50%,transparent);mask-image:linear-gradient(90deg,transparent,#000 50%,transparent)}
.hp-slide>*{position:relative;z-index:1}
.hp-slide>.deck-footer{position:absolute;z-index:10;bottom:30px;left:104px;right:104px;font-size:15px;letter-spacing:.09em;color:var(--text-3)}
.hp-slide .slide-number{font-family:var(--font-mono)}
.hp-kicker{font-size:18px;letter-spacing:.18em;color:var(--accent);margin:0 0 20px}
.hp-title{font-size:62px;line-height:1.08;letter-spacing:-.043em;max-width:1560px;margin:0;color:var(--text-1)}
.hp-rule{height:2px;width:100%;background:linear-gradient(90deg,var(--accent),rgba(109,216,255,.06));margin:22px 0 40px}
.hp-accent-rule{width:80px;height:6px;border-radius:4px;background:var(--accent);margin:12px 0 30px}
/* Capa */
.hp-cover-slide{justify-content:center}
.hp-cover{display:grid;grid-template-columns:1.15fr .85fr;align-items:center;gap:40px}
.hp-cover-title{font-size:112px;line-height:1.02;letter-spacing:-.055em;margin:0 0 30px;color:var(--text-1)}
.hp-cover .lede{font-size:29px;line-height:1.5;max-width:900px;color:var(--text-2)}
.hp-tags{display:flex;gap:24px;flex-wrap:wrap;margin-top:54px}
.hp-tags span{padding-top:14px;border-top:2px solid var(--border-strong);min-width:170px;font:18px var(--font-mono);letter-spacing:.04em;color:var(--text-3);text-transform:uppercase}
.hp-tags span:nth-child(2){border-color:color-mix(in srgb,var(--accent-2) 55%,transparent)}.hp-tags span:nth-child(3){border-color:color-mix(in srgb,var(--accent-3) 55%,transparent)}
.hp-brand-art{position:relative;display:grid;place-items:center;height:720px;background:radial-gradient(circle,rgba(54,118,185,.22) 0%,rgba(54,118,185,.07) 34%,transparent 65%)}
.hp-logo{width:470px;height:490px;overflow:visible;filter:drop-shadow(0 26px 26px rgba(0,0,0,.30));animation:hp-logo-float 7s ease-in-out 2.4s infinite}
.hp-layer,.hp-bars{opacity:0;transform-box:fill-box;transform-origin:center}
.is-active .hp-layer.l1{animation:hp-assemble .85s cubic-bezier(.2,.7,.2,1) .15s forwards}
.is-active .hp-layer.l2{animation:hp-assemble .85s cubic-bezier(.2,.7,.2,1) .5s forwards}
.is-active .hp-layer.l3{animation:hp-assemble .85s cubic-bezier(.2,.7,.2,1) .85s forwards}
.is-active .hp-bars{animation:hp-assemble .65s cubic-bezier(.2,.7,.2,1) 1.3s forwards}
@keyframes hp-assemble{from{opacity:0;transform:translateY(38px)}to{opacity:1;transform:none}}
@keyframes hp-logo-float{50%{transform:translateY(-11px)}}
/* Roteiro e listas numeradas */
.hp-agenda{list-style:none;padding:0;margin:10px 0 0;display:grid;grid-template-columns:1fr 1fr;gap:10px 90px}
.hp-agenda li,.hp-bullets li{display:flex;gap:21px;align-items:baseline;border-bottom:1px solid var(--border);padding:20px 0;font-size:29px;color:var(--text-2)}
.hp-agenda b,.hp-bullets b{font:700 19px var(--font-mono);color:var(--accent)}
.hp-agenda li:nth-child(3n+2) b,.hp-bullets li:nth-child(3n+2) b{color:var(--accent-2)}
.hp-agenda li:nth-child(3n) b,.hp-bullets li:nth-child(3n) b{color:var(--accent-3)}
.hp-bullets{display:grid;grid-template-columns:1.05fr .95fr;gap:100px;align-items:center;margin-top:20px}
.hp-lead{font-size:42px;line-height:1.24;letter-spacing:-.03em;font-weight:650;color:var(--text-1);margin:0;max-width:780px}
.hp-bullets ol{list-style:none;margin:0;padding:0}
/* Indicadores */
.hp-kpis{margin-top:10px;gap:28px}
.hp-kpi{border:1px solid var(--border-strong);border-top:5px solid var(--c,var(--accent));background:var(--grad-soft);border-radius:18px;padding:30px 32px;box-shadow:var(--shadow)}
.hp-kpi small{display:block;font:700 15px var(--font-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--text-3)}
.hp-kpi b{display:block;white-space:nowrap;margin:20px 0 12px;font:800 var(--kfs,62px)/1 var(--font-mono);letter-spacing:-.06em;color:var(--text-1)}
.hp-kpi span{font-size:21px;color:var(--c,var(--accent))}
.hp-insight{margin-top:46px;padding:24px 32px;border-left:5px solid var(--accent-3);background:rgba(255,158,106,.07);font-size:26px;line-height:1.45;color:var(--text-2);max-width:1500px}
/* Gráficos */
.hp-chart-row{display:grid;grid-template-columns:1080px 1fr;gap:56px;align-items:start}
.hp-chart-box,.hp-chart-wide{border:1px solid var(--border);border-radius:20px;background:linear-gradient(145deg,rgba(11,32,55,.7),rgba(10,24,43,.55));padding:26px 30px}
.hp-chart-wide{display:flex;justify-content:center}
.hp-chart-wide .hp-chart{width:1560px;height:auto}
.hp-side{border-top:5px solid var(--accent-2);padding-top:24px}
.hp-side small{display:block;font:700 15px var(--font-mono);letter-spacing:.14em;text-transform:uppercase;color:var(--accent-2);margin-bottom:16px}
.hp-side p{font-size:27px;line-height:1.42;color:var(--text-1);margin:0 0 20px}
.hp-side ul{margin:0;padding:0;list-style:none;display:grid;gap:14px}
.hp-side li{position:relative;padding-left:26px;font-size:22px;line-height:1.45;color:var(--text-2)}
.hp-side li::before{content:'';position:absolute;left:0;top:13px;width:10px;height:10px;border-radius:50%;background:var(--accent-3)}
.hp-chart text{font-family:var(--font-sans)}
.hp-label{fill:var(--text-2);font-size:19px}
.hp-value-sm{font-size:15px!important}
.hp-value{fill:var(--text-1);font-size:19px;font-weight:700;font-family:var(--font-mono)!important}
.hp-note{fill:var(--text-3);font-size:16px}
.hp-legend{fill:var(--text-2);font-size:16px}
.hp-track{fill:rgba(130,173,211,.10)}
.hp-axis{stroke:var(--border-strong);stroke-width:1.5}
.hp-grow-x{transform-box:fill-box;transform-origin:left center}
.hp-grow-y{transform-box:fill-box;transform-origin:center bottom}
.slide.is-active .hp-grow-x{animation:hp-grow-x .9s cubic-bezier(.2,.7,.2,1) both}
.slide.is-active .hp-grow-y{animation:hp-grow-y .9s cubic-bezier(.2,.7,.2,1) both}
.slide.is-active .hp-fade{animation:hp-fade .6s ease both}
.slide.is-active .hp-ring{animation:hp-ring 1.1s cubic-bezier(.2,.7,.2,1) both}
@keyframes hp-grow-x{from{transform:scaleX(0)}}
@keyframes hp-grow-y{from{transform:scaleY(0)}}
@keyframes hp-fade{from{opacity:0;transform:translateY(8px)}}
@keyframes hp-ring{from{stroke-dasharray:0 1000}}
.hp-donut{display:flex;align-items:center;gap:40px}
.hp-donut-legend{display:grid;gap:26px}
.hp-donut-key{display:grid;grid-template-columns:22px 250px 100px 170px;align-items:center;gap:14px;font-size:26px;color:var(--text-2)}
.hp-donut-key i{width:18px;height:18px;border-radius:5px}
.hp-donut-key b{color:var(--text-1);font-size:23px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hp-donut-key span{font:800 26px var(--font-mono);color:var(--text-1)}.hp-donut-key small{color:var(--text-3);font-size:20px;white-space:nowrap}
.hp-matrix,.hp-table{border-collapse:collapse;font-size:22px;width:100%}
.hp-matrix th,.hp-matrix td,.hp-table th,.hp-table td{padding:15px 22px;border-bottom:1px solid var(--border);text-align:right;color:var(--text-2);font-variant-numeric:tabular-nums}
.hp-matrix td,.hp-table td{font-family:var(--font-mono)}
.hp-matrix tbody th,.hp-table td:first-child{text-align:left;font-family:var(--font-sans);font-weight:750;color:var(--text-1)}
.hp-table th:first-child,.hp-matrix thead th:first-child{text-align:left}
.hp-matrix thead th,.hp-table thead th{font:700 16px var(--font-mono);letter-spacing:.13em;text-transform:uppercase;color:var(--text-3);border-bottom:2px solid var(--border-strong)}
.hp-matrix .hp-total{font-weight:800;color:var(--accent)}
.hp-matrix td{color:var(--text-1);font-weight:600}
.hp-matrix td.hp-hot{color:var(--bg);font-weight:800}
.hp-table td:nth-child(2){color:var(--accent)}
/* Colunas (faixas ciano / lilás / laranja) */
.hp-columns{display:grid;grid-template-columns:repeat(3,1fr);gap:42px;margin-top:40px;align-items:stretch}
.hp-col{border-top:5px solid var(--c);padding:26px 10px 12px 0}
.hp-col small{display:block;font:800 22px var(--font-mono);color:var(--text-3);margin-bottom:30px;text-transform:uppercase}
.hp-col h3{font-size:40px;line-height:1.12;margin:0 0 18px;color:var(--text-1)}
.hp-col p{font-size:25px;line-height:1.42;color:var(--text-2);margin:0}
/* Destaque e encerramento */
.hp-highlight{display:flex;flex-direction:column;align-items:center}
.hp-big{font:800 170px/1 var(--font-sans);letter-spacing:-.05em;margin:24px 0 30px}
.hp-closing{justify-content:center}
.hp-thanks{text-align:center;align-self:center}
.hp-thanks-title{font-size:170px;line-height:1.04;letter-spacing:-.065em;color:var(--text-1);margin:0;opacity:0;transform:translateY(38px)}
.hp-thanks-rule{width:0;height:5px;border-radius:3px;background:var(--accent);margin:48px auto 0}
.hp-thanks-sub{font-size:27px;color:var(--text-2);letter-spacing:.12em;text-transform:uppercase;margin-top:40px;opacity:0;transform:translateY(16px)}
.is-active .hp-thanks-title{animation:hp-rise 1s cubic-bezier(.2,.7,.2,1) .15s forwards}
.is-active .hp-thanks-rule{animation:hp-draw .8s ease .8s forwards}
.is-active .hp-thanks-sub{animation:hp-rise .7s ease 1.2s forwards}
@keyframes hp-rise{to{opacity:1;transform:none}}
@keyframes hp-draw{to{width:190px}}
.hp-source{margin-top:70px;font-size:17px;color:var(--text-3);letter-spacing:.04em}
.hp-big{background:linear-gradient(90deg,var(--accent),var(--accent-2),var(--accent-3));-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent}
.hp-highlight-slide .lede{max-width:1200px;margin:18px auto 0}
/* Efeito de fundo (constellation do html-ppt) na capa e no encerramento — discreto */
.hp-slide>.hp-fx{position:absolute;inset:0;z-index:0;opacity:.24;pointer-events:none}
.hp-slide>.hp-fx canvas{width:100%;height:100%}
/* Abertura de capítulo: número grande translúcido */
.hp-section-slide{justify-content:center}
.hp-section{display:grid;grid-template-columns:520px 1fr;align-items:center;gap:40px}
.hp-section-num{font:800 420px/0.8 var(--font-sans);letter-spacing:-.06em;color:transparent;-webkit-text-stroke:3px color-mix(in srgb,var(--accent-2) 55%,transparent);opacity:0;transform:translateX(-40px)}
.is-active .hp-section-num{animation:hp-num-in 1.1s cubic-bezier(.2,.7,.2,1) .05s forwards,hp-num-drift 9s ease-in-out 1.2s infinite}
@keyframes hp-num-in{to{opacity:.9;transform:none}}
@keyframes hp-num-drift{50%{transform:translateY(-14px)}}
.hp-section-title{font-size:96px;line-height:1.02;letter-spacing:-.05em;margin:0;color:var(--text-1)}
.hp-section-rule{height:5px;width:0;border-radius:3px;background:linear-gradient(90deg,var(--accent),var(--accent-2),var(--accent-3));margin:36px 0 32px}
.is-active .hp-section-rule{animation:hp-draw-wide 1s ease .55s forwards}
@keyframes hp-draw-wide{to{width:420px}}
.hp-section .lede{font-size:31px;line-height:1.45;color:var(--text-2);max-width:980px}
/* Colunas: número grande translúcido (deck de referência) */
.hp-col-num{font:800 94px/1 var(--font-mono);color:var(--c);opacity:.2;margin-bottom:8px}
/* Gráficos clicáveis: destaque e painel de detalhe */
.hp-hit{fill:transparent}
.hp-pick{cursor:pointer;outline:none}
.hp-bar-row,.hp-col-bar{transition:opacity .25s}
.hp-pickable.has-sel .hp-bar-row:not(.sel),.hp-pickable.has-sel .hp-col-bar:not(.sel){opacity:.3}
.hp-bar-row:hover .hp-label,.hp-bar-row.sel .hp-label{fill:var(--text-1);font-weight:700}
.hp-bar-row.sel rect[class*="hp-grow"],.hp-col-bar.sel .hp-seg{filter:drop-shadow(0 0 10px color-mix(in srgb,var(--accent) 70%,transparent))}
.hp-bar-row:focus-visible .hp-hit,.hp-col-bar:focus-visible .hp-hit{stroke:var(--accent);stroke-width:2}
.hp-matrix td.hp-pick{transition:box-shadow .2s}
.hp-matrix td.hp-pick:hover,.hp-matrix td.sel{box-shadow:inset 0 0 0 2px var(--accent);color:var(--text-1)}
.hp-hl .hp-seg{filter:drop-shadow(0 0 10px var(--accent-3));stroke:var(--accent-3);stroke-width:2px}
.hp-hl .hp-label,.hp-hl .hp-value{fill:var(--accent-3)!important;font-weight:800}
.hp-donut-key.hp-hl,.hp-table tr.hp-hl{box-shadow:inset 4px 0 0 var(--accent-3);background:color-mix(in srgb,var(--accent-3) 10%,transparent)}
.hp-detail{margin:26px 0 0;padding:14px 20px;border-radius:12px;border:1px dashed var(--border-strong);font:18px/1.45 var(--font-mono);color:var(--text-3);transition:all .25s}
.hp-detail.on{border-style:solid;border-color:color-mix(in srgb,var(--accent) 60%,transparent);background:color-mix(in srgb,var(--accent) 8%,transparent);color:var(--text-1)}
.hp-side .hp-detail{font-size:17px;line-height:1.45;color:var(--text-3);margin:26px 0 0}.hp-side .hp-detail.on{color:var(--text-1)}
.hp-chart-wide+.hp-detail,.hp-flow+.hp-detail{max-width:1700px;margin:18px auto 0;width:100%}
.hp-line{fill:none;stroke:var(--accent-3);stroke-width:4;stroke-linecap:round;stroke-linejoin:round}
.hp-draw{stroke-dasharray:1;stroke-dashoffset:1}
.slide.is-active .hp-draw{animation:hp-path 1.4s ease .6s forwards}
@keyframes hp-path{to{stroke-dashoffset:0}}
.hp-dot{fill:var(--bg);stroke:var(--accent-3);stroke-width:4}
.hp-line-label{fill:var(--accent-3);font-size:18px;font-weight:700;font-family:var(--font-mono)!important}
/* Fluxo do aging (modelo: fluxograma do deck de referência) */
.hp-flow-slide{padding-top:64px}
.hp-flow{position:relative;margin:4px auto 0;background:linear-gradient(145deg,rgba(7,25,44,.85),rgba(11,28,48,.58));border:1px solid var(--border);border-radius:24px;overflow:hidden}
.hp-flow::before{content:'';position:absolute;inset:0;background-image:radial-gradient(rgba(129,178,223,.2) 1px,transparent 1px);background-size:24px 24px;opacity:.38}
.hp-flow-lines{position:absolute;inset:0;z-index:1;overflow:visible}
.hp-flow-line{fill:none;stroke:color-mix(in srgb,var(--tone) 62%,#6f8198);stroke-width:var(--w);stroke-linecap:round;opacity:.55;stroke-dasharray:1;stroke-dashoffset:1;transition:opacity .25s,stroke .25s}
.is-active .hp-flow-line{animation:hp-path 1s ease var(--delay) forwards}
.hp-flow-pulse{fill:none;stroke:rgba(255,255,255,.75);stroke-width:2.5;stroke-linecap:round;stroke-dasharray:.015 .085;opacity:0}
.is-active .hp-flow-pulse{animation:hp-pulse-in .4s ease calc(var(--delay) + 1s) forwards,hp-flow-run 2.6s linear calc(var(--delay) + 1s) infinite}
@keyframes hp-pulse-in{to{opacity:.55}}
@keyframes hp-flow-run{to{stroke-dashoffset:-1}}
.hp-flow-hit{fill:none;stroke:transparent;stroke-width:26;pointer-events:stroke}
.hp-flow-link:hover .hp-flow-line,.hp-flow-link.sel .hp-flow-line,.hp-flow-link.rel .hp-flow-line{opacity:1;stroke:var(--tone)}
.hp-flow-link.sel .hp-flow-line{filter:drop-shadow(0 0 8px var(--tone))}
.hp-flow.has-sel .hp-flow-link:not(.sel):not(.rel) .hp-flow-line{opacity:.16}
.hp-flow-node{position:absolute;z-index:2;height:84px;padding:10px 18px;box-sizing:border-box;border-radius:12px;display:flex;flex-direction:column;justify-content:center;
  background:color-mix(in srgb,var(--tone) 9%,#10253e);border:1px solid color-mix(in srgb,var(--tone) 45%,#435770);box-shadow:0 9px 20px rgba(0,0,0,.2);
  opacity:0;transform:translateY(14px);transition:opacity .25s,transform .2s,background .25s,box-shadow .25s}
.hp-flow-node small{font:700 14px var(--font-mono);letter-spacing:.1em;text-transform:uppercase;color:var(--tone)}
.hp-flow-node b{font:800 29px/1.15 var(--font-mono);letter-spacing:-.03em;color:var(--text-1);margin:3px 0 1px}
.hp-flow-node span{font-size:15px;color:var(--text-2)}
.is-active .hp-flow-node{animation:hp-node-in .58s ease forwards}
.is-active .hp-flow-node.s2{animation-delay:.55s}.is-active .hp-flow-node.s3{animation-delay:1.2s}.is-active .hp-flow-node.s4{animation-delay:1.85s}
@keyframes hp-node-in{to{opacity:1;transform:none}}
.hp-flow.touched .hp-flow-node{animation:none;opacity:1;transform:none}
.hp-flow.touched .hp-flow-line{animation:none;stroke-dashoffset:0}
.hp-flow.has-sel .hp-flow-node:not(.sel):not(.rel){opacity:.35}
.hp-flow-node.sel,.hp-flow-node.rel{opacity:1}
.hp-flow-node.sel{transform:scale(1.04);background:color-mix(in srgb,var(--tone) 22%,#10253e);border-color:var(--tone);box-shadow:0 0 0 3px color-mix(in srgb,var(--tone) 22%,transparent),0 0 26px color-mix(in srgb,var(--tone) 25%,transparent)}
.hp-flow-node:hover{border-color:var(--tone)}
.hp-flow-stage{position:absolute;top:16px;z-index:3;padding:0 0 9px;background:none;border:0;border-bottom:2px solid color-mix(in srgb,var(--tone) 62%,transparent);color:#a7c1d8;font:700 16px var(--font-mono);letter-spacing:.08em;text-align:left;cursor:pointer}
.hp-flow-stage:hover,.hp-flow-stage.sel{color:#fff;border-color:var(--tone);text-shadow:0 0 14px color-mix(in srgb,var(--tone) 45%,transparent)}
@media (prefers-reduced-motion:reduce){.hp-layer,.hp-bars,.hp-thanks-title,.hp-thanks-sub,.hp-flow-node,.hp-section-num{opacity:1!important;transform:none!important;animation:none!important}
  .hp-flow-line,.hp-draw{stroke-dashoffset:0!important;animation:none!important}.hp-flow-pulse{display:none}}
"""

# Comportamento do deck (além do runtime do html-ppt): números que contam ao entrar no slide e gráficos/fluxo clicáveis.
DECK_JS = r"""
(() => {
  const unit = v => { const a = Math.abs(v); return a >= 1e9 ? [1e9, ' bi', 2] : a >= 1e6 ? [1e6, ' mi', 1] : a >= 1e3 ? [1e3, ' mil', 1] : [1, '', 2]; };
  const nf = (v, d) => v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
  const fmt = (v, kind, target, full, dec) => {
    if (kind === 'brl' && full) return 'R$ ' + nf(v, dec == null ? 0 : dec);
    if (kind === 'brl') { const [div, suf, d] = unit(target); return 'R$ ' + nf(v / div, dec == null ? d : dec) + suf; }
    if (kind === 'pct') return nf(v, 1) + '%';
    return nf(v, 0);
  };
  const count = slide => slide.querySelectorAll('[data-count]').forEach((el, i) => {
    const target = parseFloat(el.dataset.count); const kind = el.dataset.fmt || 'num';
    const full = el.dataset.full === '1'; const dec = el.dataset.dec == null ? null : +el.dataset.dec;
    if (!isFinite(target)) return;
    if (!el.dataset.final) el.dataset.final = el.textContent;
    const final = el.dataset.final; const dur = 1400; const wait = 250 + (el.closest('.hp-flow-node') ? 500 : i * 90);
    el.textContent = fmt(0, kind, target, full, dec);
    const t0 = performance.now() + wait;
    const tick = now => {
      const t = Math.max(0, Math.min(1, (now - t0) / dur));
      el.textContent = t < 1 ? fmt(target * (1 - Math.pow(1 - t, 3)), kind, target, full, dec) : final;
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  const clear = slide => {
    slide.querySelectorAll('.sel,.rel').forEach(el => el.classList.remove('sel', 'rel'));
    slide.querySelectorAll('.has-sel').forEach(el => el.classList.remove('has-sel'));
    slide.querySelectorAll('.hp-detail').forEach(el => { el.textContent = el.dataset.empty || ''; el.classList.remove('on'); });
  };
  const pick = el => {
    const slide = el.closest('.slide'); if (!slide) return;
    const was = el.classList.contains('sel');
    clear(slide);
    const flow = el.closest('.hp-flow'); if (flow) flow.classList.add('touched');
    if (was) return;
    el.classList.add('sel');
    const box = el.closest('.hp-pickable'); if (box) box.classList.add('has-sel');
    if (flow) {
      const links = [...flow.querySelectorAll('.hp-flow-link')];
      const nodes = [...flow.querySelectorAll('.hp-flow-node')];
      const mark = id => nodes.forEach(n => { if (n.dataset.node === id) n.classList.add('rel'); });
      if (el.dataset.node) links.forEach(l => { if (l.dataset.from === el.dataset.node || l.dataset.to === el.dataset.node) { l.classList.add('rel'); mark(l.dataset.from); mark(l.dataset.to); } });
      if (el.dataset.from) { mark(el.dataset.from); mark(el.dataset.to); }
      if (el.classList.contains('hp-flow-stage')) nodes.forEach(n => { if (n.dataset.stage === el.dataset.stage) n.classList.add('rel'); });
    }
    const detail = slide.querySelector('.hp-detail');
    if (detail && el.dataset.detail) { detail.textContent = el.dataset.detail; detail.classList.add('on'); }
  };
  document.addEventListener('click', ev => {
    const el = ev.target.closest('.hp-pick');
    if (el) { ev.stopPropagation(); pick(el); return; }
    const slide = ev.target.closest('.slide'); if (slide && ev.target.closest('.hp-pickable')) clear(slide);
  });
  document.addEventListener('keydown', ev => {
    const el = document.activeElement;
    if ((ev.key === 'Enter') && el && el.classList && el.classList.contains('hp-pick')) { ev.preventDefault(); ev.stopPropagation(); pick(el); }
  }, true);
  const boot = () => {
    document.querySelectorAll('.slide').forEach(slide => {
      new MutationObserver(() => {
        const active = slide.classList.contains('is-active');
        if (active && !slide.dataset.on) { slide.dataset.on = '1'; clear(slide); slide.querySelectorAll('.hp-flow').forEach(f => f.classList.remove('touched')); count(slide); }
        if (!active) delete slide.dataset.on;
      }).observe(slide, { attributes: true, attributeFilter: ['class'] });
      if (slide.classList.contains('is-active')) { slide.dataset.on = '1'; count(slide); }
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
"""


def render_html(spec: dict[str, Any], facts: dict[str, Any]) -> str:
    """HTML único e autocontido (CSS, runtime e efeitos embutidos)."""
    css = "\n".join((ASSETS / name).read_text(encoding="utf-8") for name in ("base.css", "animations.css"))
    theme = (ASSETS / "themes" / f"{spec['theme']}.css").read_text(encoding="utf-8")
    fx = "\n".join((ASSETS / "fx" / f"{name}.js").read_text(encoding="utf-8") for name in FX_MODULES)
    # Módulos de efeito já embutidos: o carregador não busca arquivos (lista vazia).
    fx_runtime = re.sub(r"const FX_LIST = \[.*?\];", "const FX_LIST = [];", (ASSETS / "fx-runtime.js").read_text(encoding="utf-8"), flags=re.S)
    runtime = (ASSETS / "runtime.js").read_text(encoding="utf-8")
    total = len(spec["slides"])
    slides = "\n".join(render_slide(slide, index, total, spec, facts) for index, slide in enumerate(spec["slides"], 1))
    safe = lambda text: text.replace("</script", "<\\/script")  # noqa: E731 - nada fecha o <script> antes da hora
    return (
        f'<!DOCTYPE html>\n<html lang="pt-BR" data-theme="{esc(spec["theme"])}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(spec["title"])}</title>'
        '<meta name="generator" content="Estoque Contábil · Optimus · html-ppt-skill (MIT)">'
        f"<style>{css}\n{theme}\n{DECK_CSS}\n{style_css(spec)}</style></head>"
        f'<body><div class="deck">{slides}</div>'
        f"<script>{safe(fx)}</script><script>{safe(fx_runtime)}</script><script>{safe(runtime)}</script>"
        f"<script>{safe(DECK_JS)}</script>"
        "</body></html>"
    )


# ------------------------------------------------------------------ armazenamento


def storage_root(settings: Any) -> Path:
    root = settings.path("processed").parent / "presentations"
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_deck_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]


def deck_dir(settings: Any, deck_id: str) -> Path:
    if not re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{6}", deck_id):
        raise ValueError("Apresentação inválida.")
    return storage_root(settings) / deck_id


def save_version(settings: Any, deck_id: str, spec: dict[str, Any], html_text: str, meta: dict[str, Any]) -> int:
    folder = deck_dir(settings, deck_id)
    folder.mkdir(parents=True, exist_ok=True)
    versions = sorted(int(p.stem[1:]) for p in folder.glob("v*.html"))
    version = (versions[-1] + 1) if versions else 1
    (folder / f"v{version}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    (folder / f"v{version}.html").write_text(html_text, encoding="utf-8")
    meta = {**meta, "deck_id": deck_id, "version": version, "title": spec["title"], "slides": len(spec["slides"]),
            "updated_at": datetime.now().isoformat(timespec="seconds")}
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return version


def load_meta(settings: Any, deck_id: str) -> dict[str, Any]:
    path = deck_dir(settings, deck_id) / "meta.json"
    if not path.exists():
        raise FileNotFoundError("Apresentação não encontrada.")
    return json.loads(path.read_text(encoding="utf-8"))


def load_version(settings: Any, deck_id: str, version: int | None = None) -> tuple[int, dict[str, Any], str]:
    folder = deck_dir(settings, deck_id)
    version = version or int(load_meta(settings, deck_id)["version"])
    spec = json.loads((folder / f"v{version}.json").read_text(encoding="utf-8"))
    return version, spec, (folder / f"v{version}.html").read_text(encoding="utf-8")


def latest_deck(settings: Any, period: str, user_email: str | None = None) -> tuple[dict[str, Any], str] | None:
    """Última apresentação pronta da competência nesta máquina (de preferência de quem pede o relatório)."""
    found = []
    for meta_path in storage_root(settings).glob("*/meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        html_path = meta_path.parent / f"v{meta.get('version')}.html"
        if meta.get("period") == period and html_path.is_file():
            mine = bool(user_email) and str(meta.get("created_by") or "").lower() == str(user_email).lower()
            found.append((mine, str(meta.get("updated_at") or ""), meta, html_path))
    if not found:
        return None
    _mine, _when, meta, html_path = max(found, key=lambda item: (item[0], item[1]))
    return meta, html_path.read_text(encoding="utf-8")


def report_section(meta: dict[str, Any], deck_html: str) -> str:
    """Bloco do relatório HTML (Share Link) com a apresentação embutida: abre em qualquer computador, sem o sistema.

    A apresentação vai inteira dentro do arquivo (JSON num <script>), exibida num quadro 16:9 e com botões para
    tela cheia, nova aba e baixar o HTML dela. O PDF do relatório não leva este bloco."""
    payload = json.dumps(deck_html, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    updated = str(meta.get("updated_at") or "")[:16].replace("T", " ")
    try:
        updated = datetime.fromisoformat(updated).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        pass
    name = f"Apresentacao_{re.sub(r'[^A-Za-z0-9]+', '_', str(meta.get('period') or ''))}.html"
    return (
        '<section class="ec-deck" id="apresentacao" aria-label="Apresentação da competência">'
        "<style>"
        ".ec-deck{max-width:1280px;margin:18px auto 26px;padding:18px 20px 20px;border-radius:16px;background:#0B2545;color:#e8f0fb;"
        "font-family:'Segoe UI',Arial,sans-serif;box-shadow:0 10px 30px rgba(11,37,69,.25)}"
        ".ec-deck-head{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:14px}"
        ".ec-deck small{display:block;font:700 11px/1 Consolas,monospace;letter-spacing:.14em;color:#6dd8ff;margin-bottom:8px}"
        ".ec-deck h2{margin:0 0 6px;font-size:22px;color:#fff}.ec-deck p{margin:0;font-size:12.5px;color:#9fb6d3}"
        ".ec-deck-actions{display:flex;gap:8px;flex-wrap:wrap}"
        ".ec-deck button{padding:8px 14px;border:1px solid #2b4c7a;border-radius:9px;background:#13315C;color:#e8f0fb;font:600 13px 'Segoe UI',Arial,sans-serif;cursor:pointer}"
        ".ec-deck button:hover{border-color:#F58634;background:#1c4378}"
        ".ec-deck-frame{position:relative;width:100%;aspect-ratio:16/9;border-radius:12px;overflow:hidden;background:#000}"
        ".ec-deck-frame iframe{position:absolute;inset:0;width:100%;height:100%;border:0}"
        "@media print{.ec-deck{display:none}}"
        "</style>"
        '<div class="ec-deck-head"><div><small>APRESENTAÇÃO DA COMPETÊNCIA</small>'
        f"<h2>{esc(meta.get('title'))}</h2>"
        f"<p>{esc(meta.get('slides'))} slides · versão {esc(meta.get('version'))} · atualizada em {esc(updated)}. "
        "Clique na apresentação e use as setas (ou espaço) para avançar.</p></div>"
        '<div class="ec-deck-actions"><button type="button" id="ec-deck-full">Tela cheia</button>'
        '<button type="button" id="ec-deck-open">Abrir em nova aba</button>'
        '<button type="button" id="ec-deck-save">Baixar apresentação</button></div></div>'
        '<div class="ec-deck-frame"><iframe id="ec-deck-iframe" title="Apresentação da competência" allowfullscreen></iframe></div>'
        f'<script type="application/json" id="ec-deck-data">{payload}</script>'
        "<script>(()=>{const html=JSON.parse(document.getElementById('ec-deck-data').textContent),"
        "frame=document.getElementById('ec-deck-iframe');frame.srcdoc=html;"
        "const url=()=>URL.createObjectURL(new Blob([html],{type:'text/html'}));"
        "document.getElementById('ec-deck-open').onclick=()=>window.open(url(),'_blank');"
        f"document.getElementById('ec-deck-save').onclick=()=>{{const a=document.createElement('a');a.href=url();a.download={json.dumps(name)};"
        "document.body.appendChild(a);a.click();a.remove()};"
        "document.getElementById('ec-deck-full').onclick=()=>{(frame.requestFullscreen||frame.webkitRequestFullscreen||(()=>{})).call(frame);"
        "setTimeout(()=>{try{frame.contentWindow.focus()}catch(e){}},300)}})()</script>"
        "</section>"
    )


def file_name(spec: dict[str, Any], facts_period: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", spec["title"].encode("ascii", "ignore").decode()).strip("_")[:60] or "Apresentacao"
    return f"{slug}_{facts_period}"


def zip_bytes(html_text: str, name: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{name}.html", html_text)
        archive.writestr("LEIA-ME.txt", "Abra o arquivo .html no navegador. Setas ou espaço: avançar · F: tela cheia · "
                                         "O: visão geral · S: modo apresentador (com roteiro de fala).\n"
                                         "Gerado pelo Optimus (Estoque Contábil) com html-ppt-skill (MIT).\n")
        archive.writestr("LICENSE-html-ppt-skill.txt", (ASSETS / "LICENSE").read_text(encoding="utf-8"))
    return buffer.getvalue()
