from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RuntimeSettings:
    root: Path
    raw: dict[str, Any]

    @property
    def project(self) -> dict[str, Any]:
        return self.raw["project"]

    def path(self, key: str) -> Path:
        value = Path(os.path.expandvars(self.project[key]))
        return value if value.is_absolute() else self.root / value


def load_runtime_settings(config_path: str | Path | None = None) -> RuntimeSettings:
    requested = Path(config_path or os.getenv("OPS_CONFIG", "config/production.yaml"))
    if not requested.is_absolute():
        requested = Path.cwd() / requested
    requested = requested.resolve()
    raw = yaml.safe_load(requested.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "project" not in raw or "sources" not in raw:
        raise ValueError(f"Configuração inválida: {requested}")
    return RuntimeSettings(root=requested.parent.parent, raw=raw)
