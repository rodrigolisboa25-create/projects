"""Agenda de fechamento: janela (último dia → 3º dia útil), fases, rotas, aviso do Optimus e Drive compartilhado."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ops_contabil import closing_agenda as agenda
from ops_contabil.db import connect
from ops_contabil.inventory import ensure_inventory_schema
from ops_contabil.settings import Settings
from test_optimus_import import ADMIN, USER, env  # noqa: F401 - fixture reaproveitada


def machine(tmp_path: Path, name: str) -> Settings:
    database = tmp_path / name / "processed" / "ops.duckdb"
    database.parent.mkdir(parents=True)
    settings = Settings(root=tmp_path / name, raw={
        "project": {"database": str(database), "processed": str(database.parent), "output": str(tmp_path / name / "output")},
        "runtime": {"machine_name": name}})
    with connect(database) as connection:
        ensure_inventory_schema(connection)
    return settings


def test_default_window_goes_from_the_last_day_to_the_third_business_day() -> None:
    # 31/10/2026 é sábado: o fechamento começa imediatamente no dia útil anterior (sexta 30/10).
    october = agenda.window(None, "2026-10", {})
    assert (october["start"], october["end"]) == ("2026-10-30", "2026-11-05")  # 02/11 Finados não conta
    assert october["business_days"] == ["2026-10-30", "2026-11-03", "2026-11-04", "2026-11-05"]
    september = agenda.window(None, "2026-09", {})
    assert september["start"] == "2026-09-30"  # último dia útil: começa nele mesmo
    march = agenda.window(None, "2026-03", {})
    assert march["end"] == "2026-04-06"  # 03/04 Sexta-feira Santa
    assert "último dia útil do mês até o 3º dia útil" in march["rule_text"]
    may = agenda.window(None, "2026-05", {})
    assert may["start"] == "2026-05-29"  # 31/05 é domingo e 30/05 sábado
    # Regra antiga gravada com "último dia do mês" também passa a seguir o dia útil anterior.
    old = {"rule": {"data": {"start": "last_day", "end_business_day": 5}}}
    assert agenda.window(None, "2026-10", old)["start"] == "2026-10-30"
    assert agenda.window(None, "2026-10", old)["end"] == "2026-11-09"


def test_phases_follow_today() -> None:
    before = agenda.status(None, date(2026, 10, 28), {"closed:2026-09": {"data": {"closed": True}}})
    assert before["period"] == "2026-10" and before["phase"] == "proximo" and before["days_to_start"] == 2 and before["alert"]
    running = agenda.status(None, date(2026, 11, 4), {})  # 30/10, 03/11, 04/11, 05/11
    assert running["phase"] == "em_andamento" and running["business_day_index"] == 3 and running["business_days_total"] == 4
    late = agenda.status(None, date(2026, 10, 11), {})
    assert late["period"] == "2026-09" and late["phase"] == "atrasado" and late["days_to_end"] == -6
    done = agenda.status(None, date(2026, 10, 3), {"closed:2026-09": {"data": {"closed": True}}})
    assert done["period"] == "2026-09" and done["phase"] == "concluido"


def test_page_routes_rules_tasks_and_calendar_export(env) -> None:  # noqa: F811
    settings, _db, _downloads, client_for, _sent, _replies = env
    user, _ = client_for(USER)
    assert user.get("/api/closing/overview").status_code == 403  # página não liberada para este usuário
    client, csrf = client_for(ADMIN)
    headers = {"X-CSRF-Token": csrf}
    data = client.get("/api/closing/overview", params={"year": 2026, "month": 10}).json()
    assert data["rule"] == agenda.DEFAULT_RULE and len(data["year_windows"]) == 12 and len(data["checklist"]) == 7
    assert [w["period"] for w in data["windows"]] == ["2026-09", "2026-10"]

    assert client.put("/api/closing/rule", headers=headers, json={"start": "last_day", "end_business_day": 2, "pre_alert_days": 5}).status_code == 200
    assert agenda.window(settings, "2026-10")["end"] == "2026-11-04"
    saved = client.put("/api/closing/windows/2026-10", headers=headers,
                       json={"start_date": "2026-10-30", "end_date": "2026-11-06", "notes": "Inventário no CD"}).json()
    assert saved["source"] == "definida" and saved["notes"] == "Inventário no CD"
    assert client.put("/api/closing/windows/2026-10", headers=headers, json={"start_date": "2026-11-10", "end_date": "2026-11-01"}).status_code == 400
    client.put("/api/closing/windows/2026-10", headers=headers, json={})  # volta à regra
    assert agenda.window(settings, "2026-10")["source"] == "regra"

    task = client.post("/api/closing/tasks", headers=headers,
                       json={"period": "2026-10", "title": "Conciliar trânsito", "due_date": "2026-11-03", "owner": "Gabriella"}).json()
    client.put(f"/api/closing/tasks/{task['id']}", headers=headers, json={"done": True})
    assert agenda.tasks(agenda.entries(settings), "2026-10")[0]["done"] is True
    client.delete(f"/api/closing/tasks/{task['id']}", headers=headers)
    assert agenda.tasks(agenda.entries(settings), "2026-10") == []

    client.put("/api/closing/holidays", headers=headers, json={"date": "2026-11-03", "name": "Ponte", "enabled": True})
    assert "2026-11-03" not in agenda.window(settings, "2026-10")["business_days"]
    client.post("/api/closing/windows/2026-09/closed", headers=headers, json={"closed": True})
    assert agenda.window(settings, "2026-09")["closed"] is True

    assert client.get("/api/closing/ics", params={"year": 2026}).status_code == 404  # exportação .ics retirada


def test_optimus_milestones(env) -> None:  # noqa: F811
    settings, *_ = env
    agenda.put_entry(settings, "closed:2026-09", {"closed": True}, by=ADMIN)
    assert agenda.agenda_event(settings, date(2026, 10, 20)) is None  # longe do início: sem aviso
    assert agenda.agenda_event(settings, date(2026, 10, 28))["fingerprint"] == "pre_aviso"
    assert agenda.agenda_event(settings, date(2026, 10, 30))["fingerprint"] == "inicio"  # sexta: 31/10 é sábado
    start = agenda.agenda_event(settings, date(2026, 11, 3))
    assert start["key"] == "closing_agenda:2026-10" and start["fingerprint"] == "inicio" and start["event"]["pending_checklist"]
    assert agenda.agenda_event(settings, date(2026, 11, 5))["fingerprint"] == "ultimo_dia"
    agenda.put_entry(settings, "closed:2026-10", {"closed": True}, by=ADMIN)
    assert agenda.agenda_event(settings, date(2026, 11, 5)) is None


def test_dates_travel_between_machines_by_the_drive(tmp_path: Path) -> None:
    root = tmp_path / "Estoque_Cont"
    a, b = machine(tmp_path, "PC-A"), machine(tmp_path, "PC-B")
    agenda.put_entry(a, "window:2026-10", {"start_date": "2026-10-30", "end_date": "2026-11-06"}, by="a@gruposbf.com.br")
    agenda.save_rule(a, {"end_business_day": 4}, "a@gruposbf.com.br")
    assert agenda.sync_agenda(a, root)["published"] is True
    assert (root / "agenda" / "alteracoes" / "PC-A.json").is_file()
    received = agenda.sync_agenda(b, root)
    assert received["received"] == 2 and agenda.window(b, "2026-10")["end"] == "2026-11-06"
    assert agenda.rule(agenda.entries(b))["end_business_day"] == 4

    # A alteração mais recente vence, inclusive exclusão (voltar à regra) feita na outra máquina.
    agenda.save_window(b, "2026-10", {}, "b@gruposbf.com.br")
    agenda.sync_agenda(b, root)
    agenda.sync_agenda(a, root)
    assert agenda.window(a, "2026-10")["source"] == "regra"
