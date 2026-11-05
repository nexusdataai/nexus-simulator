"""Ordered seed for all telecom simulators (BSS → NSS → OSS → golden)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/telco", tags=["Telco"])

_ORDER = ("bss", "nss", "oss", "telco_golden")


class SeedAllResponse(BaseModel):
    success: bool
    message: str
    results: dict


@router.post("/seed-all", response_model=SeedAllResponse)
async def seed_all(request: Request):
    sim = getattr(request.app.state, "simulator", None)
    if sim is None:
        raise HTTPException(status_code=503, detail="simulator not initialised")

    results = {}
    for name in _ORDER:
        svc = sim.registry.get(name) or getattr(sim, name, None)
        if svc is None:
            results[name] = {"status": "skipped", "reason": "not configured"}
            continue
        try:
            summary = await svc.seed_data()
            results[name] = {"status": "seeded", "summary": summary}
            logger.info("telco seed-all completed plugin=%s", name)
        except Exception as exc:
            logger.exception("telco seed-all failed plugin=%s", name)
            results[name] = {"status": "error", "reason": str(exc)}
            return SeedAllResponse(
                success=False,
                message=f"Seed failed at {name}",
                results=results,
            )

    return SeedAllResponse(success=True, message="All telco plugins seeded", results=results)
