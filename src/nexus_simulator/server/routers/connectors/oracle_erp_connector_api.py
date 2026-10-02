"""
Oracle ERP connector API - simulator-backed write surface.

Each endpoint mirrors the spec in
``services/control_plane/connector_apis.py`` and is the place a ReAct
tool ultimately POSTs/PATCHes to. Every mutation is followed by an
audit-event append.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Path
from pydantic import BaseModel, Field
from loguru import logger

from ...connector_runtime import (
    append_row, emit_audit, get_sim, update_one, _now_iso,
)

router = APIRouter(prefix="/api/v1/simulator/oracle-erp", tags=["Oracle ERP Connector"])
oracle_logger = logger.bind(component="oracle-erp-connector")

SCHEMA = "oracle_erp"


class InvoiceStatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None
    actor: str = "ai-copilot"


@router.patch("/invoices/{invoice_id}")
async def update_invoice_status(invoice_id: str = Path(...), body: InvoiceStatusUpdate = Body(...)):
    sim = await get_sim("oracle")
    patch: Dict[str, Any] = {"Status": body.status}
    if body.reason:
        patch["Update_Reason"] = body.reason
    patch["Last_Updated"] = _now_iso()
    previous, new_row = await update_one(sim, SCHEMA, "Oracle_AR_Invoice", "Invoice_ID", invoice_id, patch)
    await emit_audit(body.actor, "update_invoice_status", invoice_id,
                     {"previous_status": previous.get("Status"), "status": body.status, "reason": body.reason},
                     api_id="oracle.invoice.status.set")
    return {
        "invoice_id": invoice_id,
        "previous_status": previous.get("Status"),
        "status": body.status,
    }


class CreditNoteCreate(BaseModel):
    customer_id: str
    invoice_id: str
    amount: float
    reason: str
    actor: str = "ai-copilot"


@router.post("/credit-notes")
async def create_credit_note(body: CreditNoteCreate):
    sim = await get_sim("oracle")
    credit_note_id = f"CN-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    row = {
        "Credit_Note_ID": credit_note_id,
        "Customer_ID": body.customer_id,
        "Invoice_ID": body.invoice_id,
        "Amount": body.amount,
        "Reason": body.reason,
        "Date": _now_iso(),
        "Status": "Issued",
    }
    await append_row(sim, SCHEMA, "Oracle_AR_Credit_Note", row)
    await emit_audit(body.actor, "create_credit_note", credit_note_id,
                     row, api_id="oracle.credit_note.create")
    return {"credit_note_id": credit_note_id, "amount": body.amount}


class PaymentRecord(BaseModel):
    customer_id: str
    invoice_id: str
    amount: float
    payment_method: str = "Wire"
    actor: str = "ai-copilot"


@router.post("/payments")
async def record_payment(body: PaymentRecord):
    sim = await get_sim("oracle")
    payment_id = f"PAY-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    row = {
        "Payment_ID": payment_id,
        "Invoice_ID": body.invoice_id,
        "Customer_ID": body.customer_id,
        "Amount": body.amount,
        "Payment_Date": _now_iso(),
        "Payment_Method": body.payment_method,
        "Applied_Flag": True,
    }
    await append_row(sim, SCHEMA, "Oracle_AR_Payment", row)
    await emit_audit(body.actor, "record_payment", payment_id, row, api_id="oracle.payment.record")
    return {"payment_id": payment_id}


class EarlyPayDiscount(BaseModel):
    discount_pct: float
    expires_in_days: int = 7
    actor: str = "ai-copilot"


@router.patch("/invoices/{invoice_id}/early-pay-discount")
async def offer_early_pay_discount(invoice_id: str = Path(...), body: EarlyPayDiscount = Body(...)):
    sim = await get_sim("oracle")
    patch = {
        "Early_Pay_Discount_Pct": body.discount_pct,
        "Discount_Expires_At": _now_iso(),
        "Discount_Window_Days": body.expires_in_days,
    }
    _, _ = await update_one(sim, SCHEMA, "Oracle_AR_Invoice", "Invoice_ID", invoice_id, patch)
    await emit_audit(body.actor, "offer_early_pay_discount", invoice_id, patch,
                     api_id="oracle.invoice.discount.offer")
    return {"invoice_id": invoice_id, "discount_pct": body.discount_pct}


class CustomerTermsUpdate(BaseModel):
    payment_terms: str
    actor: str = "ai-copilot"


@router.patch("/ar-customers/{customer_id}")
async def set_customer_terms(customer_id: str = Path(...), body: CustomerTermsUpdate = Body(...)):
    sim = await get_sim("oracle")
    previous, _ = await update_one(sim, SCHEMA, "Oracle_AR_Customer", "Customer_ID", customer_id,
                                    {"Payment_Terms": body.payment_terms, "Terms_Updated": _now_iso()})
    await emit_audit(body.actor, "update_customer_terms", customer_id,
                     {"previous": previous.get("Payment_Terms"), "new": body.payment_terms},
                     api_id="oracle.customer.terms.set")
    return {"customer_id": customer_id, "payment_terms": body.payment_terms}


class PurchaseOrderUpdate(BaseModel):
    status: str
    actor: str = "ai-copilot"


@router.patch("/purchase-orders/{po_id}")
async def update_purchase_order(po_id: str = Path(...), body: PurchaseOrderUpdate = Body(...)):
    sim = await get_sim("oracle")
    _, _ = await update_one(sim, SCHEMA, "Oracle_Purchase_Order", "PO_ID", po_id, {"Status": body.status})
    await emit_audit(body.actor, "update_purchase_order", po_id, {"status": body.status},
                     api_id="oracle.purchase_order.approve")
    return {"po_id": po_id, "status": body.status}


# ---------------------------------------------------------------------------
# Phase 3 - retain-risky / liquidation / supplier-block endpoints.
# ---------------------------------------------------------------------------

class PromotionCreate(BaseModel):
    name: str
    discount_pct: float
    promo_code: Optional[str] = None
    applies_to: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Targeting filter (e.g. {'segment': 'at_risk', 'tier': 'Bronze'}).",
    )
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    max_redemptions: Optional[int] = None
    actor: str = "ai-copilot"


@router.post("/promotions")
async def create_promotion(body: PromotionCreate):
    sim = await get_sim("oracle")
    promo_id = f"PROMO-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    promo_code = body.promo_code or promo_id.lower()
    row = {
        "Promo_ID": promo_id,
        "Promo_Code": promo_code,
        "Name": body.name,
        "Discount_Pct": body.discount_pct,
        "Applies_To": body.applies_to or {},
        "Valid_From": body.valid_from or _now_iso(),
        "Valid_To": body.valid_to,
        "Max_Redemptions": body.max_redemptions,
        "Status": "Active",
        "Created_At": _now_iso(),
    }
    await append_row(sim, SCHEMA, "Oracle_AR_Promotion", row)
    await emit_audit(body.actor, "create_promotion", promo_id, row,
                     api_id="oracle.promotion.create")
    return {"promo_id": promo_id, "promo_code": promo_code}


class KitComponent(BaseModel):
    sku: str
    quantity: int = 1


class KitCreate(BaseModel):
    name: str
    components: list[KitComponent]
    kit_sku: Optional[str] = None
    list_price: Optional[float] = None
    discount_pct: Optional[float] = None
    actor: str = "ai-copilot"


@router.post("/kits")
async def create_kit(body: KitCreate):
    sim = await get_sim("oracle")
    kit_id = f"KIT-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    kit_sku = body.kit_sku or kit_id.lower()
    row = {
        "Kit_ID": kit_id,
        "Kit_SKU": kit_sku,
        "Name": body.name,
        "Components": [c.model_dump() for c in body.components],
        "List_Price": body.list_price,
        "Discount_Pct": body.discount_pct,
        "Status": "Active",
        "Created_At": _now_iso(),
    }
    await append_row(sim, SCHEMA, "Oracle_Kit", row)
    await emit_audit(body.actor, "create_kit", kit_id, row,
                     api_id="oracle.kit.create")
    return {"kit_id": kit_id, "kit_sku": kit_sku}


class SupplierBlockUpdate(BaseModel):
    block: bool
    reason: Optional[str] = None
    block_until: Optional[str] = None
    actor: str = "ai-copilot"


@router.patch("/suppliers/{supplier_id}")
async def block_supplier(supplier_id: str = Path(...), body: SupplierBlockUpdate = Body(...)):
    sim = await get_sim("oracle")
    new_status = "Blocked" if body.block else "Active"
    patch = {
        "Status": new_status,
        "Block_Reason": body.reason,
        "Block_Until": body.block_until,
        "Last_Updated": _now_iso(),
    }
    previous, _ = await update_one(sim, SCHEMA, "Oracle_Supplier", "Supplier_ID", supplier_id, patch)
    await emit_audit(body.actor, "block_supplier", supplier_id,
                     {"previous_status": previous.get("Status"), **patch},
                     api_id="oracle.supplier.block")
    return {"supplier_id": supplier_id, "status": new_status}
