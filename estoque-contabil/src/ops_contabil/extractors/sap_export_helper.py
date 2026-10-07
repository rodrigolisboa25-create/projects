from __future__ import annotations

import re
import sys
import time
import unicodedata
from pathlib import Path

import pythoncom
import win32com.client


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _try_find(session, control_id: str):
    try:
        return session.findById(control_id)
    except Exception:
        return None


def _sessions():
    sap_gui = win32com.client.GetObject("SAPGUI")
    engine = sap_gui.GetScriptingEngine
    for connection_index in range(engine.Children.Count):
        connection = engine.Children(connection_index)
        for session_index in range(connection.Children.Count):
            yield connection.Children(session_index)


def _descendants(root):
    pending = [root]
    while pending:
        parent = pending.pop()
        try:
            count = parent.Children.Count
        except Exception:
            continue
        for index in range(count):
            child = parent.Children(index)
            yield child
            pending.append(child)


def _find_export_session():
    fallback = None
    for session in _sessions():
        if _try_find(session, "wnd[1]") is not None:
            return session
        if fallback is None:
            fallback = session
    return fallback


def _choose_xlsx(combo) -> bool:
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


def _select_format(session) -> bool:
    window = _try_find(session, "wnd[1]")
    if window is None:
        return False
    title = _normalize(getattr(window, "Text", ""))
    known_radio = _try_find(session, "wnd[1]/usr/radRB_OTHERS")
    known_combo = _try_find(session, "wnd[1]/usr/cmbG_LISTBOX")
    radio = known_radio
    combo = known_combo

    if radio is None or combo is None:
        for control in _descendants(window):
            control_type = str(getattr(control, "Type", ""))
            control_text = _normalize(getattr(control, "Text", ""))
            if radio is None and control_type == "GuiRadioButton" and (
                "todos formatos" in control_text or "all available formats" in control_text
            ):
                radio = control
            if combo is None and control_type == "GuiComboBox":
                combo = control

    is_format_dialog = (
        "planilha eletronica" in title
        or "spreadsheet" in title
        or radio is not None
        or combo is not None
    )
    if not is_format_dialog:
        return False
    if radio is not None:
        radio.Select()
    if combo is not None and not _choose_xlsx(combo):
        raise RuntimeError("A opção XLSX não foi localizada na lista de formatos do SAP.")
    confirm = _try_find(session, "wnd[1]/tbar[0]/btn[0]")
    if confirm is None:
        raise RuntimeError("O botão verde do seletor de planilha não foi localizado.")
    confirm.press()
    return True


def _save_file(session, output_path: Path) -> bool:
    path_control = _try_find(session, "wnd[1]/usr/ctxtDY_PATH")
    file_control = _try_find(session, "wnd[1]/usr/ctxtDY_FILENAME")
    if path_control is None or file_control is None:
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    path_control.text = str(output_path.parent)
    file_control.text = output_path.name
    save = (
        _try_find(session, "wnd[1]/tbar[0]/btn[0]")
        or _try_find(session, "wnd[1]/tbar[0]/btn[11]")
    )
    if save is None:
        raise RuntimeError("O botão Salvar do SAP não foi localizado.")
    save.press()
    return True


def automate_export(output_path: Path, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    format_confirmed = False
    save_confirmed = False
    no_dialog_since: float | None = None

    while time.monotonic() < deadline:
        session = _find_export_session()
        if session is None:
            time.sleep(0.25)
            continue
        modal = _try_find(session, "wnd[1]")
        if modal is None:
            if save_confirmed or (format_confirmed and output_path.exists()):
                no_dialog_since = no_dialog_since or time.monotonic()
                if time.monotonic() - no_dialog_since >= 2:
                    return
            time.sleep(0.25)
            continue
        no_dialog_since = None
        if not format_confirmed and _select_format(session):
            format_confirmed = True
            time.sleep(0.5)
            continue
        if not save_confirmed and _save_file(session, output_path):
            save_confirmed = True
            time.sleep(0.5)
            continue
        if save_confirmed:
            if _try_find(session, "wnd[1]/usr/ctxtDY_PATH") is not None:
                time.sleep(0.25)
                continue
            # Handles the overwrite confirmation shown only when the target already exists.
            confirm = _try_find(session, "wnd[1]/tbar[0]/btn[0]")
            if confirm is not None:
                confirm.press()
                time.sleep(0.5)
                continue
        time.sleep(0.25)

    raise TimeoutError("O assistente não concluiu os diálogos de exportação do SAP no prazo.")


def main() -> int:
    if len(sys.argv) != 3:
        print("Uso: sap_export_helper.py ARQUIVO_SAIDA TIMEOUT", file=sys.stderr)
        return 2
    output_path = Path(sys.argv[1]).resolve()
    timeout_seconds = int(sys.argv[2])
    pythoncom.CoInitialize()
    try:
        automate_export(output_path, timeout_seconds)
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
