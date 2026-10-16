"""Agente de conferência: layout flexível da planilha manual (só as colunas usadas, em qualquer ordem e aba)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from openpyxl import Workbook

from ops_contabil.conference import read_position_file
from test_optimus_import import env  # noqa: F401 - fixture reaproveitada


def workbook(path: Path, header: list[str], rows: list[list[object]], sheet: str = "Minha aba") -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(["Posição de Estoque - conferência"])  # título antes do cabeçalho
    ws.append(header)
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


def test_minimal_columns_in_any_order_and_sheet(env, tmp_path) -> None:  # noqa: F811
    settings, *_ = env
    file = workbook(tmp_path / "manual.xlsx", ["Year", "Vlr Tot Fisc", "Material", "Centro", "Season", "Empresa"], [
        [2026, 100.5, "AAA111-001-M", "1081", "FA", "7170"],
        ["<2022", 20.0, "BBB222-002-L", "2115", "SP", "7170"],
        [2025, 999.0, "CCC333-003-S", "1081", "HO", "8000"],  # outra empresa: fica fora
    ])
    progress: list[int] = []
    table, info = read_position_file(settings, file, lambda p, _m: progress.append(p), 2)
    rows = table.to_pylist()
    assert info["sheet"] == "Minha aba" and info["discarded_company_rows"] == 1
    assert [(r["k"], r["year"], r["season"], r["value"]) for r in rows] == [
        ("1081AAA111-001-M", 2026, "FA", 100.5), ("2115BBB222-002-L", 0, "SP", 20.0)]  # "<2022" vira 0
    assert rows[0]["pod"] is None  # Product Offer End Dt é opcional quando há Season/Year


def test_missing_required_columns_explain_the_layout(env, tmp_path) -> None:  # noqa: F811
    settings, *_ = env
    no_value = workbook(tmp_path / "sem_valor.xlsx", ["Material", "Centro", "Year"], [["AAA111-001-M", "1081", 2026]])
    with pytest.raises(ValueError, match="Vlr Tot Fisc"):
        read_position_file(settings, no_value)
    no_fields = workbook(tmp_path / "sem_campos.xlsx", ["Material", "Centro", "Vlr Tot Fisc"], [["AAA111-001-M", "1081", 1.0]])
    with pytest.raises(ValueError, match="Product Offer End Dt, Season e Year"):
        read_position_file(settings, no_fields)
    with_date = workbook(tmp_path / "data.xlsx", ["CE & MAT", "Material", "Vlr Tot Fisc", "Product Offer End Dt"],
                         [["1081AAA111-001-M", "AAA111-001-M", 5.0, date(2026, 9, 3)]])
    table, _info = read_position_file(settings, with_date)
    assert table.to_pylist()[0]["pod"] == date(2026, 9, 3)
