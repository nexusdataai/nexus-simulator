"""In-process connector helpers for simulator-backed write APIs."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from loguru import logger

connector_logger = logger.bind(component="connector-runtime")

_simulator = None

_KEY_ALIASES = {
    "simulator": "sfdc",
    "sfdc": "sfdc",
    "oracle": "oracle",
    "oracle_erp": "oracle",
    "sap": "sap",
    "external": "external",
    "external_source": "external",
    "tpm": "tpm",
    "sourcing": "sourcing",
}


def configure_runtime(simulator) -> None:
    global _simulator
    _simulator = simulator


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_sim(key: str):
    if _simulator is None:
        raise HTTPException(status_code=503, detail="simulator not initialised")
    name = _KEY_ALIASES.get(key, key)
    sim = _simulator.registry.get(name)
    if sim is None:
        raise HTTPException(status_code=503, detail=f"simulator '{key}' not initialised")
    if hasattr(sim, "ensure_loaded"):
        try:
            await sim.ensure_loaded()
            if not getattr(sim, "loaded", False) and hasattr(sim, "seed_data"):
                await sim.seed_data()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"simulator load failed: {exc}") from exc
    return sim


async def fetch_rows(sim: Any, schema: str, table: str) -> List[Dict[str, Any]]:
    rows = await sim._get_table_data(schema, table)
    return list(rows or [])


async def replace_rows(sim: Any, schema: str, table: str, rows: List[Dict[str, Any]]) -> int:
    return await sim.write_table(schema, table, rows)


async def append_row(sim: Any, schema: str, table: str, row: Dict[str, Any]) -> None:
    await sim.append_rows(schema, table, [row])


async def update_one(
    sim: Any,
    schema: str,
    table: str,
    pk_col: str,
    pk_value: str,
    patch: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    rows = await fetch_rows(sim, schema, table)
    target_idx = -1
    for i, row in enumerate(rows):
        if str(row.get(pk_col, "")) == str(pk_value):
            target_idx = i
            break
    if target_idx < 0:
        raise HTTPException(status_code=404, detail=f"{table} not found: {pk_col}={pk_value}")
    previous = dict(rows[target_idx])
    new_row = {**previous, **patch}
    rows[target_idx] = new_row
    await replace_rows(sim, schema, table, rows)
    return previous, new_row


async def emit_audit(
    actor: str,
    verb: str,
    target: str,
    payload: Optional[Dict[str, Any]] = None,
    api_id: Optional[str] = None,
) -> str:
    event_id = str(uuid.uuid4())
    row = {
        "event_id": event_id,
        "actor": actor,
        "verb": verb,
        "target": target,
        "payload": payload or {},
        "api_id": api_id,
        "event_ts": _now_iso(),
    }
    try:
        ext = await get_sim("external")
        await append_row(ext, "external_sources", "Audit_Event", row)
    except Exception as exc:
        connector_logger.debug("audit write skipped: {}", exc)
    return event_id


async def emit_alert(
    prefix: str,
    severity: str,
    title: str,
    message: str,
    entity_id: Optional[str] = None,
) -> str:
    alert_id = f"ALERT-{prefix}-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    row = {
        "alert_id": alert_id,
        "severity": severity,
        "title": title,
        "message": message,
        "entity_id": entity_id,
        "created_at": _now_iso(),
    }
    ext = await get_sim("external")
    await append_row(ext, "external_sources", f"{prefix}_Alert", row)
    return alert_id
