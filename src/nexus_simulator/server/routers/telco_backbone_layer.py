"""Backbone catalog / generate / files / stream for one of BSS / NSS / OSS."""

from __future__ import annotations

import asyncio
import json
import urllib.parse
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from nexus_simulator.plugins.telco_seed_pools import clear_telco_pools_cache, get_telco_pools


def make_backbone_router(attr: str, registry_key: str, tag: str) -> APIRouter:
    router = APIRouter()

    def _svc(request: Request):
        sim = getattr(request.app.state, "simulator", None)
        if sim is None:
            raise HTTPException(status_code=503, detail="simulator not initialised")
        svc = getattr(sim, attr, None) or sim.registry.get(registry_key)
        if svc is None:
            raise HTTPException(status_code=503, detail=f"{registry_key} simulator not configured")
        return svc

    @router.get("/backbone/catalog", tags=[tag])
    async def backbone_catalog(request: Request):
        svc = _svc(request)
        if not hasattr(svc, "get_backbone_catalog"):
            raise HTTPException(status_code=501, detail="backbone not supported")
        return await svc.get_backbone_catalog()

    class GenerateBody(BaseModel):
        systems: Optional[list[str]] = None
        deliveries: Optional[list[str]] = Field(default=None, description="Table, File, API, Stream")
        system_deliveries: Optional[Dict[str, list[str]]] = Field(
            default=None,
            description="Per product family: modalities to generate (Table, File, API, Stream)",
        )
        vendor_code: Optional[str] = Field(
            default=None,
            description="Default vendor (single letter) when a row has no system_vendors entry",
        )
        system_vendors: Optional[Dict[str, str]] = Field(
            default=None,
            description="Per product family: vendor code (H,N,E,A,S,O,X)",
        )
        refresh_identity: bool = False
        include_legacy_tables: bool = True

    @router.post("/backbone/generate", tags=[tag])
    async def backbone_generate(request: Request, body: GenerateBody | None = None):
        svc = _svc(request)
        if not hasattr(svc, "generate_backbone"):
            raise HTTPException(status_code=501, detail="backbone not supported")
        if body and body.refresh_identity:
            clear_telco_pools_cache()
        systems = set(body.systems) if body and body.systems else None
        deliveries = set(body.deliveries) if body and body.deliveries else None
        sd: dict[str, set[str]] | None = None
        if body and body.system_deliveries:
            sd = {}
            for k, modes in body.system_deliveries.items():
                if not modes:
                    continue
                sd[k] = {str(m).strip() for m in modes if m}
        sv = None
        if body and body.system_vendors:
            sv = {str(k): str(v) for k, v in body.system_vendors.items()}
        return await svc.generate_backbone(
            pools=get_telco_pools(),
            systems=systems,
            deliveries=deliveries,
            system_deliveries=sd,
            system_vendors=sv,
            vendor_code=body.vendor_code if body else None,
            include_legacy_tables=body.include_legacy_tables if body else True,
        )

    @router.get("/backbone/summary", tags=[tag])
    async def backbone_summary(request: Request):
        svc = _svc(request)
        if not hasattr(svc, "get_backbone_summary"):
            raise HTTPException(status_code=501, detail="backbone summary not supported")
        return await svc.get_backbone_summary()

    @router.get("/backbone/artifacts", tags=[tag])
    async def backbone_artifacts(request: Request):
        svc = _svc(request)
        return await svc.get_backbone_artifacts()

    @router.get("/backbone/files", tags=[tag])
    async def backbone_files(request: Request):
        svc = _svc(request)
        return {"files": await svc.get_files_manifest()}

    @router.get("/backbone/file", tags=[tag])
    async def backbone_file_content(request: Request, path: str = Query(...)):
        svc = _svc(request)
        decoded = urllib.parse.unquote(path)
        content = await svc.read_backbone_file(decoded)
        if content is None:
            raise HTTPException(status_code=404, detail=f"file not found: {decoded}")
        return PlainTextResponse(content)

    @router.get("/backbone/vendor-catalog", tags=[tag])
    async def backbone_vendor_catalog(request: Request):
        svc = _svc(request)
        if not hasattr(svc, "get_vendor_api_index"):
            raise HTTPException(status_code=501, detail="vendor API catalog not supported")
        idx = await svc.get_vendor_api_index()
        paths = []
        for _k, ent in (idx or {}).items():
            if not isinstance(ent, dict):
                continue
            rp = ent.get("route_path")
            if rp:
                paths.append(
                    {
                        "method": ent.get("method", "GET"),
                        "route_path": rp,
                        "system_key": ent.get("system_key"),
                    }
                )
        return {"vendor_api_paths": paths, "total": len(paths)}

    @router.api_route("/vendor-api/{full_path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"], tags=[tag])
    async def backbone_vendor_api(request: Request, full_path: str):
        svc = _svc(request)
        if not hasattr(svc, "resolve_vendor_api"):
            raise HTTPException(status_code=501, detail="vendor API not supported")
        resolved = await svc.resolve_vendor_api(request.method, full_path)
        if not resolved:
            raise HTTPException(status_code=404, detail=f"vendor API not found: {request.method} /{full_path}")
        exp_m = str(resolved.get("method", "GET")).upper()
        if request.method != exp_m and not (request.method == "GET" and exp_m == "POST"):
            raise HTTPException(status_code=405, detail=f"expected {exp_m}")
        body = resolved.get("body")
        if isinstance(body, (dict, list)):
            return JSONResponse(content=body)
        return JSONResponse(content=body if body is not None else {})

    @router.get("/backbone/stream/{topic:path}", tags=[tag])
    async def backbone_stream(request: Request, topic: str):
        svc = _svc(request)
        streams = await svc.get_stream_topics()
        decoded = urllib.parse.unquote(topic)
        events = streams.get(decoded)
        if events is None:
            raise HTTPException(status_code=404, detail=f"unknown topic: {decoded}")

        async def gen():
            for ev in events:
                yield f"data: {json.dumps(ev)}\n\n"
                await asyncio.sleep(0.05)

        return StreamingResponse(gen(), media_type="text/event-stream")

    return router
