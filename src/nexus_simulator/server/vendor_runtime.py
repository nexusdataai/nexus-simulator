"""Shared CRUD helpers for official-style vendor API routers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from .vendor_catalog import pick_pk_column


def registry(request: Request):
    sim = getattr(request.app.state, "simulator", None)
    if sim is None:
        raise HTTPException(status_code=503, detail="simulator not initialised")
    return sim.registry


def require_table(svc: Any, table: str) -> None:
    names = {t.table_name for t in (getattr(svc, "_tables", None) or [])}
    if names and table not in names:
        raise HTTPException(status_code=404, detail=f"object not found: {table}")


async def get_service(request: Request, name: str):
    svc = registry(request).get(name)
    if svc is None:
        raise HTTPException(status_code=503, detail=f"{name} simulator not initialised")
    if hasattr(svc, "ensure_loaded"):
        await svc.ensure_loaded()
    return svc


def schema_for(svc: Any, fallback: str) -> str:
    schema = (svc.get_status() or {}).get("schema") if hasattr(svc, "get_status") else ""
    if schema:
        return schema
    tables = getattr(svc, "_tables", None) or []
    if tables:
        return tables[0].schema_name
    return fallback


async def load_rows(svc: Any, schema: str, table: str) -> list[dict[str, Any]]:
    rows = await svc._get_table_data(schema, table)
    return list(rows or [])


def resolve_pk(table: str, rows: list[dict[str, Any]], hinted: str | None = None) -> str:
    return pick_pk_column(table, rows[0] if rows else None, hinted)


def find_index(rows: list[dict[str, Any]], pk: str, value: str) -> int:
    for i, row in enumerate(rows):
        if str(row.get(pk, "")) == str(value):
            return i
    raise HTTPException(status_code=404, detail=f"{pk}={value} not found")


async def get_row(svc: Any, schema: str, table: str, value: str, hinted_pk: str | None = None) -> dict[str, Any]:
    rows = await load_rows(svc, schema, table)
    if not rows:
        raise HTTPException(status_code=404, detail=f"{table} is empty")
    pk = resolve_pk(table, rows, hinted_pk)
    return rows[find_index(rows, pk, value)]


async def create_row(svc: Any, schema: str, table: str, body: dict[str, Any]) -> dict[str, Any]:
    row = dict(body or {})
    await svc.append_rows(schema, table, [row])
    return row


async def patch_row(
    svc: Any, schema: str, table: str, value: str, patch: dict[str, Any], hinted_pk: str | None = None
) -> dict[str, Any]:
    rows = await load_rows(svc, schema, table)
    if not rows:
        raise HTTPException(status_code=404, detail=f"{table} is empty")
    pk = resolve_pk(table, rows, hinted_pk)
    idx = find_index(rows, pk, value)
    rows[idx] = {**rows[idx], **(patch or {})}
    await svc.write_table(schema, table, rows)
    return rows[idx]


async def delete_row(svc: Any, schema: str, table: str, value: str, hinted_pk: str | None = None) -> dict[str, Any]:
    rows = await load_rows(svc, schema, table)
    if not rows:
        raise HTTPException(status_code=404, detail=f"{table} is empty")
    pk = resolve_pk(table, rows, hinted_pk)
    idx = find_index(rows, pk, value)
    removed = rows.pop(idx)
    await svc.write_table(schema, table, rows)
    return removed
