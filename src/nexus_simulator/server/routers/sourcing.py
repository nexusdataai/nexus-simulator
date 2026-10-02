"""Sourcing Simulator REST API (Buy-side / SAP Ariba-style)."""

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

SCHEMA = "sourcing_cpq"

router = APIRouter()


def get_service(request: Request):
    sim = getattr(request.app.state, "simulator", None)
    svc = getattr(sim, "sourcing", None) if sim is not None else None
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="Sourcing simulator plugin not configured.",
        )
    return svc


@router.get("/status", tags=["Sourcing Simulator"])
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


@router.get("/load/status", tags=["Sourcing Simulator"])
async def get_load_status(request: Request):
    return get_service(request).get_load_status()


@router.post("/load", response_model=AdminResponse, tags=["Sourcing Simulator"])
async def load_data(request: Request):
    service = get_service(request)
    asyncio.create_task(service.load_from_s3())
    return AdminResponse(success=True, message="Load started in background. Poll GET /status for updates.")


@router.post("/seed", response_model=AdminResponse, tags=["Sourcing Simulator"])
async def seed_data(request: Request):
    service = get_service(request)
    asyncio.create_task(service.seed_data())
    return AdminResponse(success=True, message="Seed started in background. Poll GET /status for updates.")


@router.post("/reset", response_model=AdminResponse, tags=["Sourcing Simulator"])
async def reset_data(request: Request):
    service = get_service(request)
    if service.bucket:
        asyncio.create_task(service.load_from_s3())
    else:
        asyncio.create_task(service.seed_data())
    return AdminResponse(success=True, message="Reset started. Poll GET /status for updates.")


@router.get("/objects", tags=["Sourcing Simulator"])
async def list_objects(request: Request):
    service = get_service(request)
    if service.loaded:
        return {"objects": await service.get_object_list()}
    return {"objects": [], "message": "Simulator not loaded. Click 'Load Data' or 'Seed Data'."}


@router.get("/objects/{schema}/{table}", tags=["Sourcing Simulator"])
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


@router.get("/objects/{schema}/{table}/columns", tags=["Sourcing Simulator"])
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


@router.get("/health", tags=["Sourcing Simulator"])
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


class RfxCreate(BaseModel):
    category: str
    plants: Optional[List[str]] = None
    target_qty: Optional[float] = None
    due_date: Optional[str] = None
    title: Optional[str] = None
    actor: str = "ai-copilot"


@router.post("/rfx-events", tags=["Sourcing Connector"])
async def create_rfx_event(body: RfxCreate):
    sim = await get_sim("sourcing")
    event_id = f"RFX-{uuid.uuid4().hex[:6].upper()}"
    plants = body.plants or []
    close_date = body.due_date or (datetime.now(timezone.utc) + timedelta(days=14)).strftime("%Y-%m-%d")
    event_row: Dict[str, Any] = {
        "Event_ID": event_id,
        "Type": "RFQ",
        "Buyer_Plant_ID": plants[0] if plants else "",
        "Category": body.category,
        "Status": "Draft",
        "Open_Date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "Close_Date": close_date,
        "Owner_ID": body.actor,
        "Title": body.title or f"RFQ for {body.category} {event_id[-4:]}",
        "Target_Qty": body.target_qty,
    }
    await append_row(sim, SCHEMA, "RFx_Event", event_row)
    await emit_audit(body.actor, "launch_rfx", event_id, event_row, api_id="sourcing.rfx.create")
    return {"event_id": event_id, "event": event_row}


class RfxInvite(BaseModel):
    vendor_ids: List[str]
    actor: str = "ai-copilot"


@router.post("/rfx-events/{event_id}/invitations", tags=["Sourcing Connector"])
async def invite_rfx_vendors(event_id: str = Path(...), body: RfxInvite = Body(...)):
    sim = await get_sim("sourcing")
    invitations: List[Dict[str, Any]] = []
    for vendor_id in body.vendor_ids:
        inv_id = f"RFI-{uuid.uuid4().hex[:6].upper()}"
        inv = {
            "Invitation_ID": inv_id,
            "Event_ID": event_id,
            "Vendor_ID": vendor_id,
            "Status": "Invited",
            "Invited_At": _now_iso(),
        }
        await append_row(sim, SCHEMA, "RFx_Invitation", inv)
        invitations.append(inv)
    await emit_audit(
        body.actor, "solicit_vendors", event_id,
        {"vendor_count": len(invitations)},
        api_id="sourcing.rfx.invite",
    )
    return {"event_id": event_id, "invitations": invitations}


class ScenarioCreate(BaseModel):
    event_id: str
    split_strategy: Optional[str] = "cost_optimal"
    actor: str = "ai-copilot"


@router.post("/scenarios", tags=["Sourcing Connector"])
async def create_sourcing_scenario(body: ScenarioCreate):
    sim = await get_sim("sourcing")
    scenario_id = f"SCN-{uuid.uuid4().hex[:6].upper()}"
    strategy = body.split_strategy or "cost_optimal"
    scenario_row: Dict[str, Any] = {
        "Scenario_ID": scenario_id,
        "Event_ID": body.event_id,
        "Name": strategy.replace("_", " ").title(),
        "Split_JSON": json.dumps([]),
        "Modeled_Savings": 0.0,
        "Modeled_Risk_Score": 0.0,
        "Concentration_Pct": 100,
        "Generated_At": _now_iso(),
    }
    await append_row(sim, SCHEMA, "Sourcing_Scenario", scenario_row)
    await emit_audit(
        body.actor, "run_award_scenario", scenario_id,
        {"strategy": strategy},
        api_id="sourcing.scenario.create",
    )
    return {"scenario_id": scenario_id, "scenario": scenario_row}


class AwardIssue(BaseModel):
    actor: str = "ai-copilot"


@router.patch("/awards/{award_id}/issue", tags=["Sourcing Connector"])
async def issue_award(award_id: str = Path(...), body: AwardIssue = Body(...)):
    sim = await get_sim("sourcing")
    previous, new_row = await update_one(
        sim, SCHEMA, "Sourcing_Award", "Award_ID", award_id,
        {"Status": "Issued", "Issued_At": _now_iso()},
    )
    await emit_audit(
        body.actor, "convert_award_to_po", award_id,
        {"previous_status": previous.get("Status"), "new_status": "Issued"},
        api_id="sourcing.award.issue",
    )
    return {"award_id": award_id, "new_status": new_row.get("Status")}
