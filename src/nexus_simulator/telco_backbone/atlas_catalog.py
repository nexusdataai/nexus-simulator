"""Load atlas_catalog.json (system slugs, vendors, default vendor per layer)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AtlasCatalog:
    version: int
    vendors: dict[str, str]
    vendor_defaults: dict[str, str]
    systems: list[dict[str, Any]]

    def systems_for_layer(self, layer: str) -> dict[str, dict[str, Any]]:
        lu = layer.upper()
        out: dict[str, dict[str, Any]] = {}
        for row in self.systems:
            if (row.get("layer") or "").upper() != lu:
                continue
            key = str(row.get("system_key") or "")
            if key:
                out[key] = dict(row)
        return out


def _path_under_src() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "telco" / "atlas_catalog.json"


@lru_cache(maxsize=1)
def load_atlas_catalog() -> AtlasCatalog:
    raw: str | None = None
    try:
        pkg = resources.files("nexus_simulator.data.telco")
        ref = pkg / "atlas_catalog.json"
        if ref.is_file():
            raw = ref.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        pass
    if raw is None:
        p = _path_under_src()
        if not p.is_file():
            raise FileNotFoundError("atlas_catalog.json missing under nexus_simulator/data/telco/")
        raw = p.read_text(encoding="utf-8")
    data = json.loads(raw)
    return AtlasCatalog(
        version=int(data.get("version") or 1),
        vendors=dict(data.get("vendors") or {}),
        vendor_defaults=dict(data.get("vendor_defaults") or {}),
        systems=list(data.get("systems") or []),
    )


def default_vendor_for_layer(layer: str) -> str:
    """Return vendor code (e.g. H) for bss|nss|oss."""
    cat = load_atlas_catalog()
    k = layer.lower()
    return str(cat.vendor_defaults.get(k) or "H")
