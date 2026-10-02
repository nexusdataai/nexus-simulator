"""Oracle Fusion Cloud REST compatibility layer over the Oracle ERP simulator."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

from ..vendor_catalog import ORACLE_BY_RESOURCE, ORACLE_RESOURCES, ORACLE_VERSION
from ..vendor_runtime import create_row, delete_row, get_row, get_service, patch_row, schema_for

router = APIRouter(tags=["Oracle Fusion REST"])


def _table(resource: str) -> tuple[str, str | None]:
    table = ORACLE_BY_RESOURCE.get(resource)
    if not table:
        raise HTTPException(status_code=404, detail=f"Fusion resource not found: {resource}")
    return table, ORACLE_RESOURCES.get(table, {}).get("pk")


def _schema(svc) -> str:
    return schema_for(svc, "oracle_erp")


@router.get(f"/fscmRestApi/resources/{ORACLE_VERSION}/{{resource}}")
async def list_resource(resource: str, request: Request, limit: int = Query(50, ge=1, le=1000), offset: int = Query(0, ge=0)):
    table, _ = _table(resource)
    svc = await get_service(request, "oracle")
    page = await svc.get_object_records(_schema(svc), table, limit, offset)
    return {"items": page.get("rows", []), "count": page.get("total", 0), "hasMore": False}


@router.post(f"/fscmRestApi/resources/{ORACLE_VERSION}/{{resource}}")
async def create_resource(resource: str, request: Request, body: dict[str, Any] = Body(default_factory=dict)):
    table, _ = _table(resource)
    svc = await get_service(request, "oracle")
    row = await create_row(svc, _schema(svc), table, body)
    return row


@router.get(f"/fscmRestApi/resources/{ORACLE_VERSION}/{{resource}}/{{item_id}}")
async def get_resource(resource: str, item_id: str, request: Request):
    table, pk = _table(resource)
    svc = await get_service(request, "oracle")
    return await get_row(svc, _schema(svc), table, item_id, pk)


@router.patch(f"/fscmRestApi/resources/{ORACLE_VERSION}/{{resource}}/{{item_id}}")
async def patch_resource(resource: str, item_id: str, request: Request, body: dict[str, Any] = Body(default_factory=dict)):
    table, pk = _table(resource)
    svc = await get_service(request, "oracle")
    return await patch_row(svc, _schema(svc), table, item_id, body, pk)


@router.delete(f"/fscmRestApi/resources/{ORACLE_VERSION}/{{resource}}/{{item_id}}")
async def delete_resource(resource: str, item_id: str, request: Request):
    table, pk = _table(resource)
    svc = await get_service(request, "oracle")
    await delete_row(svc, _schema(svc), table, item_id, pk)
    return {"success": True, "id": item_id}
