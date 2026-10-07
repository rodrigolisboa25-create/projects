"""Lista central de acessos pela pasta do Drive compartilhado (Estoque_Cont/acesso).

Problema resolvido: cada máquina tinha a própria lista de usuários; desativar,
excluir ou cadastrar alguém só valia na máquina de quem fez a alteração.

Desenho:
- Cada máquina de administrador grava SOMENTE o próprio arquivo
  ``acesso/alteracoes/<COMPUTADOR>.json`` com a sua visão da lista. Duas máquinas
  nunca gravam o mesmo arquivo (sem conflitos de sincronização do Google Drive).
- Todas as máquinas leem todos os arquivos; para cada e-mail vale a alteração mais
  recente feita por um administrador (``changed_at``, em UTC). Exclusões ficam
  registradas como "excluído" para nunca serem desfeitas por uma lista antiga.
- O login altera ``updated_at``; por isso a decisão usa ``access_changed_at``.
  Registros anteriores a esta funcionalidade entram como "linha de base" e perdem
  para qualquer alteração explícita.
- Usuários comuns ficam bloqueados se a máquina passar mais de ``GRACE_DAYS`` dias
  sem conseguir consultar a lista (administradores continuam entrando).
- Administradores iniciais (BOOTSTRAP_ADMINS) nunca são desativados nem excluídos.
"""

from __future__ import annotations

import json
import os
import re
import socket
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .auth import BOOTSTRAP_ADMINS, sanitize_role_pages
from .db import connect

ACCESS_FOLDER = "acesso"
JOURNAL_FOLDER = "alteracoes"
STATE_KEY = "access_state"
GRACE_DAYS = 7
FORMAT_VERSION = 1

_STATE_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()  # horário local da máquina
    return parsed.astimezone(timezone.utc)


def _as_utc_text(value: Any) -> str | None:
    parsed = _parse(value)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") if parsed else None


def machine_name(settings: Any) -> str:
    """Nome do computador (a configuração runtime.machine_name permite simular máquinas nos testes)."""
    configured = str(((getattr(settings, "raw", {}) or {}).get("runtime") or {}).get("machine_name") or "")
    return configured or socket.gethostname()


def machine_file_name(settings: Any) -> str:
    return (re.sub(r"[^A-Za-z0-9-]+", "-", machine_name(settings)).strip("-").upper() or "MAQUINA") + ".json"


# ------------------------------------------------------------------ estado local


def load_state(settings: Any) -> dict[str, Any]:
    with connect(settings.path("database")) as connection:
        row = connection.execute("select setting_value from system_settings where setting_key=?", [STATE_KEY]).fetchone()
    try:
        state = json.loads(row[0]) if row else {}
    except (TypeError, ValueError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    state.setdefault("tombstones", {})
    return state


def _save_state(settings: Any, state: dict[str, Any]) -> None:
    with connect(settings.path("database")) as connection:
        connection.execute(
            """insert into system_settings(setting_key,setting_value,updated_at) values (?,?,current_timestamp)
               on conflict(setting_key) do update set setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
            [STATE_KEY, json.dumps(state, ensure_ascii=False)],
        )


def _update_state(settings: Any, mutate) -> dict[str, Any]:
    with _STATE_LOCK:
        state = load_state(settings)
        mutate(state)
        _save_state(settings, state)
        return state


# ------------------------------------------------------------- visão da lista


def rank(entry: dict[str, Any]) -> tuple[int, str]:
    """Alteração explícita de administrador vence linha de base; depois, a mais recente."""
    changed = entry.get("changed_at")
    return (1, str(changed)) if changed else (0, str(entry.get("baseline_at") or ""))


def local_view(settings: Any) -> dict[str, dict[str, Any]]:
    with connect(settings.path("database")) as connection:
        rows = connection.execute(
            """select email, is_active, role, allowed_pages, access_changed_at, access_changed_by, updated_at
               from allowed_users"""
        ).fetchall()
    view: dict[str, dict[str, Any]] = {}
    for email, active, role, pages, changed_at, changed_by, updated_at in rows:
        try:
            parsed_pages = json.loads(pages or "[]")
        except (TypeError, ValueError):
            parsed_pages = []
        view[str(email)] = {
            "active": bool(active),
            "role": "admin" if role == "admin" else "user",
            "pages": parsed_pages if isinstance(parsed_pages, list) else [],
            "deleted": False,
            "changed_at": changed_at or None,
            "changed_by": changed_by or None,
            "baseline_at": None if changed_at else _as_utc_text(updated_at),
        }
    for email, tombstone in load_state(settings)["tombstones"].items():
        entry = {"deleted": True, "active": False, "role": "user", "pages": [],
                 "changed_at": tombstone.get("changed_at"), "changed_by": tombstone.get("changed_by"), "baseline_at": None}
        if email not in view or rank(entry) > rank(view[email]):
            view[email] = entry
    return view


def record_change(settings: Any, email: str, *, by: str, deleted: bool = False) -> str:
    """Registra uma alteração de acesso feita por um administrador nesta máquina."""
    changed_at = utc_now()
    if not deleted:
        with connect(settings.path("database")) as connection:
            connection.execute(
                "update allowed_users set access_changed_at=?, access_changed_by=? where email=?",
                [changed_at, by, email],
            )

    def mutate(state: dict[str, Any]) -> None:
        if deleted:
            state["tombstones"][email] = {"changed_at": changed_at, "changed_by": by}
        else:
            state["tombstones"].pop(email, None)
        state["publisher"] = True
        state["pending_publish"] = True

    _update_state(settings, mutate)
    return changed_at


def mark_publisher(settings: Any) -> None:
    """Máquina usada por um administrador: passa a publicar a sua visão da lista."""
    state = load_state(settings)
    if not state.get("publisher"):
        _update_state(settings, lambda current: current.update(publisher=True, pending_publish=True))


# --------------------------------------------------------------- pasta do Drive


def _journal_folder(root: Path) -> Path:
    return root / ACCESS_FOLDER / JOURNAL_FOLDER


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def publish_journal(settings: Any, root: Path) -> bool:
    """Grava a visão desta máquina no próprio arquivo (só quando mudou)."""
    users = local_view(settings)
    folder = _journal_folder(root)
    target = folder / machine_file_name(settings)
    current = _read_json(target)
    if current and current.get("users") == users:
        return False
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": FORMAT_VERSION,
        "machine": machine_name(settings),
        "updated_at": utc_now(),
        "users": users,
    }
    partial = folder / f".{target.name}.parcial"
    partial.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(partial, target)
    return True


def read_merged(root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Junta os arquivos de todas as máquinas: por e-mail, vale a alteração mais recente."""
    merged: dict[str, dict[str, Any]] = {}
    machines: list[dict[str, Any]] = []
    folder = _journal_folder(root)
    if not folder.is_dir():
        return merged, machines
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if not payload or int(payload.get("format", 0) or 0) > FORMAT_VERSION or not isinstance(payload.get("users"), dict):
            continue
        machines.append({"machine": payload.get("machine") or path.stem, "updated_at": payload.get("updated_at"),
                         "users": len(payload["users"])})
        for email, entry in payload["users"].items():
            if not isinstance(entry, dict):
                continue
            email = str(email).strip().lower()
            if email not in merged or rank(entry) > rank(merged[email]):
                merged[email] = entry
    return merged, machines


def apply_merged(settings: Any, merged: dict[str, dict[str, Any]]) -> list[str]:
    """Aplica nesta máquina as alterações mais recentes da lista central."""
    local = local_view(settings)
    changed: list[str] = []
    new_tombstones: dict[str, dict[str, Any]] = {}
    cleared_tombstones: list[str] = []
    with connect(settings.path("database")) as connection:
        for email, remote in merged.items():
            if email in BOOTSTRAP_ADMINS:
                continue  # administradores iniciais nunca são desativados nem excluídos
            current = local.get(email)
            if current is not None and rank(current) >= rank(remote):
                continue
            if remote.get("deleted"):
                if current is not None and not current.get("deleted"):
                    connection.execute("delete from allowed_users where email=?", [email])
                    changed.append(email)
                new_tombstones[email] = {"changed_at": remote.get("changed_at"), "changed_by": remote.get("changed_by")}
                continue
            try:
                role, pages = sanitize_role_pages(str(remote.get("role") or "user"), list(remote.get("pages") or []))
            except ValueError:
                continue
            baseline = _parse(remote.get("baseline_at"))
            connection.execute(
                """insert into allowed_users(email,is_active,role,allowed_pages,access_changed_at,access_changed_by,updated_at)
                   values (?,?,?,?,?,?,?)
                   on conflict(email) do update set is_active=excluded.is_active, role=excluded.role,
                     allowed_pages=excluded.allowed_pages, access_changed_at=excluded.access_changed_at,
                     access_changed_by=excluded.access_changed_by,
                     updated_at=case when excluded.access_changed_at is null then excluded.updated_at else updated_at end""",
                [email, bool(remote.get("active")), role, json.dumps(pages, ensure_ascii=False),
                 remote.get("changed_at"), remote.get("changed_by"),
                 (baseline.astimezone().replace(tzinfo=None) if baseline else datetime.now())],
            )
            cleared_tombstones.append(email)
            changed.append(email)
    if new_tombstones or cleared_tombstones:
        def mutate(state: dict[str, Any]) -> None:
            for email in cleared_tombstones:
                state["tombstones"].pop(email, None)
            state["tombstones"].update(new_tombstones)
        _update_state(settings, mutate)
    return changed


def sync_access(settings: Any, root: Path) -> dict[str, Any]:
    """Publica a visão desta máquina (se for de administrador) e aplica a lista central."""
    if not root.is_dir():
        raise OSError(f"Pasta do Drive inacessível: {root}")
    state = load_state(settings)
    published = False
    publish_error = None
    if state.get("publisher"):
        try:
            published = publish_journal(settings, root)
        except OSError as exc:
            publish_error = f"Sem permissão de gravação na pasta de acessos do Drive: {exc}"
    folder = root / ACCESS_FOLDER
    merged, machines = read_merged(root)
    changed = apply_merged(settings, merged) if merged else []
    now = utc_now()

    def mutate(current: dict[str, Any]) -> None:
        current.update(
            last_sync_at=now,
            last_verified_at=now,
            last_error=publish_error,
            machines=machines,
            folder=str(folder),
            last_changed=changed[-20:],
        )
        if publish_error is None and current.get("publisher"):
            current["pending_publish"] = False
            current["last_publish_at"] = now if published else current.get("last_publish_at")

    _update_state(settings, mutate)
    return {"published": published, "changed": changed, "machines": machines, "error": publish_error}


def record_error(settings: Any, message: str) -> None:
    _update_state(settings, lambda state: state.update(last_error=message, last_attempt_at=utc_now()))


# ------------------------------------------------------------ verificação local


def verification(settings: Any, now: datetime | None = None) -> dict[str, Any]:
    """Situação da última consulta à lista central (bloqueio após GRACE_DAYS dias)."""
    state = load_state(settings)
    if not state.get("first_seen_at"):
        first_seen = utc_now()
        _update_state(settings, lambda current: current.setdefault("first_seen_at", first_seen))
        state["first_seen_at"] = first_seen
    reference = _parse(state.get("last_verified_at")) or _parse(state.get("first_seen_at"))
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expires = (reference or now) + timedelta(days=GRACE_DAYS)
    return {
        "last_verified_at": state.get("last_verified_at"),
        "first_seen_at": state.get("first_seen_at"),
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "expired": now > expires,
        "days_left": max(0, (expires - now).days),
    }


def access_status(settings: Any) -> dict[str, Any]:
    state = load_state(settings)
    return {
        **verification(settings),
        "last_sync_at": state.get("last_sync_at"),
        "last_publish_at": state.get("last_publish_at"),
        "pending_publish": bool(state.get("pending_publish")),
        "publisher": bool(state.get("publisher")),
        "last_error": state.get("last_error"),
        "machines": state.get("machines") or [],
        "folder": state.get("folder"),
        "grace_days": GRACE_DAYS,
    }
