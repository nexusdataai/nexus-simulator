from __future__ import annotations

from ..engine import load_table
from ..helpers import field, iso_days, match_any, next_ids, pick_rows
from . import register


@register("sourcing.dual-vs-single", "bind-rfx")
async def bind(registry, spec, step, ctx):
    events = pick_rows(await load_table(registry, "sourcing", "RFx_Event"), 1, lambda r: match_any(r, ("Status",), {"Open", "Evaluating"})) or pick_rows(await load_table(registry, "sourcing", "RFx_Event"), 1)
    vendors = pick_rows(await load_table(registry, "sap", "Vendor_Master"), 3)
    return {
        "bindings": {
            "events": [field(r, "Event_ID") for r in events],
            "vendors": [field(r, "Vendor_ID") for r in vendors],
        },
        "planned": {"RFx_Event": len(events)},
        "message": f"Bound RFx {field(events[0], 'Event_ID') if events else ''}",
        "rows": [],
    }


@register("sourcing.dual-vs-single", "quotes")
async def quotes(registry, spec, step, ctx):
    event = (ctx["bindings"].get("events") or [""])[0]
    vendors = ctx["bindings"].get("vendors") or ["VEN-00001", "VEN-00002"]
    n = min(3, max(len(vendors), 1))
    ids = next_ids("SCN-SRC-VQ-", n)
    rows = []
    for i in range(n):
        rows.append({
            "Vendor_Quote_ID": ids[i],
            "Event_ID": event,
            "Vendor_ID": vendors[i % len(vendors)],
            "Submitted_At": iso_days(-1),
            "Total_Value": 220000 if i == 0 else 140000 + i * 8000,
            "Validity_Date": iso_days(30),
            "Status": "Submitted",
            "Award_Split_Pct": 100 if i == 0 else 50,
        })
    return {
        "bindings": {},
        "planned": {"Vendor_Quote": n},
        "message": f"Plan {n} competing quotes (single vs dual)",
        "rows": [{"plugin": "sourcing", "table": "Vendor_Quote", "rows": rows}],
    }
