"""Shared admin endpoints for FDW-style simulator plugins."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel


class AdminResponse(BaseModel):
    success: bool
    message: str


def make_admin_router(attr: str, registry_key: str, tag: str) -> APIRouter:
    router = APIRouter()

    def _svc(request: Request):
        sim = getattr(request.app.state, "simulator", None)
        svc = None
        if sim is not None:
            svc = getattr(sim, attr, None) or sim.registry.get(registry_key)
        if svc is None:
            raise HTTPException(status_code=503, detail=f"{registry_key} simulator not configured")
        return svc

    @router.get("/status", tags=[tag])
    async def get_status(request: Request):
        service = _svc(request)
        return service.get_status()

    @router.get("/load/status", tags=[tag])
    async def get_load_status(request: Request):
        return _svc(request).get_load_status()

    @router.post("/load", response_model=AdminResponse, tags=[tag])
    async def load_data(request: Request):
        import asyncio

        service = _svc(request)
        asyncio.create_task(service.load_from_s3())
        return AdminResponse(success=True, message="Load started in background.")

    @router.post("/seed", response_model=AdminResponse, tags=[tag])
    async def seed_data(request: Request):
        import asyncio

        service = _svc(request)
        asyncio.create_task(service.seed_data())
        return AdminResponse(success=True, message="Seed started in background.")

    @router.post("/reset", response_model=AdminResponse, tags=[tag])
    async def reset_data(request: Request):
        import asyncio

        service = _svc(request)
        if service.bucket:
            asyncio.create_task(service.load_from_s3())
        else:
            asyncio.create_task(service.seed_data())
        return AdminResponse(success=True, message="Reset started.")

    @router.get("/objects", tags=[tag])
    async def list_objects(request: Request):
        service = _svc(request)
        if getattr(service, "loaded", False):
            return {"objects": await service.get_object_list()}
        return {"objects": [], "message": "Simulator not loaded."}

    @router.get("/objects/{schema}/{table}", tags=[tag])
    async def get_object_records(
        schema: str,
        table: str,
        request: Request,
        limit: int = Query(50, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ):
        service = _svc(request)
        if not getattr(service, "loaded", False):
            raise HTTPException(status_code=400, detail="Simulator not loaded.")
        return await service.get_object_records(schema, table, limit, offset)

    @router.get("/objects/{schema}/{table}/columns", tags=[tag])
    async def get_object_columns(schema: str, table: str, request: Request):
        service = _svc(request)
        if not getattr(service, "loaded", False):
            raise HTTPException(status_code=400, detail="Simulator not loaded")
        cols = await service.get_table_columns(schema, table)
        return {
            "schemaName": schema,
            "tableName": table,
            "columns": [
                {
                    "columnName": c.column_name,
                    "dataType": c.data_type,
                    "isNullable": c.is_nullable,
                    "ordinalPosition": c.ordinal_position,
                }
                for c in cols
            ],
        }

    @router.get("/health", tags=[tag])
    async def health_check(request: Request):
        try:
            service = _svc(request)
        except HTTPException:
            return {
                "status": "degraded",
                "mode": "simulator",
                "enabled": False,
                "loaded": False,
                "timestamp": datetime.utcnow().isoformat(),
            }
        return {
            "status": "healthy" if service.loaded else "not_loaded",
            "mode": "simulator",
            "enabled": service.enabled,
            "loaded": service.loaded,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # silence unused import warning if Callable not used
    _ = Callable
    return router
