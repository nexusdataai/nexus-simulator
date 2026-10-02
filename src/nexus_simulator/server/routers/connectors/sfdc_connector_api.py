"""Salesforce connector API - simulator-backed write surface."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Path
from pydantic import BaseModel

from ...connector_runtime import (
    append_row, emit_audit, get_sim, update_one, _now_iso,
)

router = APIRouter(prefix="/api/v1/simulator/sfdc", tags=["SFDC Connector"])

SCHEMA = "sfdc_itxp2dev"


class CreditHoldUpdate(BaseModel):
    hold: bool
    reason: Optional[str] = None
    approved_by: Optional[str] = None
    actor: str = "ai-copilot"


@router.patch("/accounts/{account_id}/credit-hold")
async def set_account_credit_hold(account_id: str = Path(...), body: CreditHoldUpdate = Body(...)):
    sim = await get_sim("simulator")
    new_status = "Credit_Hold" if body.hold else "Active"
    patch: Dict[str, Any] = {
        "Account_Status": new_status,
        "Credit_Hold_Reason": body.reason,
        "Credit_Hold_Approved_By": body.approved_by,
        "Last_Updated": _now_iso(),
    }
    previous, _ = await update_one(sim, SCHEMA, "Account", "Account_ID", account_id, patch)
    await emit_audit(body.actor, "set_credit_hold", account_id,
                     {"previous_status": previous.get("Account_Status"), **patch},
                     api_id="sfdc.account.credit_hold.set")
    return {"account_id": account_id, "account_status": new_status}


class CaseCreate(BaseModel):
    account_id: str
    subject: str
    description: str
    priority: str = "Medium"
    actor: str = "ai-copilot"


@router.post("/cases")
async def create_case(body: CaseCreate):
    sim = await get_sim("simulator")
    case_id = f"CASE-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    row = {
        "Case_ID": case_id,
        "Account_ID": body.account_id,
        "Subject": body.subject,
        "Description": body.description,
        "Priority": body.priority,
        "Status": "Open",
        "Created_Date": _now_iso(),
    }
    await append_row(sim, SCHEMA, "Case", row)
    await emit_audit(body.actor, "create_case", case_id, row, api_id="sfdc.case.create")
    return {"case_id": case_id}


class OpportunityUpdate(BaseModel):
    stage: Optional[str] = None
    amount: Optional[float] = None
    close_date: Optional[str] = None
    actor: str = "ai-copilot"


@router.patch("/opportunities/{opportunity_id}")
async def update_opportunity(opportunity_id: str = Path(...), body: OpportunityUpdate = Body(...)):
    sim = await get_sim("simulator")
    patch: Dict[str, Any] = {}
    if body.stage is not None: patch["Stage"] = body.stage
    if body.amount is not None: patch["Amount"] = body.amount
    if body.close_date is not None: patch["Close_Date"] = body.close_date
    patch["Last_Updated"] = _now_iso()
    _, _ = await update_one(sim, SCHEMA, "Opportunity", "Opportunity_ID", opportunity_id, patch)
    await emit_audit(body.actor, "update_opportunity", opportunity_id, patch,
                     api_id="sfdc.opportunity.update")
    return {"opportunity_id": opportunity_id, **patch}


class AccountHealthUpdate(BaseModel):
    health_bucket: Optional[str] = None
    health_score: Optional[float] = None
    churn_date: Optional[str] = None
    churn_reason: Optional[str] = None
    actor: str = "ai-copilot"


@router.patch("/accounts/{account_id}/health")
async def set_account_health(account_id: str = Path(...), body: AccountHealthUpdate = Body(...)):
    sim = await get_sim("simulator")
    patch: Dict[str, Any] = {}
    if body.health_bucket is not None: patch["Health_Bucket"] = body.health_bucket
    if body.health_score is not None: patch["Health_Score"] = body.health_score
    if body.churn_date is not None: patch["Churn_Date"] = body.churn_date
    if body.churn_reason is not None: patch["Churn_Reason"] = body.churn_reason
    patch["Last_Updated"] = _now_iso()
    _, _ = await update_one(sim, SCHEMA, "Account", "Account_ID", account_id, patch)
    await emit_audit(body.actor, "update_account_health", account_id, patch,
                     api_id="sfdc.account.churn_risk.set")
    return {"account_id": account_id, **patch}


class ForecastOverrideCreate(BaseModel):
    product_id: str
    region: str
    period: str
    override_qty: int
    justification: str
    actor: str = "ai-copilot"


@router.post("/forecast-overrides")
async def create_forecast_override(body: ForecastOverrideCreate):
    sim = await get_sim("simulator")
    override_id = f"OV-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    row = {
        "Override_ID": override_id,
        "Product_ID": body.product_id,
        "Region": body.region,
        "Period": body.period,
        "Override_Qty": body.override_qty,
        "Justification": body.justification,
        "Created_At": _now_iso(),
        "Status": "Pending",
    }
    await append_row(sim, SCHEMA, "Forecast_Override", row)
    await emit_audit(body.actor, "create_forecast_override", override_id, row,
                     api_id="sfdc.forecast_override.create")
    return {"override_id": override_id}


# ---------------------------------------------------------------------------
# Phase 3 - CSM outreach task creation.
# ---------------------------------------------------------------------------

class CsmTaskCreate(BaseModel):
    account_id: str
    subject: str
    description: Optional[str] = None
    priority: str = "Medium"
    due_date: Optional[str] = None
    owner_user_id: Optional[str] = None
    outreach_type: Optional[str] = "csm_outreach"
    actor: str = "ai-copilot"


@router.post("/tasks")
async def create_csm_outreach_task(body: CsmTaskCreate):
    sim = await get_sim("simulator")
    task_id = f"TASK-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    row = {
        "Task_ID": task_id,
        "Account_ID": body.account_id,
        "Subject": body.subject,
        "Description": body.description,
        "Priority": body.priority,
        "Due_Date": body.due_date,
        "Owner_User_ID": body.owner_user_id,
        "Outreach_Type": body.outreach_type,
        "Status": "Open",
        "Created_Date": _now_iso(),
    }
    await append_row(sim, SCHEMA, "Task", row)
    await emit_audit(body.actor, "create_csm_outreach_task", task_id, row,
                     api_id="sfdc.task.create_csm_outreach")
    return {"task_id": task_id}
