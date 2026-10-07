"""Notificações do Windows: preferências por máquina, categorias e avisos das tarefas."""

from __future__ import annotations

from pathlib import Path

import ops_contabil.web.app as web_app
from ops_contabil.notifications import Notifier, build_toast_xml
from test_bridge_api import ADMIN, USER, drive, make_machine  # noqa: F401 - fixture drive
from test_sap_upload import upload, wait_job, zmm119_workbook


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def __call__(self, xml: str, tag: str | None) -> None:
        self.calls.append((xml, tag))


def notifier_of(client) -> Notifier:
    return client.app.state.notifier


def wait_for(notifier: Notifier, title: str, seconds: float = 10.0) -> dict:
    """O aviso é enfileirado logo depois de a tarefa mudar de status."""
    import time

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        for item in reversed(notifier.sent):
            if item["title"] == title:
                return item
        time.sleep(0.05)
    raise AssertionError(f"notificação não enviada: {title} | enviadas: {[item['title'] for item in notifier.sent]}")


def test_toast_xml_is_escaped_and_opens_the_right_page() -> None:
    xml = build_toast_xml('Carga <ZMM119> & "MB59"', "linha 1\nlinha 2", url="http://127.0.0.1:8765/#sap", sound=False)
    assert "&lt;ZMM119&gt; &amp;" in xml and "linha 1 linha 2" in xml
    assert 'launch="http://127.0.0.1:8765/#sap"' in xml and '<audio silent="true"/>' in xml
    assert "<audio" not in build_toast_xml("t", "b", url="http://x/", sound=True)


def test_preferences_gate_each_category_and_the_master_switch(tmp_path: Path) -> None:
    settings, admin, csrf = make_machine(tmp_path, "admin", ADMIN, "admin", "[]")
    recorder = Recorder()
    notifier = notifier_of(admin)
    notifier.sender = recorder

    assert notifier.notify("sap", "SAP", "ok") is True
    notifier.flush()
    assert len(recorder.calls) == 1

    admin.put("/api/notifications/preferences", json={"sap": False}, headers={"X-CSRF-Token": csrf})
    assert notifier.notify("sap", "SAP", "ok") is False
    assert notifier.notify("uploads", "Upload", "ok") is True

    admin.put("/api/notifications/preferences", json={"enabled": False}, headers={"X-CSRF-Token": csrf})
    assert notifier.notify("uploads", "Upload", "ok") is False
    sent = admin.post("/api/notifications/test", headers={"X-CSRF-Token": csrf})  # o teste sempre é enviado
    assert sent.status_code == 200
    notifier.flush()
    assert len(recorder.calls) == 3

    status = admin.get("/api/notifications/preferences").json()
    assert status["preferences"]["enabled"] is False and status["preferences"]["sap"] is False
    assert {item["key"] for item in status["categories"]} == {"sap", "uploads", "optimus", "bridge", "backup", "connectivity"}


def test_any_profile_adjusts_its_own_notifications_and_optimus_needs_its_page(tmp_path: Path) -> None:
    _, user, user_csrf = make_machine(tmp_path, "user", USER, "user", '["overview"]')
    _, chat_user, chat_csrf = make_machine(tmp_path, "chat", "chat.user@gruposbf.com.br", "user", '["overview","agent"]')

    changed = user.put("/api/notifications/preferences", json={"sound": False}, headers={"X-CSRF-Token": user_csrf})
    assert changed.status_code == 200 and changed.json()["preferences"]["sound"] is False

    assert user.post("/api/optimus/notify", json={"text": "x"}, headers={"X-CSRF-Token": user_csrf}).status_code == 403
    recorder = Recorder()
    notifier_of(chat_user).sender = recorder
    answer = "O PMM de setembro foi R$ 131,62. " * 20
    sent = chat_user.post("/api/optimus/notify", json={"text": answer}, headers={"X-CSRF-Token": chat_csrf})
    assert sent.status_code == 200 and sent.json()["sent"] is True
    notifier_of(chat_user).flush()
    last = notifier_of(chat_user).sent[-1]
    assert last["title"] == "Optimus respondeu" and last["view"] == "agent" and len(last["body"]) <= 181
    assert "estoquecontabil:abrir?view=agent" in recorder.calls[-1][0]


def test_windows_notification_click_brings_the_open_tab_to_the_task_page(tmp_path: Path) -> None:
    import asyncio

    _, admin, _csrf = make_machine(tmp_path, "admin", ADMIN, "admin", "[]")
    notifier = notifier_of(admin)
    windows = Recorder()
    notifier.sender = windows
    loop = asyncio.new_event_loop()
    try:
        tab, queue = notifier.hub.connect(loop, False)  # sistema aberto numa aba
        assert notifier.notify("sap", "Extração ZMM119 concluída · 09/2026", "ok", view="sap")
        notifier.flush()
        # Sempre notificação do Windows; o clique chama o protocolo do sistema.
        assert len(windows.calls) == 1
        item_id = notifier.sent[-1]["id"]
        assert f"estoquecontabil:abrir?view=sap&amp;id={item_id}" in windows.calls[0][0]
        loop.run_until_complete(asyncio.sleep(0))
        assert queue.get_nowait() == {"type": "notification", "id": item_id, "category": "sap", "view": "sap"}

        # Clique: sem a chave local é recusado; com a chave, a aba aberta vai para a página.
        assert admin.post("/api/notifications/activate", json={"view": "sap", "id": item_id}).status_code == 403
        clicked = admin.post("/api/notifications/activate", json={"view": "sap", "id": str(item_id)},
                             headers={"X-Ops-Activation": notifier.activation_token})
        assert clicked.status_code == 200 and clicked.json() == {"tabs": 1}
        loop.run_until_complete(asyncio.sleep(0))
        assert queue.get_nowait() == {"type": "navigate", "view": "sap", "id": item_id}
        assert admin.get("/api/notifications").json()["unread"] == 0  # clicada = lida

        notifier.hub.disconnect(tab)  # sistema fechado: o atalho do clique abre o sistema
        answer = admin.post("/api/notifications/activate", json={"view": "agent", "id": ""},
                            headers={"X-Ops-Activation": notifier.activation_token})
        assert answer.json() == {"tabs": 0}
        assert admin.post("/api/notifications/activate", json={"view": "<script>"},
                          headers={"X-Ops-Activation": notifier.activation_token}).status_code == 422
    finally:
        loop.close()

def test_bell_history_counts_unread_and_job_completion_replaces_its_start(tmp_path: Path) -> None:
    _, admin, csrf = make_machine(tmp_path, "admin", ADMIN, "admin", "[]")
    notifier = notifier_of(admin)
    notifier.sender = Recorder()
    notifier.notify("sap", "Extração ZMM119 iniciada · 09/2026", "robô em execução", view="sap", tag="sap-job1", replace=True)
    notifier.notify("optimus", "Optimus respondeu", "PMM de setembro...", view="agent", tag="optimus")
    notifier.notify("sap", "Extração ZMM119 concluída · 09/2026", "492.036 linhas", view="sap", tag="sap-job1", replace=True)

    history = admin.get("/api/notifications").json()
    assert history["unread"] == 2
    assert [item["title"] for item in history["items"]] == ["Optimus respondeu", "Extração ZMM119 concluída · 09/2026"] or \
           [item["title"] for item in history["items"]] == ["Extração ZMM119 concluída · 09/2026", "Optimus respondeu"]
    assert all(not item["read"] for item in history["items"])
    sap_item = next(item for item in history["items"] if item["view"] == "sap")
    assert sap_item["category_label"] == "Extrações SAP"

    read = admin.post("/api/notifications/read", json={"ids": [sap_item["id"]]}, headers={"X-CSRF-Token": csrf}).json()
    assert read["unread"] == 1
    assert admin.post("/api/notifications/read", json={"all": True}, headers={"X-CSRF-Token": csrf}).json()["unread"] == 0
    cleared = admin.delete("/api/notifications", headers={"X-CSRF-Token": csrf}).json()
    assert cleared == {"items": [], "unread": 0}


def test_optimus_errors_notify_even_with_the_chat_closed(tmp_path: Path, monkeypatch) -> None:
    _, chat_user, csrf = make_machine(tmp_path, "chat", "chat.user@gruposbf.com.br", "user", '["overview","agent"]')
    notifier = notifier_of(chat_user)
    notifier.sender = Recorder()

    class LoopingN8n:  # o n8n pede ferramentas locais sem nunca responder
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            class Response:
                status_code = 200

                @staticmethod
                def json():
                    return {"output": '[[OPS_ACTION]]{"type":"system_manual","topics":["Página Mapping"]}[[/OPS_ACTION]]'}

            return Response()

    monkeypatch.setenv("N8N_CHAT_URL", "http://n8n.invalid/webhook")
    monkeypatch.setattr(web_app.httpx, "AsyncClient", LoopingN8n)
    response = chat_user.post("/api/optimus/chat", json={"message": "Explique o Mapping", "session_id": "sessao-erro-1", "period": "2026-09"},
                              headers={"X-CSRF-Token": csrf})
    assert response.status_code == 502
    error = wait_for(notifier, "Optimus não conseguiu responder")
    assert error["body"] == "O Optimus excedeu o limite de interações com ferramentas locais." and error["view"] == "agent"

    # Sem a URL do n8n configurada: também avisa.
    monkeypatch.delenv("N8N_CHAT_URL")
    before = len(notifier.sent)
    assert chat_user.post("/api/optimus/chat", json={"message": "oi", "session_id": "sessao-erro-2", "period": "2026-09"},
                          headers={"X-CSRF-Token": csrf}).status_code == 503
    assert len(notifier.sent) == before + 1 and "não está configurada" in notifier.sent[-1]["body"]


def test_upload_completion_and_failure_notify_the_user(drive: Path, tmp_path: Path) -> None:  # noqa: F811
    _, admin, csrf = make_machine(tmp_path, "admin", ADMIN, "admin", "[]")
    notifier = notifier_of(admin)
    notifier.sender = Recorder()

    good = zmm119_workbook(tmp_path / "zmm119.xlsx", [("7170", "1081", "MAT000000001", 10)])
    job = wait_job(admin, upload(admin, csrf, "ZMM119", "2026-09", good).json()["job_id"])
    assert job["status"] == "COMPLETED"
    done = wait_for(notifier, "Carga da planilha ZMM119 concluída · 09/2026")
    assert done["view"] == "sap" and done["category"] == "uploads"

    # Planilha da transação errada: recusada na hora (o erro aparece na tela), sem tarefa nem aviso.
    rejected = upload(admin, csrf, "MB59", "2026-09", good)
    assert rejected.status_code == 422
    assert not any("MB59" in item["title"] for item in notifier.sent)

    # Falha durante a tarefa (ZMM119 sem a empresa 7170): o usuário é avisado.
    only_8000 = zmm119_workbook(tmp_path / "zmm119_8000.xlsx", [("8000", "1081", "MAT000000001", 10)])
    job = wait_job(admin, upload(admin, csrf, "ZMM119", "2026-09", only_8000).json()["job_id"])
    assert job["status"] == "FAILED"
    failed = wait_for(notifier, "Carga da planilha ZMM119 falhou · 09/2026")
    assert "7170" in failed["body"]


def test_data_received_from_the_drive_notifies(tmp_path: Path, monkeypatch) -> None:
    _, admin, csrf = make_machine(tmp_path, "admin", ADMIN, "admin", "[]")
    notifier = notifier_of(admin)
    notifier.sender = Recorder()
    monkeypatch.setattr(web_app, "sync_from_bridge", lambda settings, apply_lock=None: {
        "applied": [{"period": "2026-09", "version": "v1", "rows": 492036}], "waiting": [], "skipped": []})
    admin.post("/api/bridge/sync", headers={"X-CSRF-Token": csrf})
    received = [item for item in notifier.sent if item["category"] == "bridge"]
    assert received and received[-1]["title"] == "Competência 09/2026 atualizada pelo Drive"
    assert "492.036 linhas" in received[-1]["body"]
