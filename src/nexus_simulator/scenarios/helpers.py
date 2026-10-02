"""Shared helpers for scenario builders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def field(row: dict[str, Any] | None, *names: str, default: Any = None) -> Any:
    if not row:
        return default
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return default


def num(row: dict[str, Any] | None, *names: str, default: float = 0.0) -> float:
    raw = field(row, *names, default=default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def iso_days(offset_days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=offset_days)).date().isoformat()


def tag_row(row: dict[str, Any], scenario_id: str, run_id: str, step: int) -> dict[str, Any]:
    out = dict(row)
    out["_scenario_id"] = scenario_id
    out["_scenario_run_id"] = run_id
    out["_scenario_step"] = step
    return out


def match_any(row: dict[str, Any], field_names: tuple[str, ...], values: set[str]) -> bool:
    raw = field(row, *field_names)
    if raw is None:
        return False
    return str(raw) in values


def pick_rows(rows: list[dict[str, Any]], limit: int, predicate=None) -> list[dict[str, Any]]:
    chosen = [r for r in rows if predicate(r)] if predicate else list(rows)
    return chosen[:limit]


def next_ids(prefix: str, count: int) -> list[str]:
    return [f"{prefix}{i + 1:04d}" for i in range(count)]


PLUGIN_LABELS = {
    "sfdc": "Salesforce",
    "oracle": "Oracle ERP",
    "sap": "SAP S/4HANA",
    "external": "External sources",
    "tpm": "TPM CPQ",
    "sourcing": "Sourcing CPQ",
}


def row_pk(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    for key, value in row.items():
        if key.startswith("_"):
            continue
        if (key.endswith("_ID") or key in ("Id", "ID")) and value not in (None, ""):
            return str(value)
    return None


def summarize_bindings(bindings: dict[str, Any] | None, limit: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, value in (bindings or {}).items():
        if isinstance(value, list):
            out.append({"name": name, "count": len(value), "sample": value[:limit]})
        elif value not in (None, ""):
            out.append({"name": name, "count": 1, "sample": [value]})
    return out
