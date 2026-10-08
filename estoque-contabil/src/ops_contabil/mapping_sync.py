"""Mapping compartilhado pela pasta do Drive (Estoque_Cont/mapping).

Problema resolvido: as regras do Mapping (Planta e local, Status da operação, Lifecycle e
Faixas de aging) ficavam só na máquina de quem cadastrou. As competências calculadas lá
chegavam pela ponte já com o local novo, mas a página Mapping das outras máquinas não
mostrava a regra — e um recálculo local apagava o valor (ex.: centro 2115).

Desenho (o mesmo da lista central de acessos, ``access_sync``):
- Cada máquina grava SOMENTE o próprio arquivo ``mapping/alteracoes/<COMPUTADOR>.json``
  com a sua visão das regras; duas máquinas nunca gravam o mesmo arquivo.
- Todas as máquinas leem todos os arquivos; para cada regra (grupo + chave) vale a
  alteração mais recente (``changed_at``, em UTC). Exclusões ficam registradas como
  "excluída" para nunca serem desfeitas por uma lista antiga.
- Regras anteriores a esta funcionalidade (ou carregadas da configuração inicial) entram
  como "linha de base" (``updated_at``) e perdem para qualquer alteração explícita.
- Quem recebe regras novas recalcula as competências locais com elas, sem republicar no
  Drive (as outras máquinas fazem o mesmo ao receber as regras).
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .access_sync import _as_utc_text, _parse, _read_json, machine_file_name, machine_name, utc_now
from .access_sync import load_state as load_access_state
from .db import connect
from .mappings import MAPPING_GROUPS, ensure_mapping_schema

MAPPING_FOLDER = "mapping"
JOURNAL_FOLDER = "alteracoes"
STATE_KEY = "mapping_state"
FORMAT_VERSION = 1

_STATE_LOCK = threading.Lock()


def rule_key(group_key: str, key_value: str) -> str:
    return f"{group_key}|{str(key_value).strip()}"


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


def _update_state(settings: Any, mutate) -> dict[str, Any]:
    with _STATE_LOCK:
        state = load_state(settings)
        mutate(state)
        with connect(settings.path("database")) as connection:
            connection.execute(
                """insert into system_settings(setting_key,setting_value,updated_at) values (?,?,current_timestamp)
                   on conflict(setting_key) do update set setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
                [STATE_KEY, json.dumps(state, ensure_ascii=False)],
            )
        return state


# ------------------------------------------------------------- visão das regras


def rank(entry: dict[str, Any]) -> tuple[int, str]:
    """Alteração explícita vence linha de base; depois, a mais recente."""
    changed = entry.get("changed_at")
    return (1, str(changed)) if changed else (0, str(entry.get("baseline_at") or ""))


def local_view(settings: Any) -> dict[str, dict[str, Any]]:
    with connect(settings.path("database")) as connection:
        ensure_mapping_schema(connection)
        rows = connection.execute(
            "select group_key, key_value, value_1, value_2, changed_at, changed_by, updated_at from mapping_rules"
        ).fetchall()
    view: dict[str, dict[str, Any]] = {}
    for group_key, key_value, value_1, value_2, changed_at, changed_by, updated_at in rows:
        view[rule_key(group_key, key_value)] = {
            "group": group_key,
            "key": str(key_value).strip(),
            "value_1": value_1,
            "value_2": value_2,
            "deleted": False,
            "changed_at": changed_at or None,
            "changed_by": changed_by or None,
            "baseline_at": None if changed_at else _as_utc_text(updated_at),
        }
    for key, tombstone in load_state(settings)["tombstones"].items():
        group_key, _, key_value = key.partition("|")
        entry = {"group": group_key, "key": key_value, "value_1": None, "value_2": None, "deleted": True,
                 "changed_at": tombstone.get("changed_at"), "changed_by": tombstone.get("changed_by"), "baseline_at": None}
        if key not in view or rank(entry) > rank(view[key]):
            view[key] = entry
    return view


def record_change(settings: Any, group_key: str, key_value: str, *, by: str, deleted: bool = False) -> str:
    """Registra uma inclusão, alteração ou exclusão de regra feita nesta máquina."""
    changed_at = utc_now()
    key = rule_key(group_key, key_value)
    if not deleted:
        with connect(settings.path("database")) as connection:
            ensure_mapping_schema(connection)
            connection.execute(
                "update mapping_rules set changed_at=?, changed_by=? where group_key=? and trim(key_value)=?",
                [changed_at, by, group_key, str(key_value).strip()],
            )

    def mutate(state: dict[str, Any]) -> None:
        if deleted:
            state["tombstones"][key] = {"changed_at": changed_at, "changed_by": by}
        else:
            state["tombstones"].pop(key, None)
        state["publisher"] = True
        state["pending_publish"] = True

    _update_state(settings, mutate)
    return changed_at


# --------------------------------------------------------------- pasta do Drive


def _journal_folder(root: Path) -> Path:
    return root / MAPPING_FOLDER / JOURNAL_FOLDER


def is_publisher(settings: Any) -> bool:
    """Publica quem alterou o Mapping aqui ou é máquina de administrador (lista de acessos)."""
    return bool(load_state(settings).get("publisher") or load_access_state(settings).get("publisher"))


def publish_journal(settings: Any, root: Path) -> bool:
    """Grava a visão desta máquina no próprio arquivo (só quando mudou)."""
    rules = local_view(settings)
    folder = _journal_folder(root)
    target = folder / machine_file_name(settings)
    current = _read_json(target)
    if current and current.get("rules") == rules:
        return False
    folder.mkdir(parents=True, exist_ok=True)
    payload = {"format": FORMAT_VERSION, "machine": machine_name(settings), "updated_at": utc_now(), "rules": rules}
    partial = folder / f".{target.name}.parcial"
    partial.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(partial, target)
    return True


def read_merged(root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Junta os arquivos de todas as máquinas: por regra, vale a alteração mais recente."""
    merged: dict[str, dict[str, Any]] = {}
    machines: list[dict[str, Any]] = []
    folder = _journal_folder(root)
    if not folder.is_dir():
        return merged, machines
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if not payload or int(payload.get("format", 0) or 0) > FORMAT_VERSION or not isinstance(payload.get("rules"), dict):
            continue
        machines.append({"machine": payload.get("machine") or path.stem, "updated_at": payload.get("updated_at"),
                         "rules": len(payload["rules"])})
        for entry in payload["rules"].values():
            if not isinstance(entry, dict) or entry.get("group") not in MAPPING_GROUPS or not str(entry.get("key") or "").strip():
                continue
            key = rule_key(str(entry["group"]), str(entry["key"]))
            if key not in merged or rank(entry) > rank(merged[key]):
                merged[key] = entry
    return merged, machines


def _local_naive(value: Any) -> datetime:
    parsed = _parse(value)
    return parsed.astimezone().replace(tzinfo=None) if parsed else datetime.now()


def purge_shadowed_rules(settings: Any) -> list[str]:
    """Remove regras locais que têm exclusão registrada mais nova (ex.: regra renomeada e recriada por engano)."""
    tombstones = load_state(settings)["tombstones"]
    if not tombstones:
        return []
    removed: list[str] = []
    with connect(settings.path("database")) as connection:
        ensure_mapping_schema(connection)
        rows = connection.execute("select group_key, key_value, changed_at, updated_at from mapping_rules").fetchall()
        for group_key, key_value, changed_at, updated_at in rows:
            key = rule_key(group_key, key_value)
            tombstone = tombstones.get(key)
            if not tombstone:
                continue
            row_rank = (1, str(changed_at)) if changed_at else (0, str(_as_utc_text(updated_at) or ""))
            if (1, str(tombstone.get("changed_at") or "")) > row_rank:
                connection.execute("delete from mapping_rules where group_key=? and key_value=?", [group_key, key_value])
                removed.append(key)
    return removed


def apply_merged(settings: Any, merged: dict[str, dict[str, Any]]) -> list[str]:
    """Aplica nesta máquina as regras mais recentes. Devolve as regras cujo efeito mudou."""
    changed: list[str] = purge_shadowed_rules(settings)
    local = local_view(settings)
    new_tombstones: dict[str, dict[str, Any]] = {}
    cleared_tombstones: list[str] = []
    with connect(settings.path("database")) as connection:
        ensure_mapping_schema(connection)
        for key, remote in merged.items():
            current = local.get(key)
            if current is not None and rank(current) >= rank(remote):
                continue
            group_key, key_value = str(remote["group"]), str(remote["key"]).strip()
            if remote.get("deleted"):
                if current is not None and not current.get("deleted"):
                    connection.execute("delete from mapping_rules where group_key=? and trim(key_value)=?", [group_key, key_value])
                    changed.append(key)
                new_tombstones[key] = {"changed_at": remote.get("changed_at"), "changed_by": remote.get("changed_by")}
                continue
            same_values = (current is not None and not current.get("deleted")
                           and current.get("value_1") == remote.get("value_1") and current.get("value_2") == remote.get("value_2"))
            stamp = _local_naive(remote.get("baseline_at") or remote.get("changed_at"))
            if current is not None and not current.get("deleted"):
                connection.execute(
                    """update mapping_rules set value_1=?, value_2=?, changed_at=?, changed_by=?, updated_at=?
                       where group_key=? and trim(key_value)=?""",
                    [remote.get("value_1"), remote.get("value_2"), remote.get("changed_at"), remote.get("changed_by"), stamp,
                     group_key, key_value],
                )
            else:
                position = connection.execute(
                    "select coalesce(max(position),0)+1 from mapping_rules where group_key=?", [group_key]).fetchone()[0]
                connection.execute(
                    """insert into mapping_rules(group_key,key_value,value_1,value_2,position,updated_at,changed_at,changed_by)
                       values (?,?,?,?,?,?,?,?)""",
                    [group_key, key_value, remote.get("value_1"), remote.get("value_2"), position, stamp,
                     remote.get("changed_at"), remote.get("changed_by")],
                )
            cleared_tombstones.append(key)
            if not same_values:
                changed.append(key)  # só muda o resultado quando os valores mudam (datas iguais não recalculam)
    if new_tombstones or cleared_tombstones:
        def mutate(state: dict[str, Any]) -> None:
            for key in cleared_tombstones:
                state["tombstones"].pop(key, None)
            state["tombstones"].update(new_tombstones)
        _update_state(settings, mutate)
    return changed


def sync_mapping(settings: Any, root: Path) -> dict[str, Any]:
    """Publica a visão desta máquina (se publicar) e aplica as regras mais recentes de todas."""
    if not root.is_dir():
        raise OSError(f"Pasta do Drive inacessível: {root}")
    published = False
    publish_error = None
    if is_publisher(settings):
        try:
            published = publish_journal(settings, root)
        except OSError as exc:
            publish_error = f"Sem permissão de gravação na pasta do Mapping no Drive: {exc}"
    merged, machines = read_merged(root)
    changed = apply_merged(settings, merged) if merged else purge_shadowed_rules(settings)
    now = utc_now()

    def mutate(current: dict[str, Any]) -> None:
        current.update(last_sync_at=now, last_error=publish_error, machines=machines,
                       folder=str(root / MAPPING_FOLDER), last_changed=changed[-20:])
        if changed:
            current["last_received_at"] = now
        if publish_error is None and published:
            current["last_publish_at"] = now
        if publish_error is None:
            current["pending_publish"] = False

    _update_state(settings, mutate)
    return {"published": published, "changed": changed, "machines": machines, "error": publish_error}


def record_error(settings: Any, message: str) -> None:
    _update_state(settings, lambda state: state.update(last_error=message, last_attempt_at=utc_now()))


def mapping_sync_status(settings: Any) -> dict[str, Any]:
    state = load_state(settings)
    return {
        "last_sync_at": state.get("last_sync_at"),
        "last_publish_at": state.get("last_publish_at"),
        "last_received_at": state.get("last_received_at"),
        "pending_publish": bool(state.get("pending_publish")),
        "last_error": state.get("last_error"),
        "machines": state.get("machines") or [],
        "last_changed": state.get("last_changed") or [],
    }
