"""FDW-compatible discovery and query HTTP surface."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ...models.fdw import ColumnInfo, ForeignServerInfo, ForeignTableInfo, QueryRequest, QueryResponse

router = APIRouter(prefix="/api/fdw", tags=["fdw"])

_SOURCE_ALIASES = {
    "sfdc": "sfdc",
    "simulator": "sfdc",
    "oracle": "oracle",
    "oracle_erp": "oracle",
    "sap": "sap",
    "external": "external",
    "file_uploads": "external",
    "google_drive": "external",
    "social_listening": "external",
    "tpm": "tpm",
    "sourcing": "sourcing",
}


def _registry(request: Request):
    sim = getattr(request.app.state, "simulator", None)
    if sim is None:
        raise HTTPException(status_code=503, detail="simulator not initialised")
    return sim.registry


def _pick(request: Request, source: Optional[str]):
    registry = _registry(request)
    if not source:
        for name in ("sfdc", "oracle", "sap", "external", "tpm", "sourcing"):
            svc = registry.get(name)
            if svc is not None:
                return svc
        raise HTTPException(status_code=404, detail="no simulator plugins registered")
    key = _SOURCE_ALIASES.get(source, source)
    svc = registry.get(key)
    if svc is None:
        raise HTTPException(status_code=404, detail=f"simulator not found: {source}")
    return svc


@router.get("/servers", response_model=list[ForeignServerInfo])
async def list_servers(request: Request, source: Optional[str] = Query(None)):
    svc = _pick(request, source)
    if hasattr(svc, "ensure_loaded"):
        await svc.ensure_loaded()
    return await svc.list_foreign_servers()


@router.get("/tables", response_model=list[ForeignTableInfo])
async def list_tables(
    request: Request,
    server: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
):
    svc = _pick(request, source)
    if hasattr(svc, "ensure_loaded"):
        await svc.ensure_loaded()
    return await svc.list_foreign_tables(server_name=server)


@router.get("/tables/{schema}/{table}/columns", response_model=list[ColumnInfo])
async def get_columns(schema: str, table: str, request: Request, source: Optional[str] = Query(None)):
    svc = _pick(request, source)
    if hasattr(svc, "ensure_loaded"):
        await svc.ensure_loaded()
    columns = await svc.get_table_columns(schema, table)
    if not columns:
        raise HTTPException(status_code=404, detail=f"{schema}.{table} not found")
    return columns


@router.post("/query", response_model=QueryResponse)
async def execute_query(body: QueryRequest, request: Request, source: Optional[str] = Query(None)):
    svc = _pick(request, source)
    if hasattr(svc, "ensure_loaded"):
        await svc.ensure_loaded()
    try:
        return await svc.execute_query(body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"simulator query failed: {exc}") from exc


class WriteTableRequest(BaseModel):
    schema_name: str = Field(..., alias="schemaName")
    table: str
    rows: list[dict[str, Any]]
    append: bool = False

    class Config:
        populate_by_name = True


@router.post("/write")
async def write_table(body: WriteTableRequest, request: Request, source: Optional[str] = Query(None)):
    svc = _pick(request, source)
    if hasattr(svc, "ensure_loaded"):
        await svc.ensure_loaded()
    if body.append and hasattr(svc, "append_rows"):
        count = await svc.append_rows(body.schema_name, body.table, body.rows)
    elif hasattr(svc, "write_table"):
        count = await svc.write_table(body.schema_name, body.table, body.rows)
    else:
        raise HTTPException(status_code=500, detail="simulator missing write_table")
    return {"success": True, "rowCount": count}
