"""Scenario builders for telco customer-intelligence overlays."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..engine import load_table
from ..helpers import field, iso_days, next_ids, pick_rows
from . import register


def _now() -> datetime:
    return datetime.now(timezone.utc)


@register("telco.usage-decline", "bind-decline")
async def usage_bind(registry, spec, step, ctx):
    rows = await load_table(registry, "bss", "Subscriber_Profile")
    chosen = pick_rows(rows, ctx["limit"]) or []
    return {
        "bindings": {
            "customers": [field(r, "customer_id") for r in chosen],
            "regions": [field(r, "region_code") for r in chosen],
        },
        "planned": {"Subscriber_Profile": len(chosen)},
        "message": f"Bound {len(chosen)} BSS subscribers",
        "rows": [],
    }


@register("telco.usage-decline", "outage")
async def usage_outage(registry, spec, step, ctx):
    customers = ctx["bindings"].get("customers") or []
    n = min(ctx["limit"], max(len(customers), 1))
    profiles = await load_table(registry, "nss", "Subscriber_Network_Profile")
    home = {field(r, "customer_id"): field(r, "home_cell_id") for r in profiles}
    ids = next_ids("SCN-TEL-ALM-", n)
    rows = []
    for i in range(n):
        cid = customers[i % len(customers)] if customers else ""
        rows.append(
            {
                "alarm_id": ids[i],
                "cell_id": home.get(cid) or f"CELL-{(i % 50) + 1:04d}",
                "site_id": f"SITE-{(i % 10) + 1:03d}",
                "severity": "critical",
                "alarm_type": "cell_down",
                "started_at": (_now() - timedelta(days=3)).isoformat(),
                "duration_hours": 6.5,
            }
        )
    return {
        "bindings": {"alarms": ids},
        "planned": {"Network_Alarm": n},
        "message": f"Plan {n} home-cell outage alarms",
        "rows": [{"plugin": "oss", "table": "Network_Alarm", "rows": rows}],
    }


@register("telco.usage-decline", "usage-drop")
async def usage_drop(registry, spec, step, ctx):
    customers = ctx["bindings"].get("customers") or []
    n = min(ctx["limit"], max(len(customers), 1))
    ids = next_ids("SCN-TEL-USG-", n)
    day = (_now().date() - timedelta(days=1)).isoformat()
    rows = [
        {
            "agg_id": ids[i],
            "customer_id": customers[i % len(customers)] if customers else "",
            "day": day,
            "data_gb": 0.4,
            "voice_mins": 3.0,
            "sms_count": 0,
        }
        for i in range(n)
    ]
    return {
        "bindings": {"usage": ids},
        "planned": {"Usage_Daily_Agg": n},
        "message": f"Plan {n} depressed usage days",
        "rows": [{"plugin": "nss", "table": "Usage_Daily_Agg", "rows": rows}],
    }


@register("telco.churn-portout", "bind-portout")
async def port_bind(registry, spec, step, ctx):
    rows = await load_table(registry, "bss", "Subscriber_Profile")
    chosen = pick_rows(rows, ctx["limit"]) or []
    return {
        "bindings": {"customers": [field(r, "customer_id") for r in chosen]},
        "planned": {"Subscriber_Profile": len(chosen)},
        "message": f"Bound {len(chosen)} port-out candidates",
        "rows": [],
    }


@register("telco.churn-portout", "mnp")
async def port_mnp(registry, spec, step, ctx):
    customers = ctx["bindings"].get("customers") or []
    n = min(ctx["limit"], max(len(customers), 1))
    ids = next_ids("SCN-TEL-MNP-", n)
    rows = [
        {
            "request_id": ids[i],
            "customer_id": customers[i % len(customers)] if customers else "",
            "requested_at": iso_days(-2),
            "status": "requested",
            "porting_code_issued": True,
        }
        for i in range(n)
    ]
    return {
        "bindings": {"mnp": ids},
        "planned": {"MNP_Port_Out_Request": n},
        "message": f"Plan {n} MNP requests",
        "rows": [{"plugin": "bss", "table": "MNP_Port_Out_Request", "rows": rows}],
    }


@register("telco.churn-portout", "care")
async def port_care(registry, spec, step, ctx):
    customers = ctx["bindings"].get("customers") or []
    n = min(ctx["limit"], max(len(customers), 1))
    ids = next_ids("SCN-TEL-CARE-", n)
    rows = [
        {
            "interaction_id": ids[i],
            "customer_id": customers[i % len(customers)] if customers else "",
            "channel": "call",
            "reason": "port_out",
            "resolved": False,
            "agent_id": "AGT-001",
            "opened_at": iso_days(-1),
        }
        for i in range(n)
    ]
    return {
        "bindings": {"care": ids},
        "planned": {"Care_Interaction": n},
        "message": f"Plan {n} care interactions",
        "rows": [{"plugin": "bss", "table": "Care_Interaction", "rows": rows}],
    }


@register("telco.upsell-ready", "bind-upsell")
async def upsell_bind(registry, spec, step, ctx):
    rows = await load_table(registry, "bss", "Subscriber_Profile")
    chosen = pick_rows(rows, ctx["limit"]) or []
    return {
        "bindings": {"customers": [field(r, "customer_id") for r in chosen]},
        "planned": {"Subscriber_Profile": len(chosen)},
        "message": f"Bound {len(chosen)} upsell candidates",
        "rows": [],
    }


@register("telco.upsell-ready", "offers")
async def upsell_offers(registry, spec, step, ctx):
    customers = ctx["bindings"].get("customers") or []
    n = min(ctx["limit"], max(len(customers), 1))
    ids = next_ids("SCN-TEL-OFR-", n)
    rows = [
        {
            "offer_event_id": ids[i],
            "customer_id": customers[i % len(customers)] if customers else "",
            "offer_id": f"OFR-{(i % 10) + 1:03d}",
            "offer_name": "Upgrade to 499",
            "sent_at": iso_days(-7),
            "accepted": False,
            "channel": "app",
        }
        for i in range(n)
    ]
    return {
        "bindings": {"offers": ids},
        "planned": {"Campaign_Offer": n},
        "message": f"Plan {n} ignored offers",
        "rows": [{"plugin": "bss", "table": "Campaign_Offer", "rows": rows}],
    }


@register("telco.upsell-ready", "app-intent")
async def upsell_app(registry, spec, step, ctx):
    customers = ctx["bindings"].get("customers") or []
    n = min(ctx["limit"], max(len(customers), 1))
    ids = next_ids("SCN-TEL-APP-", n)
    rows = [
        {
            "session_id": ids[i],
            "customer_id": customers[i % len(customers)] if customers else "",
            "page_type": "plan_compare",
            "session_at": iso_days(-3),
            "duration_sec": 180,
        }
        for i in range(n)
    ]
    return {
        "bindings": {"sessions": ids},
        "planned": {"App_Web_Session": n},
        "message": f"Plan {n} plan-compare sessions",
        "rows": [{"plugin": "bss", "table": "App_Web_Session", "rows": rows}],
    }


@register("telco.policy-throttle", "bind-policy")
async def policy_bind(registry, spec, step, ctx):
    rows = await load_table(registry, "bss", "Subscriber_Profile")
    chosen = pick_rows(rows, ctx["limit"]) or []
    return {
        "bindings": {"customers": [field(r, "customer_id") for r in chosen]},
        "planned": {"Subscriber_Profile": len(chosen)},
        "message": f"Bound {len(chosen)} policy-decline customers",
        "rows": [],
    }


@register("telco.policy-throttle", "throttle")
async def policy_throttle(registry, spec, step, ctx):
    customers = ctx["bindings"].get("customers") or []
    n = min(ctx["limit"], max(len(customers), 1))
    ids = next_ids("SCN-TEL-THR-", n)
    rows = [
        {
            "event_id": ids[i],
            "customer_id": customers[i % len(customers)] if customers else "",
            "policy_type": "fair_usage",
            "fair_usage_limit_hit": True,
            "occurred_at": iso_days(-5),
        }
        for i in range(n)
    ]
    return {
        "bindings": {"throttle": ids},
        "planned": {"Policy_Throttle_Event": n},
        "message": f"Plan {n} FUP throttle events",
        "rows": [{"plugin": "nss", "table": "Policy_Throttle_Event", "rows": rows}],
    }
