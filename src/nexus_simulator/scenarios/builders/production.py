from __future__ import annotations

from ..engine import load_table
from ..helpers import field, iso_days, next_ids, pick_rows
from . import register


@register("pq.yield-drop", "bind-orders")
async def bind(registry, spec, step, ctx):
    orders = pick_rows(await load_table(registry, "sap", "Production_Order"), ctx["limit"])
    return {
        "bindings": {
            "orders": [field(r, "Production_Order_ID") for r in orders],
            "materials": [field(r, "Material_ID") for r in orders],
        },
        "planned": {"Production_Order": len(orders)},
        "message": f"Bound {len(orders)} production orders",
        "rows": [],
    }


@register("pq.yield-drop", "failed-lots")
async def failed_lots(registry, spec, step, ctx):
    orders = ctx["bindings"].get("orders") or []
    materials = ctx["bindings"].get("materials") or ["MAT-00001"]
    n = min(ctx["limit"], max(len(orders), 1))
    ids = next_ids("SCN-PQ-IL-", n)
    rows = [{
        "Inspection_ID": ids[i],
        "Batch_ID": "",
        "Material_ID": materials[i % len(materials)],
        "Inspection_Type": "In_Process",
        "Inspection_Date": iso_days(-2),
        "Result": "Fail",
        "Inspector": "Scenario Engine",
        "Production_Order_ID": orders[i % len(orders)] if orders else "",
    } for i in range(n)]
    return {
        "bindings": {},
        "planned": {"Quality_Inspection_Lot": n},
        "message": f"Plan {n} failed inspection lots",
        "rows": [{"plugin": "sap", "table": "Quality_Inspection_Lot", "rows": rows}],
    }
