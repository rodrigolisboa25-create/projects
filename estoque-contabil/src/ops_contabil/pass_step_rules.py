"""Regras ajustáveis do PASSO A PASSO (Product Offer End Dt, Season e Year).

Cada campo tem dois parâmetros, escolhidos entre opções fixas (nada é inventado pelo sistema):
- passo 1, Base GR do mês: de qual entrada da MB59/Base GR vem o valor (``STEP1_OPTIONS``);
- passo 2, posição do mês anterior: por qual chave a posição anterior é consultada (``STEP2_OPTIONS``).
O passo 3 (All Brazil) e o 4 (preenchimento manual) são fixos.

O padrão (``DEFAULT_RULES``) é a regra validada com o fechamento manual de 09/2026. Uma regra só muda
quando um administrador aprova a sugestão da conferência (ou restaura uma versão anterior): cada mudança
fica no histórico (``pass_step_rule_history``) e vai para as outras máquinas pela pasta do Drive
(``Estoque_Cont/regras/passo_a_passo.json``), para todas calcularem igual.

As mesmas consultas (``step1_sql``/``step2_sql``) servem ao PASSO A PASSO (mb59.enrich_inventory_pass_step)
e ao diagnóstico da conferência (conference.py), que testa as combinações contra a planilha manual.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import connect

FIELDS = ("product_offer_end_date", "season", "year")
FIELD_LABELS = {"product_offer_end_date": "Product Offer End Dt", "season": "Season", "year": "Year"}
# Pedidos de importação (Material Origin "IMPORTADO" na Base GR do fechamento).
IMPORT_ORDER_PREFIX = "48"

STEP1_OPTIONS: dict[str, str] = {
    "gr_import_first": "Base GR pelo Material: primeira entrada de pedido de importação (48…) com coleção",
    "gr_all_first": "Base GR pelo Material: primeira entrada do Material (qualquer pedido)",
    "gr_all_latest": "Base GR pelo Material: entrada mais recente do Material",
    "sku_latest": "Base GR pelo SKU (10 caracteres): entrada mais recente, sem intercompany (regra anterior)",
    "none": "Não usar a Base GR",
}
STEP2_OPTIONS: dict[str, str] = {
    "ce_mat": "Mês anterior pelo CE & MAT (mesmo centro e material)",
    "material": "Mês anterior pelo Material completo (qualquer centro)",
    "ce_mat_material": "Mês anterior pelo CE & MAT; se não houver, pelo Material",
}
DEFAULT_RULES: dict[str, dict[str, str]] = {
    "product_offer_end_date": {"step1": "gr_all_first", "step2": "ce_mat"},
    "season": {"step1": "gr_all_first", "step2": "ce_mat"},
    "year": {"step1": "gr_import_first", "step2": "material"},
}
RULES_KEY = "pass_step_rules"
BRIDGE_FOLDER = "regras"
BRIDGE_FILE = "passo_a_passo.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_rules(raw: Any) -> dict[str, dict[str, str]]:
    """Completa e valida: opção desconhecida volta ao padrão daquele campo."""
    rules = {field: dict(values) for field, values in DEFAULT_RULES.items()}
    if isinstance(raw, dict):
        for field in FIELDS:
            item = raw.get(field)
            if isinstance(item, dict):
                if item.get("step1") in STEP1_OPTIONS:
                    rules[field]["step1"] = str(item["step1"])
                if item.get("step2") in STEP2_OPTIONS:
                    rules[field]["step2"] = str(item["step2"])
    return rules


def describe(rules: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    return {field: {"label": FIELD_LABELS[field], "step1": STEP1_OPTIONS[r["step1"]], "step2": STEP2_OPTIONS[r["step2"]],
                    "step3": "All Brazil pelo Material (ou Estilo-Cor)", "step4": "Preenchimento manual"}
            for field, r in rules.items()}


# ------------------------------------------------------------------ armazenamento local


def ensure_rules_schema(connection: Any) -> None:
    connection.execute(
        """create table if not exists pass_step_rule_history (
               version integer not null,
               action varchar not null,
               rules_json varchar not null,
               previous_json varchar,
               reason varchar,
               conference_id varchar,
               period varchar,
               changed_by varchar,
               changed_at timestamp not null default current_timestamp,
               machine varchar
           )"""
    )


def _stored(connection: Any) -> dict[str, Any]:
    row = connection.execute("select setting_value from system_settings where setting_key=?", [RULES_KEY]).fetchone()
    try:
        data = json.loads(row[0]) if row else {}
    except (TypeError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


def load_rules(connection: Any) -> dict[str, dict[str, str]]:
    return normalize_rules(_stored(connection).get("rules"))


def rules_state(connection: Any) -> dict[str, Any]:
    data = _stored(connection)
    return {"rules": normalize_rules(data.get("rules")), "version": int(data.get("version") or 0),
            "updated_at": data.get("updated_at"), "updated_by": data.get("updated_by"), "reason": data.get("reason")}


def save_rules(connection: Any, rules: dict[str, Any], *, action: str, changed_by: str, reason: str = "",
               conference_id: str | None = None, period: str | None = None, updated_at: str | None = None) -> dict[str, Any]:
    """Grava a nova versão das regras e registra no histórico (ação: aprovar, restaurar ou sincronizar)."""
    ensure_rules_schema(connection)
    current = rules_state(connection)
    clean = normalize_rules(rules)
    version = int(connection.execute("select coalesce(max(version),0)+1 from pass_step_rule_history").fetchone()[0])
    stamp = updated_at or utc_now()
    payload = {"rules": clean, "version": version, "updated_at": stamp, "updated_by": changed_by, "reason": reason}
    connection.execute(
        """insert into system_settings(setting_key, setting_value, updated_at) values (?, ?, current_timestamp)
           on conflict(setting_key) do update set setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
        [RULES_KEY, json.dumps(payload, ensure_ascii=False)],
    )
    connection.execute(
        """insert into pass_step_rule_history(version, action, rules_json, previous_json, reason, conference_id, period,
               changed_by, machine) values (?,?,?,?,?,?,?,?,?)""",
        [version, action, json.dumps(clean, ensure_ascii=False), json.dumps(current["rules"], ensure_ascii=False),
         reason, conference_id, period, changed_by, os.getenv("COMPUTERNAME", "")],
    )
    return payload


def rules_history(connection: Any, limit: int = 30) -> list[dict[str, Any]]:
    ensure_rules_schema(connection)
    rows = connection.execute(
        """select version, action, rules_json, previous_json, reason, conference_id, period, changed_by, changed_at, machine
             from pass_step_rule_history order by version desc limit ?""", [limit]).fetchall()
    keys = ("version", "action", "rules", "previous", "reason", "conference_id", "period", "changed_by", "changed_at", "machine")
    items = []
    for row in rows:
        item = dict(zip(keys, row, strict=True))
        item["rules"] = normalize_rules(json.loads(item["rules"] or "{}"))
        item["previous"] = normalize_rules(json.loads(item["previous"] or "{}"))
        item["changed_at"] = item["changed_at"].isoformat() if hasattr(item["changed_at"], "isoformat") else str(item["changed_at"])
        items.append(item)
    return items


# ------------------------------------------------------------------ consultas dos passos


def _value(field: str, source: str) -> str:
    return {"product_offer_end_date": "e.posting_date", "season": f"{source}.season", "year": f"{source}.year"}[field]


def step1_sql(option: str, field: str) -> tuple[str, str, list[str]] | None:
    """(SQL, tipo de chave, tabelas exigidas) do passo 1; o SQL recebe a competência (?) e devolve (chave, valor).
    ``None`` = não usar a Base GR. Tipo de chave: ``material`` (Material completo) ou ``sku`` (10 caracteres)."""
    join = ("join gr_collection_rows c on c.period=e.period and c.purchase_order=e.purchase_order")
    if option == "none":
        return None
    if option == "gr_import_first":
        value = _value(field, "c")
        return (f"""select e.material, arg_min({value}, e.source_row) from mb59_material_entries e {join}
                    where e.period=? and e.purchase_order like '{IMPORT_ORDER_PREFIX}%' group by 1""", "material", ["mb59_material_entries"])
    if option == "gr_all_first":
        if field == "product_offer_end_date":
            return ("""select e.material, arg_min(e.posting_date, e.source_row) from mb59_material_entries e
                       where e.period=? group by 1""", "material", ["mb59_material_entries"])
        return (f"""select e.material, arg_min({_value(field, 'c')}, e.source_row) from mb59_material_entries e {join}
                    where e.period=? group by 1""", "material", ["mb59_material_entries"])
    if option == "gr_all_latest":
        latest = "coalesce(e.last_posting_date, e.posting_date)"
        if field == "product_offer_end_date":
            return (f"""select e.material, max({latest}) from mb59_material_entries e where e.period=? group by 1""",
                    "material", ["mb59_material_entries"])
        return (f"""select e.material, arg_max({_value(field, 'c')}, {latest}) from mb59_material_entries e {join}
                    where e.period=? group by 1""", "material", ["mb59_material_entries"])
    if option == "sku_latest":
        if field == "product_offer_end_date":
            return ("select e.sku, e.posting_date from mb59_sku_entries e where e.period=?", "sku", ["mb59_sku_entries"])
        return (f"""select e.sku, {_value(field, 'c')} from mb59_sku_entries e {join} where e.period=?""", "sku", ["mb59_sku_entries"])
    raise ValueError(f"Opção desconhecida no passo 1: {option}")


def step2_sql(option: str, field: str, from_master: bool) -> list[tuple[str, str]]:
    """Consultas do passo 2, em ordem: lista de (SQL, tipo de chave ``ce_mat``|``material``); recebe a competência anterior."""
    table = "master_base_rows" if from_master else "inventory_rows"
    ce = (f"select center_material_key, {field} from {table} where period=? and {field} is not null", "ce_mat")
    if from_master:  # a base mestre guarda só CE & MAT: Centro (4 dígitos) + Material
        material = (f"""select upper(trim(substr(center_material_key, 5))), arg_min({field}, center_material_key) from master_base_rows
                        where period=? and {field} is not null and length(center_material_key) > 4 group by 1""", "material")
    else:  # primeira linha da posição (PROCV)
        material = (f"""select upper(trim(material)), arg_min({field}, source_row) from inventory_rows
                        where period=? and {field} is not null and material is not null group by 1""", "material")
    return {"ce_mat": [ce], "material": [material], "ce_mat_material": [ce, material]}[option]


def has_rows(connection: Any, table: str, period: str) -> bool:
    try:
        return bool(connection.execute(f"select count(*) > 0 from {table} where period=?", [period]).fetchone()[0])
    except Exception:  # noqa: BLE001 - tabela ainda não criada
        return False


def step1_lookup(connection: Any, period: str, option: str, field: str) -> tuple[dict[str, Any], str] | None:
    """Valores do passo 1 por chave; ``None`` quando a opção não tem dados nesta competência (carga antiga)."""
    spec = step1_sql(option, field)
    if spec is None:
        return {}, "material"
    sql, kind, tables = spec
    if not all(has_rows(connection, table, period) for table in tables):
        return None
    return {str(row[0]).strip().upper(): row[1] for row in connection.execute(sql, [period]).fetchall()
            if row[0] not in (None, "") and row[1] not in (None, "")}, kind


def step2_lookups(connection: Any, previous_period: str, option: str, field: str, from_master: bool) -> list[tuple[dict[str, Any], str]]:
    return [({str(row[0]).strip() if kind == "ce_mat" else str(row[0]).strip().upper(): row[1]
              for row in connection.execute(sql, [previous_period]).fetchall() if row[0] not in (None, "")}, kind)
            for sql, kind in step2_sql(option, field, from_master)]


# ------------------------------------------------------------------ ponte do Drive


def publish_rules(settings: Any, root: Path) -> None:
    """Grava a versão local no Drive (só se for mais nova que a de lá)."""
    with connect(settings.path("database")) as connection:
        state = rules_state(connection)
    if not state["updated_at"]:
        return  # nunca alterada: todas as máquinas usam o padrão
    target = Path(root) / BRIDGE_FOLDER / BRIDGE_FILE
    remote = _read_remote(target)
    if remote and str(remote.get("updated_at") or "") >= str(state["updated_at"]):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps({"format": 1, "machine": os.getenv("COMPUTERNAME", ""), **state}, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    os.replace(temporary, target)


def _read_remote(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def sync_rules(settings: Any, root: Path) -> dict[str, Any] | None:
    """Adota a versão do Drive quando ela é mais nova que a local (vale a alteração mais recente)."""
    remote = _read_remote(Path(root) / BRIDGE_FOLDER / BRIDGE_FILE)
    if not remote or not remote.get("updated_at"):
        return None
    with connect(settings.path("database")) as connection:
        local = rules_state(connection)
        if local["updated_at"] and str(local["updated_at"]) >= str(remote["updated_at"]):
            return None
        return save_rules(connection, remote.get("rules") or {}, action="sincronizada",
                          changed_by=str(remote.get("updated_by") or ""), reason=str(remote.get("reason") or ""),
                          updated_at=str(remote["updated_at"]))
