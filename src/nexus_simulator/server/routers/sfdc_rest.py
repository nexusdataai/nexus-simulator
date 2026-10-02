"""Salesforce REST API compatibility layer over the SFDC simulator catalog."""

from __future__ import annotations

import re
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request

from ..vendor_catalog import SFDC_VERSION
from ..vendor_runtime import create_row, delete_row, get_row, get_service, load_rows, patch_row, require_table, schema_for

router = APIRouter(tags=["Salesforce REST"])

_SOQL = re.compile(
    r"^\s*SELECT\s+(?P<cols>.+?)\s+FROM\s+(?P<table>[\w]+(?:__c)?)"
    r"(?:\s+WHERE\s+(?P<where_col>[\w]+)\s*=\s*'(?P<where_val>[^']*)')?"
    r"(?:\s+LIMIT\s+(?P<limit>\d+))?\s*$",
    re.IGNORECASE,
)


def _schema(svc) -> str:
    return schema_for(svc, "sfdc_itxp2dev")


@router.get("/services/data")
@router.get(f"/services/data/{SFDC_VERSION}")
async def versions():
    return [{"label": "Winter '25", "url": f"/services/data/{SFDC_VERSION}", "version": "61.0"}]


@router.get(f"/services/data/{SFDC_VERSION}/sobjects")
async def global_describe(request: Request):
    svc = await get_service(request, "sfdc")
    objects = await svc.get_object_list()
    sobjects = [
        {
            "name": o.get("tableName"),
            "label": o.get("tableName"),
            "urls": {
                "sobject": f"/services/data/{SFDC_VERSION}/sobjects/{o.get('tableName')}",
                "describe": f"/services/data/{SFDC_VERSION}/sobjects/{o.get('tableName')}/describe",
            },
            "rowCount": o.get("rowCount", 0),
        }
        for o in objects
    ]
    return {"encoding": "UTF-8", "maxBatchSize": 200, "sobjects": sobjects}


@router.get(f"/services/data/{SFDC_VERSION}/sobjects/{{sobject}}/describe")
async def describe(sobject: str, request: Request):
    svc = await get_service(request, "sfdc")
    require_table(svc, sobject)
    schema = _schema(svc)
    cols = await svc.get_table_columns(schema, sobject) if hasattr(svc, "get_table_columns") else []
    if not cols:
        rows = await load_rows(svc, schema, sobject)
        if not rows:
            raise HTTPException(status_code=404, detail=f"sObject not found: {sobject}")
        fields = [{"name": k, "type": "string", "nillable": True} for k in rows[0].keys()]
    else:
        fields = [
            {
                "name": getattr(c, "column_name", None) or c.get("column_name"),
                "type": getattr(c, "data_type", None) or c.get("data_type") or "string",
                "nillable": getattr(c, "is_nullable", True) if not isinstance(c, dict) else c.get("is_nullable", True),
            }
            for c in cols
        ]
    return {"name": sobject, "label": sobject, "fields": fields, "custom": "__" in sobject}


@router.get(f"/services/data/{SFDC_VERSION}/sobjects/{{sobject}}")
async def list_or_basic(sobject: str, request: Request, limit: int = Query(50, ge=1, le=1000), offset: int = Query(0, ge=0)):
    svc = await get_service(request, "sfdc")
    require_table(svc, sobject)
    schema = _schema(svc)
    page = await svc.get_object_records(schema, sobject, limit, offset)
    return {
        "objectDescribe": {"name": sobject},
        "recentItems": page.get("rows", []),
        "totalSize": page.get("total", 0),
        "done": True,
        "records": page.get("rows", []),
    }


@router.post(f"/services/data/{SFDC_VERSION}/sobjects/{{sobject}}")
async def create_sobject(sobject: str, request: Request, body: dict[str, Any] = Body(default_factory=dict)):
    svc = await get_service(request, "sfdc")
    require_table(svc, sobject)
    schema = _schema(svc)
    row = await create_row(svc, schema, sobject, body)
    pk = next((k for k in ("Id", f"{sobject}_ID", f"{sobject}Id") if k in row), None)
    return {"id": row.get(pk) if pk else None, "success": True, "errors": [], "record": row}


@router.get(f"/services/data/{SFDC_VERSION}/sobjects/{{sobject}}/{{record_id}}")
async def get_sobject(sobject: str, record_id: str, request: Request):
    svc = await get_service(request, "sfdc")
    require_table(svc, sobject)
    return await get_row(svc, _schema(svc), sobject, record_id)


@router.patch(f"/services/data/{SFDC_VERSION}/sobjects/{{sobject}}/{{record_id}}")
async def patch_sobject(sobject: str, record_id: str, request: Request, body: dict[str, Any] = Body(default_factory=dict)):
    svc = await get_service(request, "sfdc")
    require_table(svc, sobject)
    row = await patch_row(svc, _schema(svc), sobject, record_id, body)
    return {"id": record_id, "success": True, "record": row}


@router.delete(f"/services/data/{SFDC_VERSION}/sobjects/{{sobject}}/{{record_id}}")
async def delete_sobject(sobject: str, record_id: str, request: Request):
    svc = await get_service(request, "sfdc")
    require_table(svc, sobject)
    await delete_row(svc, _schema(svc), sobject, record_id)
    return {"id": record_id, "success": True}


@router.get(f"/services/data/{SFDC_VERSION}/query")
async def soql_query(request: Request, q: Optional[str] = Query(None)):
    if not q:
        raise HTTPException(status_code=400, detail="q is required")
    match = _SOQL.match(q)
    if not match:
        raise HTTPException(status_code=400, detail="Unsupported SOQL subset. Use SELECT a,b FROM Object [WHERE col = 'x'] [LIMIT n]")
    table = match.group("table")
    cols = [c.strip() for c in match.group("cols").split(",")]
    svc = await get_service(request, "sfdc")
    schema = _schema(svc)
    rows = await load_rows(svc, schema, table)
    where_col, where_val = match.group("where_col"), match.group("where_val")
    if where_col:
        rows = [r for r in rows if str(r.get(where_col, "")) == str(where_val)]
    limit = int(match.group("limit") or 200)
    rows = rows[:limit]
    if cols != ["*"]:
        rows = [{c: r.get(c) for c in cols} for r in rows]
    return {"totalSize": len(rows), "done": True, "records": rows}
