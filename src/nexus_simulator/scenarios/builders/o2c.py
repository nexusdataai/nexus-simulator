from __future__ import annotations

from typing import Any

from ..engine import load_table
from ..helpers import field, iso_days, match_any, next_ids, num, pick_rows
from . import register


async def _bind_closed_won(registry, ctx) -> dict[str, Any]:
    rows = await load_table(registry, "sfdc", "Opportunity")
    won = pick_rows(
        rows,
        ctx["limit"],
        lambda r: match_any(r, ("Stage", "StageName"), {"Closed_Won", "Closed Won", "Fulfilled"}),
    )
    if not won:
        won = pick_rows(rows, ctx["limit"])
    accounts = [field(r, "Account_ID", "AccountId") for r in won if field(r, "Account_ID", "AccountId")]
    materials = []
    try:
        lines = await load_table(registry, "sfdc", "Opportunity_Line_Item")
        opp_ids = {field(r, "Opportunity_ID", "Id") for r in won}
        for line in lines:
            if field(line, "Opportunity_ID") in opp_ids and field(line, "Product_ID", "Material_ID"):
                materials.append(field(line, "Product_ID", "Material_ID"))
    except Exception:
        materials = []
    if not materials:
        sap_mats = await load_table(registry, "sap", "Material_Master")
        materials = [field(r, "Material_ID") for r in sap_mats[: ctx["limit"]] if field(r, "Material_ID")]
    return {
        "bindings": {
            "opportunities": [field(r, "Opportunity_ID", "Id") for r in won],
            "accounts": accounts,
            "materials": materials[: ctx["limit"]],
            "amounts": [num(r, "Amount", "TotalPrice", default=5000) for r in won],
        },
        "planned": {"Opportunity": len(won)},
        "message": f"Bound {len(won)} opportunities",
        "rows": [],
    }


@register("o2c.revenue-leakage", "bind-accounts")
async def leakage_bind(registry, spec, step, ctx):
    return await _bind_closed_won(registry, ctx)


@register("o2c.revenue-leakage", "deliveries")
async def leakage_deliveries(registry, spec, step, ctx):
    accounts = ctx["bindings"].get("accounts") or []
    opps = ctx["bindings"].get("opportunities") or []
    materials = ctx["bindings"].get("materials") or ["MAT-00001"]
    n = min(ctx["limit"], max(len(accounts), 1))
    del_ids = next_ids(f"SCN-O2C-DEL-", n)
    shp_ids = next_ids(f"SCN-O2C-SHP-", n)
    deliveries, shipments = [], []
    for i in range(n):
        deliveries.append({
            "Delivery_ID": del_ids[i],
            "Sales_Order_ID": opps[i % len(opps)] if opps else "",
            "Ship_To_Account_ID": accounts[i % len(accounts)] if accounts else "",
            "Material_ID": materials[i % len(materials)],
            "Quantity": 120 + i * 10,
            "Delivery_Date": iso_days(-14 + i),
            "Status": "Delivered",
            "Priority": "Standard",
        })
        shipments.append({
            "Shipment_ID": shp_ids[i],
            "Carrier": "Local_Fleet",
            "Origin_Plant": "PLT-001",
            "Destination": "Singapore",
            "Departure_Date": iso_days(-16 + i),
            "Arrival_Date": iso_days(-14 + i),
            "Status": "Delivered",
            "Weight_KG": 800 + i * 20,
        })
    return {
        "bindings": {"deliveries": del_ids},
        "planned": {"Delivery_Document": n, "Shipment": n},
        "message": f"Plan {n} unmatched deliveries",
        "rows": [
            {"plugin": "sap", "table": "Delivery_Document", "rows": deliveries},
            {"plugin": "sap", "table": "Shipment", "rows": shipments},
        ],
    }


@register("o2c.revenue-leakage", "underbill")
async def leakage_underbill(registry, spec, step, ctx):
    accounts = ctx["bindings"].get("accounts") or []
    deliveries = ctx["bindings"].get("deliveries") or []
    amounts = ctx["bindings"].get("amounts") or [4000]
    n = min(max(len(deliveries) // 2, 1), ctx["limit"])
    inv_ids = next_ids("SCN-O2C-INV-", n)
    rows = []
    for i in range(n):
        rows.append({
            "Invoice_ID": inv_ids[i],
            "Customer_ID": accounts[i % len(accounts)] if accounts else "",
            "Invoice_Date": iso_days(-10 + i),
            "Due_Date": iso_days(20 + i),
            "Amount": round(amounts[i % len(amounts)] * 0.7, 2),
            "Status": "Open",
            "Linked_Delivery_ID": deliveries[i] if i < len(deliveries) else "",
            "Currency": "SGD",
        })
    return {
        "bindings": {"invoices": inv_ids},
        "planned": {"Oracle_AR_Invoice": n},
        "message": f"Plan {n} under-billed invoices; remaining deliveries stay unmatched",
        "rows": [{"plugin": "oracle", "table": "Oracle_AR_Invoice", "rows": rows}],
    }


@register("o2c.past-due-ar", "bind-customers")
async def past_due_bind(registry, spec, step, ctx):
    rows = await load_table(registry, "oracle", "Oracle_AR_Customer")
    chosen = pick_rows(rows, ctx["limit"], lambda r: match_any(r, ("Status",), {"Active"})) or pick_rows(rows, ctx["limit"])
    return {
        "bindings": {"customers": [field(r, "Customer_ID") for r in chosen]},
        "planned": {"Oracle_AR_Customer": len(chosen)},
        "message": f"Bound {len(chosen)} AR customers",
        "rows": [],
    }


@register("o2c.past-due-ar", "overdue-invoices")
async def past_due_invoices(registry, spec, step, ctx):
    customers = ctx["bindings"].get("customers") or []
    n = min(ctx["limit"], max(len(customers), 1))
    inv_ids = next_ids("SCN-O2C-DUE-", n)
    rows = []
    for i in range(n):
        rows.append({
            "Invoice_ID": inv_ids[i],
            "Customer_ID": customers[i % len(customers)] if customers else "",
            "Invoice_Date": iso_days(-90 - i),
            "Due_Date": iso_days(-60 - i),
            "Amount": 8500 + i * 250,
            "Status": "Overdue",
            "Linked_Delivery_ID": "",
            "Currency": "SGD",
        })
    return {
        "bindings": {"overdueInvoices": inv_ids},
        "planned": {"Oracle_AR_Invoice": n},
        "message": f"Plan {n} invoices past 60 days",
        "rows": [{"plugin": "oracle", "table": "Oracle_AR_Invoice", "rows": rows}],
    }
