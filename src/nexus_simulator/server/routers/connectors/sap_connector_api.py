"""SAP S/4HANA connector API - simulator-backed write surface."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Path
from pydantic import BaseModel

from ...connector_runtime import (
    append_row, emit_audit, get_sim, update_one, _now_iso,
)

router = APIRouter(prefix="/api/v1/simulator/sap", tags=["SAP Connector"])

SCHEMA = "sap_s4hana"


class DeliveryUpdate(BaseModel):
    priority: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    actor: str = "ai-copilot"


@router.patch("/deliveries/{delivery_id}")
async def update_delivery(delivery_id: str = Path(...), body: DeliveryUpdate = Body(...)):
    sim = await get_sim("sap")
    patch: Dict[str, Any] = {}
    if body.priority is not None:
        patch["Priority"] = body.priority
    if body.status is not None:
        patch["Status"] = body.status
    if body.reason:
        patch["Update_Reason"] = body.reason
    patch["Last_Updated"] = _now_iso()
    previous, _ = await update_one(sim, SCHEMA, "Delivery_Document", "Delivery_ID", delivery_id, patch)
    await emit_audit(body.actor, "update_delivery", delivery_id,
                     {"previous_priority": previous.get("Priority"), **patch},
                     api_id="sap.delivery.expedite")
    return {"delivery_id": delivery_id, **patch}


class WarehouseTransferCreate(BaseModel):
    from_plant: str
    to_plant: str
    material_id: str
    quantity: int
    reason: Optional[str] = None
    actor: str = "ai-copilot"


@router.post("/warehouse-transfers")
async def create_warehouse_transfer(body: WarehouseTransferCreate):
    sim = await get_sim("sap")
    transfer_id = f"WT-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    row = {
        "Transfer_ID": transfer_id,
        "From_Plant": body.from_plant,
        "To_Plant": body.to_plant,
        "Material_ID": body.material_id,
        "Quantity": body.quantity,
        "Request_Date": _now_iso(),
        "Status": "Planned",
        "Reason": body.reason,
    }
    await append_row(sim, SCHEMA, "Warehouse_Transfer", row)
    await emit_audit(body.actor, "create_warehouse_transfer", transfer_id, row,
                     api_id="sap.warehouse_transfer.create")
    return {"transfer_id": transfer_id, "status": "Planned"}


class BatchHold(BaseModel):
    hold: bool
    reason: Optional[str] = None
    actor: str = "ai-copilot"


@router.patch("/batches/{batch_id}/hold")
async def hold_batch(batch_id: str = Path(...), body: BatchHold = Body(...)):
    sim = await get_sim("sap")
    new_status = "Quality_Hold" if body.hold else "Released"
    _, _ = await update_one(sim, SCHEMA, "Batch_Master", "Batch_ID", batch_id,
                             {"Status": new_status, "Hold_Reason": body.reason, "Last_Updated": _now_iso()})
    await emit_audit(body.actor, "hold_batch", batch_id,
                     {"hold": body.hold, "reason": body.reason}, api_id="sap.batch.hold")
    return {"batch_id": batch_id, "status": new_status}


class ProductionOrderUpdate(BaseModel):
    status: Optional[str] = None
    quantity: Optional[int] = None
    shift_id: Optional[str] = None
    actor: str = "ai-copilot"


@router.patch("/production-orders/{production_order_id}")
async def update_production_order(production_order_id: str = Path(...), body: ProductionOrderUpdate = Body(...)):
    sim = await get_sim("sap")
    patch: Dict[str, Any] = {}
    if body.status is not None: patch["Status"] = body.status
    if body.quantity is not None: patch["Qty_Planned"] = body.quantity
    if body.shift_id is not None: patch["Shift"] = body.shift_id
    patch["Last_Updated"] = _now_iso()
    _, _ = await update_one(sim, SCHEMA, "Production_Order", "Order_ID", production_order_id, patch)
    await emit_audit(body.actor, "update_production_order", production_order_id, patch,
                     api_id="sap.production_order.update")
    return {"production_order_id": production_order_id, **patch}


class MaterialPlantUpdate(BaseModel):
    plant_id: str
    safety_stock: Optional[int] = None
    reorder_point: Optional[int] = None
    actor: str = "ai-copilot"


@router.patch("/material-plants/{material_id}")
async def update_material_plant(material_id: str = Path(...), body: MaterialPlantUpdate = Body(...)):
    """
    Material_Plant has a composite key (Material_ID, Plant_ID). We update
    the row matching both.
    """
    sim = await get_sim("sap")
    rows = await sim._get_table_data(SCHEMA, "Material_Plant")
    rows = list(rows or [])
    target_idx = next(
        (i for i, r in enumerate(rows)
         if str(r.get("Material_ID")) == material_id and str(r.get("Plant_ID")) == body.plant_id),
        -1,
    )
    if target_idx < 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=404,
                            detail=f"Material_Plant not found: {material_id}/{body.plant_id}")
    patch: Dict[str, Any] = {}
    if body.safety_stock is not None: patch["Safety_Stock"] = body.safety_stock
    if body.reorder_point is not None: patch["Reorder_Point"] = body.reorder_point
    patch["Last_Updated"] = _now_iso()
    rows[target_idx] = {**rows[target_idx], **patch}
    await sim.write_table(SCHEMA, "Material_Plant", rows)
    await emit_audit(body.actor, "update_material_plant", f"{material_id}/{body.plant_id}", patch,
                     api_id="sap.material_plant.reorder")
    return {"material_id": material_id, "plant_id": body.plant_id, **patch}


# ---------------------------------------------------------------------------
# Phase 3 - CAPA + Predictive maintenance.
# ---------------------------------------------------------------------------

class CAPAOpen(BaseModel):
    subject: str
    severity: str = "medium"
    trigger_event_id: Optional[str] = None
    owner: Optional[str] = None
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[str] = None
    actor: str = "ai-copilot"


@router.post("/capa")
async def open_capa(body: CAPAOpen):
    sim = await get_sim("sap")
    capa_id = f"CAPA-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    row = {
        "CAPA_ID": capa_id,
        "Subject": body.subject,
        "Severity": body.severity,
        "Trigger_Event_ID": body.trigger_event_id,
        "Owner": body.owner,
        "Linked_Entity_Type": body.linked_entity_type,
        "Linked_Entity_ID": body.linked_entity_id,
        "Status": "Open",
        "Opened_At": _now_iso(),
    }
    await append_row(sim, SCHEMA, "CAPA", row)
    await emit_audit(body.actor, "open_capa", capa_id, row,
                     api_id="sap.capa.open")
    return {"capa_id": capa_id, "status": "Open"}


class MaintenanceSchedule(BaseModel):
    equipment_id: str
    scheduled_for: str
    maintenance_type: str = "Preventive"
    estimated_hours: Optional[float] = None
    priority: Optional[str] = "Medium"
    reason: Optional[str] = None
    actor: str = "ai-copilot"


@router.post("/maintenance-orders")
async def schedule_maintenance(body: MaintenanceSchedule):
    sim = await get_sim("sap")
    mo_id = f"MO-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
    row = {
        "Maintenance_Order_ID": mo_id,
        "Equipment_ID": body.equipment_id,
        "Scheduled_For": body.scheduled_for,
        "Maintenance_Type": body.maintenance_type,
        "Estimated_Hours": body.estimated_hours,
        "Priority": body.priority,
        "Reason": body.reason,
        "Status": "Scheduled",
        "Created_At": _now_iso(),
    }
    await append_row(sim, SCHEMA, "Maintenance_Order", row)
    await emit_audit(body.actor, "schedule_maintenance", mo_id, row,
                     api_id="sap.maintenance.schedule")
    return {"maintenance_order_id": mo_id}
