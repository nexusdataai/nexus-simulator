from __future__ import annotations

from ..engine import load_table
from ..helpers import field, iso_days, next_ids, pick_rows
from . import register


@register("esg.intensity-spike", "bind-plants")
async def bind(registry, spec, step, ctx):
    plants = pick_rows(await load_table(registry, "sap", "Plant_Master"), 3)
    mats = pick_rows(await load_table(registry, "sap", "Material_Master"), ctx["limit"])
    return {
        "bindings": {
            "plants": [field(r, "Plant_ID") for r in plants] or ["PLT-001"],
            "materials": [field(r, "Material_ID") for r in mats],
        },
        "planned": {"Plant_Master": len(plants), "Material_Master": len(mats)},
        "message": f"Bound {len(plants)} plants",
        "rows": [],
    }


@register("esg.intensity-spike", "extra-orders")
async def extra_orders(registry, spec, step, ctx):
    plants = ctx["bindings"].get("plants") or ["PLT-001"]
    materials = ctx["bindings"].get("materials") or ["MAT-00001"]
    n = min(ctx["limit"], 6)
    ids = next_ids("SCN-ESG-PO-", n)
    rows = [{
        "Production_Order_ID": ids[i],
        "Material_ID": materials[i % len(materials)],
        "Plant_ID": plants[i % len(plants)],
        "Production_Line": "PL-001",
        "Quantity": 40000 + i * 1000,
        "Start_Date": iso_days(-10),
        "End_Date": iso_days(5),
        "Status": "In_Progress",
        "Yield_Pct": 88.0,
    } for i in range(n)]
    return {
        "bindings": {},
        "planned": {"Production_Order": n},
        "message": f"Plan {n} high-volume production orders",
        "rows": [{"plugin": "sap", "table": "Production_Order", "rows": rows}],
    }


@register("esg.intensity-spike", "report")
async def report(registry, spec, step, ctx):
    rows = [{
        "Report_ID": "SCN-ESG-SR-0001",
        "Document_Path": "/sustainability/scenario_intensity_spike.pdf",
        "Report_Type": "Quarterly",
        "Period": "2026-Q3",
        "KPIs_Extracted": "CO2 emissions, Water usage, Energy consumption",
        "Targets": "30% reduction by 2030",
        "Actuals": "Intensity +18% vs prior quarter",
        "Framework": "GRI",
        "Plant_ID": (ctx["bindings"].get("plants") or [""])[0],
    }]
    return {
        "bindings": {},
        "planned": {"Sustainability_Report": 1},
        "message": "Plan 1 intensity sustainability report",
        "rows": [{"plugin": "external", "table": "Sustainability_Report", "rows": rows}],
    }
