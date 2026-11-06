"""Telco source artifacts — profile, generate, files, streams, lineage."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from ...telco_sources.catalog import catalog_systems, default_profile, zain_profile
from ...telco_sources.models import TelcoSourceProfile

router = APIRouter(prefix="/api/v1/telco-sources", tags=["Telco Sources"])


def _svc(request: Request):
    sim = getattr(request.app.state, "simulator", None)
    if sim is None:
        raise HTTPException(status_code=503, detail="simulator not initialised")
    svc = sim.registry.get("telco_sources") or getattr(sim, "telco_sources", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="telco_sources simulator not configured")
    return svc


class ProfileBody(BaseModel):
    profile_id: str = "default"
    vendor_defaults: dict[str, str] = Field(default_factory=dict)
    preset: Optional[str] = None
    systems: list[dict] = Field(default_factory=list)
    products: list[dict] = Field(default_factory=list)


class GenerateBody(BaseModel):
    layers: Optional[list[str]] = None
    systems: Optional[list[str]] = None
    deliveries: Optional[list[str]] = None
    refresh_identity: bool = False
    all_systems: bool = False


@router.get("/catalog")
async def get_catalog():
    return {"systems": catalog_systems(), "presets": ["default", "zain"]}


@router.get("/profile")
async def get_profile(request: Request):
    svc = _svc(request)
    prof = await svc.get_profile()
    return prof.to_dict()


@router.put("/profile")
async def put_profile(request: Request, body: ProfileBody):
    svc = _svc(request)
    if body.preset == "zain" and not body.systems:
        prof = await svc.save_profile(zain_profile().to_dict())
    else:
        prof = await svc.save_profile(body.model_dump())
    return prof.to_dict()


@router.post("/generate")
async def generate(request: Request, body: GenerateBody | None = None):
    svc = _svc(request)
    kwargs = body.model_dump(exclude_none=True) if body else {}
    summary = await svc.seed_data(**kwargs)
    return {"success": True, "summary": summary}


@router.get("/artifacts")
async def list_artifacts(request: Request):
    svc = _svc(request)
    bundle = await svc.get_bundle()
    if not bundle:
        raise HTTPException(status_code=404, detail="No artifacts generated yet")
    return bundle


@router.get("/files")
async def list_files(request: Request, system: str | None = None, latest: bool = False):
    svc = _svc(request)
    files = await svc.get_files_manifest()
    if system:
        files = [f for f in files if f.get("system_key") == system]
    if latest and files:
        files = [files[-1]]
    return {"files": files}


@router.get("/files/content")
async def file_content(request: Request, path: str = Query(...)):
    svc = _svc(request)
    content = await svc.read_file_artifact(path)
    if content is None:
        raise HTTPException(status_code=404, detail=f"file not found: {path}")
    return PlainTextResponse(content)


@router.get("/stream/{topic:path}")
async def stream_topic(request: Request, topic: str):
    svc = _svc(request)
    streams = await svc.get_streams()
    events = streams.get(topic)
    if events is None:
        raise HTTPException(status_code=404, detail=f"unknown topic: {topic}")

    async def event_gen():
        for ev in events:
            payload = json.dumps(ev)
            yield f"data: {payload}\n\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/lineage")
async def lineage(request: Request, customer_id: str | None = None):
    svc = _svc(request)
    bundle = await svc.get_bundle()
    if not bundle:
        await svc.seed_data()
        bundle = await svc.get_bundle()
    lin = (bundle or {}).get("lineage") or {}
    if customer_id and lin.get("customer_id") != customer_id:
        return {"customer_id": customer_id, "note": "lineage trace uses primary subscriber", "lineage": lin}
    return lin


@router.post("/scenario/{name}")
async def run_scenario(request: Request, name: str):
    svc = _svc(request)
    return await svc.seed_scenario(name)
