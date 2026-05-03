"""End-to-end plugin-seed YAML runner.

Loads a plugin-seed YAML, dispatches it to the configured plugin via the
in-process API, and returns a structured ``SeedRunResult``. Full per-plugin
functionality activates per phase (5 for WXCC, 6 for SFDC, 7 for Oracle ERP +
SAP, 8 for External Source). Until each phase lands the runner performs
shape validation so seed YAMLs can be authored and reviewed today.

Expected YAML shape (subset)::

    name: "wxcc-smoke"            # required
    plugin: "wxcc"                # required: wxcc | sfdc | oracle_erp | sap | external_source
    config:                       # optional plugin-specific overrides
      num_tasks: 10
      include_recordings: true
      days_back: 7
    actions:                      # required, non-empty
      - { kind: load }
      - { kind: seed }
      - { kind: verify }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

KNOWN_PLUGINS = {"wxcc", "sfdc", "oracle_erp", "sap", "external_source"}


@dataclass
class SeedRunResult:
    """Outcome of running a plugin-seed YAML end-to-end."""

    ok: bool
    status: str
    name: str | None = None
    plugin: str | None = None
    actions: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        header = f"Seed run: status={self.status} ok={self.ok}"
        parts = [header]
        if self.name:
            parts.append(f"  name   = {self.name}")
        if self.plugin:
            parts.append(f"  plugin = {self.plugin}")
        if self.actions:
            parts.append(f"  actions = {len(self.actions)}")
        if self.errors:
            parts.append("  errors:")
            parts.extend(f"    - {err}" for err in self.errors)
        if self.metrics:
            parts.append("  metrics:")
            parts.extend(f"    {k} = {v}" for k, v in self.metrics.items())
        return "\n".join(parts)


class SeedYAMLRunner:
    """Run a plugin-seed YAML against an in-process harness.

    Phase-2 behavior: validate that the YAML parses, names a known plugin,
    and carries a non-empty ``actions`` list. Returns ``SeedRunResult`` with
    ``status='validated'``. Per-phase behavior (full run) lands when each
    plugin's owning phase activates.
    """

    def __init__(self, app: Any | None = None) -> None:
        self._app = app

    def run(self, yaml_path: str | Path) -> SeedRunResult:
        path = Path(yaml_path)
        if not path.exists():
            return SeedRunResult(
                ok=False, status="missing", errors=[f"File not found: {path}"]
            )

        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            return SeedRunResult(ok=False, status="invalid_yaml", errors=[str(exc)])

        if not isinstance(payload, dict):
            return SeedRunResult(
                ok=False,
                status="invalid_shape",
                errors=["Top-level YAML document must be a mapping."],
            )

        name = payload.get("name")
        plugin = payload.get("plugin")
        actions = payload.get("actions")

        missing: list[str] = []
        if not name:
            missing.append("name")
        if not plugin:
            missing.append("plugin")
        elif plugin not in KNOWN_PLUGINS:
            missing.append(f"plugin (got '{plugin}', expected one of {sorted(KNOWN_PLUGINS)})")
        if not isinstance(actions, list) or not actions:
            missing.append("actions (non-empty list)")

        if missing:
            return SeedRunResult(
                ok=False,
                status="invalid_shape",
                name=name if isinstance(name, str) else None,
                plugin=plugin if isinstance(plugin, str) else None,
                errors=[f"Missing or malformed fields: {', '.join(missing)}"],
            )

        if self._app is None:
            return SeedRunResult(
                ok=True,
                status="validated",
                name=name,
                plugin=plugin,
                actions=actions,
                metrics={"actions": len(actions)},
            )

        return SeedRunResult(
            ok=False,
            status=f"pending_phase_{_phase_for_plugin(plugin)}",
            name=name,
            plugin=plugin,
            actions=actions,
            errors=[
                f"Full end-to-end seed runner for plugin '{plugin}' activates in "
                f"phase {_phase_for_plugin(plugin)}. YAML validated successfully."
            ],
            metrics={"actions": len(actions)},
        )


def _phase_for_plugin(plugin: str | None) -> int:
    """Map a plugin name to the master-plan phase that activates its runner."""
    return {
        "wxcc": 5,
        "sfdc": 6,
        "oracle_erp": 7,
        "sap": 7,
        "external_source": 8,
    }.get(plugin or "", 0)
