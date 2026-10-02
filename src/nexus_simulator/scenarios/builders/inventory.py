from __future__ import annotations

from ..engine import load_table
from ..helpers import field, iso_days, next_ids, pick_rows
from . import register


@register("io.expiry-stockout", "bind-materials")
async def bind(registry, spec, step, ctx):
    mats = pick_rows(await load_table(registry, "sap", "Material_Master"), ctx["limit"])
    plants = pick_rows(await load_table(registry, "sap", "Plant_Master"), 3)
    return {
        "bindings": {
            "materials": [field(r, "Material_ID") for r in mats],
            "plants": [field(r, "Plant_ID") for r in plants] or ["PLT-001"],
        },
        "planned": {"Material_Master": len(mats), "Plant_Master": len(plants)},
        "message": f"Bound {len(mats)} materials",
        "rows": [],
    }


@register("io.expiry-stockout", "expiry-batches")
async def batches(registry, spec, step, ctx):
    materials = ctx["bindings"].get("materials") or ["MAT-00001"]
    plants = ctx["bindings"].get("plants") or ["PLT-001"]
    n = min(ctx["limit"], len(materials) or 1)
    ids = next_ids("SCN-IO-BAT-", n)
    rows = [{
        "Batch_ID": ids[i],
        "Material_ID": materials[i % len(materials)],
        "Plant_ID": plants[i % len(plants)],
        "Production_Date": iso_days(-350),
        "Expiry_Date": iso_days(12 + i),
        "Quantity": 400 + i * 10,
        "Status": "Quality_Hold",
    } for i in range(n)]
    return {
        "bindings": {"batches": ids},
        "planned": {"Batch_Master": n},
        "message": f"Plan {n} near-expiry batches",
        "rows": [{"plugin": "sap", "table": "Batch_Master", "rows": rows}],
    }


@register("io.expiry-stockout", "low-stock")
async def low_stock(registry, spec, step, ctx):
    materials = ctx["bindings"].get("materials") or ["MAT-00001"]
    plants = ctx["bindings"].get("plants") or ["PLT-001"]
    batches = ctx["bindings"].get("batches") or [""]
    n = min(ctx["limit"], len(materials) or 1)
    ids = next_ids("SCN-IO-INV-", n)
    rows = [{
        "Inventory_ID": ids[i],
        "Material_ID": materials[i % len(materials)],
        "Plant_ID": plants[i % len(plants)],
        "Storage_Location": "SL-001",
        "Batch_ID": batches[i % len(batches)],
        "Quantity_On_Hand": 8 + i,
        "Quantity_Reserved": 6,
        "In_Transit_Qty": 0,
        "Valuation_Price": 2.4,
        "Unit_Value": 2.4,
        "Last_Count_Date": iso_days(-3),
    } for i in range(n)]
    return {
        "bindings": {},
        "planned": {"Inventory_Position": n},
        "message": f"Plan {n} low-stock positions",
        "rows": [{"plugin": "sap", "table": "Inventory_Position", "rows": rows}],
    }
