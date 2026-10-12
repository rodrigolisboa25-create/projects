"""Agenda de Fechamento contábil (página ANÁLISE CONTÁBIL > Agenda de fechamento).

Regra padrão do negócio: o fechamento da competência AAAA-MM começa no último dia útil do mês (se o último dia
cair em fim de semana ou feriado, vale o dia útil imediatamente anterior) e vai até o 3º dia
útil do mês seguinte (dias úteis = segunda a sexta, sem feriados nacionais nem os cadastrados). A equipe pode
mudar a regra e definir datas próprias mês a mês; a página mostra a janela, a contagem regressiva, o checklist
automático (o que o sistema já sabe: ZMM119, MB59, All Brazil, PASSO A PASSO, Mapping, relatório e
apresentação), tarefas da equipe e os eventos do sistema no calendário.

Tudo o que a equipe define é um "registro" (regra, janela do mês, fechamento concluído, tarefa, feriado) com
data/hora da alteração. Os registros valem para todas as máquinas pela pasta do Drive (Estoque_Cont/agenda),
no mesmo desenho do Mapping compartilhado: cada máquina grava só o próprio arquivo e, por registro, vale a
alteração mais recente (exclusões também ficam registradas).
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .access_sync import _read_json, machine_file_name, machine_name, utc_now
from .access_sync import load_state as load_access_state
from .db import connect

AGENDA_FOLDER = "agenda"
JOURNAL_FOLDER = "alteracoes"
STATE_KEY = "closing_state"
FORMAT_VERSION = 1
DEFAULT_RULE = {"start": "last_business_day", "end_business_day": 3, "pre_alert_days": 3}
MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
          "novembro", "dezembro")
WEEKDAYS = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
_LOCK = threading.Lock()


# ------------------------------------------------------------------ armazenamento local


def ensure_closing_schema(connection) -> None:
    connection.execute(
        """create table if not exists closing_entries (
               entry_key varchar primary key, payload varchar, changed_at varchar, changed_by varchar,
               deleted boolean default false)"""
    )


def entries(settings: Any, include_deleted: bool = False) -> dict[str, dict[str, Any]]:
    with connect(settings.path("database")) as connection:
        ensure_closing_schema(connection)
        rows = connection.execute("select entry_key, payload, changed_at, changed_by, deleted from closing_entries").fetchall()
    result = {}
    for key, payload, changed_at, changed_by, deleted in rows:
        if deleted and not include_deleted:
            continue
        try:
            data = json.loads(payload or "{}")
        except ValueError:
            data = {}
        result[key] = {"data": data, "changed_at": changed_at, "changed_by": changed_by, "deleted": bool(deleted)}
    return result


def _write(settings: Any, key: str, data: dict[str, Any] | None, *, by: str, changed_at: str | None = None,
           deleted: bool = False) -> None:
    with connect(settings.path("database")) as connection:
        ensure_closing_schema(connection)
        connection.execute(
            """insert into closing_entries(entry_key,payload,changed_at,changed_by,deleted) values (?,?,?,?,?)
               on conflict(entry_key) do update set payload=excluded.payload, changed_at=excluded.changed_at,
                 changed_by=excluded.changed_by, deleted=excluded.deleted""",
            [key, json.dumps(data or {}, ensure_ascii=False), changed_at or utc_now(), by, deleted],
        )


def put_entry(settings: Any, key: str, data: dict[str, Any] | None, *, by: str, deleted: bool = False) -> None:
    """Alteração feita nesta máquina: grava e marca para publicar no Drive."""
    _write(settings, key, data, by=by, deleted=deleted)
    _update_state(settings, lambda state: state.update(publisher=True, pending_publish=True))


def load_state(settings: Any) -> dict[str, Any]:
    with connect(settings.path("database")) as connection:
        row = connection.execute("select setting_value from system_settings where setting_key=?", [STATE_KEY]).fetchone()
    try:
        state = json.loads(row[0]) if row else {}
    except (TypeError, ValueError):
        state = {}
    return state if isinstance(state, dict) else {}


def _update_state(settings: Any, mutate) -> dict[str, Any]:
    with _LOCK:
        state = load_state(settings)
        mutate(state)
        with connect(settings.path("database")) as connection:
            connection.execute(
                """insert into system_settings(setting_key,setting_value,updated_at) values (?,?,current_timestamp)
                   on conflict(setting_key) do update set setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
                [STATE_KEY, json.dumps(state, ensure_ascii=False)],
            )
        return state


# ------------------------------------------------------------------ calendário: feriados e dias úteis


def _easter(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def national_holidays(year: int) -> list[dict[str, Any]]:
    easter = _easter(year)
    fixed = [((1, 1), "Confraternização Universal"), ((4, 21), "Tiradentes"), ((5, 1), "Dia do Trabalho"),
             ((9, 7), "Independência do Brasil"), ((10, 12), "Nossa Senhora Aparecida"), ((11, 2), "Finados"),
             ((11, 15), "Proclamação da República"), ((11, 20), "Dia da Consciência Negra"), ((12, 25), "Natal")]
    items = [{"date": date(year, m, d), "name": name, "kind": "nacional"} for (m, d), name in fixed]
    items += [{"date": easter - timedelta(days=48), "name": "Carnaval (ponto facultativo)", "kind": "nacional"},
              {"date": easter - timedelta(days=47), "name": "Carnaval (ponto facultativo)", "kind": "nacional"},
              {"date": easter - timedelta(days=2), "name": "Sexta-feira Santa", "kind": "nacional"},
              {"date": easter + timedelta(days=60), "name": "Corpus Christi (ponto facultativo)", "kind": "nacional"}]
    return sorted(items, key=lambda item: item["date"])


def holidays(settings: Any, year: int, data: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Feriados do ano: nacionais (desativáveis) + os cadastrados pela equipe."""
    data = entries(settings) if data is None else data
    result = {item["date"]: {**item, "enabled": True} for item in national_holidays(year)}
    for key, entry in data.items():
        if not key.startswith("holiday:"):
            continue
        try:
            day = date.fromisoformat(key.split(":", 1)[1])
        except ValueError:
            continue
        if day.year != year:
            continue
        base = result.get(day, {"date": day, "kind": "cadastrado"})
        result[day] = {**base, "name": entry["data"].get("name") or base.get("name") or "Feriado",
                       "enabled": entry["data"].get("enabled", True) is not False}
    return [{**item, "date": item["date"].isoformat()} for item in sorted(result.values(), key=lambda item: item["date"])]


def _holiday_set(settings: Any, years: set[int], data: dict[str, dict[str, Any]]) -> set[date]:
    return {date.fromisoformat(item["date"]) for year in years for item in holidays(settings, year, data) if item["enabled"]}


def is_business_day(day: date, blocked: set[date]) -> bool:
    return day.weekday() < 5 and day not in blocked


def nth_business_day(year: int, month: int, n: int, blocked: set[date]) -> date:
    day, count = date(year, month, 1), 0
    while True:
        if is_business_day(day, blocked):
            count += 1
            if count >= n:
                return day
        day += timedelta(days=1)


def _shift(period: str, months: int) -> str:
    year, month = map(int, period.split("-"))
    index = year * 12 + month - 1 + months
    return f"{index // 12}-{index % 12 + 1:02d}"


def period_label(period: str) -> str:
    year, month = period.split("-")
    return f"{MONTHS[int(month) - 1]}/{year}"


def rule(data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    stored = (data.get("rule") or {}).get("data") or {}
    merged = {**DEFAULT_RULE, **{k: v for k, v in stored.items() if k in DEFAULT_RULE}}
    merged["end_business_day"] = max(1, min(10, int(merged["end_business_day"])))
    merged["pre_alert_days"] = max(0, min(10, int(merged["pre_alert_days"])))
    # Regra do negócio: o fechamento começa no último dia do mês; se ele não for dia útil
    # (fim de semana ou feriado), vale imediatamente o dia útil anterior. Regras antigas
    # gravadas com "last_day" passam a seguir essa regra.
    merged["start"] = "last_business_day"
    return merged


def window(settings: Any, period: str, data: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Janela de fechamento da competência (regra padrão ou datas definidas para o mês)."""
    data = entries(settings) if data is None else data
    current = rule(data)
    year, month = map(int, period.split("-"))
    next_year, next_month = map(int, _shift(period, 1).split("-"))
    blocked = _holiday_set(settings, {year, next_year}, data)
    last = date(year, month, monthrange(year, month)[1])
    start = last
    if current["start"] == "last_business_day":
        while not is_business_day(start, blocked):
            start -= timedelta(days=1)
    end = nth_business_day(next_year, next_month, current["end_business_day"], blocked)
    custom = (data.get(f"window:{period}") or {}).get("data") or {}
    source = "regra"
    try:
        if custom.get("start_date"):
            start, source = date.fromisoformat(custom["start_date"]), "definida"
        if custom.get("end_date"):
            end, source = date.fromisoformat(custom["end_date"]), "definida"
    except ValueError:
        pass
    if end < start:
        end = start
    closed = (data.get(f"closed:{period}") or {})
    business = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    business = [day for day in business if is_business_day(day, blocked)]
    return {
        "period": period, "label": period_label(period), "start": start.isoformat(), "end": end.isoformat(),
        "source": source, "notes": custom.get("notes") or "",
        "rule_text": (f"{'último dia útil' if current['start'] == 'last_business_day' else 'último dia'} do mês até o "
                      f"{current['end_business_day']}º dia útil do mês seguinte"),
        "business_days": [day.isoformat() for day in business], "calendar_days": (end - start).days + 1,
        "closed": bool(closed.get("data", {}).get("closed")), "closed_by": closed.get("changed_by") if closed.get("data", {}).get("closed") else None,
        "closed_at": closed.get("changed_at") if closed.get("data", {}).get("closed") else None,
    }


def status(settings: Any, today: date | None = None, data: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Fechamento em foco hoje: o do mês anterior enquanto a janela dele não terminou (ou não foi concluído, por
    até 10 dias depois do prazo); senão, o do mês atual."""
    today = today or date.today()
    data = entries(settings) if data is None else data
    current_period = f"{today.year}-{today.month:02d}"
    previous = window(settings, _shift(current_period, -1), data)
    prev_end = date.fromisoformat(previous["end"])
    if today <= prev_end or (not previous["closed"] and today <= prev_end + timedelta(days=10)):
        focus = previous
    else:
        focus = window(settings, current_period, data)
    start, end = date.fromisoformat(focus["start"]), date.fromisoformat(focus["end"])
    business = [date.fromisoformat(day) for day in focus["business_days"]]
    if focus["closed"]:
        phase = "concluido"
    elif today < start:
        phase = "proximo"
    elif today <= end:
        phase = "em_andamento"
    else:
        phase = "atrasado"
    elapsed = sum(1 for day in business if day <= today)
    pre_alert = rule(data)["pre_alert_days"]
    return {
        **focus, "today": today.isoformat(), "phase": phase,
        "days_to_start": (start - today).days, "days_to_end": (end - today).days,
        "business_day_index": elapsed, "business_days_total": len(business),
        "pct_time": round(100 * min(1, max(0, (today - start).days + 1) / max(1, (end - start).days + 1)), 1),
        "alert": phase == "em_andamento" or phase == "atrasado" or (phase == "proximo" and (start - today).days <= pre_alert),
        "pre_alert_days": pre_alert,
    }


# ------------------------------------------------------------------ checklist, tarefas e eventos


def checklist(settings: Any, period: str) -> list[dict[str, Any]]:
    """O que o sistema já sabe sobre o fechamento da competência (sem digitar nada)."""
    items: list[dict[str, Any]] = []

    def one(connection, sql: str, params: list[Any]) -> Any:
        try:
            row = connection.execute(sql, params).fetchone()
            return row[0] if row else None
        except Exception:  # noqa: BLE001 - tabela ainda não criada nesta máquina
            return None

    with connect(settings.path("database")) as connection:
        zmm = one(connection, "select imported_at from inventory_imports where period=?", [period])
        mb59 = one(connection, "select count(*) from mb59_imports where period=?", [period])
        all_brazil = one(connection, "select coverage_pct from all_brazil_imports where period=?", [period])
        pending = one(connection, """select count(*) from inventory_rows where period=? and
                                     (product_offer_end_date is null or season is null or year is null)""", [period]) if zmm else None
        unmapped = one(connection, """select count(distinct plant) from inventory_rows where period=? and
                                      coalesce(nullif(trim(cast(location_group as varchar)),''),'')=''""", [period]) if zmm else None
    output = settings.path("output")
    reports = [output / "pdf" / f"Relatorio_Estoque_Contabil_{period}.pdf", output / "html" / f"Relatorio_Estoque_Contabil_{period}.html"]
    report = next((path for path in reports if path.is_file()), None)
    try:
        from .presentations import latest_deck
        deck = latest_deck(settings, period)
    except Exception:  # noqa: BLE001
        deck = None
    when = lambda value: str(value)[:16].replace("T", " ") if value else ""  # noqa: E731
    items.append({"key": "zmm119", "label": "ZMM119 da competência carregada", "done": bool(zmm),
                  "detail": f"carregada em {when(zmm)}" if zmm else "extraia ou faça o upload da posição", "view": "sap"})
    items.append({"key": "mb59", "label": "MB59 (Base GR) da competência", "done": bool(mb59),
                  "detail": "carregada" if mb59 else "extraia a MB59 do mês", "view": "sap"})
    items.append({"key": "all_brazil", "label": "All Brazil do mês aplicada", "done": all_brazil is not None,
                  "detail": f"cobertura {float(all_brazil):.1f}%" if all_brazil is not None else "aguardando a base do mês",
                  "view": "all-brazil"})
    items.append({"key": "pass_step", "label": "PASSO A PASSO sem Não localizados", "done": zmm is not None and not pending,
                  "detail": (f"{int(pending)} linha(s) sem PO End/Season/Year" if pending else "completo") if zmm else "depende da ZMM119",
                  "view": "inventory"})
    items.append({"key": "mapping", "label": "Todos os centros com local no Mapping", "done": zmm is not None and not unmapped,
                  "detail": (f"{int(unmapped)} centro(s) sem local" if unmapped else "todos mapeados") if zmm else "depende da ZMM119",
                  "view": "mapping"})
    items.append({"key": "report", "label": "Relatório da Visão e relatórios gerado (PDF ou HTML)", "done": report is not None,
                  "detail": f"{report.suffix[1:].upper()} de {datetime.fromtimestamp(report.stat().st_mtime):%d/%m %H:%M}" if report else "gere pelo Share Link ou pelo Optimus",
                  "view": "overview"})
    items.append({"key": "presentation", "label": "Apresentação da competência", "done": deck is not None,
                  "detail": f"versão {deck[0].get('version')} · {deck[0].get('slides')} slides" if deck else "peça ao Optimus",
                  "view": "agent"})
    return items


def tasks(data: dict[str, dict[str, Any]], period: str | None = None) -> list[dict[str, Any]]:
    result = []
    for key, entry in data.items():
        if key.startswith("task:") and (period is None or entry["data"].get("period") == period):
            result.append({"id": key.split(":", 1)[1], **entry["data"], "changed_by": entry["changed_by"]})
    return sorted(result, key=lambda task: (bool(task.get("done")), str(task.get("due_date") or "9999"), str(task.get("title"))))


def system_events(settings: Any, year: int, month: int, data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Marcos do sistema no mês: cargas, apresentações, tarefas e fechamentos concluídos."""
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    events: list[dict[str, Any]] = []

    def add(value: Any, label: str, kind: str, view: str) -> None:
        try:
            day = value if isinstance(value, date) and not isinstance(value, datetime) else datetime.fromisoformat(str(value)[:19]).date()
        except ValueError:
            return
        if first <= day <= last:
            events.append({"date": day.isoformat(), "label": label, "kind": kind, "view": view})

    with connect(settings.path("database")) as connection:
        for table, label, view in (("inventory_imports", "ZMM119", "sap"), ("mb59_imports", "MB59", "sap"),
                                   ("all_brazil_imports", "All Brazil", "all-brazil")):
            try:
                rows = connection.execute(f"select period, imported_at from {table}").fetchall()
            except Exception:  # noqa: BLE001
                rows = []
            for period, imported_at in rows:
                add(imported_at, f"{label} {period_label(str(period))} carregada", "carga", view)
    try:
        from .presentations import storage_root
        for meta_path in storage_root(settings).glob("*/meta.json"):
            meta = _read_json(meta_path) or {}
            add(meta.get("updated_at"), f"Apresentação {period_label(str(meta.get('period') or '2000-01'))}", "apresentacao", "agent")
    except Exception:  # noqa: BLE001
        pass
    for task in tasks(data):
        if task.get("due_date"):
            add(task["due_date"], f"Tarefa: {task.get('title')}", "tarefa_feita" if task.get("done") else "tarefa", "closing")
    for key, entry in data.items():
        if key.startswith("closed:") and entry["data"].get("closed"):
            add(entry["changed_at"], f"Fechamento {period_label(key.split(':', 1)[1])} concluído", "concluido", "closing")
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for event in events:  # mesmo evento repetido no dia (ex.: várias versões de apresentação) vira uma linha com contagem
        key = (event["date"], event["label"], event["kind"])
        if key in grouped:
            grouped[key]["count"] += 1
        else:
            grouped[key] = {**event, "count": 1}
    return [{**event, "label": event["label"] + (f" (×{event['count']})" if event["count"] > 1 else "")}
            for event in sorted(grouped.values(), key=lambda item: (item["date"], item["kind"]))]


def overview(settings: Any, year: int, month: int, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    data = entries(settings)
    period = f"{year}-{month:02d}"
    # Janelas que aparecem no mês: a da competência anterior (termina no começo do mês) e a do próprio mês.
    windows = [window(settings, _shift(period, -1), data), window(settings, period, data)]
    year_windows = [window(settings, f"{year}-{m:02d}", data) for m in range(1, 13)]
    focus = status(settings, today, data)
    for item in year_windows:
        start, end = date.fromisoformat(item["start"]), date.fromisoformat(item["end"])
        mine = item["period"] == focus["period"]
        # Passado sem registro de conclusão: só o fechamento em foco fica "pendente"; os anteriores, "encerrado".
        item["state"] = ("concluido" if item["closed"] else "em_andamento" if start <= today <= end
                         else ("atrasado" if mine else "encerrado") if today > end else "proximo" if mine else "planejado")
    return {
        "today": today.isoformat(), "month": period, "month_label": period_label(period), "rule": rule(data),
        "status": focus, "checklist": checklist(settings, focus["period"]), "tasks": tasks(data, focus["period"]),
        "all_tasks": tasks(data), "windows": windows, "year": year, "year_windows": year_windows,
        "holidays": holidays(settings, year, data) + holidays(settings, year + 1, data)[:3],
        "events": system_events(settings, year, month, data), "sync": sync_status(settings),
    }


# ------------------------------------------------------------------ alterações pela página


def save_rule(settings: Any, payload: dict[str, Any], by: str) -> dict[str, Any]:
    clean = rule({"rule": {"data": payload}})
    put_entry(settings, "rule", clean, by=by)
    return clean


def save_window(settings: Any, period: str, payload: dict[str, Any], by: str) -> dict[str, Any]:
    start, end = payload.get("start_date") or None, payload.get("end_date") or None
    for value in (start, end):
        if value:
            date.fromisoformat(value)
    if start and end and end < start:
        raise ValueError("A data final do fechamento não pode ser anterior à data inicial.")
    if not start and not end and not (payload.get("notes") or "").strip():
        put_entry(settings, f"window:{period}", {}, by=by, deleted=True)  # volta à regra padrão
    else:
        put_entry(settings, f"window:{period}", {"start_date": start, "end_date": end,
                                                 "notes": str(payload.get("notes") or "")[:500]}, by=by)
    return window(settings, period)


def set_closed(settings: Any, period: str, closed: bool, by: str) -> dict[str, Any]:
    put_entry(settings, f"closed:{period}", {"closed": bool(closed)}, by=by)
    return window(settings, period)


def save_task(settings: Any, payload: dict[str, Any], by: str, task_id: str | None = None) -> dict[str, Any]:
    task_id = task_id or uuid.uuid4().hex[:12]
    current = (entries(settings).get(f"task:{task_id}") or {}).get("data") or {}
    title = str(payload.get("title", current.get("title")) or "").strip()[:160]
    if not title:
        raise ValueError("Informe a descrição da tarefa.")
    due = payload.get("due_date", current.get("due_date")) or None
    if due:
        date.fromisoformat(due)
    done = bool(payload.get("done", current.get("done", False)))
    data = {"period": payload.get("period") or current.get("period"), "title": title, "due_date": due,
            "owner": str(payload.get("owner", current.get("owner")) or "").strip()[:80], "done": done,
            "done_by": by if done and not current.get("done") else current.get("done_by") if done else None}
    put_entry(settings, f"task:{task_id}", data, by=by)
    return {"id": task_id, **data}


def delete_task(settings: Any, task_id: str, by: str) -> None:
    put_entry(settings, f"task:{task_id}", {}, by=by, deleted=True)


def save_holiday(settings: Any, day: str, name: str, enabled: bool, by: str) -> None:
    date.fromisoformat(day)
    put_entry(settings, f"holiday:{day}", {"name": (name or "Feriado").strip()[:80], "enabled": bool(enabled)}, by=by)


# ------------------------------------------------------------------ aviso do Optimus


def agenda_event(settings: Any, today: date | None = None) -> dict[str, Any] | None:
    """Marcos do fechamento para o Optimus avisar no chat: X dias antes (regra), início, último dia e atraso."""
    today = today or date.today()
    current = status(settings, today)
    if current["phase"] == "concluido":
        return None
    start, end = date.fromisoformat(current["start"]), date.fromisoformat(current["end"])
    if current["phase"] == "proximo" and (start - today).days > current["pre_alert_days"]:
        return None
    milestone = ("atrasado" if current["phase"] == "atrasado" else "ultimo_dia" if today == end
                 else "inicio" if start <= today else "pre_aviso")
    pending = [item["label"] for item in checklist(settings, current["period"]) if not item["done"]]
    return {
        "key": f"closing_agenda:{current['period']}",
        "fingerprint": milestone,
        "event": {"type": "closing_agenda", "topic": "Agenda de fechamento", "milestone": milestone,
                  "period": current["period"], "label": current["label"], "start": current["start"], "end": current["end"],
                  "days_to_start": current["days_to_start"], "days_to_end": current["days_to_end"],
                  "business_day_index": current["business_day_index"], "business_days_total": current["business_days_total"],
                  "pending_checklist": pending, "today": today.isoformat()},
        "parameters": None,
        "summary": None,
    }


# ------------------------------------------------------------------ Drive compartilhado (Estoque_Cont/agenda)


def _journal(root: Path) -> Path:
    return root / AGENDA_FOLDER / JOURNAL_FOLDER


def sync_agenda(settings: Any, root: Path) -> dict[str, Any]:
    """Publica os registros desta máquina (se ela alterou algo ou é de administrador) e aplica os mais novos das outras."""
    local = entries(settings, include_deleted=True)
    published = False
    if load_state(settings).get("publisher") or load_access_state(settings).get("publisher"):
        folder = _journal(root)
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
    folder = _journal(root)
    if folder.is_dir():
        newest: dict[str, dict[str, Any]] = {}
        for path in sorted(folder.glob("*.json")):
            payload = _read_json(path)
            if not payload or int(payload.get("format", 0) or 0) > FORMAT_VERSION or not isinstance(payload.get("entries"), dict):
                continue
            for key, entry in payload["entries"].items():
                if isinstance(entry, dict) and (key not in newest or str(entry.get("changed_at") or "") > str(newest[key].get("changed_at") or "")):
                    newest[key] = entry
        for key, entry in newest.items():
            mine = local.get(key)
            if mine is None or str(entry.get("changed_at") or "") > str(mine.get("changed_at") or ""):
                _write(settings, key, entry.get("data") or {}, by=str(entry.get("changed_by") or ""),
                       changed_at=str(entry.get("changed_at") or utc_now()), deleted=bool(entry.get("deleted")))
                received += 1
    def mutate(state: dict[str, Any]) -> None:
        state.update(last_sync=utc_now(), error=None)
        if published:
            state["pending_publish"] = False

    _update_state(settings, mutate)
    return {"published": published, "received": received, "changed": received > 0}


def record_error(settings: Any, message: str) -> None:
    _update_state(settings, lambda state: state.update(error=message[:300]))


def sync_status(settings: Any) -> dict[str, Any]:
    state = load_state(settings)
    return {"last_sync": state.get("last_sync"), "pending_publish": bool(state.get("pending_publish")), "error": state.get("error")}
