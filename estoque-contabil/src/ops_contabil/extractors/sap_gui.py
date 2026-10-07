from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pythoncom
import win32com.client
import win32api
import win32con
import win32file
import win32gui


class SapGuiError(RuntimeError):
    pass


class SapGuiCancelled(SapGuiError):
    """Execução interrompida explicitamente pelo usuário."""


StatusCallback = Callable[[str, str], None]


# SAP GUI Scripting expõe todas as sessões do usuário pelo mesmo engine COM.
# Sem uma reserva explícita, duas threads podem selecionar a mesma sessão e uma
# transação passa a dirigir a janela da outra. A reserva vale apenas durante a
# vida do robô e permite paralelismo real em conexões/sessões distintas.
_SAP_SESSION_RESERVATION_LOCK = threading.Lock()
_SAP_RESERVED_SESSION_KEYS: set[str] = set()
_SAP_CONNECTION_OPEN_LOCK = threading.Lock()


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def load_sap_connection_names(paths: list[Path] | tuple[Path, ...]) -> list[str]:
    """Lê entradas SAPGUI dos arquivos Landscape sem depender do nome do usuário."""
    names: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if not Path(path).is_file():
            continue
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError):
            continue
        for node in root.iter():
            if str(node.tag).split("}")[-1].casefold() != "service":
                continue
            attrs = {str(key).casefold(): str(value or "").strip() for key, value in node.attrib.items()}
            if _normalize(attrs.get("type")) != "sapgui":
                continue
            name = attrs.get("name") or attrs.get("description")
            identity = name.casefold()
            if name and identity not in seen:
                seen.add(identity)
                names.append(name)
    return names


def _connection_name_score(name: str) -> int:
    normalized = _normalize(name)
    words = set(normalized.split())
    blocked = any(
        token in normalized
        for token in ("qas", "quality", "dev", "desenvolvimento", "tst", "teste", "hml", "homolog")
    )
    if blocked:
        return -100_000
    has_prd = any(token in normalized for token in ("prd", "prod", "producao", "production"))
    has_hana = (
        "4hana" in normalized
        or "s4hana" in normalized
        or "s 4 hana" in normalized
        or ("hana" in words and ("s4" in words or ("s" in words and "4" in words)))
    )
    if not (has_prd and has_hana):
        return -100_000
    return 1_000 + (300 if "sso" in normalized else 0) + (100 if "prd" in normalized else 0)


def resolve_sap_connection_name(
    requested: str = "",
    connection_names: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Seleciona uma conexão produtiva de forma portável e determinística."""
    names = [str(name).strip() for name in (connection_names or []) if str(name).strip()]
    requested_normalized = _normalize(requested)
    if requested_normalized:
        matches = [name for name in names if requested_normalized in _normalize(name)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise SapGuiError("A conexão informada corresponde a mais de uma entrada do SAP Logon.")

    ranked = [(name, _connection_name_score(name)) for name in names]
    eligible = [item for item in ranked if item[1] > 0]
    if eligible:
        eligible.sort(key=lambda item: item[1], reverse=True)
        return eligible[0][0]

    raise SapGuiError(
        "Não foi possível identificar automaticamente a conexão produtiva. "
        "Informe a conexão desejada do SAP Logon."
    )


@dataclass
class SapGuiRobot:
    timeout_seconds: int = 300
    connection_name: str = ""
    status_callback: StatusCallback | None = None
    cancel_event: threading.Event | None = None
    session: Any = field(init=False, default=None, repr=False)
    connection: Any = field(init=False, default=None, repr=False)
    engine: Any = field(init=False, default=None, repr=False)
    _security_stop: threading.Event = field(init=False, default_factory=threading.Event, repr=False)
    _security_thread: threading.Thread | None = field(init=False, default=None, repr=False)
    _reserved_session_key: str = field(init=False, default="", repr=False)
    _observed_export_paths: list[Path] = field(init=False, default_factory=list, repr=False)

    def cancel(self) -> None:
        if self.cancel_event is not None:
            self.cancel_event.set()

    def _check_cancelled(self) -> None:
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise SapGuiCancelled("Execução SAP cancelada pelo usuário.")

    def _sleep(self, seconds: float) -> None:
        if self.cancel_event is None:
            time.sleep(seconds)
            return
        if self.cancel_event.wait(seconds):
            raise SapGuiCancelled("Execução SAP cancelada pelo usuário.")

    def _status(self, status: str, message: str) -> None:
        if self.status_callback is None:
            return
        try:
            self.status_callback(status, message)
        except Exception:
            # A atualização visual nunca pode interromper a extração SAP.
            pass

    def __enter__(self) -> "SapGuiRobot":
        pythoncom.CoInitialize()
        try:
            self._check_cancelled()
            self._status("OPENING_SAP", "Conectando ao SAP GUI desta máquina.")
            self.engine = self._wait_for_engine()
            self._start_security_watcher()
            self.connection, self.session = self._select_or_wait_session()
            description = self._connection_description(self.connection, self.session)
            self._status(
                "CONNECTION_SELECTED",
                f"Conexão SAP selecionada: {description or 'sessão autenticada'}.",
            )
            self._wait_not_busy()
            return self
        except Exception as exc:
            self._release_session_reservation()
            self._stop_security_watcher()
            pythoncom.CoUninitialize()
            if isinstance(exc, (SapGuiError, TimeoutError)):
                raise
            raise SapGuiError(
                "Não foi possível conectar ao SAP GUI. Abra o SAP Logon, autentique-se "
                "na conexão produtiva e confirme que SAP GUI Scripting está habilitado."
            ) from exc

    def __exit__(self, *_: object) -> None:
        self._stop_security_watcher()
        self._release_session_reservation()
        self.session = None
        self.connection = None
        self.engine = None
        pythoncom.CoUninitialize()

    @staticmethod
    def _native_child_windows(hwnd: int) -> list[int]:
        children: list[int] = []

        def collect(child: int, _: object) -> bool:
            children.append(child)
            return True

        try:
            win32gui.EnumChildWindows(hwnd, collect, None)
        except Exception:
            return []
        return children

    def _permit_sap_security_dialog(self) -> bool:
        """Autoriza apenas a janela nativa de Segurança SAPGUI durante a execução do robô."""
        windows: list[int] = []

        def collect(hwnd: int, _: object) -> bool:
            try:
                if win32gui.IsWindowVisible(hwnd):
                    windows.append(hwnd)
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(collect, None)
        except Exception:
            return False

        for hwnd in windows:
            try:
                title = _normalize(win32gui.GetWindowText(hwnd))
            except Exception:
                continue
            if not (
                "seguranca sapgui" in title
                or "sapgui security" in title
                or "sap gui security" in title
            ):
                continue

            for child in self._native_child_windows(hwnd):
                try:
                    child_text = _normalize(win32gui.GetWindowText(child))
                    child_class = win32gui.GetClassName(child).casefold()
                except Exception:
                    continue
                if "button" not in child_class:
                    continue
                if child_text in {"permitir", "allow"} or child_text.startswith("permitir " ) or child_text.startswith("allow " ):
                    try:
                        win32gui.PostMessage(child, win32con.BM_CLICK, 0, 0)
                        self._status("EXPORTING_FILE", "Permissão de segurança do SAP GUI autorizada automaticamente.")
                        return True
                    except Exception:
                        continue
        return False

    def _click_native_dialog_ok(self, title_markers: tuple[str, ...]) -> bool:
        """Aciona o IDOK de diálogos nativos do SAP GUI sem bloquear o COM."""
        windows: list[int] = []

        def collect(hwnd: int, _: object) -> bool:
            try:
                if win32gui.IsWindowVisible(hwnd):
                    windows.append(hwnd)
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(collect, None)
        except Exception:
            return False

        markers = tuple(_normalize(marker) for marker in title_markers)
        for hwnd in windows:
            try:
                title = _normalize(win32gui.GetWindowText(hwnd))
            except Exception:
                continue
            if not any(marker in title for marker in markers):
                continue
            # Nessas janelas o botão verde/Gerar é a ação padrão. Enviar Enter
            # diretamente ao HWND funciona mesmo quando o botão owner-drawn não
            # aceita BM_CLICK e sem depender de foco/coordenadas.
            try:
                win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
                win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
                return True
            except Exception:
                pass
            children = self._native_child_windows(hwnd)
            for control_id in (111, 1):
                try:
                    for button in children:
                        if win32gui.GetDlgCtrlID(button) != control_id:
                            continue
                        if not win32gui.IsWindow(button) or not win32gui.IsWindowEnabled(button):
                            continue
                        left, top, right, bottom = win32gui.GetWindowRect(button)
                        if right <= left or bottom <= top:
                            continue
                        win32gui.PostMessage(button, win32con.BM_CLICK, 0, 0)
                        return True
                except Exception:
                    continue
        return False

    @staticmethod
    def _native_dialog_visible(title_markers: tuple[str, ...]) -> bool:
        markers = tuple(_normalize(marker) for marker in title_markers)
        found = False

        def collect(hwnd: int, _: object) -> bool:
            nonlocal found
            try:
                if win32gui.IsWindowVisible(hwnd):
                    title = _normalize(win32gui.GetWindowText(hwnd))
                    if any(marker in title for marker in markers):
                        found = True
                        return False
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(collect, None)
        except Exception:
            return False
        return found

    def _security_watch_loop(self) -> None:
        while not self._security_stop.wait(0.02):
            self._permit_sap_security_dialog()

    def _start_security_watcher(self) -> None:
        self._security_stop.clear()
        if self._security_thread is not None and self._security_thread.is_alive():
            return
        self._security_thread = threading.Thread(
            target=self._security_watch_loop,
            name="OpsContabil-SapSecurity",
            daemon=True,
        )
        self._security_thread.start()

    def _stop_security_watcher(self) -> None:
        self._security_stop.set()
        thread = self._security_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.5)
        self._security_thread = None

    def _saplogon_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        for env_name in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
            root = os.getenv(env_name, "").strip()
            if root:
                candidates.append(Path(root) / "SAP" / "FrontEnd" / "SAPgui" / "saplogon.exe")
        return candidates

    def _launch_saplogon(self) -> bool:
        for executable in self._saplogon_candidates():
            if executable.is_file():
                self._status("OPENING_SAP", "Abrindo o SAP Logon.")
                subprocess.Popen([str(executable)], close_fds=True)
                return True
        return False

    def _get_engine(self):
        sap_gui = win32com.client.GetObject("SAPGUI")
        return sap_gui.GetScriptingEngine

    def _wait_for_engine(self):
        deadline = time.monotonic() + min(max(self.timeout_seconds, 30), 120)
        launched = False
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                return self._get_engine()
            except Exception as exc:
                last_error = exc
                if not launched:
                    launched = self._launch_saplogon()
                self._sleep(0.5)
        raise SapGuiError(
            "O SAP GUI Scripting não ficou disponível. Abra o SAP Logon e confirme "
            "que o scripting está habilitado."
        ) from last_error

    def _connections(self) -> list[Any]:
        result: list[Any] = []
        try:
            count = self.engine.Children.Count
        except Exception:
            return result
        for index in range(count):
            try:
                result.append(self.engine.Children(index))
            except Exception:
                continue
        return result

    @staticmethod
    def _sessions(connection: Any) -> list[Any]:
        result: list[Any] = []
        try:
            count = connection.Children.Count
        except Exception:
            return result
        for index in range(count):
            try:
                result.append(connection.Children(index))
            except Exception:
                continue
        return result

    @staticmethod
    def _connection_description(connection: Any, session: Any | None = None) -> str:
        values: list[str] = []
        for attr in ("Description", "Name", "Id"):
            try:
                value = str(getattr(connection, attr, "") or "").strip()
            except Exception:
                value = ""
            if value and value not in values:
                values.append(value)
        if session is not None:
            try:
                system = str(session.Info.SystemName or "").strip()
            except Exception:
                system = ""
            if system and system not in values:
                values.append(system)
        return " · ".join(values)

    @staticmethod
    def _is_target_text(text: str) -> bool:
        normalized = _normalize(text)
        words = set(normalized.split())
        has_hana = (
            "4hana" in normalized
            or "s4hana" in normalized
            or "s 4 hana" in normalized
            or ("hana" in words and ("s4" in words or ("s" in words and "4" in words)))
        )
        has_prd = any(token in normalized for token in ("prd", "prod", "producao", "production"))
        blocked = any(
            token in normalized
            for token in ("qas", "quality", "dev", "desenvolvimento", "tst", "teste", "hml", "homolog")
        )
        return has_hana and has_prd and not blocked

    def _target_score(self, text: str) -> int:
        normalized = _normalize(text)
        if not self._is_target_text(normalized):
            return -100_000

        score = 1_000
        if "sso" in normalized:
            score += 300
        if "s 4hana" in normalized or "s4hana" in normalized or "s 4 hana" in normalized:
            score += 120
        if "prd" in normalized:
            score += 100

        # O campo opcional funciona como pista, nunca como nome exato obrigatório.
        requested = _normalize(self.connection_name)
        if requested:
            requested_tokens = [token for token in requested.split() if len(token) > 1]
            score += 25 * sum(token in normalized for token in requested_tokens)

        # Evita escolher entradas de outros produtos mesmo que também tenham PRD.
        if "fiori" in normalized:
            score -= 500
        if "ecc" in normalized:
            score -= 500
        return score

    def _connection_score(self, connection: Any) -> int:
        sessions = self._sessions(connection)
        session = sessions[0] if sessions else None
        description = self._connection_description(connection, session)
        score = self._target_score(description)
        if sessions and score > 0:
            score += 50
        return score

    def _best_open_connection(self) -> Any | None:
        candidates = [
            connection
            for connection in self._connections()
            if self._connection_score(connection) > 0
        ]
        if not candidates:
            return None
        return max(candidates, key=self._connection_score)

    @staticmethod
    def _session_reservation_key(connection: Any, session: Any) -> str:
        def identifier(value: Any, fallback: str) -> str:
            for attribute in ("Id", "Name"):
                try:
                    text = str(getattr(value, attribute, "") or "").strip()
                except Exception:
                    text = ""
                if text:
                    return text
            return fallback

        return (
            f"{identifier(connection, f'connection-{id(connection)}')}::"
            f"{identifier(session, f'session-{id(session)}')}"
        ).casefold()

    def _claim_ready_session(self) -> tuple[Any, Any] | None:
        connections = sorted(
            (
                connection
                for connection in self._connections()
                if self._connection_score(connection) > 0
            ),
            key=self._connection_score,
            reverse=True,
        )
        for connection in connections:
            for session in self._sessions(connection):
                if not self._session_ready(session):
                    continue
                key = self._session_reservation_key(connection, session)
                with _SAP_SESSION_RESERVATION_LOCK:
                    if key in _SAP_RESERVED_SESSION_KEYS:
                        continue
                    _SAP_RESERVED_SESSION_KEYS.add(key)
                    self._reserved_session_key = key
                return connection, session
        return None

    def _release_session_reservation(self) -> None:
        key = self._reserved_session_key
        if not key:
            return
        with _SAP_SESSION_RESERVATION_LOCK:
            _SAP_RESERVED_SESSION_KEYS.discard(key)
        self._reserved_session_key = ""

    def _landscape_paths(self) -> list[Path]:
        paths: list[Path] = []
        appdata = os.getenv("APPDATA", "").strip()
        programdata = os.getenv("PROGRAMDATA", "").strip()
        if appdata:
            common = Path(appdata) / "SAP" / "Common"
            paths.extend([
                common / "SAPUILandscape.xml",
                common / "SAPUILandscapeGlobal.xml",
            ])
        if programdata:
            common = Path(programdata) / "SAP" / "Common"
            paths.extend([
                common / "SAPUILandscape.xml",
                common / "SAPUILandscapeGlobal.xml",
            ])

        # Algumas empresas apontam o SAP Logon para um XML central via registro.
        try:
            import winreg

            registry_locations = [
                (winreg.HKEY_CURRENT_USER, r"Software\SAP\SAPLogon\Options"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\SAP\SAPLogon\Options"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\SAP\SAPLogon\Options"),
            ]
            for hive, key_name in registry_locations:
                try:
                    with winreg.OpenKey(hive, key_name) as key:
                        value, _ = winreg.QueryValueEx(key, "LandscapeFileOnServer")
                    expanded = os.path.expandvars(str(value or "").strip())
                    if expanded and not re.match(r"^[a-z]+://", expanded, re.I):
                        paths.append(Path(expanded))
                except OSError:
                    continue
        except ImportError:
            pass

        unique: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            key = str(path).casefold()
            if key not in seen:
                seen.add(key)
                unique.append(path)
        return unique

    def _landscape_service_names(self) -> list[str]:
        services: dict[str, str] = {}
        for path in self._landscape_paths():
            if not path.is_file():
                continue
            try:
                root = ET.parse(path).getroot()
            except (OSError, ET.ParseError):
                continue
            for node in root.iter():
                tag = str(node.tag).split("}")[-1].casefold()
                if tag != "service":
                    continue
                attrs = {str(k).casefold(): str(v or "") for k, v in node.attrib.items()}
                if _normalize(attrs.get("type")) != "sapgui":
                    continue
                name = attrs.get("name", "").strip()
                if not name:
                    continue
                searchable = " ".join(
                    filter(
                        None,
                        (
                            name,
                            attrs.get("description", ""),
                            attrs.get("systemid", ""),
                            attrs.get("server", ""),
                        ),
                    )
                )
                score = self._target_score(searchable)
                if score > 0:
                    current = services.get(name)
                    if current is None or score > self._target_score(current):
                        services[name] = searchable

        ranked = sorted(
            services.items(),
            key=lambda item: self._target_score(item[1]),
            reverse=True,
        )
        return [name for name, _ in ranked]

    def _connection_names_to_try(self) -> list[str]:
        names = self._landscape_service_names()
        # Fallbacks só entram se o XML não puder ser lido. Em máquinas com nomes
        # diferentes o XML é a fonte principal, portanto não dependemos destes textos.
        for fallback in ("S/4HANA - PRD (SSO)", "S/4HANA - PRD"):
            if fallback not in names:
                names.append(fallback)
        return names

    def _open_target_connection(self) -> Any | None:
        names = self._connection_names_to_try()
        if not names:
            return None

        last_error: Exception | None = None
        for name in names:
            self._status(
                "OPENING_CONNECTION",
                f"Abrindo SAP S/4HANA PRD: {name}.",
            )
            try:
                opened = self.engine.OpenConnection(name, True)
                if opened is not None:
                    return opened
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise SapGuiError(
                "O SAP Logon foi aberto, mas nenhuma conexão S/4HANA PRD pôde ser iniciada. "
                "O sistema procura automaticamente S/4HANA + PRD e prioriza SSO."
            ) from last_error
        return None

    def _session_ready(self, session: Any) -> bool:
        try:
            if bool(getattr(session, "Busy", False)):
                return False
        except Exception:
            pass
        try:
            # O campo de comando existe na tela principal após o logon/SSO.
            return session.findById("wnd[0]/tbar[0]/okcd") is not None
        except Exception:
            return False

    def _select_or_wait_session(self) -> tuple[Any, Any]:
        deadline = time.monotonic() + self.timeout_seconds
        attempted_open = False

        while time.monotonic() < deadline:
            self._check_cancelled()
            claimed = self._claim_ready_session()
            if claimed is not None:
                return claimed

            if not attempted_open:
                attempted_open = True
                self._status(
                    "OPENING_CONNECTION",
                    "Abrindo uma sessão SAP exclusiva para esta extração.",
                )
                # Revalida dentro do lock: outra extração pode ter terminado
                # enquanto esta aguardava para abrir uma nova conexão.
                with _SAP_CONNECTION_OPEN_LOCK:
                    claimed = self._claim_ready_session()
                    if claimed is not None:
                        return claimed
                    self._open_target_connection()

            target_connections = [
                connection
                for connection in self._connections()
                if self._connection_score(connection) > 0
            ]
            if target_connections:
                self._status(
                    "WAITING_FOR_LOGIN",
                    "Sessão SAP exclusiva aberta. Aguardando o SSO concluir o logon.",
                )

            self._sleep(0.20)

        raise SapGuiError(
            "A conexão S/4HANA PRD foi solicitada, mas a sessão não ficou pronta no prazo. "
            "O robô procura S/4HANA + PRD automaticamente e prioriza a entrada SSO."
        )

    def _find(self, control_id: str):
        try:
            return self.session.findById(control_id)
        except Exception as exc:
            raise SapGuiError(f"Controle SAP não encontrado: {control_id}") from exc

    def _try_find(self, control_id: str):
        try:
            return self.session.findById(control_id)
        except Exception:
            return None

    def _wait_control(self, control_id: str, timeout_seconds: float = 20.0):
        deadline = time.monotonic() + min(timeout_seconds, self.timeout_seconds)
        while time.monotonic() < deadline:
            self._check_cancelled()
            control = self._try_find(control_id)
            if control is not None:
                return control
            self._sleep(0.05)
        raise SapGuiError(f"Controle SAP não apareceu no prazo: {control_id}")

    def _transaction(self, code: str) -> None:
        self._status("RUNNING", f"Abrindo a transação {code.upper()}.")
        command = code.upper().removeprefix("/N").removeprefix("N")
        ok_code = self._wait_control("wnd[0]/tbar[0]/okcd")
        ok_code.text = f"/n{command}"
        self._find("wnd[0]").sendVKey(0)
        self._wait_not_busy()

    def _wait_not_busy(self) -> None:
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            self._check_cancelled()
            try:
                busy = bool(self.session.Busy)
            except Exception:
                busy = False
            if not busy:
                return
            self._sleep(0.10)
        raise TimeoutError("A sessão SAP permaneceu ocupada além do limite configurado.")

    @staticmethod
    def _descendants(root: Any):
        pending = [root]
        while pending:
            parent = pending.pop()
            try:
                count = parent.Children.Count
            except Exception:
                continue
            for index in range(count):
                try:
                    child = parent.Children(index)
                except Exception:
                    continue
                yield child
                pending.append(child)

    @staticmethod
    def _choose_xlsx(combo: Any) -> bool:
        current = _normalize(getattr(combo, "Text", ""))
        if "xlsx" in current or "open formato xml" in current or "open xml" in current:
            return True
        try:
            entries = combo.Entries
        except Exception:
            return False
        candidates: list[tuple[int, str]] = []
        for index in range(entries.Count):
            entry = entries(index)
            value = _normalize(getattr(entry, "Value", ""))
            key = str(getattr(entry, "Key", ""))
            score = 0
            if "xlsx" in value:
                score += 100
            if "open formato xml" in value or "open xml" in value:
                score += 80
            if "excel" in value:
                score += 20
            candidates.append((score, key))
        if not candidates:
            return False
        score, key = max(candidates)
        if score <= 0:
            return False
        try:
            combo.Key = key
        except Exception:
            combo.Selected = key
        return True

    def _find_by_technical_name(
        self,
        root: Any,
        technical_name: str,
        control_types: tuple[str, ...],
    ):
        """Localiza um componente pelo Name técnico exposto pelo SAP GUI Scripting.

        Não depende do texto visível, idioma, posição da janela nem do caminho completo
        do ID. Primeiro usa FindByName do próprio SAP; a varredura por Name/Type é
        apenas um fallback técnico para versões em que o método COM não esteja exposto.
        """
        for control_type in control_types:
            try:
                control = root.FindByName(technical_name, control_type)
                if control is not None:
                    return control
            except Exception:
                pass

        wanted_name = technical_name.casefold()
        wanted_types = set(control_types)
        for candidate in self._descendants(root):
            try:
                candidate_name = str(getattr(candidate, "Name", "") or "").casefold()
                candidate_type = str(getattr(candidate, "Type", "") or "")
            except Exception:
                continue
            if candidate_name == wanted_name and candidate_type in wanted_types:
                return candidate
        return None

    def _selection_parameter(
        self,
        control_ids: tuple[str, ...],
        technical_names: tuple[str, ...],
    ):
        for control_id in control_ids:
            control = self._try_find(control_id)
            if control is not None:
                return control
        window = self._find("wnd[0]")
        for technical_name in technical_names:
            control = self._find_by_technical_name(
                window,
                technical_name,
                ("GuiTextField", "GuiCTextField"),
            )
            if control is not None:
                return control
        return None

    @staticmethod
    def _numeric_value(control: Any) -> int | None:
        try:
            digits = re.sub(r"\D+", "", str(getattr(control, "Text", "") or ""))
            return int(digits) if digits else None
        except (TypeError, ValueError):
            return None

    def _set_zmm119_period(self, period: str) -> None:
        match = re.fullmatch(r"(\d{4})-(\d{2})", str(period or "").strip())
        if match is None:
            raise SapGuiError("Competência inválida para a ZMM119. Use AAAA-MM.")
        year, month = map(int, match.groups())
        if not 1 <= month <= 12:
            raise SapGuiError("Mês inválido para a ZMM119.")
        year_field = self._selection_parameter(
            (
                "wnd[0]/usr/txtP_LFGJA", "wnd[0]/usr/ctxtP_LFGJA",
                "wnd[0]/usr/txtP_GJAHR", "wnd[0]/usr/ctxtP_GJAHR",
                "wnd[0]/usr/txtP_ANO", "wnd[0]/usr/ctxtP_ANO",
                "wnd[0]/usr/txtP_YEAR", "wnd[0]/usr/ctxtP_YEAR",
            ),
            ("P_LFGJA", "P_GJAHR", "P_ANO", "P_YEAR"),
        )
        month_field = self._selection_parameter(
            (
                "wnd[0]/usr/txtP_LFMON", "wnd[0]/usr/ctxtP_LFMON",
                "wnd[0]/usr/txtP_MONAT", "wnd[0]/usr/ctxtP_MONAT",
                "wnd[0]/usr/txtP_MES", "wnd[0]/usr/ctxtP_MES",
                "wnd[0]/usr/txtP_MONTH", "wnd[0]/usr/ctxtP_MONTH",
            ),
            ("P_LFMON", "P_MONAT", "P_MES", "P_MONTH"),
        )
        if year_field is None or month_field is None:
            raise SapGuiError(
                "Os campos Ano/Mês da ZMM119 não foram localizados. A execução foi "
                "interrompida para impedir a exportação de uma competência incorreta."
            )
        year_field.Text = str(year)
        month_field.Text = str(month)
        if self._numeric_value(year_field) != year or self._numeric_value(month_field) != month:
            raise SapGuiError(
                f"O SAP não confirmou a competência {month:02d}/{year} nos campos Ano/Mês."
            )
        self._status("RUNNING", f"Competência confirmada no SAP: {month:02d}/{year}.")

    def _select_format_dialog(self) -> bool:
        window = self._try_find("wnd[1]")
        if window is None:
            return False

        # O cliente corporativo abre este diálogo já com "todos os formatos" e
        # XLSX selecionados. Manipular rádio/combo via COM bloqueia a sessão;
        # confirma primeiro pelo botão nativo visível e valida o XLSX ao final.
        if self._click_native_dialog_ok(
            ("Selecionar planilha eletrônica", "Select spreadsheet")
        ):
            self._status(
                "EXPORTING_FILE",
                "Formato XLSX confirmado no SAP; aguardando o diálogo de gravação.",
            )
            return True

        # Nomes técnicos do dynpro, independentes do idioma e do caminho wnd/usr.
        radio = self._find_by_technical_name(
            window,
            "RB_OTHERS",
            ("GuiRadioButton",),
        )
        combo = self._find_by_technical_name(
            window,
            "G_LISTBOX",
            ("GuiComboBox",),
        )

        if radio is None and combo is None:
            return False

        if radio is not None:
            radio.Select()
        if combo is not None and not self._choose_xlsx(combo):
            raise SapGuiError("A opção XLSX não foi localizada na lista de formatos do SAP.")

        # Neste cliente a janela é nativa (#32770). O clique via COM bloqueia;
        # IDOK=1 aciona o ícone verde sem interferência humana.
        try:
            if self._click_native_dialog_ok(
                ("Selecionar planilha eletrônica", "Select spreadsheet")
            ):
                self._status(
                    "EXPORTING_FILE",
                    "Formato XLSX confirmado no SAP; aguardando o diálogo de gravação.",
                )
                return True
            confirm_button = self._try_find("wnd[1]/tbar[0]/btn[0]")
            if confirm_button is None:
                raise SapGuiError(
                    "O botão verde de confirmação do formato XLSX não foi localizado."
                )
            confirm_button.press()
            self._status(
                "EXPORTING_FILE",
                "Formato XLSX confirmado no SAP; aguardando o diálogo de gravação.",
            )
        except Exception as exc:
            if isinstance(exc, SapGuiError):
                raise
            raise SapGuiError(
                "Não foi possível confirmar o seletor de formato do SAP."
            ) from exc
        return True

    def _save_dialog(self, output_path: Path) -> bool:
        window = self._try_find("wnd[1]")
        if window is None:
            return False

        # DY_PATH e DY_FILENAME são os Names técnicos dos campos do dynpro de gravação.
        path_control = self._try_find("wnd[1]/usr/ctxtDY_PATH")
        if path_control is None:
            path_control = self._find_by_technical_name(
                window,
                "DY_PATH",
                ("GuiCTextField", "GuiTextField"),
            )
        file_control = self._try_find("wnd[1]/usr/ctxtDY_FILENAME")
        if file_control is None:
            file_control = self._find_by_technical_name(
                window,
                "DY_FILENAME",
                ("GuiCTextField", "GuiTextField"),
            )

        if path_control is None or file_control is None:
            return False

        # Guarde também o destino originalmente apresentado pelo SAP. Alguns
        # clientes corporativos aceitam o clique em Gerar, mas mantêm C:\TEMP
        # (ou outra pasta configurada pelo usuário) apesar da atribuição via COM.
        # Esse caminho observado passa a ser monitorado durante toda a exportação.
        self._remember_export_location(
            getattr(path_control, "text", ""),
            getattr(file_control, "text", ""),
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        path_control.text = str(output_path.parent)
        file_control.text = output_path.name

        # Confirma que o SAP recebeu os dois valores antes de pressionar Gerar.
        # Alguns clientes corporativos ignoram a primeira atribuição enquanto o
        # dynpro ainda está terminando de montar os controles.
        if str(getattr(path_control, "text", "")).strip() != str(output_path.parent):
            path_control.text = str(output_path.parent)
        if str(getattr(file_control, "text", "")).strip() != output_path.name:
            file_control.text = output_path.name
        self._remember_export_location(
            getattr(path_control, "text", ""),
            getattr(file_control, "text", ""),
        )

        # Neste dynpro, Enter apenas aceita a configuração e pode manter a janela
        # aberta. O botão técnico btn[0] é a ação "Gerar" observada no SAP GUI;
        # btn[11] é "Substituir" e não deve ser usado para um destino novo.
        # O botão visual "Gerar" nem sempre é o btn[0] da toolbar. Primeiro
        # identifica o botão real pelo texto/tooltip acessível e só então usa o
        # ID legado como fallback.
        generate_button = None
        for candidate in self._descendants(window):
            try:
                if str(getattr(candidate, "Type", "")) != "GuiButton":
                    continue
                descriptor = _normalize(
                    " ".join(
                        str(getattr(candidate, attr, "") or "")
                        for attr in ("Text", "Tooltip", "AccTooltip", "DefaultTooltip")
                    )
                )
                if any(word in descriptor.split() for word in ("gerar", "generate", "salvar", "save")):
                    generate_button = candidate
                    break
            except Exception:
                continue
        if generate_button is None:
            generate_button = self._try_find("wnd[1]/tbar[0]/btn[0]")
        if generate_button is None:
            raise SapGuiError(
                "Os campos DY_PATH/DY_FILENAME foram preenchidos, mas o botão Gerar "
                "não foi localizado no diálogo de gravação."
            )
        native_generate = self._click_native_dialog_ok(
            ("Gravar file", "Save file", "Save as")
        )
        if not native_generate:
            try:
                generate_button.press()
            except Exception as exc:
                raise SapGuiError(
                    "Os campos técnicos DY_PATH/DY_FILENAME foram localizados, mas o SAP "
                    "não aceitou o comando Gerar."
                ) from exc
        # Não presume sucesso apenas porque press() não lançou exceção. Confirma
        # que o diálogo deixou de ser o "Gravar file" ou que o SAP iniciou o
        # download. Se nada mudar, devolve False para uma nova tentativa rápida.
        accepted = False
        for _ in range(30):
            self._check_cancelled()
            current_window = self._try_find("wnd[1]")
            current_path = self._try_find("wnd[1]/usr/ctxtDY_PATH")
            if current_path is None and current_window is not None:
                current_path = self._find_by_technical_name(
                    current_window,
                    "DY_PATH",
                    ("GuiCTextField", "GuiTextField"),
                )
            if current_path is None:
                accepted = True
                break
            if self._transfer_in_progress():
                accepted = True
                break
            self._sleep(0.05)
        if not accepted:
            return False
        self._status(
            "EXPORTING_FILE",
            f"Comando Gerar confirmado; aguardando a gravação de {output_path.name}.",
        )
        return True

    def _remember_export_location(self, directory: object, filename: object) -> None:
        raw_directory = str(directory or "").strip().strip('"')
        raw_filename = str(filename or "").strip().strip('"')
        if not raw_directory:
            return
        candidate = Path(raw_directory)
        if raw_filename:
            candidate = candidate / Path(raw_filename).name
        key = str(candidate).casefold()
        if key not in {str(path).casefold() for path in self._observed_export_paths}:
            self._observed_export_paths.append(candidate)

    def _sap_status_bar_text(self) -> str:
        texts: list[str] = []
        for control_id in ("wnd[0]/sbar", "wnd[1]/sbar"):
            control = self._try_find(control_id)
            if control is None:
                continue
            try:
                text = str(getattr(control, "Text", "") or "").strip()
            except Exception:
                text = ""
            if text:
                texts.append(text)
        return " | ".join(texts)

    @staticmethod
    def _is_transfer_text(text: object) -> bool:
        status = _normalize(str(text or ""))
        return any(
            marker in status
            for marker in (
                "transferring package",
                "transferindo pacote",
                "transfer package",
                "download:",
                "download ",
                "baixando",
            )
        )

    def _transfer_in_progress(self) -> bool:
        return self._is_transfer_text(self._sap_status_bar_text())

    @staticmethod
    def _extract_xlsx_paths(text: object) -> list[Path]:
        raw = str(text or "")
        if not raw:
            return []
        matches = re.findall(
            r'(?i)([a-z]:\\[^\r\n"<>|?*]+?\.xlsx)',
            raw,
        )
        result: list[Path] = []
        seen: set[str] = set()
        for match in matches:
            candidate = Path(match.strip())
            key = str(candidate).casefold()
            if key not in seen:
                seen.add(key)
                result.append(candidate)
        return result

    def _sap_reported_export_paths(self) -> list[Path]:
        texts: list[str] = []
        for control_id in ("wnd[0]/sbar", "wnd[1]/sbar"):
            control = self._try_find(control_id)
            if control is not None:
                try:
                    texts.append(str(getattr(control, "Text", "") or ""))
                except Exception:
                    pass
        result: list[Path] = []
        seen: set[str] = set()
        for text in texts:
            for path in self._extract_xlsx_paths(text):
                key = str(path).casefold()
                if key not in seen:
                    seen.add(key)
                    result.append(path)
        return result

    @staticmethod
    def _is_recent_xlsx_candidate(path: Path, after_timestamp: float) -> bool:
        try:
            stat = path.stat()
            return (
                path.is_file()
                and path.suffix.casefold() == ".xlsx"
                and stat.st_size > 0
                and stat.st_mtime >= after_timestamp - 3
            )
        except (OSError, PermissionError):
            return False

    @staticmethod
    def _is_valid_xlsx_archive(path: Path) -> bool:
        try:
            # A central directory só existe quando o XLSX terminou de ser
            # gravado. Isso impede aceitar um arquivo parcial durante os pacotes.
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                return "[Content_Types].xml" in names and "xl/workbook.xml" in names
        except (OSError, PermissionError, zipfile.BadZipFile):
            return False

    @staticmethod
    def _is_valid_recent_xlsx(path: Path, after_timestamp: float) -> bool:
        return (
            SapGuiRobot._is_recent_xlsx_candidate(path, after_timestamp)
            and SapGuiRobot._is_valid_xlsx_archive(path)
        )

    def _export_search_folders(self, output_path: Path) -> list[Path]:
        folders: list[Path] = [output_path.parent]
        folders.extend(
            path if path.suffix.casefold() != ".xlsx" else path.parent
            for path in self._observed_export_paths
        )
        for env_name in ("TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA"):
            value = os.getenv(env_name, "").strip()
            if value:
                folders.append(Path(value))
        home = Path.home()
        folders.extend([home / "Downloads", home / "Documents", home / "Desktop"])

        # Alguns ambientes SAP usam pastas temporárias diretamente na raiz do disco,
        # como C:\TEMP. Incluímos TEMP/TMP em todos os discos locais disponíveis.
        try:
            drives = [item for item in win32api.GetLogicalDriveStrings().split("\x00") if item]
        except Exception:
            drives = []
        for drive in drives:
            try:
                if win32file.GetDriveType(drive) not in {win32file.DRIVE_FIXED, win32file.DRIVE_RAMDISK}:
                    continue
            except Exception:
                continue
            root = Path(drive)
            folders.extend([root / "TEMP", root / "TMP"])

        unique: list[Path] = []
        seen: set[str] = set()
        for folder in folders:
            key = str(folder).casefold()
            if key not in seen:
                seen.add(key)
                unique.append(folder)
        return unique

    def _recent_export_candidates(self, output_path: Path, after_timestamp: float) -> list[Path]:
        candidates: list[Path] = []
        seen: set[str] = set()

        # Caminhos exatos observados no diálogo/status pertencem à exportação
        # corrente. Não dependem do relógio do filesystem; a integridade ZIP é
        # verificada antes de qualquer adoção.
        for path in self._observed_export_paths:
            key = str(path).casefold()
            if key in seen:
                continue
            seen.add(key)
            if path.is_file() and path.suffix.casefold() == ".xlsx":
                candidates.append(path)

        # Pastas usuais e temporárias detectadas dinamicamente. Não consulta a
        # barra de status COM aqui porque ela bloqueia enquanto diálogos nativos
        # do frontend estão abertos.
        for folder in self._export_search_folders(output_path):
            if not folder.is_dir():
                continue
            try:
                paths = folder.glob("*.xlsx")
                for path in paths:
                    key = str(path).casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    if self._is_recent_xlsx_candidate(path, after_timestamp):
                        candidates.append(path)
            except OSError:
                continue

        def score(path: Path) -> tuple[int, float, int]:
            name = _normalize(path.name)
            relevance = 0
            if path.resolve() == output_path.resolve():
                relevance += 1000
            if str(path).casefold() in {
                str(item).casefold() for item in self._observed_export_paths
            }:
                relevance += 800
            if "export" in name:
                relevance += 200
            if "zmm119" in name or "mb59" in name:
                relevance += 150
            try:
                stat = path.stat()
                return relevance, stat.st_mtime, stat.st_size
            except OSError:
                return relevance, 0.0, 0

        return sorted(candidates, key=score, reverse=True)

    def _adopt_recent_export(self, output_path: Path, after_timestamp: float) -> bool:
        if self._is_valid_recent_xlsx(output_path, after_timestamp):
            return True
        candidates = self._recent_export_candidates(output_path, after_timestamp)
        if not candidates:
            return False
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_suffix(output_path.suffix + ".part")
        for source in candidates:
            try:
                same_file = source.resolve() == output_path.resolve()
            except OSError:
                same_file = False
            if same_file:
                if self._is_valid_recent_xlsx(output_path, after_timestamp):
                    return True
                continue
            # Enquanto o SAP ainda grava, o ZIP não tem o diretório central (fica
            # no fim do arquivo). A checagem no próprio arquivo lê só o final; copiar
            # o arquivo parcial a cada volta disputaria o disco com o SAP e com o
            # antivírus, atrasando a exportação em máquinas mais lentas.
            if not self._is_valid_xlsx_archive(source):
                continue
            try:
                if temporary.exists():
                    temporary.unlink()
                # O SAP/Excel pode manter o arquivo-fonte aberto. A cópia ainda
                # costuma ser permitida; validamos a cópia, nunca presumimos que
                # extensão e tamanho bastam.
                shutil.copy2(source, temporary)
                if not self._is_valid_xlsx_archive(temporary):
                    temporary.unlink(missing_ok=True)
                    continue
                temporary.replace(output_path)
            except (OSError, PermissionError):
                try:
                    if temporary.exists():
                        temporary.unlink()
                except OSError:
                    pass
                continue
            self._status(
                "EXPORTING_FILE",
                f"Arquivo exportado pelo SAP localizado em {source} e normalizado para {output_path.name}.",
            )
            return True
        return False

    def _export_progress_marker(self, output_path: Path, after_timestamp: float) -> tuple[int, str]:
        """Bytes já gravados nos XLSX candidatos + texto de status do SAP.

        Qualquer mudança entre duas leituras indica que a exportação ainda avança.
        """
        total = 0
        for path in self._recent_export_candidates(output_path, after_timestamp):
            try:
                total += path.stat().st_size
            except OSError:
                continue
        status = ""
        # A barra de status é lida por COM, que pode bloquear enquanto um diálogo
        # nativo do frontend estiver aberto; nesse caso vale só o progresso em disco.
        if not self._native_dialog_visible(
            ("Selecionar planilha eletrônica", "Select spreadsheet", "Gravar file", "Save file", "Save as")
        ):
            try:
                status = self._sap_status_bar_text()
            except Exception:
                status = ""
        known = {str(item).casefold() for item in self._observed_export_paths}
        for path in self._extract_xlsx_paths(status):
            if str(path).casefold() not in known:
                self._observed_export_paths.append(path)
        return total, status

    def _wait_file_stable(self, output_path: Path, after_timestamp: float) -> Path:
        # O prazo acompanha o progresso real: é renovado sempre que o arquivo cresce
        # no disco ou o status do SAP muda ("Download: 39 MB" → "40 MB"). Só falha
        # quando nada avança por timeout_seconds (ou 3x isso enquanto o SAP ainda
        # reporta download), ou ao atingir o teto absoluto.
        started = time.monotonic()
        hard_deadline = started + max(self.timeout_seconds * 9, 2700)
        last_progress = started
        progress_marker: tuple[int, str] | None = None
        next_progress_check = started
        last_progress_message = 0.0
        transfer_reported = False
        last_size = -1
        stable_checks = 0
        while True:
            now = time.monotonic()
            stall_limit = self.timeout_seconds * (3 if transfer_reported else 1)
            if now >= hard_deadline or now - last_progress >= stall_limit:
                break
            if now >= next_progress_check:
                next_progress_check = now + min(2.0, max(0.2, self.timeout_seconds / 4))
                marker = self._export_progress_marker(output_path, after_timestamp)
                transfer_reported = self._is_transfer_text(marker[1])
                if progress_marker is not None and marker != progress_marker:
                    last_progress = now
                    if now - last_progress_message >= 10:
                        last_progress_message = now
                        written = f" ({marker[0] / 1048576:.0f} MB gravados até agora)" if marker[0] else ""
                        self._status(
                            "EXPORTING_FILE",
                            f"O SAP ainda está transferindo o XLSX{written}; aguardando a conclusão.",
                        )
                progress_marker = marker
            self._check_cancelled()
            self._adopt_recent_export(output_path, after_timestamp)
            try:
                size = output_path.stat().st_size
            except OSError:
                size = 0
            if size > 0 and size == last_size and self._is_valid_recent_xlsx(output_path, after_timestamp):
                stable_checks += 1
                if stable_checks >= 3:
                    self._status(
                        "FILE_READY",
                        f"Arquivo XLSX localizado: {output_path.name}.",
                    )
                    return output_path
            else:
                stable_checks = 0
                last_size = size
            self._sleep(0.15)
        # Uma última leitura é obrigatória: o SAP pode concluir e fechar o ZIP
        # exatamente no limite. Se o arquivo reportado estiver íntegro, ele é
        # adotado em vez de gerar um falso erro de timeout.
        if self._adopt_recent_export(output_path, after_timestamp):
            if self._is_valid_xlsx_archive(output_path):
                self._status("FILE_READY", f"Arquivo XLSX localizado: {output_path.name}.")
                return output_path
        status_paths = self._sap_reported_export_paths()
        reported = ", ".join(str(path) for path in status_paths) or "nenhum caminho informado pelo SAP"
        sap_status = self._sap_status_bar_text()
        transfer_note = (
            f" O SAP ainda indicava transferência em andamento: {sap_status}."
            if self._transfer_in_progress()
            else (f" Último status do SAP: {sap_status}." if sap_status else "")
        )
        waited_minutes = (time.monotonic() - started) / 60
        raise SapGuiError(
            "O arquivo XLSX ainda não pôde ser validado no destino "
            f"(aguardado {waited_minutes:.0f} min, sem progresso nos últimos "
            f"{(time.monotonic() - last_progress) / 60:.0f} min). "
            f"Destino oficial: {output_path}. Caminho reportado pelo SAP: {reported}."
            f"{transfer_note}"
        )

    def _find_result_grid(self):
        candidates = (
            "wnd[0]/usr/cntlGRID1/shellcont/shell",
            "wnd[0]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell",
            "wnd[0]/usr/cntlCONTAINER/shellcont/shell",
            "wnd[0]/usr/cntlALV_CONTAINER_1/shellcont/shell",
        )
        for control_id in candidates:
            grid = self._try_find(control_id)
            if grid is not None:
                return grid
        raise SapGuiError("A grade de resultado do SAP não foi localizada para exportação.")

    def _open_xlsx_export(self, grid: Any) -> None:
        try:
            grid.contextMenu()
            grid.selectContextMenuItem("&XXL")
            return
        except Exception:
            pass
        try:
            grid.pressToolbarContextButton("&MB_EXPORT")
            grid.selectContextMenuItem("&XXL")
            return
        except Exception as exc:
            raise SapGuiError("Não foi possível abrir a exportação XLSX da grade do SAP.") from exc

    def _export_grid(self, output_path: Path) -> Path:
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        started_at = time.time()
        if output_path.exists():
            try:
                output_path.unlink()
            except OSError:
                # Se o arquivo estiver aberto, o SAP pode apresentar confirmação de sobrescrita.
                pass

        self._status("EXPORTING", "Abrindo a exportação da grade do SAP.")
        grid = self._find_result_grid()
        self._open_xlsx_export(grid)
        self._status("EXPORTING_FILE", f"Salvando {output_path.name}.")

        deadline = time.monotonic() + self.timeout_seconds
        format_attempts = 0
        last_format_attempt = 0.0
        save_attempts = 0
        last_save_attempt = 0.0
        transfer_seen = False
        native_grace_until = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            self._check_cancelled()
            if output_path.is_file() and output_path.stat().st_size > 0:
                break

            # Esses dois diálogos são janelas nativas do frontend SAP. Consultá-los
            # por wnd[1] pode bloquear o COM. O botão visível verde/Gerar é o
            # controle Windows 111 em ambos os casos.
            now = time.monotonic()
            if (
                format_attempts < 3
                and (format_attempts == 0 or now - last_format_attempt >= 0.75)
                and self._click_native_dialog_ok(
                    ("Selecionar planilha eletrônica", "Select spreadsheet")
                )
            ):
                format_attempts += 1
                last_format_attempt = now
                self._status(
                    "EXPORTING_FILE",
                    "Formato XLSX confirmado automaticamente no SAP.",
                )
                self._sleep(0.20)
                continue
            if (
                save_attempts < 3
                and (save_attempts == 0 or now - last_save_attempt >= 0.75)
                and self._click_native_dialog_ok(
                    ("Gravar file", "Save file", "Save as")
                )
            ):
                save_attempts += 1
                last_save_attempt = now
                self._status(
                    "EXPORTING_FILE",
                    "Comando Gerar acionado automaticamente; monitorando o XLSX produzido pelo SAP.",
                )
                self._sleep(0.20)
                continue

            native_titles = (
                "Selecionar planilha eletrônica",
                "Select spreadsheet",
                "Gravar file",
                "Save file",
                "Save as",
            )
            if now < native_grace_until or self._native_dialog_visible(native_titles):
                self._sleep(0.05)
                continue

            # Não consulta wnd[1] aqui: neste frontend os diálogos de formato e
            # gravação são nativos e uma chamada COM pode bloquear indefinidamente.
            # O tratamento acima cobre ambos pelos controles Windows reais.
            modal = None
            if modal is not None:
                # A janela "Gravar file" precisa ser tratada primeiro. Isso evita
                # gastar tempo procurando controles de formato em uma janela de salvamento.
                path_field = self._try_find("wnd[1]/usr/ctxtDY_PATH")
                if path_field is None:
                    path_field = self._find_by_technical_name(
                        modal,
                        "DY_PATH",
                        ("GuiCTextField", "GuiTextField"),
                    )
                if path_field is not None:
                    now = time.monotonic()
                    transferring = self._transfer_in_progress()
                    if transferring and not transfer_seen:
                        transfer_seen = True
                        # A transferência real pode iniciar perto do limite se o
                        # SAP demorou a montar/autorizar os diálogos. Dá ao arquivo
                        # um prazo completo a partir do início efetivo da transferência.
                        deadline = max(deadline, now + self.timeout_seconds)
                        self._status(
                            "EXPORTING_FILE",
                            "Transferência do XLSX iniciada no SAP; aguardando a gravação terminar.",
                        )
                    should_press = (
                        not transferring
                        and save_attempts < 3
                        and (save_attempts == 0 or now - last_save_attempt >= 0.75)
                    )
                    if should_press:
                        try:
                            if self._save_dialog(output_path):
                                save_attempts += 1
                                last_save_attempt = time.monotonic()
                                self._sleep(0.02)
                                continue
                        except SapGuiError:
                            if save_attempts == 0:
                                raise
                    if self._permit_sap_security_dialog():
                        last_save_attempt = time.monotonic()
                    self._sleep(0.02)
                    continue
                now = time.monotonic()
                if (
                    format_attempts < 3
                    and (format_attempts == 0 or now - last_format_attempt >= 0.50)
                    and self._select_format_dialog()
                ):
                    format_attempts += 1
                    last_format_attempt = time.monotonic()
                    self._sleep(0.02)
                    continue
                if save_attempts:
                    # Confirmação de sobrescrita, quando exibida em outro dynpro.
                    confirm = self._try_find("wnd[1]/tbar[0]/btn[0]")
                    if confirm is not None:
                        confirm.press()
                        self._sleep(0.02)
                        continue

            if self._adopt_recent_export(output_path, started_at):
                break
            self._sleep(0.03)

        return self._wait_file_stable(output_path, started_at)

    def run_zmm119(
        self,
        fisia_only: bool = True,
        output_path: Path | None = None,
        period: str | None = None,
    ) -> Path | None:
        self._check_cancelled()
        self._find("wnd[0]").maximize()
        self._transaction("ZMM119")
        if period is None:
            raise SapGuiError("A competência é obrigatória para executar a ZMM119 com segurança.")
        self._set_zmm119_period(period)
        checkbox = self._wait_control("wnd[0]/usr/chkP_FISIA")
        checkbox.selected = bool(fisia_only)
        self._status("RUNNING", "Executando a ZMM119 no SAP.")
        self._wait_control("wnd[0]/tbar[1]/btn[8]").press()
        self._wait_not_busy()
        if output_path is None:
            return None
        return self._export_grid(output_path)

    def _apply_mb59_variant(self, variant: str) -> None:
        try:
            self._wait_control("wnd[0]/mbar/menu[2]/menu[0]/menu[0]").select()
            variant_field = self._wait_control("wnd[1]/usr/txtV-LOW")
            variant_field.text = variant
            owner = self._try_find("wnd[1]/usr/txtENAME-LOW")
            if owner is not None:
                owner.text = ""
            self._wait_control("wnd[1]/tbar[0]/btn[8]").press()
            self._wait_not_busy()
        except Exception as exc:
            raise SapGuiError(f"Não foi possível aplicar a variante MB59 '{variant}'.") from exc

    def run_mb59(
        self,
        date_from: date,
        date_to: date,
        variant: str = "BASE GR",
        output_path: Path | None = None,
    ) -> Path | None:
        self._check_cancelled()
        if date_to < date_from:
            raise ValueError("A data final não pode ser anterior à data inicial.")
        self._find("wnd[0]").maximize()
        self._transaction("MB59")
        if variant.strip():
            self._apply_mb59_variant(variant.strip())

        material = self._try_find("wnd[0]/usr/ctxtMATNR-LOW")
        if material is not None:
            material.text = ""
        date_from_field = self._wait_control("wnd[0]/usr/ctxtBUDAT-LOW")
        date_to_field = self._wait_control("wnd[0]/usr/ctxtBUDAT-HIGH")
        date_from_field.text = date_from.strftime("%d.%m.%Y")
        date_to_field.text = date_to.strftime("%d.%m.%Y")
        expected_from = int(date_from.strftime("%d%m%Y"))
        expected_to = int(date_to.strftime("%d%m%Y"))
        if (
            self._numeric_value(date_from_field) != expected_from
            or self._numeric_value(date_to_field) != expected_to
        ):
            raise SapGuiError("O SAP não confirmou o intervalo informado nos campos de data da MB59.")
        self._status(
            "RUNNING",
            f"Período confirmado no SAP: {date_from:%d/%m/%Y} a {date_to:%d/%m/%Y}.",
        )
        self._status("RUNNING", "Executando a MB59 no SAP.")
        self._wait_control("wnd[0]/tbar[1]/btn[8]").press()
        self._wait_not_busy()
        if output_path is None:
            return None
        return self._export_grid(output_path)


def newest_export(directory: Path, after_timestamp: float) -> Path:
    candidates = [
        path
        for path in directory.glob("*.xlsx")
        if path.is_file() and path.stat().st_mtime >= after_timestamp and path.stat().st_size > 0
    ]
    if not candidates:
        raise SapGuiError(
            "O SAP não produziu um XLSX no diretório configurado. "
            "Confirme o diálogo de exportação e o diretório padrão do Excel."
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)
