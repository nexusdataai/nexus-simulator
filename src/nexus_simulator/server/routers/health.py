"""Health, readiness, and version endpoints. Library-native, not ported."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ... import __version__

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/readiness")
async def readiness(request: Request) -> dict:
    simulator = getattr(request.app.state, "simulator", None)
    ready = simulator is not None
    return {"ready": ready, "version": __version__}


@router.get("/version")
async def version() -> dict:
    return {"name": "nexus-simulator", "version": __version__}
