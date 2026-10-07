"""Vigia do Optimus: detecta fatos que merecem um aviso proativo aos administradores.

Aqui não há mensagem pronta: cada verificação devolve só FATOS estruturados (números, arquivos,
centros, indicadores), obtidos por consultas exatas ao banco, ao Drive e ao Health Center. O texto
mostrado no chat é escrito pelo próprio agente Optimus a partir desses fatos (evento proativo).

Cada evento tem uma chave estável e uma "impressão digital". Ele só volta a ser enviado se a
impressão digital mudar (ou se o problema sumir e voltar). Correções nunca são feitas aqui: o
evento pode sugerir uma ação, que só é executada depois da confirmação do administrador no chat.
"""

from __future__ import annotations

import json
from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Any

from .db import connect

WATCH_SEEN_KEY = "optimus_watch_seen"
# "slides" fica sempre em verificação parcial e "permissions" é da sessão de quem consulta.
IGNORED_HEALTH = {"slides", "permissions"}

ALL_BRAZIL_CAUSE = "material sem correspondência no All Brazil do mês (nem pelo Material completo, nem pelo Estilo-Cor de 10 caracteres)"
PASS_STEP_CAUSE = "sem valor na MB59 da competência (CE & MAT), na posição do mês anterior e no All Brazil"
GAP_FIELDS: tuple[tuple[str, str, str, str], ...] = (
    ("division_description", "Division Description", "All Brazil", ALL_BRAZIL_CAUSE),
    ("material_origin", "Material Origin", "All Brazil", ALL_BRAZIL_CAUSE),
    ("lifecycle_description", "Lifecycle Descrip.", "All Brazil", ALL_BRAZIL_CAUSE),
    ("season", "Season", "PASSO A PASSO", PASS_STEP_CAUSE),
    ("year", "Year", "PASSO A PASSO", PASS_STEP_CAUSE),
    ("product_offer_end_date", "Product Offer End Dt", "PASSO A PASSO", PASS_STEP_CAUSE),
    ("aging_bucket", "AGING", "Mapping · Faixas de aging", "sem Product Offer End Dt para calcular os dias ou faixa não coberta pelo Mapping"),
    ("lifecycle", "Lifecycle", "Mapping · Lifecycle", "Lifecycle Descrip. sem regra na aba Lifecycle do Mapping"),
)


def _blank(field: str) -> str:
    return f"coalesce(nullif(trim(cast({field} as varchar)),''),'')=''"


def latest_period(settings: Any) -> str | None:
    with connect(settings.path("database")) as connection:
        row = connection.execute("select max(period) from inventory_rows").fetchone()
    return str(row[0]) if row and row[0] else None


# ------------------------------------------------------------ Base de Estoque


def inventory_gaps(settings: Any, period: str) -> dict[str, Any]:
    """Linhas sem preenchimento nos campos enriquecidos (All Brazil, PASSO A PASSO e Mapping)."""
    with connect(settings.path("database")) as connection:
        total = int(connection.execute("select count(*) from inventory_rows where period=?", [period]).fetchone()[0])
        gaps = []
        for field, label, source, cause in GAP_FIELDS:
            rows, value = connection.execute(
                f"select count(*), coalesce(sum(fiscal_total_amount),0) from inventory_rows where period=? and {_blank(field)}",
                [period],
            ).fetchone()
            if rows:
                gaps.append({"field": field, "label": label, "source": source, "probable_cause": cause, "rows": int(rows),
                             "fiscal_value": round(float(value), 2), "pct_rows": round(100 * int(rows) / total, 2) if total else 0})
    return {"period": period, "total_rows": total, "gaps": gaps}


def inventory_gap_event(settings: Any, period: str) -> dict[str, Any] | None:
    report = inventory_gaps(settings, period)
    if not report["gaps"]:
        return None
    return {
        "key": f"gaps:{period}",
        "fingerprint": json.dumps([(gap["field"], gap["rows"]) for gap in report["gaps"]]),
        "event": {"type": "inventory_gaps", "topic": "campos sem preenchimento na Base de Estoque", **report},
        "parameters": None,
        "summary": None,
    }


# --------------------------------------------------------------------- Mapping


def mapping_gaps(settings: Any, period: str) -> dict[str, Any]:
    """Centros da competência sem Local (Planta e local) ou sem Status da operação no Mapping."""
    with connect(settings.path("database")) as connection:
        def plants_without(field: str) -> list[dict[str, Any]]:
            rows = connection.execute(
                f"""select coalesce(nullif(trim(cast(plant as varchar)),''),'(sem centro)'), count(*), coalesce(sum(fiscal_total_amount),0)
                    from inventory_rows where period=? and {_blank(field)} group by 1 order by 3 desc""",
                [period],
            ).fetchall()
            return [{"plant": str(row[0]), "rows": int(row[1]), "fiscal_value": round(float(row[2]), 2)} for row in rows]

        location = plants_without("location_group")
        status = plants_without("operation_status")
        known_locations = [str(row[0]) for row in connection.execute(
            "select distinct value_2 from mapping_rules where group_key='location' and coalesce(value_2,'')<>'' order by 1"
        ).fetchall()]
        known_status = [str(row[0]) for row in connection.execute(
            "select distinct value_1 from mapping_rules where group_key='operation_status' and coalesce(value_1,'')<>'' order by 1"
        ).fetchall()]
    return {"period": period, "plants_without_location": location, "plants_without_operation_status": status,
            "known_locations": known_locations, "known_operation_status": known_status}


def mapping_event(settings: Any, period: str) -> dict[str, Any] | None:
    report = mapping_gaps(settings, period)
    if not report["plants_without_location"] and not report["plants_without_operation_status"]:
        return None
    return {
        "key": f"mapping:{period}",
        "fingerprint": json.dumps({"location": [item["plant"] for item in report["plants_without_location"]],
                                   "status": [item["plant"] for item in report["plants_without_operation_status"]]}),
        "event": {"type": "mapping_gaps", "topic": "Mapping Planta e local e Status da operação", **report},
        "parameters": None,
        "summary": None,
    }


# ------------------------------------------------------------------ All Brazil


def all_brazil_event(settings: Any, period: str) -> dict[str, Any] | None:
    """All Brazil mais nova no Drive do que a usada no enriquecimento da competência."""
    from .sources.all_brazil import resolve_all_brazil

    with connect(settings.path("database")) as connection:
        try:
            used = connection.execute(
                "select snapshot_date, source_path from all_brazil_imports where period=?", [period]
            ).fetchone()
        except Exception:  # noqa: BLE001 - tabela ainda não criada
            used = None
    if used is None:
        return None
    year, month = map(int, period.split("-"))
    try:
        latest = resolve_all_brazil(settings, date(year, month, monthrange(year, month)[1]))
    except Exception:  # noqa: BLE001 - Drive indisponível: o Health Center já avisa
        return None
    used_date = used[0] if isinstance(used[0], date) else date.fromisoformat(str(used[0])[:10])
    used_name = Path(str(used[1])).name
    if latest.snapshot_date <= used_date or used_name.casefold() == latest.path.name.casefold():
        return None
    return {
        "key": f"all_brazil:{period}",
        "fingerprint": latest.path.name,
        "event": {
            "type": "all_brazil_newer",
            "topic": "All Brazil nova e reprocessamento dos joins",
            "period": period,
            "new_file": latest.path.name,
            "new_snapshot_date": latest.snapshot_date.isoformat(),
            "used_file": used_name,
            "used_snapshot_date": used_date.isoformat(),
        },
        "parameters": {"kind": "reprocess", "period": period},
        "summary": (
            f"Reprocessar os joins da Base de Estoque {period} com a All Brazil {latest.path.name} "
            f"(hoje usa {used_name}). A ZMM119 carregada é preservada."
        ),
    }


# --------------------------------------------------------------- Health Center


CONNECTIVITY_KEYS = ("health:network", "health:n8n")


def connectivity_cause(indicators: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Indicador que deixa o agente sem conexão (n8n inacessível); a VPN, quando fora, é apontada como causa.

    Sem n8n o agente não consegue escrever: quem avisa é o próprio sistema (Health Center).
    Com a VPN fora mas o n8n acessível, o agente escreve normalmente (evento health:network).
    """
    by_key = {str(item.get("key")): item for item in indicators}
    n8n = by_key.get("n8n")
    if n8n is None or n8n.get("level") == "healthy":
        return None
    network = by_key.get("network")
    if network is not None and network.get("level") in {"warning", "critical"}:
        return network
    return n8n


def health_events(health: dict[str, Any] | None, documentation=None) -> list[dict[str, Any]]:
    events = []
    for item in (health or {}).get("indicators") or []:
        level = str(item.get("level") or "")
        key = str(item.get("key") or "")
        if level not in {"warning", "critical"} or key in IGNORED_HEALTH:
            continue
        if key == "sap" and level == "warning":
            continue  # falha da última extração: a oferta de importação já trata
        if key == "n8n":
            continue  # sem n8n o agente não escreve: o aviso de conexão do sistema trata (connectivity_cause)
        events.append({
            "key": f"health:{key}",
            "fingerprint": f"{level}|{item.get('status')}",
            "event": {
                "type": "health_center",
                "topic": f"Health Center {item.get('title')}",
                "indicator": {name: item.get(name) for name in ("key", "title", "level", "status", "summary", "details", "fix", "support_email")},
                "documentation": documentation(str(item.get("title") or "")) if documentation else [],
            },
            "parameters": None,
            "summary": None,
        })
    return events


def documentation_matches(settings: Any, query: str, limit: int = 3) -> list[dict[str, Any]]:
    """Trechos da Documentação técnica (página, seção e texto) sobre o assunto."""
    from .documentation import search_document

    try:
        result = search_document(settings, query)
    except Exception:  # noqa: BLE001 - documentação indisponível nesta máquina
        return []
    return [
        {"page": page["page"], "section": page.get("section"),
         "snippets": [snippet.get("text") for snippet in page.get("snippets") or []][:2]}
        for page in (result.get("pages") or [])[:limit]
    ]


# ----------------------------------------------------- outros eventos de negócio

VARIATION_TOTAL_PCT = 10.0       # variação do valor fiscal total vs competência anterior
VARIATION_DIVISION_PCT = 15.0    # variação do valor fiscal de uma divisão
RISK_INCREASE_POINTS = 2.0       # aumento (pontos percentuais) do estoque com mais de 12 meses
STUCK_JOB_MINUTES = 40


def _previous_period(connection: Any, period: str) -> str | None:
    row = connection.execute("select max(period) from inventory_rows where period < ?", [period]).fetchone()
    return str(row[0]) if row and row[0] else None


def closing_event(settings: Any, today: date | None = None) -> dict[str, Any] | None:
    """Fechamento: o mês virou e a competência do mês anterior ainda não foi compilada."""
    today = today or date.today()
    year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    expected = f"{year}-{month:02d}"
    with connect(settings.path("database")) as connection:
        exists = connection.execute("select count(*) from inventory_rows where period=?", [expected]).fetchone()[0]
        latest = connection.execute("select max(period) from inventory_rows").fetchone()[0]
    if exists:
        return None
    return {
        "key": f"closing:{expected}",
        "fingerprint": expected,
        "event": {"type": "closing_reminder", "topic": "Extrações SAP ZMM119 e MB59 da competência",
                  "missing_period": expected, "latest_compiled_period": latest, "today": today.isoformat()},
        "parameters": None,
        "summary": None,
    }


def all_brazil_quality_event(settings: Any, period: str) -> dict[str, Any] | None:
    with connect(settings.path("database")) as connection:
        try:
            row = connection.execute(
                """select snapshot_date, source_path, inventory_keys, matched_keys, coverage_pct, duplicate_keys, conflict_keys
                   from all_brazil_imports where period=?""",
                [period],
            ).fetchone()
        except Exception:  # noqa: BLE001 - tabela ainda não criada
            row = None
    if row is None:
        return None
    coverage, conflicts = float(row[4] or 0), int(row[6] or 0)
    if coverage >= 100 and conflicts == 0:
        return None
    return {
        "key": f"all_brazil_quality:{period}",
        "fingerprint": f"{coverage:.2f}|{conflicts}",
        "event": {"type": "all_brazil_quality", "topic": "cobertura e conflitos do All Brazil", "period": period,
                  "file": Path(str(row[1])).name, "inventory_keys": int(row[2] or 0), "matched_keys": int(row[3] or 0),
                  "coverage_pct": coverage, "duplicate_keys": int(row[5] or 0), "conflict_keys": conflicts},
        "parameters": None,
        "summary": None,
    }


def variation_event(settings: Any, period: str) -> dict[str, Any] | None:
    """Mudanças relevantes vs competência anterior: valor fiscal total, por divisão e estoque com mais de 12 meses."""
    risky = "regexp_matches(coalesce(aging_bucket,''), '^[5-8]\\)')"
    with connect(settings.path("database")) as connection:
        previous = _previous_period(connection, period)
        if previous is None:
            return None

        def snapshot(target: str) -> dict[str, Any]:
            total = float(connection.execute(
                "select coalesce(sum(fiscal_total_amount),0) from inventory_rows where period=?", [target]).fetchone()[0])
            rows = connection.execute(
                f"""select coalesce(nullif(trim(division_description),''),'Não informado'),
                           coalesce(sum(fiscal_total_amount),0),
                           coalesce(sum(case when {risky} then fiscal_total_amount else 0 end),0),
                           coalesce(sum(case when coalesce(aging_bucket,'') like '0)%' then fiscal_total_amount else 0 end),0)
                    from inventory_rows where period=? group by 1""",
                [target],
            ).fetchall()
            divisions = {}
            for label, value, risk, futures in rows:
                received = float(value) - float(futures)
                divisions[str(label)] = {"value": float(value), "risk_pct": round(100 * float(risk) / received, 2) if received > 0 else 0.0}
            return {"total": total, "divisions": divisions}

        current, before = snapshot(period), snapshot(previous)
    findings = []
    if before["total"]:
        change = 100 * (current["total"] - before["total"]) / before["total"]
        if abs(change) >= VARIATION_TOTAL_PCT:
            findings.append({"kind": "total_fiscal_value", "previous": round(before["total"], 2),
                             "current": round(current["total"], 2), "change_pct": round(change, 2)})
    for label, data in current["divisions"].items():
        old = before["divisions"].get(label)
        if not old:
            continue
        if old["value"]:
            change = 100 * (data["value"] - old["value"]) / old["value"]
            if abs(change) >= VARIATION_DIVISION_PCT:
                findings.append({"kind": "division_fiscal_value", "division": label, "previous": round(old["value"], 2),
                                 "current": round(data["value"], 2), "change_pct": round(change, 2)})
        if data["risk_pct"] - old["risk_pct"] >= RISK_INCREASE_POINTS:
            findings.append({"kind": "obsolescence_risk_increase", "division": label, "previous_pct_over_12_months": old["risk_pct"],
                             "current_pct_over_12_months": data["risk_pct"]})
    if not findings:
        return None
    return {
        "key": f"variation:{period}",
        "fingerprint": json.dumps(sorted((item["kind"], item.get("division", "")) for item in findings)),
        "event": {"type": "relevant_variation", "topic": "variação da posição de estoque e risco de obsolescência",
                  "period": period, "previous_period": previous, "findings": findings,
                  "thresholds": {"total_pct": VARIATION_TOTAL_PCT, "division_pct": VARIATION_DIVISION_PCT,
                                 "risk_points": RISK_INCREASE_POINTS}},
        "parameters": None,
        "summary": None,
    }


def stuck_job_events(jobs: list[dict[str, Any]], now: float) -> list[dict[str, Any]]:
    from datetime import datetime

    events = []
    for job in jobs:
        status = str(job.get("status") or "")
        if status in {"COMPLETED", "FAILED", "CANCELLED", "ACTION_REQUIRED"} or not job.get("started_at"):
            continue
        try:
            started = datetime.fromisoformat(str(job["started_at"])).timestamp()
        except ValueError:
            continue
        minutes = (now - started) / 60
        if minutes < STUCK_JOB_MINUTES:
            continue
        events.append({
            "key": f"stuck_job:{job.get('job_id')}",
            "fingerprint": "stuck",
            "event": {"type": "sap_job_stuck", "topic": "Extrações SAP execução travada cancelar",
                      "transaction": job.get("transaction"), "period": job.get("period"), "status": status,
                      "message": job.get("message"), "running_minutes": round(minutes), "source": job.get("source")},
            "parameters": None,
            "summary": None,
        })
    return events


def latest_period_event(settings: Any, period: str) -> dict[str, Any]:
    """Nova competência compilada (carga local ou recebida pela ponte do Drive). Só avisa quando muda."""
    with connect(settings.path("database")) as connection:
        rows, value = connection.execute(
            "select count(*), coalesce(sum(fiscal_total_amount),0) from inventory_rows where period=?", [period]).fetchone()
    return {
        "key": "latest_period",
        "fingerprint": period,
        "silent_first": True,
        "event": {"type": "new_period_available", "topic": "Visão e relatórios competência", "period": period,
                  "rows": int(rows), "fiscal_value": round(float(value), 2)},
        "parameters": None,
        "summary": None,
    }


def documentation_event(settings: Any) -> dict[str, Any] | None:
    from .documentation import document_info

    try:
        info = document_info(settings)
    except Exception:  # noqa: BLE001 - documentação indisponível
        return None
    if not info.get("available"):
        return None
    return {
        "key": "documentation",
        "fingerprint": str(info.get("version") or info.get("doc_version")),
        "silent_first": True,
        "event": {"type": "documentation_updated", "topic": "Documentação", "doc_version": info.get("doc_version"),
                  "generated_at": info.get("generated_at"), "pages": info.get("pages")},
        "parameters": None,
        "summary": None,
    }


# --------------------------------------------------------------- controle de repetição


def collect_events(
    settings: Any, period: str, health: dict[str, Any] | None, jobs: list[dict[str, Any]] | None = None,
    now: float | None = None,
) -> list[dict[str, Any]]:
    import time

    events: list[dict[str, Any]] = []
    checks = (
        lambda: all_brazil_event(settings, period),
        lambda: mapping_event(settings, period),
        lambda: inventory_gap_event(settings, period),
        lambda: closing_event(settings),
        lambda: all_brazil_quality_event(settings, period),
        lambda: variation_event(settings, period),
        lambda: latest_period_event(settings, period),
        lambda: documentation_event(settings),
    )
    for check in checks:
        try:
            event = check()
        except Exception:  # noqa: BLE001 - uma verificação com erro não impede as demais
            event = None
        if event:
            events.append(event)
    events.extend(stuck_job_events(jobs or [], now or time.time()))
    events.extend(health_events(health, lambda title: documentation_matches(settings, title)))
    return events


def new_events(settings: Any, events: list[dict[str, Any]], scope: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    """Só o que é novo ou mudou desde o último ciclo; problemas resolvidos saem da memória.

    Eventos informativos (silent_first) só avisam quando mudam: na primeira verificação viram a referência.
    Com scope (ex.: CONNECTIVITY_KEYS), a verificação é parcial: só essas chaves são atualizadas.
    """
    with connect(settings.path("database")) as connection:
        row = connection.execute("select setting_value from system_settings where setting_key=?", [WATCH_SEEN_KEY]).fetchone()
        try:
            seen = json.loads(row[0]) if row else {}
        except (TypeError, ValueError):
            seen = {}
        fresh = [
            event for event in events
            if seen.get(event["key"]) != event["fingerprint"] and not (event.get("silent_first") and event["key"] not in seen)
        ]
        current = {event["key"]: event["fingerprint"] for event in events}
        if scope:
            current = {**{key: value for key, value in seen.items() if key not in scope}, **current}
        connection.execute(
            """insert into system_settings(setting_key,setting_value,updated_at) values (?,?,current_timestamp)
               on conflict(setting_key) do update set setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
            [WATCH_SEEN_KEY, json.dumps(current, ensure_ascii=False)],
        )
    return fresh
