from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml

from .excel import normalize_column


class SchemaResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class ColumnContract:
    canonical: str
    required: bool
    data_type: str
    aliases: tuple[str, ...]

    @property
    def normalized_aliases(self) -> set[str]:
        return {normalize_column(alias, 0) for alias in (*self.aliases, self.canonical)}


@dataclass(frozen=True)
class SchemaContract:
    name: str
    sheet_aliases: tuple[str, ...]
    header_search_rows: int
    columns: tuple[ColumnContract, ...]


@dataclass
class Resolution:
    header_row: int
    positions: dict[str, int]
    source_headers: dict[str, str]
    optional_missing: list[str] = field(default_factory=list)
    suggestions: dict[str, list[tuple[str, float]]] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.source_headers, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_contracts(path: Path) -> dict[str, SchemaContract]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["schemas"]
    contracts = {}
    for name, spec in raw.items():
        columns = tuple(
            ColumnContract(
                canonical=canonical,
                required=bool(definition.get("required", False)),
                data_type=str(definition.get("type", "text")),
                aliases=tuple(definition.get("aliases", [])),
            )
            for canonical, definition in spec["columns"].items()
        )
        contracts[name] = SchemaContract(
            name=name,
            sheet_aliases=tuple(spec.get("sheet_aliases", [])),
            header_search_rows=int(spec.get("header_search_rows", 30)),
            columns=columns,
        )
    return contracts


def _resolve_one_row(headers: list[Any], contract: SchemaContract) -> tuple[dict[str, int], dict[str, str]]:
    normalized_to_positions: dict[str, list[int]] = {}
    source_headers: dict[str, str] = {}
    for position, header in enumerate(headers):
        if header is None or not str(header).strip():
            continue
        normalized = normalize_column(header, position + 1)
        normalized_to_positions.setdefault(normalized, []).append(position)
        source_headers[str(position)] = str(header).strip()

    positions: dict[str, int] = {}
    for column in contract.columns:
        matches = {
            position
            for alias in column.normalized_aliases
            for position in normalized_to_positions.get(alias, [])
        }
        if len(matches) > 1:
            raise SchemaResolutionError(
                f"Cabeçalho ambíguo para {column.canonical}: posições {sorted(matches)}"
            )
        if len(matches) == 1:
            positions[column.canonical] = matches.pop()
    return positions, source_headers


def resolve_headers(rows: list[list[Any]], contract: SchemaContract) -> Resolution:
    candidates = []
    for row_number, row in enumerate(rows[: contract.header_search_rows], start=1):
        try:
            positions, source_headers = _resolve_one_row(row, contract)
        except SchemaResolutionError:
            continue
        required_matches = sum(
            1 for column in contract.columns if column.required and column.canonical in positions
        )
        total_matches = len(positions)
        candidates.append((required_matches, total_matches, row_number, positions, source_headers, row))
    if not candidates:
        raise SchemaResolutionError("Nenhuma linha candidata a cabeçalho foi encontrada.")

    best = max(candidates, key=lambda item: (item[0], item[1], -item[2]))
    _, _, row_number, positions, source_headers, header_values = best
    required_missing = [
        column.canonical
        for column in contract.columns
        if column.required and column.canonical not in positions
    ]
    optional_missing = [
        column.canonical
        for column in contract.columns
        if not column.required and column.canonical not in positions
    ]
    suggestions: dict[str, list[tuple[str, float]]] = {}
    normalized_headers = [
        (str(value), normalize_column(value, index + 1))
        for index, value in enumerate(header_values)
        if value is not None and str(value).strip()
    ]
    for canonical in required_missing + optional_missing:
        column = next(item for item in contract.columns if item.canonical == canonical)
        scored = []
        for source, normalized in normalized_headers:
            score = max(
                SequenceMatcher(None, alias, normalized).ratio()
                for alias in column.normalized_aliases
            )
            if score >= 0.72:
                scored.append((source, round(score, 3)))
        if scored:
            suggestions[canonical] = sorted(scored, key=lambda item: item[1], reverse=True)[:3]

    if required_missing:
        raise SchemaResolutionError(
            "Colunas obrigatórias ausentes: "
            + ", ".join(required_missing)
            + (f". Sugestões: {suggestions}" if suggestions else "")
        )
    return Resolution(
        header_row=row_number,
        positions=positions,
        source_headers=source_headers,
        optional_missing=optional_missing,
        suggestions=suggestions,
    )
