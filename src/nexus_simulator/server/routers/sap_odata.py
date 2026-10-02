"""SAP S/4HANA OData V2 compatibility layer over the SAP simulator."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from ..vendor_catalog import SAP_BY_ENTITY, SAP_ENTITIES
from ..vendor_runtime import create_row, delete_row, get_row, get_service, patch_row, schema_for

router = APIRouter(tags=["SAP OData"])

_KEY = re.compile(r"^(?P<entity>[^(]+)\('(?P<key>[^']*)'\)$")


def _lookup(service: str, entity: str) -> tuple[str, str | None]:
    table = SAP_BY_ENTITY.get((service, entity))
    if not table:
        raise HTTPException(status_code=404, detail=f"OData entity not found: {service}/{entity}")
    return table, SAP_ENTITIES.get(table, {}).get("pk")


def _schema(svc) -> str:
    return schema_for(svc, "sap_s4hana")


def _parse_entity(rest: str) -> tuple[str, str | None]:
    rest = rest.rstrip("/")
    if rest in ("$metadata", ""):
        return "$metadata", None
    match = _KEY.match(rest)
    if match:
        return match.group("entity"), match.group("key")
    return rest, None


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


@router.api_route("/sap/opu/odata/sap/{service}/{rest:path}", methods=["GET", "POST", "PATCH", "DELETE", "MERGE"])
async def odata_dispatch(
    service: str,
    rest: str,
    request: Request,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    svc = await get_service(request, "sap")
    schema = _schema(svc)
    entity, key = _parse_entity(rest)
    if entity == "$metadata":
        entities = [meta["entity"] for table, meta in SAP_ENTITIES.items() if meta["service"] == service]
        return {
            "service": service,
            "entitySets": entities,
            "odataVersion": "2.0",
        }

    table, pk = _lookup(service, entity)
    method = request.method.upper()
    if method == "MERGE":
        method = "PATCH"
    body = await _json_body(request) if method in ("POST", "PATCH") else {}

    if key is None:
        if method == "GET":
            page = await svc.get_object_records(schema, table, limit, offset)
            return {"d": {"results": page.get("rows", []), "__count": page.get("total", 0)}}
        if method == "POST":
            row = await create_row(svc, schema, table, body)
            return {"d": row}
        raise HTTPException(status_code=405, detail=f"{method} not allowed on entity set")

    if method == "GET":
        return {"d": await get_row(svc, schema, table, key, pk)}
    if method == "PATCH":
        return {"d": await patch_row(svc, schema, table, key, body, pk)}
    if method == "DELETE":
        await delete_row(svc, schema, table, key, pk)
        return {"d": {"success": True, "id": key}}
    raise HTTPException(status_code=405, detail=f"{method} not allowed on entity")


@router.get("/sap/opu/odata/sap/{service}")
@router.get("/sap/opu/odata/sap/{service}/")
async def service_root(service: str):
    entities = [meta["entity"] for table, meta in SAP_ENTITIES.items() if meta["service"] == service]
    if not entities:
        raise HTTPException(status_code=404, detail=f"OData service not found: {service}")
    return {"d": {"EntitySets": entities}}
