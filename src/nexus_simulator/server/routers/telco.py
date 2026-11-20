"""Ordered seed for all telecom simulators (BSS → NSS → OSS → golden)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/telco", tags=["Telco"])

# Default seed order (BSS → NSS → OSS only). Append legacy plugins when include_* is true.
_ORDER = ("bss", "nss", "oss", "telco_golden", "telco_sources")


class SeedAllResponse(BaseModel):
    success: bool
    message: str
    results: dict


@router.post("/seed-billing", response_model=SeedAllResponse)
async def seed_billing(request: Request):
    """Seed BSS → NSS → OSS with the billing backbone profile (Kenan BP–aligned families + Kenan tables on BSS)."""
    import os

    prev = os.environ.get("TELCO_BACKBONE_PROFILE")
    os.environ["TELCO_BACKBONE_PROFILE"] = "billing"
    try:
        return await seed_all(request, include_sources=False, include_golden=False)
    finally:
        if prev is None:
            os.environ.pop("TELCO_BACKBONE_PROFILE", None)
        else:
            os.environ["TELCO_BACKBONE_PROFILE"] = prev


@router.post("/seed-all", response_model=SeedAllResponse)
async def seed_all(request: Request, include_sources: bool = False, include_golden: bool = False):
    sim = getattr(request.app.state, "simulator", None)
    if sim is None:
        raise HTTPException(status_code=503, detail="simulator not initialised")

    results = {}
    order = tuple(
        n
        for n in _ORDER
        if (include_sources or n != "telco_sources") and (include_golden or n != "telco_golden")
    )
    for name in order:
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
