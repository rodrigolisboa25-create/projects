"""Notificações nativas do Windows (as mesmas do Teams/Outlook) para as tarefas do sistema.

As notificações saem do próprio servidor local, não do navegador: chegam mesmo com a
aba fechada ou minimizada. O aplicativo é registrado no Windows com nome e ícone
próprios ("Estoque Contábil", AUMID em HKCU\\Software\\Classes\\AppUserModelId), aparece
na Central de Notificações e pode ser silenciado pelo próprio Windows. Clicar abre o
sistema na página da tarefa.

As preferências valem para esta máquina (cada usuário tem a sua): liga/desliga geral,
por categoria e som. O envio é feito numa fila em segundo plano e nunca atrasa ou
derruba a tarefa que gerou o aviso.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable
from xml.sax.saxutils import escape

from .db import connect

AUMID = "GrupoSBF.EstoqueContabil"
APP_NAME = "Estoque Contábil"
PREFERENCES_KEY = "notification_preferences"
HISTORY_LIMIT = 200
ICON_PATH = Path(__file__).with_name("assets") / "estoque_contabil.png"

CATEGORIES: dict[str, dict[str, str]] = {
    # (categorias configuráveis; "test" é a notificação de teste, sempre enviada)
    "sap": {"label": "Extrações SAP", "description": "Início, conclusão, falha ou cancelamento das transações ZMM119 e MB59."},
    "uploads": {"label": "Uploads e cargas da base", "description": "Planilhas carregadas por upload, recarga da Base de Estoque e reprocessamento de joins."},
    "optimus": {"label": "Respostas do Optimus", "description": "Quando o Optimus responder e você estiver em outra janela ou página."},
    "bridge": {"label": "Atualizações recebidas pelo Drive", "description": "Competências novas ou atualizadas por outra máquina."},
    "backup": {"label": "Backup e restauração", "description": "Backup programado concluído ou com falha e restauração concluída."},
    "connectivity": {"label": "VPN e conexão do Optimus", "description": "Quando a VPN ou o n8n cai e o Optimus fica sem conexão (administradores com o sistema aberto)."},
}
DEFAULT_PREFERENCES: dict[str, bool] = {"enabled": True, "sound": True, **{key: True for key in CATEGORIES}}

_TOAST_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($env:OPS_TOAST_XML)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
if ($env:OPS_TOAST_TAG) { $toast.Tag = $env:OPS_TOAST_TAG }
$toast.Group = 'estoque-contabil'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:OPS_TOAST_AUMID).Show($toast)
"""


PROTOCOL = "estoquecontabil"
CLICK_SCRIPT = Path(__file__).with_name("assets") / "abrir_notificacao.vbs"


def server_port() -> str:
    return os.getenv("OPS_PORT", "8765").strip() or "8765"


def server_url(view: str = "") -> str:
    # "origem=notificacao": se o sistema já estiver aberto em outra aba, esta aba nova
    # leva aquela para a página da tarefa e se fecha (ver dashboard.html).
    return f"http://127.0.0.1:{server_port()}/?origem=notificacao" + (f"#{view}" if view else "")


def click_target(view: str = "", notification_id: int | None = None) -> str:
    """Endereço chamado pelo clique: o Windows aciona o protocolo do sistema, que traz a
    aba já aberta para frente na página da notificação (ou abre o sistema)."""
    target = f"{PROTOCOL}:abrir?view={view}"
    return target + (f"&id={notification_id}" if notification_id else "")


def build_toast_xml(title: str, body: str, *, url: str, sound: bool) -> str:
    title = escape(" ".join(str(title).split())[:120])
    body = escape(" ".join(str(body).split())[:300])
    target = escape(url, {'"': "&quot;"})
    audio = "" if sound else '<audio silent="true"/>'
    return (
        f'<toast activationType="protocol" launch="{target}">'
        '<visual><binding template="ToastGeneric">'
        f"<text>{title}</text><text>{body}</text>"
        "</binding></visual>"
        f'<actions><action content="Abrir o sistema" activationType="protocol" arguments="{target}"/></actions>'
        f"{audio}</toast>"
    )


def register_app(activation_file: Path | None = None) -> bool:
    """Registra no Windows (somente HKCU, sem administrador) o nome e o ícone das
    notificações e o protocolo estoquecontabil: usado pelo clique."""
    if os.name != "nt":
        return False
    import winreg

    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{AUMID}")
    try:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        if ICON_PATH.is_file():
            winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, str(ICON_PATH))
        winreg.SetValueEx(key, "IconBackgroundColor", 0, winreg.REG_SZ, "FF0B2545")
    finally:
        winreg.CloseKey(key)
    if CLICK_SCRIPT.is_file():
        wscript = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wscript.exe"
        command = f'"{wscript}" "{CLICK_SCRIPT}" "%1" "{activation_file or ""}"'
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROTOCOL}")
        try:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"URL:{APP_NAME}")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        finally:
            winreg.CloseKey(key)
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROTOCOL}\shell\open\command")
        try:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
        finally:
            winreg.CloseKey(key)
    return True


def windows_toast(xml: str, tag: str | None) -> None:
    if os.name != "nt":
        return
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _TOAST_SCRIPT],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
        env={**os.environ, "OPS_TOAST_XML": xml, "OPS_TOAST_AUMID": AUMID, "OPS_TOAST_TAG": (tag or "")[:60]},
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


_REAL_SENDER = windows_toast


class BrowserHub:
    """Abas do sistema conectadas (eventos em tempo real): atualizam o contador do sino na
    hora e recebem o pedido de navegação quando o usuário clica numa notificação."""

    def __init__(self) -> None:
        self._clients: dict[int, tuple[Any, Any, bool]] = {}
        self._lock = threading.Lock()
        self._next_id = 0

    def connect(self, loop: Any, capable: bool) -> tuple[int, Any]:
        import asyncio

        queue_ = asyncio.Queue()
        with self._lock:
            self._next_id += 1
            client_id = self._next_id
            self._clients[client_id] = (loop, queue_, bool(capable))
        return client_id, queue_

    def disconnect(self, client_id: int) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def has_capable(self) -> bool:
        with self._lock:
            return any(capable for _loop, _queue, capable in self._clients.values())

    def connected(self) -> int:
        with self._lock:
            return len(self._clients)

    def publish(self, item: dict[str, Any]) -> int:
        with self._lock:
            clients = list(self._clients.values())
        delivered = 0
        for loop, queue_, _capable in clients:
            try:
                loop.call_soon_threadsafe(queue_.put_nowait, dict(item))
                delivered += 1
            except RuntimeError:  # loop encerrado: a aba já saiu
                continue
        return delivered


class Notifier:
    """Fila de notificações desta máquina, respeitando as preferências do usuário."""

    def __init__(self, settings: Any, sender: Callable[[str, str | None], None] | None = None) -> None:
        self.settings = settings
        self.sender = sender or globals()["windows_toast"]
        self.hub = BrowserHub()
        self.queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self.sent: list[dict[str, Any]] = []  # histórico curto (diagnóstico e testes)
        self.last_error: str | None = None
        self._registered = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        # Chave do clique: o script do protocolo lê este arquivo (só o usuário do Windows
        # consegue) e a envia ao servidor; páginas da web não conseguem forjar o clique.
        import secrets

        self.activation_token = secrets.token_urlsafe(24)
        self.activation_file = settings.path("database").parent.parent / "notificacoes" / "ativacao.json"
        if self.sender is _REAL_SENDER:
            try:
                self.activation_file.parent.mkdir(parents=True, exist_ok=True)
                self.activation_file.write_text(
                    json.dumps({"port": int(server_port()), "token": self.activation_token}), encoding="utf-8"
                )
            except OSError as exc:
                self.last_error = f"Não foi possível preparar o clique das notificações: {exc}"

    # ------------------------------------------------------------ preferências

    def preferences(self) -> dict[str, bool]:
        with connect(self.settings.path("database")) as connection:
            row = connection.execute("select setting_value from system_settings where setting_key=?", [PREFERENCES_KEY]).fetchone()
        stored: dict[str, Any] = {}
        if row:
            try:
                stored = json.loads(row[0])
            except (TypeError, ValueError):
                stored = {}
        return {key: bool(stored.get(key, default)) if isinstance(stored, dict) else default
                for key, default in DEFAULT_PREFERENCES.items()}

    def save_preferences(self, changes: dict[str, Any]) -> dict[str, bool]:
        current = self.preferences()
        for key, value in changes.items():
            if key in DEFAULT_PREFERENCES and isinstance(value, bool):
                current[key] = value
        with connect(self.settings.path("database")) as connection:
            connection.execute(
                """insert into system_settings(setting_key,setting_value,updated_at) values (?,?,current_timestamp)
                   on conflict(setting_key) do update set setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
                [PREFERENCES_KEY, json.dumps(current)],
            )
        return current

    def status(self) -> dict[str, Any]:
        return {
            "available": os.name == "nt",
            "preferences": self.preferences(),
            "categories": [{"key": key, **meta} for key, meta in CATEGORIES.items()],
            "last_error": self.last_error,
            "last_sent": self.sent[-1] if self.sent else None,
            "connected_tabs": self.hub.connected(),
        }

    # ------------------------------------------------------------------- envio

    def notify(self, category: str, title: str, body: str, *, view: str = "", tag: str | None = None,
               silent: bool = False, force: bool = False, replace: bool = False) -> bool:
        """Enfileira uma notificação. Devolve False quando as preferências a bloqueiam.

        ``replace``: o aviso de conclusão de uma tarefa substitui, no histórico do sino,
        o aviso de início ainda não lido da mesma tarefa (mesma etiqueta).
        """
        try:
            preferences = self.preferences()
        except Exception:  # noqa: BLE001 - sem banco não há aviso, e a tarefa segue normalmente
            return False
        if not force and (not preferences["enabled"] or not preferences.get(category, False)):
            return False
        try:
            log_id = self._log(category, title, body, view, tag, replace)
        except Exception:  # noqa: BLE001 - o histórico nunca impede o aviso
            log_id = None
        self.sent.append({"category": category, "title": title, "body": body, "view": view, "tag": tag, "id": log_id})
        del self.sent[:-50]
        # As abas abertas atualizam o contador do sino na hora.
        self.hub.publish({"type": "notification", "id": log_id, "category": category, "view": view})
        # Sempre notificação do Windows ("Estoque Contábil"); o clique traz a aba já aberta.
        xml = build_toast_xml(title, body, url=click_target(view, log_id), sound=preferences["sound"] and not silent)
        self.queue.put((xml, tag))
        self._ensure_worker()
        return True

    def activate(self, token: str, view: str, notification_id: int | None) -> int | None:
        """Clique numa notificação: leva as abas abertas para a página e marca como lida.

        Devolve quantas abas estão conectadas (None quando a chave não confere)."""
        import hmac

        if not token or not hmac.compare_digest(token, self.activation_token):
            return None
        if notification_id:
            try:
                self.mark_read([int(notification_id)])
            except Exception:  # noqa: BLE001
                pass
        self.hub.publish({"type": "navigate", "view": view, "id": notification_id})
        return self.hub.connected()

    # --------------------------------------------------------- histórico (sino)

    def _ensure_log(self, connection: Any) -> None:
        connection.execute("create sequence if not exists notification_seq start 1")
        connection.execute(
            """create table if not exists notification_log (
                 id bigint primary key default nextval('notification_seq'),
                 created_at timestamp not null default current_timestamp,
                 category varchar, title varchar, body varchar, view varchar, tag varchar,
                 read_at timestamp)"""
        )

    def _log(self, category: str, title: str, body: str, view: str, tag: str | None, replace: bool) -> int:
        title = " ".join(str(title).split())[:200]
        body = " ".join(str(body).split())[:600]
        with connect(self.settings.path("database")) as connection:
            self._ensure_log(connection)
            if replace and tag:
                row = connection.execute(
                    "select id from notification_log where tag=? and read_at is null order by id desc limit 1", [tag]
                ).fetchone()
                if row:
                    connection.execute(
                        """update notification_log set category=?, title=?, body=?, view=?, created_at=current_timestamp
                           where id=?""",
                        [category, title, body, view, row[0]],
                    )
                    return int(row[0])
            new_id = int(connection.execute(
                "insert into notification_log(category,title,body,view,tag) values (?,?,?,?,?) returning id",
                [category, title, body, view, tag],
            ).fetchone()[0])
            connection.execute(
                "delete from notification_log where id not in (select id from notification_log order by id desc limit ?)",
                [HISTORY_LIMIT],
            )
            return new_id

    def history(self, limit: int = 50) -> dict[str, Any]:
        with connect(self.settings.path("database")) as connection:
            self._ensure_log(connection)
            rows = connection.execute(
                """select id, created_at, category, title, body, view, read_at
                   from notification_log order by id desc limit ?""",
                [max(1, min(int(limit), HISTORY_LIMIT))],
            ).fetchall()
            unread = int(connection.execute("select count(*) from notification_log where read_at is null").fetchone()[0])
        items = [
            {
                "id": int(row[0]),
                "created_at": row[1].isoformat() if row[1] else None,
                "category": row[2],
                "category_label": CATEGORIES.get(str(row[2]), {}).get("label", "Estoque Contábil"),
                "title": row[3],
                "body": row[4],
                "view": row[5] or "",
                "read": row[6] is not None,
            }
            for row in rows
        ]
        return {"items": items, "unread": unread}

    def mark_read(self, ids: list[int] | None = None) -> dict[str, Any]:
        with connect(self.settings.path("database")) as connection:
            self._ensure_log(connection)
            if ids is None:
                connection.execute("update notification_log set read_at=current_timestamp where read_at is null")
            elif ids:
                marks = ",".join("?" for _ in ids)
                connection.execute(
                    f"update notification_log set read_at=current_timestamp where read_at is null and id in ({marks})",
                    [int(item) for item in ids],
                )
        return self.history()

    def clear(self) -> dict[str, Any]:
        with connect(self.settings.path("database")) as connection:
            self._ensure_log(connection)
            connection.execute("delete from notification_log")
        return self.history()

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._work, daemon=True, name="ops-notificacoes")
                self._thread.start()

    def _work(self) -> None:
        while True:
            try:
                xml, tag = self.queue.get(timeout=60)
            except queue.Empty:
                return
            try:
                if not self._registered and self.sender is _REAL_SENDER:
                    self._registered = register_app(self.activation_file)
                self.sender(xml, tag)
                self.last_error = None
            except Exception as exc:  # noqa: BLE001 - registrado para o diagnóstico; a tarefa não é afetada
                self.last_error = str(exc)[:300]
            finally:
                self.queue.task_done()

    def flush(self, timeout: float = 10.0) -> None:
        """Aguarda a fila esvaziar (usado nos testes)."""
        import time

        deadline = time.monotonic() + timeout
        while self.queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.02)
