from __future__ import annotations

from ..engine import load_table
from ..helpers import field, iso_days, match_any, next_ids, pick_rows
from . import register


@register("df.promo-lift", "bind-campaign")
async def bind_campaign(registry, spec, step, ctx):
    rows = await load_table(registry, "sfdc", "Campaign")
    chosen = pick_rows(rows, 1, lambda r: match_any(r, ("Status",), {"Active"})) or pick_rows(rows, 1)
    mats = await load_table(registry, "sap", "Material_Master")
    return {
        "bindings": {
            "campaigns": [field(r, "Campaign_ID", "Id") for r in chosen],
            "materials": [field(r, "Material_ID") for r in mats[: ctx["limit"]]],
        },
        "planned": {"Campaign": len(chosen)},
        "message": f"Bound {len(chosen)} campaign(s)",
        "rows": [],
    }


@register("df.promo-lift", "overrides")
async def overrides(registry, spec, step, ctx):
    materials = ctx["bindings"].get("materials") or ["MAT-00001"]
    n = min(ctx["limit"], len(materials) or 1)
    ids = next_ids("SCN-DF-FC-", n)
    rows = [{
        "Forecast_ID": ids[i],
        "Product_ID": materials[i % len(materials)],
        "Region": "East",
        "Period": "2026-W38",
        "Override_Quantity": 18000 + i * 200,
        "Reason": "Promotion",
        "Justification": "Scenario overlay promo lift",
        "Submitted_By": "Scenario Engine",
    } for i in range(n)]
    return {
        "bindings": {},
        "planned": {"Forecast_Override": n},
        "message": f"Plan {n} forecast overrides",
        "rows": [{"plugin": "sfdc", "table": "Forecast_Override", "rows": rows}],
    }


@register("df.promo-lift", "signal")
async def signal(registry, spec, step, ctx):
    rows = [{
        "Signal_ID": "SCN-DF-MS-0001",
        "Source": "Social_Media",
        "Event_Type": "Demand_Surge",
        "Location": "Singapore",
        "Severity": "High",
        "Affected_Commodity": "Sugar",
        "Timestamp": iso_days(0),
        "Campaign_ID": (ctx["bindings"].get("campaigns") or [""])[0],
    }]
    return {
        "bindings": {},
        "planned": {"Market_Signal": 1},
        "message": "Plan 1 demand-side market signal",
        "rows": [{"plugin": "external", "table": "Market_Signal", "rows": rows}],
    }
