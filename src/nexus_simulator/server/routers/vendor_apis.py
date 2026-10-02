"""Vendor API catalog and batch runner for the simulator UI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from urllib.parse import unquote

import httpx
from fastapi import APIRouter, Body, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..vendor_catalog import build_system_catalog
from ..vendor_runtime import get_service, load_rows, resolve_pk

router = APIRouter(prefix="/api/v1/vendor-apis", tags=["Vendor APIs"])

_SYSTEMS = ("sfdc", "oracle", "sap")


class BatchOperation(BaseModel):
    method: str
    path: str
    body: dict[str, Any] | None = None


class BatchRequest(BaseModel):
    system: Optional[Literal["sfdc", "oracle", "sap"]] = None
    mode: Literal["operations", "canary_writes"] = "operations"
    operations: list[BatchOperation] = Field(default_factory=list)
    limit: int = Field(default=50, ge=1, le=500)


def _app_simulator(request: Request):
    sim = getattr(request.app.state, "simulator", None)
    if sim is None:
        raise HTTPException(status_code=503, detail="simulator not initialised")
    return sim


@router.get("")
async def list_vendor_apis(request: Request, system: Optional[str] = Query(None)):
    sim = _app_simulator(request)
    names = [system] if system in _SYSTEMS else list(_SYSTEMS)
    items: list[dict[str, Any]] = []
    for name in names:
        svc = sim.registry.get(name)
        if svc is None:
            continue
        items.extend(await build_system_catalog(svc, name))
    return {"total": len(items), "items": items}


async def _canary_ops(request: Request, system: str | None, limit: int) -> list[BatchOperation]:
    listing = await list_vendor_apis(request, system=system)
    ops: list[BatchOperation] = []
    marker = datetime.now(timezone.utc).isoformat()
    for item in listing["items"]:
        if not item.get("rowCount"):
            continue
        if len(ops) >= limit:
            break
        svc = await get_service(request, item["system"])
        rows = await load_rows(svc, item["schema"], item["table"])
        if not rows:
            continue
        pk = resolve_pk(item["table"], rows, item.get("pk"))
        record_id = rows[0].get(pk)
        if record_id is None:
            continue
        update = next((m for m in item["methods"] if m["kind"] == "update"), None)
        if not update:
            continue
        path = update["path"].replace("{id}", str(record_id))
        ops.append(BatchOperation(method="PATCH", path=path, body={"_batch_marker": marker}))
    return ops


@router.post("/batch")
async def run_batch(request: Request, body: BatchRequest = Body(default_factory=BatchRequest)):
    operations = body.operations
    if body.mode == "canary_writes":
        operations = await _canary_ops(request, body.system, body.limit)
    results = []
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://simulator") as client:
        for op in operations:
            path = unquote(op.path)
            try:
                resp = await client.request(
                    op.method.upper(),
                    path,
                    json=op.body if op.body is not None and op.method.upper() not in ("GET", "HEAD", "DELETE") else None,
                    timeout=30.0,
                )
                try:
                    payload = resp.json()
                except Exception:
                    payload = resp.text
                results.append({
                    "method": op.method.upper(),
                    "path": path,
                    "status": resp.status_code,
                    "ok": 200 <= resp.status_code < 300,
                    "response": payload,
                })
            except Exception as exc:
                results.append({
                    "method": op.method.upper(),
                    "path": path,
                    "status": 0,
                    "ok": False,
                    "response": str(exc),
                })
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r["ok"]),
        "failed": sum(1 for r in results if not r["ok"]),
        "results": results,
    }


@router.get("/{api_id}/sample")
async def sample_row(api_id: str, request: Request):
    spec = await get_vendor_api(api_id, request)
    svc = await get_service(request, spec["system"])
    rows = await load_rows(svc, spec["schema"], spec["table"])
    return {"api_id": api_id, "pk": spec.get("pk"), "row": rows[0] if rows else None, "rowCount": len(rows)}


@router.get("/{api_id}")
async def get_vendor_api(api_id: str, request: Request):
    listing = await list_vendor_apis(request, system=None)
    for item in listing["items"]:
        if item["id"] == api_id:
            return item
    raise HTTPException(status_code=404, detail=f"vendor API not found: {api_id}")
