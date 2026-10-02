from __future__ import annotations

from ..engine import load_table
from ..helpers import field, iso_days, match_any, next_ids, num, pick_rows
from . import register


@register("c360.churn-risk", "bind-accounts")
async def churn_bind(registry, spec, step, ctx):
    rows = await load_table(registry, "sfdc", "Account")
    chosen = pick_rows(rows, ctx["limit"], lambda r: match_any(r, ("Status", "Account_Status"), {"Active"})) or pick_rows(rows, ctx["limit"])
    return {
        "bindings": {
            "accounts": [field(r, "Account_ID", "Id") for r in chosen],
            "names": [field(r, "Name", "Account_Name") for r in chosen],
        },
        "planned": {"Account": len(chosen)},
        "message": f"Bound {len(chosen)} accounts",
        "rows": [],
    }


@register("c360.churn-risk", "sentiment")
async def churn_sentiment(registry, spec, step, ctx):
    n = min(ctx["limit"], max(len(ctx["bindings"].get("accounts") or []), 1))
    ids = next_ids("SCN-C360-BS-", n)
    rows = [{
        "Sentiment_ID": ids[i],
        "Brand": "StarFizz",
        "Product_Category": "Carbonated",
        "Platform": "Review_Site",
        "Sentiment_Score": -0.72,
        "Topic": "Availability",
        "Mention_Count": 1200 + i * 40,
        "Period": "2026-W36",
        "Account_ID": (ctx["bindings"].get("accounts") or [""])[i % max(len(ctx["bindings"].get("accounts") or [""]), 1)],
    } for i in range(n)]
    return {
        "bindings": {"sentiments": ids},
        "planned": {"Brand_Sentiment": n},
        "message": f"Plan {n} negative sentiment rows",
        "rows": [{"plugin": "external", "table": "Brand_Sentiment", "rows": rows}],
    }


@register("c360.churn-risk", "stalled-opps")
async def churn_opps(registry, spec, step, ctx):
    accounts = ctx["bindings"].get("accounts") or []
    n = min(ctx["limit"], max(len(accounts), 1))
    ids = next_ids("SCN-C360-OPP-", n)
    rows = [{
        "Opportunity_ID": ids[i],
        "Account_ID": accounts[i % len(accounts)] if accounts else "",
        "Opportunity_Name": f"Stalled renewal {i + 1}",
        "Amount": 18000 + i * 500,
        "Stage": "Negotiation",
        "Close_Date": iso_days(-20),
        "Region": "East",
        "Product_Category": "Carbonated",
        "Campaign_ID": "",
    } for i in range(n)]
    return {
        "bindings": {"opportunities": ids},
        "planned": {"Opportunity": n},
        "message": f"Plan {n} stalled opportunities",
        "rows": [{"plugin": "sfdc", "table": "Opportunity", "rows": rows}],
    }


@register("c360.wallet-gap", "bind-high-ar")
async def wallet_bind(registry, spec, step, ctx):
    invoices = await load_table(registry, "oracle", "Oracle_AR_Invoice")
    spend: dict[str, float] = {}
    for inv in invoices:
        cid = field(inv, "Customer_ID")
        if cid:
            spend[cid] = spend.get(cid, 0) + num(inv, "Amount")
    ranked = sorted(spend.items(), key=lambda kv: kv[1], reverse=True)[: ctx["limit"]]
    return {
        "bindings": {"accounts": [k for k, _ in ranked], "spend": [v for _, v in ranked]},
        "planned": {"Oracle_AR_Invoice": len(ranked)},
        "message": f"Bound {len(ranked)} high-AR customers",
        "rows": [],
    }


@register("c360.wallet-gap", "thin-lines")
async def wallet_lines(registry, spec, step, ctx):
    accounts = ctx["bindings"].get("accounts") or []
    opps = await load_table(registry, "sfdc", "Opportunity")
    mats = await load_table(registry, "sap", "Material_Master")
    material = field(mats[0], "Material_ID") if mats else "MAT-00001"
    n = min(ctx["limit"], max(len(accounts), 1))
    ids = next_ids("SCN-C360-OLI-", n)
    rows = []
    for i in range(n):
        opp = next((o for o in opps if field(o, "Account_ID") == accounts[i % len(accounts)]), opps[0] if opps else {})
        rows.append({
            "Line_Item_ID": ids[i],
            "Opportunity_ID": field(opp, "Opportunity_ID", "Id") or f"SCN-C360-OPP-{i+1:04d}",
            "Product_ID": material,
            "Product_Name": "Narrow assortment SKU",
            "Quantity": 20,
            "Unit_Price": 4.5,
            "Total_Price": 90,
            "Discount_Pct": 0,
            "Delivery_Priority": "Standard",
        })
    return {
        "bindings": {},
        "planned": {"Opportunity_Line_Item": n},
        "message": f"Plan {n} thin line items",
        "rows": [{"plugin": "sfdc", "table": "Opportunity_Line_Item", "rows": rows}],
    }
