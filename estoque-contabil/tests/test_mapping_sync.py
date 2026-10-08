"""Mapping compartilhado: regra cadastrada numa máquina aparece e vale nas outras (pela pasta do Drive)."""

from __future__ import annotations

import json
from pathlib import Path

from ops_contabil.db import connect
from ops_contabil.mapping_sync import local_view, read_merged
from ops_contabil.mappings import ensure_mapping_schema
from test_access_sync import ADMIN_A, ADMIN_B, drive, login, machine  # noqa: F401 - fixtures reaproveitadas


def seed_period(settings, plant: str = "2115") -> None:
    with connect(settings.path("database")) as connection:
        connection.execute(
            """insert into inventory_rows(period,source_row,material,plant,unrestricted_quantity,fiscal_total_amount)
               values ('2026-09',1,'MAT-1',?,10,100.0)""",
            [plant],
        )


def rule(settings, group: str, key: str):
    with connect(settings.path("database")) as connection:
        ensure_mapping_schema(connection)
        return connection.execute(
            "select value_1, value_2, changed_by from mapping_rules where group_key=? and key_value=?", [group, key]).fetchone()


def location(settings, plant: str = "2115"):
    with connect(settings.path("database")) as connection:
        return connection.execute("select location_group from inventory_rows where plant=?", [plant]).fetchone()[0]


def mapping_id(settings, group: str, key: str) -> int:
    with connect(settings.path("database")) as connection:
        return int(connection.execute(
            "select mapping_id from mapping_rules where group_key=? and key_value=?", [group, key]).fetchone()[0])


def test_rule_created_on_one_machine_appears_and_applies_on_the_other(tmp_path: Path, drive: Path) -> None:
    a, admin_a = machine(tmp_path, "PC-ADMIN-A", [(ADMIN_A, "admin")])
    b, admin_b = machine(tmp_path, "PC-ADMIN-B", [(ADMIN_B, "admin")])
    seed_period(b)
    csrf_a = login(admin_a, a, ADMIN_A)
    login(admin_b, b, ADMIN_B)

    response = admin_a.post("/api/mappings/location", json={"key_value": "2115", "value_1": None, "value_2": "4_NDIS - LOJAS"},
                            headers={"X-CSRF-Token": csrf_a})
    assert response.status_code == 200, response.text
    assert rule(a, "location", "2115")[2] == ADMIN_A  # quem alterou fica registrado
    admin_a.app.state.mapping_sync_once()  # a alteração já dispara a publicação; aqui garante a conclusão
    published = json.loads((drive / "mapping" / "alteracoes" / "PC-ADMIN-A.json").read_text(encoding="utf-8"))
    assert published["rules"]["location|2115"]["value_2"] == "4_NDIS - LOJAS"
    assert published["rules"]["location|2115"]["changed_by"] == ADMIN_A

    # B ainda não tinha a regra: recebe, mostra na página Mapping e recalcula a base local.
    assert rule(b, "location", "2115") is None and location(b) is None
    received = admin_b.app.state.mapping_sync_once()
    assert "location|2115" in received["changed"] and received["recalculated_periods"] == ["2026-09"]
    assert rule(b, "location", "2115")[1] == "4_NDIS - LOJAS"
    assert location(b) == "4_NDIS - LOJAS"
    rows = admin_b.get("/api/mappings/location").json()["rows"]
    assert any(item["key_value"] == "2115" and item["value_2"] == "4_NDIS - LOJAS" for item in rows)
    assert admin_b.get("/api/mapping-sync/status").json()["last_received_at"]

    # Nada mudou: nova sincronização não recalcula de novo.
    assert admin_b.app.state.mapping_sync_once()["changed"] == []


def test_update_rename_and_delete_reach_the_other_machine(tmp_path: Path, drive: Path) -> None:
    a, admin_a = machine(tmp_path, "PC-ADMIN-A", [(ADMIN_A, "admin")])
    b, admin_b = machine(tmp_path, "PC-ADMIN-B", [(ADMIN_B, "admin")])
    seed_period(b)
    csrf_a = login(admin_a, a, ADMIN_A)
    csrf_b = login(admin_b, b, ADMIN_B)
    admin_a.post("/api/mappings/location", json={"key_value": "2115", "value_2": "4_NDIS - LOJAS"}, headers={"X-CSRF-Token": csrf_a})
    admin_a.app.state.mapping_sync_once()
    admin_b.app.state.mapping_sync_once()
    admin_b.app.state.mapping_sync_once()  # B publica a própria visão (com a 2115 antiga)

    # Alteração em A vence a visão antiga publicada por B.
    rid = mapping_id(a, "location", "2115")
    admin_a.put(f"/api/mappings/location/{rid}", json={"key_value": "2115", "value_2": "5_NVS - LOJAS"}, headers={"X-CSRF-Token": csrf_a})
    admin_a.app.state.mapping_sync_once()
    admin_b.app.state.mapping_sync_once()
    assert rule(b, "location", "2115")[1] == "5_NVS - LOJAS" and location(b) == "5_NVS - LOJAS"

    # Exclusão em B chega em A e não é desfeita pela visão antiga de A.
    rid_b = mapping_id(b, "location", "2115")
    assert admin_b.delete(f"/api/mappings/location/{rid_b}", headers={"X-CSRF-Token": csrf_b}).status_code == 200
    admin_b.app.state.mapping_sync_once()
    admin_a.app.state.mapping_sync_once()
    assert rule(a, "location", "2115") is None
    admin_a.app.state.mapping_sync_once()
    admin_b.app.state.mapping_sync_once()
    assert rule(b, "location", "2115") is None and location(b) is None

    # Chave renomeada: a antiga sai e a nova entra nas duas máquinas.
    admin_a.post("/api/mappings/location", json={"key_value": "2116", "value_2": "4_NDIS - LOJAS"}, headers={"X-CSRF-Token": csrf_a})
    rid = mapping_id(a, "location", "2116")
    admin_a.put(f"/api/mappings/location/{rid}", json={"key_value": "2117", "value_2": "4_NDIS - LOJAS"}, headers={"X-CSRF-Token": csrf_a})
    admin_a.app.state.mapping_sync_once()
    admin_b.app.state.mapping_sync_once()
    assert rule(b, "location", "2116") is None and rule(b, "location", "2117")[1] == "4_NDIS - LOJAS"
    merged, machines = read_merged(drive)
    assert merged["location|2116"]["deleted"] is True and {item["machine"] for item in machines} == {"PC-ADMIN-A", "PC-ADMIN-B"}


def test_rule_from_older_version_is_adopted_but_never_beats_an_explicit_change(tmp_path: Path, drive: Path) -> None:
    b, admin_b = machine(tmp_path, "PC-ADMIN-B", [(ADMIN_B, "admin")])
    seed_period(b)
    login(admin_b, b, ADMIN_B)
    # Máquina com versão anterior: regra só com data de criação (linha de base), sem registro de alteração.
    folder = drive / "mapping" / "alteracoes"
    folder.mkdir(parents=True)
    baseline = {"group": "location", "key": "2115", "value_1": None, "value_2": "4_NDIS - LOJAS", "deleted": False,
                "changed_at": None, "changed_by": None, "baseline_at": "2026-10-08T18:43:00.000000Z"}
    seed_value = local_view(b)["location|1081"]
    stale_seed = {**seed_value, "value_2": "VALOR ANTIGO", "baseline_at": "2020-01-01T00:00:00.000000Z", "changed_at": None}
    (folder / "PC-ANTIGO.json").write_text(json.dumps({"format": 1, "machine": "PC-ANTIGO", "rules": {
        "location|2115": baseline, "location|1081": stale_seed}}), encoding="utf-8")
    result = admin_b.app.state.mapping_sync_once()
    assert result["changed"] == ["location|2115"]  # regra nova adotada; linha de base mais antiga não sobrescreve
    assert location(b) == "4_NDIS - LOJAS" and rule(b, "location", "1081")[1] == "2_CD - EXTREMA"
