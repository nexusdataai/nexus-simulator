from __future__ import annotations

from ..engine import load_table
from ..helpers import field, iso_days, next_ids, pick_rows
from . import register


@register("scr.single-source", "bind-vendor")
async def bind(registry, spec, step, ctx):
    vendors = pick_rows(await load_table(registry, "sap", "Vendor_Master"), 1)
    mats = pick_rows(await load_table(registry, "sap", "Material_Master"), ctx["limit"])
    return {
        "bindings": {
            "vendors": [field(r, "Vendor_ID") for r in vendors],
            "materials": [field(r, "Material_ID") for r in mats],
        },
        "planned": {"Vendor_Master": len(vendors)},
        "message": f"Bound vendor {field(vendors[0], 'Vendor_ID') if vendors else ''}",
        "rows": [],
    }


@register("scr.single-source", "concentrated-pos")
async def pos(registry, spec, step, ctx):
    vendor = (ctx["bindings"].get("vendors") or ["VEN-00001"])[0]
    materials = ctx["bindings"].get("materials") or ["MAT-00001"]
    n = min(ctx["limit"], 8)
    ids = next_ids("SCN-SCR-PO-", n)
    rows = [{
        "PO_ID": ids[i],
        "Vendor_ID": vendor,
        "Material_ID": materials[i % len(materials)],
        "Plant_ID": "PLT-001",
        "Quantity": 2000 + i * 100,
        "Unit_Price": 1.8,
        "Total_Amount": round((2000 + i * 100) * 1.8, 2),
        "PO_Date": iso_days(-20 + i),
        "Status": "Open",
        "Contract_ID": "CTR-001",
        "Currency": "SGD",
    } for i in range(n)]
    return {
        "bindings": {},
        "planned": {"Oracle_Purchase_Order": n},
        "message": f"Plan {n} POs on {vendor}",
        "rows": [{"plugin": "oracle", "table": "Oracle_Purchase_Order", "rows": rows}],
    }


@register("scr.single-source", "signal")
async def signal(registry, spec, step, ctx):
    rows = [{
        "Signal_ID": "SCN-SCR-MS-0001",
        "Source": "News",
        "Event_Type": "Port_Closure",
        "Location": "Singapore",
        "Severity": "Critical",
        "Affected_Commodity": "Packaging",
        "Timestamp": iso_days(0),
        "Vendor_ID": (ctx["bindings"].get("vendors") or [""])[0],
    }]
    return {
        "bindings": {},
        "planned": {"Market_Signal": 1},
        "message": "Plan 1 critical disruption signal",
        "rows": [{"plugin": "external", "table": "Market_Signal", "rows": rows}],
    }
