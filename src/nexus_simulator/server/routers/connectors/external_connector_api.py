"""External connector API - notifications, audit, alerts, outcomes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body
from pydantic import BaseModel

from ...connector_runtime import (
    append_row, emit_audit, get_sim, _now_iso,
)

router = APIRouter(prefix="/api/v1/simulator/external", tags=["External Connector"])

SCHEMA = "external_sources"


class DunningNoticeCreate(BaseModel):
    invoice_id: str
    customer_id: str
    level: str = "level_1"
    actor: str = "ai-copilot"


@router.post("/dunning-notices")
async def create_dunning_notice(body: DunningNoticeCreate):
    sim = await get_sim("external")
    notice_id = f"DUN-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    row = {
        "Notice_ID": notice_id,
        "Invoice_ID": body.invoice_id,
        "Customer_ID": body.customer_id,
        "Level": body.level,
        "Sent_At": _now_iso(),
        "Channel": "email",
    }
    await append_row(sim, SCHEMA, "Dunning_Notice", row)
    await emit_audit(body.actor, "send_dunning_notice", notice_id, row,
                     api_id="external.dunning_notice.create")
    return {"notice_id": notice_id}


class AuditEventCreate(BaseModel):
    actor: str = "ai-copilot"
    verb: str
    target: str
    payload: Optional[Dict[str, Any]] = None


@router.post("/audit-events")
async def create_audit_event(body: AuditEventCreate):
    event_id = await emit_audit(body.actor, body.verb, body.target, body.payload,
                                 api_id="external.audit_event.create")
    return {"event_id": event_id}


class AlertCreate(BaseModel):
    prefix: str
    severity: str = "medium"
    title: str
    message: str
    entity_id: Optional[str] = None
    actor: str = "ai-copilot"


@router.post("/alerts")
async def create_alert(body: AlertCreate):
    sim = await get_sim("external")
    alert_id = f"ALERT-{body.prefix}-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    row = {
        "alert_id": alert_id,
        "severity": body.severity,
        "title": body.title,
        "message": body.message,
        "entity_id": body.entity_id,
        "created_at": _now_iso(),
    }
    await append_row(sim, SCHEMA, f"{body.prefix}_Alert", row)
    await emit_audit(body.actor, "create_alert", alert_id, row, api_id="external.alert.create")
    return {"alert_id": alert_id}


class OutcomeWrite(BaseModel):
    prefix: str
    action_id: str
    kpi_name: str
    kpi_before: float
    kpi_after: float
    currency: str = "USD"
    actor: str = "ai-copilot"


@router.post("/outcomes")
async def create_outcome(body: OutcomeWrite):
    sim = await get_sim("external")
    outcome_id = str(uuid.uuid4())
    row = {
        "outcome_id": outcome_id,
        "action_id": body.action_id,
        "kpi_name": body.kpi_name,
        "kpi_before": body.kpi_before,
        "kpi_after": body.kpi_after,
        "delta_value": round(body.kpi_after - body.kpi_before, 4),
        "currency": body.currency,
        "measured_at": _now_iso(),
    }
    await append_row(sim, SCHEMA, f"{body.prefix}_Outcome_Tracker", row)
    await emit_audit(body.actor, "create_outcome", outcome_id, row,
                     api_id="external.outcome.write")
    return {"outcome_id": outcome_id}


# ---------------------------------------------------------------------------
# Phase 3 - notification channels (WhatsApp / Email / Slack).
#
# These route to simulator endpoints in dev; real channel wiring is out
# of scope for v1 (plan section 13). Each handler appends one row per
# campaign batch + an Audit_Event so the diagnostics panel can verify
# delivery without hitting real channels.
# ---------------------------------------------------------------------------

class WhatsAppRecipient(BaseModel):
    customer_id: str
    phone: str
    vars: Optional[Dict[str, Any]] = None


class WhatsAppCampaignSend(BaseModel):
    template_id: str
    recipients: List[WhatsAppRecipient]
    campaign_id: Optional[str] = None
    message_body: Optional[str] = None
    actor: str = "ai-copilot"


@router.post("/whatsapp")
async def send_whatsapp_campaign(body: WhatsAppCampaignSend):
    sim = await get_sim("external")
    campaign_id = body.campaign_id or (
        f"WAC-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    )
    row = {
        "campaign_id": campaign_id,
        "channel": "whatsapp",
        "template_id": body.template_id,
        "queued": len(body.recipients),
        "recipient_ids": [r.customer_id for r in body.recipients],
        "message_body": body.message_body,
        "queued_at": _now_iso(),
        "status": "queued",
    }
    await append_row(sim, SCHEMA, "WhatsApp_Campaign_Send", row)
    await emit_audit(body.actor, "send_whatsapp_campaign", campaign_id, row,
                     api_id="external.whatsapp.send_campaign")
    return {"campaign_id": campaign_id, "queued": len(body.recipients)}


class EmailRecipient(BaseModel):
    customer_id: str
    email: str
    vars: Optional[Dict[str, Any]] = None


class EmailCampaignSend(BaseModel):
    subject: str
    recipients: List[EmailRecipient]
    campaign_id: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    actor: str = "ai-copilot"


@router.post("/email")
async def send_email_campaign(body: EmailCampaignSend):
    sim = await get_sim("external")
    campaign_id = body.campaign_id or (
        f"EC-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    )
    row = {
        "campaign_id": campaign_id,
        "channel": "email",
        "subject": body.subject,
        "queued": len(body.recipients),
        "recipient_ids": [r.customer_id for r in body.recipients],
        "queued_at": _now_iso(),
        "status": "queued",
    }
    await append_row(sim, SCHEMA, "Email_Campaign_Send", row)
    await emit_audit(body.actor, "send_email_campaign", campaign_id, row,
                     api_id="external.email.send_campaign")
    return {"campaign_id": campaign_id, "queued": len(body.recipients)}


class SlackPostMessage(BaseModel):
    channel: str
    message: str
    title: Optional[str] = None
    severity: str = "info"
    actor: str = "ai-copilot"


@router.post("/slack")
async def post_slack_message(body: SlackPostMessage):
    sim = await get_sim("external")
    message_ts = f"{datetime.now().timestamp():.6f}"
    row = {
        "message_ts": message_ts,
        "channel": body.channel,
        "title": body.title,
        "message": body.message,
        "severity": body.severity,
        "posted_at": _now_iso(),
    }
    await append_row(sim, SCHEMA, "Slack_Message", row)
    await emit_audit(body.actor, "post_slack_message", body.channel, row,
                     api_id="external.slack.post_message")
    return {"message_ts": message_ts}


# Catalogue endpoint - returns the registered ConnectorAPISpec list -----

@router.get("/_catalogue")
async def list_connector_apis(target_system: Optional[str] = None):
    """Return the registered connector API specs (for the UI / diagnostic)."""
    return {"items": [], "targetSystem": target_system}
