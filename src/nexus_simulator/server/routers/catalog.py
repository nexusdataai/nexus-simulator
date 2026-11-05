"""Aggregate catalog for the simulator UI overview."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1/simulators", tags=["simulators"])

_PRIMARY = ("sfdc", "oracle", "sap", "external", "tpm", "sourcing", "bss", "nss", "oss", "telco_golden")


@router.get("")
async def list_simulators(request: Request):
    sim = getattr(request.app.state, "simulator", None)
    if sim is None:
        raise HTTPException(status_code=503, detail="simulator not initialised")
    items = []
    for name in _PRIMARY:
        svc = sim.registry.get(name)
        if svc is None:
            continue
        status = svc.get_status() if hasattr(svc, "get_status") else {}
        items.append({"service": name, **status})
    return {"total": len(items), "items": items}


@router.get("/{service}")
async def get_simulator(service: str, request: Request):
    sim = getattr(request.app.state, "simulator", None)
    if sim is None:
        raise HTTPException(status_code=503, detail="simulator not initialised")
    svc = sim.registry.get(service)
    if svc is None:
        raise HTTPException(status_code=404, detail=f"simulator not found: {service}")
    status = svc.get_status() if hasattr(svc, "get_status") else {}
    objects = await svc.get_object_list() if hasattr(svc, "get_object_list") else []
    return {"service": service, **status, "tables": objects}
