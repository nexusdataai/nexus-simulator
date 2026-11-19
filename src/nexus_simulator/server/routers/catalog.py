"""Aggregate catalog for the simulator UI overview."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..vendor_catalog import build_system_catalog

router = APIRouter(prefix="/api/v1/simulators", tags=["simulators"])

_PRIMARY = ("sfdc", "oracle", "sap", "external", "tpm", "sourcing", "bss", "nss", "oss")

_LEGACY_TELCO = ("telco_golden", "telco_sources")

_VENDOR_API = frozenset({"sfdc", "oracle", "sap"})


async def _catalog_status(svc, name: str) -> dict:
    """Overview counts: tables from get_status(); files/APIs/streams from backbone or vendor catalog."""
    status = dict(svc.get_status() if hasattr(svc, "get_status") else {})
    if hasattr(svc, "get_backbone_summary"):
        try:
            summary = await svc.get_backbone_summary()
            status["file_count"] = len(summary.get("files") or [])
            status["api_count"] = len(summary.get("apis") or [])
            status["stream_count"] = len(summary.get("streams") or [])
            run_id = summary.get("run_id")
            if run_id:
                status["backbone_run_id"] = run_id
            gen = summary.get("generated_at")
            if gen:
                status["backbone_generated_at"] = gen
            if summary.get("vendor_label"):
                status["vendor_label"] = summary.get("vendor_label")
            if summary.get("vendor_code"):
                status["vendor_code"] = summary.get("vendor_code")
        except Exception:
            pass
    elif name in _VENDOR_API:
        try:
            status["api_count"] = len(await build_system_catalog(svc, name))
        except Exception:
            pass
    if not status.get("file_count") and hasattr(svc, "get_files_manifest"):
        try:
            files = await svc.get_files_manifest()
            status["file_count"] = len(files or [])
        except Exception:
            pass
    return status


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
        status = await _catalog_status(svc, name)
        items.append({"service": name, **status})
    for name in _LEGACY_TELCO:
        svc = sim.registry.get(name)
        if svc is None:
            continue
        status = await _catalog_status(svc, name)
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
    status = await _catalog_status(svc, service)
    objects = await svc.get_object_list() if hasattr(svc, "get_object_list") else []
    return {"service": service, **status, "tables": objects}
