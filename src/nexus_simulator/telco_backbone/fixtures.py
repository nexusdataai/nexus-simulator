"""Load sample_fixtures.json (from Telco-Data/samples.js)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FixtureBundle:
    version: int
    source: str
    systems: dict[str, dict[str, Any]]
    counts: dict[str, int]

    def systems_for_layer(self, layer: str) -> dict[str, dict[str, Any]]:
        return {
            k: v
            for k, v in self.systems.items()
            if (v.get("layer") or "").upper() == layer.upper()
        }


def _path_under_src() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "telco" / "sample_fixtures.json"


@lru_cache(maxsize=1)
def load_sample_fixtures() -> FixtureBundle:
    """Load bundled JSON. Fallback to sibling path for tests with PYTHONPATH=src."""
    raw: str | None = None
    try:
        pkg = resources.files("nexus_simulator.data.telco")
        ref = pkg / "sample_fixtures.json"
        if ref.is_file():
            raw = ref.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        pass
    if raw is None:
        p = _path_under_src()
        if not p.is_file():
            raise FileNotFoundError(
                "sample_fixtures.json missing. Run: node scripts/export_telco_samples_fixtures.js "
                "> src/nexus_simulator/data/telco/sample_fixtures.json"
            )
        raw = p.read_text(encoding="utf-8")
    data = json.loads(raw)
    return FixtureBundle(
        version=int(data.get("version") or 1),
        source=str(data.get("source") or ""),
        systems=dict(data.get("systems") or {}),
        counts=dict(data.get("counts") or {}),
    )
