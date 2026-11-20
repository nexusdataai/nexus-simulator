"""Aggregate billing feeds and simulator table metrics across BSS / NSS / OSS."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

_TELCO_SERVICES = ("bss", "nss", "oss")


@lru_cache(maxsize=1)
def load_billing_feeds() -> list[dict[str, Any]]:
    raw: str | None = None
    try:
        pkg = resources.files("nexus_simulator.data.telco")
        ref = pkg / "billing_feeds.json"
        if ref.is_file():
            raw = ref.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        pass
    if raw is None:
        p = Path(__file__).resolve().parents[1] / "data" / "telco" / "billing_feeds.json"
        raw = p.read_text(encoding="utf-8")
    data = json.loads(raw)
    return list(data.get("feeds") or [])


def _sk(row: dict[str, Any]) -> str:
    return str(row.get("system_key") or "")


def _feed_keys(feed: dict[str, Any]) -> set[str]:
    return {str(k) for k in (feed.get("atlas_system_keys") or [])}


async def build_billing_overview(simulator: Any, *, layer: str | None = None) -> dict[str, Any]:
    """Attach row counts and link simulator tables to inbound billing feeds."""
    feeds = load_billing_feeds()
    lu = (layer or "").strip().upper()
    if lu and lu in {"BSS", "OSS", "NSS"}:
        feeds = [f for f in feeds if str(f.get("layer") or "").upper() == lu]

    tables: list[dict[str, Any]] = []
    by_service: dict[str, list[dict[str, Any]]] = {}

    for name in _TELCO_SERVICES:
        svc = simulator.registry.get(name) if hasattr(simulator, "registry") else getattr(simulator, name, None)
        if svc is None:
            continue
        if not hasattr(svc, "get_object_list"):
            continue
        try:
            objs = await svc.get_object_list()
        except Exception:
            objs = []
        billing_rows = [
            o
            for o in objs
            if isinstance(o, dict) and "billing" in (o.get("applications") or [])
        ]
        by_service[name] = billing_rows
        for o in billing_rows:
            tables.append({"service": name, **o})

    layer_rows = {"BSS": 0, "OSS": 0, "NSS": 0}
    layer_tables = {"BSS": 0, "OSS": 0, "NSS": 0}
    svc_layer = {"bss": "BSS", "nss": "NSS", "oss": "OSS"}

    for name, rows in by_service.items():
        ly = svc_layer.get(name, "BSS")
        layer_tables[ly] += len(rows)
        layer_rows[ly] += sum(int(r.get("rowCount") or r.get("rows") or 0) for r in rows)

    enriched: list[dict[str, Any]] = []
    for feed in feeds:
        keys = _feed_keys(feed)
        linked: list[dict[str, Any]] = []
        for name, rows in by_service.items():
            for r in rows:
                if keys and _sk(r) in keys:
                    linked.append(
                        {
                            "service": name,
                            "schema": r.get("schemaName"),
                            "table": r.get("tableName"),
                            "rows": r.get("rowCount") or 0,
                            "billing_target": r.get("billing_target"),
                        }
                    )
        feed_out = dict(feed)
        feed_out["linked_tables"] = linked
        feed_out["simulated_rows"] = sum(int(x.get("rows") or 0) for x in linked)
        feed_out["table_count"] = len(linked)
        enriched.append(feed_out)

    return {
        "feeds": enriched,
        "tables": tables,
        "totals": {
            "feeds": len(enriched),
            "tables": len(tables),
            "rows": sum(int(t.get("rowCount") or 0) for t in tables),
            "by_layer": {"tables": layer_tables, "rows": layer_rows},
        },
    }