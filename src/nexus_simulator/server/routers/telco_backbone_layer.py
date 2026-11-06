"""Backbone catalog / generate / files / stream for one of BSS / NSS / OSS."""

from __future__ import annotations

import asyncio
import json
import urllib.parse
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
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
        return await svc.generate_backbone(
            pools=get_telco_pools(),
            systems=systems,
            deliveries=deliveries,
            include_legacy_tables=body.include_legacy_tables if body else True,
        )

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
