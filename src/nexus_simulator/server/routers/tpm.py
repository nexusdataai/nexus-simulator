"""TPM (Trade Promotion Management) Simulator REST API."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from pydantic import BaseModel

from ..connector_runtime import append_row, emit_audit, get_sim, update_one, _now_iso
from ...plugins.sap.models import AdminResponse

SCHEMA = "tpm_cpq"

router = APIRouter()


def get_service(request: Request):
    sim = getattr(request.app.state, "simulator", None)
    svc = getattr(sim, "tpm", None) if sim is not None else None
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="TPM simulator plugin not configured.",
        )
    return svc


@router.get("/status", tags=["TPM Simulator"])
async def get_status(request: Request):
    service = get_service(request)
    status = service.get_status()
    if not service.loaded and service.bucket:
        manifest = service._s3_get_json("manifest.json")
        if manifest:
            status["dump_timestamp"] = manifest.get("dump_timestamp")
            status["dump_available"] = True
            status["dump_tables"] = manifest.get("total_tables", 0)
            status["dump_rows"] = manifest.get("total_rows_dumped", 0)
    return status


@router.get("/load/status", tags=["TPM Simulator"])
async def get_load_status(request: Request):
    return get_service(request).get_load_status()


@router.post("/load", response_model=AdminResponse, tags=["TPM Simulator"])
async def load_data(request: Request):
    service = get_service(request)
    asyncio.create_task(service.load_from_s3())
    return AdminResponse(success=True, message="Load started in background. Poll GET /status for updates.")


@router.post("/seed", response_model=AdminResponse, tags=["TPM Simulator"])
async def seed_data(request: Request):
    service = get_service(request)
    asyncio.create_task(service.seed_data())
    return AdminResponse(success=True, message="Seed started in background. Poll GET /status for updates.")


@router.post("/reset", response_model=AdminResponse, tags=["TPM Simulator"])
async def reset_data(request: Request):
    service = get_service(request)
    if service.bucket:
        asyncio.create_task(service.load_from_s3())
    else:
        asyncio.create_task(service.seed_data())
    return AdminResponse(success=True, message="Reset started. Poll GET /status for updates.")


@router.get("/objects", tags=["TPM Simulator"])
async def list_objects(request: Request):
    service = get_service(request)
    if service.loaded:
        return {"objects": await service.get_object_list()}
    return {"objects": [], "message": "Simulator not loaded. Click 'Load Data' or 'Seed Data'."}


@router.get("/objects/{schema}/{table}", tags=["TPM Simulator"])
async def get_object_records(
    schema: str,
    table: str,
    request: Request,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    service = get_service(request)
    if service.loaded:
        return await service.get_object_records(schema, table, limit, offset)
    raise HTTPException(status_code=400, detail="Simulator not loaded.")


@router.get("/objects/{schema}/{table}/columns", tags=["TPM Simulator"])
async def get_object_columns(schema: str, table: str, request: Request):
    service = get_service(request)
    if not service.loaded:
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


@router.get("/health", tags=["TPM Simulator"])
async def health_check(request: Request):
    try:
        service = get_service(request)
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
        "bucket_configured": bool(service.bucket),
        "loaded": service.loaded,
        "timestamp": datetime.utcnow().isoformat(),
    }


class QuoteCreate(BaseModel):
    account_id: str
    channel: Optional[str] = None
    material_query: Optional[str] = None
    target_materials: Optional[List[str]] = None
    qty: int = 1
    discount_pct: float = 0.0
    validity_days: int = 30
    actor: str = "ai-copilot"


@router.post("/quotes", tags=["TPM Connector"])
async def create_quote(body: QuoteCreate):
    sim = await get_sim("tpm")
    quote_id = f"QT-{uuid.uuid4().hex[:6].upper()}"
    line_id = f"QTL-{uuid.uuid4().hex[:6].upper()}"
    now = _now_iso()
    validity_date = (datetime.now(timezone.utc) + timedelta(days=body.validity_days)).strftime("%Y-%m-%d")
    offering_id = (body.target_materials or [""])[0] if body.target_materials else ""
    header = {
        "Quote_ID": quote_id,
        "Account_ID": body.account_id,
        "Owner_ID": body.actor,
        "Status": "Draft",
        "Validity_Date": validity_date,
        "Total_Net": 0.0,
        "Margin_Pct": 0.0,
        "Discount_Pct": float(body.discount_pct),
        "Approval_Chain_JSON": "[]",
        "Created_At": now,
        "Submitted_At": "",
        "Channel": body.channel or "",
        "Material_Query": body.material_query or "",
    }
    line = {
        "Line_ID": line_id,
        "Quote_ID": quote_id,
        "Offering_ID": offering_id,
        "Qty": int(body.qty),
        "Unit_Price": 0.0,
        "Discount_Pct": float(body.discount_pct),
        "Promotion_ID": "",
        "Listing_Fee": 0,
        "Slotting_Fee": 0,
        "Margin_Pct_Line": 0.0,
    }
    await append_row(sim, SCHEMA, "Quote_Header", header)
    await append_row(sim, SCHEMA, "Quote_Line", line)
    await emit_audit(
        body.actor, "create_quote", quote_id,
        {"account_id": body.account_id, "channel": body.channel, "qty": body.qty},
        api_id="tpm.quote.create",
    )
    return {"quote_id": quote_id, "header": header, "lines": [line]}


class QuotePromotionApply(BaseModel):
    campaign_id: str
    actor: str = "ai-copilot"


@router.post("/quotes/{quote_id}/promotions", tags=["TPM Connector"])
async def apply_quote_promotion(quote_id: str = Path(...), body: QuotePromotionApply = Body(...)):
    sim = await get_sim("tpm")
    promo_id = f"QPR-{uuid.uuid4().hex[:6].upper()}"
    promo_row: Dict[str, Any] = {
        "Promo_ID": promo_id,
        "Quote_ID": quote_id,
        "Campaign_ID": body.campaign_id,
        "Mechanic": "Discount",
        "Value": 5.0,
        "Stacking_Group": "CAMPAIGN_DISC",
    }
    await append_row(sim, SCHEMA, "Quote_Promotion", promo_row)
    await emit_audit(body.actor, "apply_promotion", promo_id, promo_row, api_id="tpm.quote.promotion.apply")
    return {"quote_id": quote_id, "promotion_id": promo_id}


class QuoteApproval(BaseModel):
    actor: str = "ai-copilot"


@router.patch("/quotes/{quote_id}/approval", tags=["TPM Connector"])
async def route_quote_approval(quote_id: str = Path(...), body: QuoteApproval = Body(...)):
    sim = await get_sim("tpm")
    chain = [{"role": "RegionalSalesManager", "status": "pending"}]
    previous, new_row = await update_one(
        sim, SCHEMA, "Quote_Header", "Quote_ID", quote_id,
        {
            "Status": "In_Review",
            "Approval_Chain_JSON": json.dumps(chain),
            "Submitted_At": _now_iso(),
        },
    )
    await emit_audit(
        body.actor, "route_approval", quote_id,
        {"previous_status": previous.get("Status"), "new_status": "In_Review"},
        api_id="tpm.quote.approval.route",
    )
    return {
        "quote_id": quote_id,
        "approval_chain": chain,
        "status": new_row.get("Status"),
    }


class QuoteConvert(BaseModel):
    actor: str = "ai-copilot"


@router.patch("/quotes/{quote_id}/convert", tags=["TPM Connector"])
async def convert_quote(quote_id: str = Path(...), body: QuoteConvert = Body(...)):
    sim = await get_sim("tpm")
    previous, new_row = await update_one(
        sim, SCHEMA, "Quote_Header", "Quote_ID", quote_id,
        {"Status": "Won_Converted"},
    )
    await emit_audit(
        body.actor, "convert_quote_to_order", quote_id,
        {"previous_status": previous.get("Status"), "new_status": "Won_Converted"},
        api_id="tpm.quote.convert_to_order",
    )
    return {"quote_id": quote_id, "new_status": new_row.get("Status")}
