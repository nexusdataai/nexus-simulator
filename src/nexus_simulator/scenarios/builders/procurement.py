from __future__ import annotations

from ..engine import load_table
from ..helpers import field, iso_days, next_ids, pick_rows
from . import register


@register("pa.maverick-spend", "bind-vendors")
async def bind(registry, spec, step, ctx):
    vendors = pick_rows(await load_table(registry, "sap", "Vendor_Master"), ctx["limit"])
    mats = pick_rows(await load_table(registry, "sap", "Material_Master"), ctx["limit"])
    return {
        "bindings": {
            "vendors": [field(r, "Vendor_ID") for r in vendors],
            "materials": [field(r, "Material_ID") for r in mats],
        },
        "planned": {"Vendor_Master": len(vendors)},
        "message": f"Bound {len(vendors)} vendors",
        "rows": [],
    }


@register("pa.maverick-spend", "orphan-pos")
async def orphan_pos(registry, spec, step, ctx):
    vendors = ctx["bindings"].get("vendors") or ["VEN-00001"]
    materials = ctx["bindings"].get("materials") or ["MAT-00001"]
    n = min(ctx["limit"], max(len(vendors), 1))
    ids = next_ids("SCN-PA-PO-", n)
    rows = [{
        "PO_ID": ids[i],
        "Vendor_ID": vendors[i % len(vendors)],
        "Material_ID": materials[i % len(materials)],
        "Plant_ID": "PLT-001",
        "Quantity": 400 + i * 25,
        "Unit_Price": 3.2,
        "Total_Amount": round((400 + i * 25) * 3.2, 2),
        "PO_Date": iso_days(-8),
        "Status": "Open",
        "Contract_ID": "",
        "Currency": "SGD",
    } for i in range(n)]
    return {
        "bindings": {},
        "planned": {"Oracle_Purchase_Order": n},
        "message": f"Plan {n} POs with empty Contract_ID",
        "rows": [{"plugin": "oracle", "table": "Oracle_Purchase_Order", "rows": rows}],
    }
