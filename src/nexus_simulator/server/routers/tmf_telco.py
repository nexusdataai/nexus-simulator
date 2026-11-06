"""TMF Open API read paths backed by BSS / NSS / OSS backbone caches."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/tmf-api", tags=["TMF Telco"])


async def _merged_tmf_index(sim: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for name in ("bss", "nss", "oss"):
        svc = getattr(sim, name, None) or sim.registry.get(name)
        if svc is None or not hasattr(svc, "get_tmf_index"):
            continue
        idx = await svc.get_tmf_index()
        if isinstance(idx, dict):
            for k, v in idx.items():
                merged.setdefault(k, v)
    # Optional legacy telco_sources
    ts = getattr(sim, "telco_sources", None) or sim.registry.get("telco_sources")
    if ts is not None and hasattr(ts, "get_tmf_index"):
        idx = await ts.get_tmf_index()
        if isinstance(idx, dict):
            for k, v in idx.items():
                merged.setdefault(k, v)
    return merged


@router.api_route("/{full_path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def tmf_proxy(request: Request, full_path: str):
    sim = getattr(request.app.state, "simulator", None)
    if sim is None:
        raise HTTPException(status_code=503, detail="simulator not initialised")

    index = await _merged_tmf_index(sim)
    if not index:
        raise HTTPException(status_code=503, detail="no TMF backbone data — seed BSS/NSS/OSS first")

    path = f"/tmf-api/{full_path}"
    if request.url.query:
        path = f"{path}?{request.url.query}"
    base_path = f"/tmf-api/{full_path.split('?')[0]}"
    entry = index.get(path) or index.get(base_path)
    if not entry and request.method == "GET":
        for k, v in index.items():
            if k.rstrip("/").endswith(full_path.rstrip("/").split("/")[-1]):
                entry = v
                break
    if not entry:
        raise HTTPException(status_code=404, detail=f"TMF resource not found: {path}")
    method = entry.get("method", "GET")
    if request.method != method and request.method == "GET" and method in ("GET", "POST"):
        pass
    elif request.method != method:
        raise HTTPException(status_code=405, detail=f"expected {method}")
    return entry.get("body") or {}
