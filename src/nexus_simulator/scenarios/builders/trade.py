from __future__ import annotations

from ..engine import load_table
from ..helpers import field, iso_days, match_any, next_ids, num, pick_rows
from . import register


@register("trade.quote-leakage", "bind-book")
async def bind(registry, spec, step, ctx):
    books = pick_rows(await load_table(registry, "tpm", "Price_Book"), 1, lambda r: match_any(r, ("Status",), {"Active"})) or pick_rows(await load_table(registry, "tpm", "Price_Book"), 1)
    entries = await load_table(registry, "tpm", "Price_Book_Entry")
    book_id = field(books[0], "Price_Book_ID") if books else ""
    book_entries = [e for e in entries if not book_id or field(e, "Price_Book_ID") == book_id][: ctx["limit"]]
    accounts = pick_rows(await load_table(registry, "sfdc", "Account"), ctx["limit"])
    return {
        "bindings": {
            "priceBooks": [book_id] if book_id else [],
            "offerings": [field(e, "Offering_ID") for e in book_entries],
            "floors": [num(e, "Floor_Price", default=5) for e in book_entries] or [5],
            "accounts": [field(a, "Account_ID", "Id") for a in accounts],
        },
        "planned": {"Price_Book": len(books), "Price_Book_Entry": len(book_entries)},
        "message": f"Bound price book {book_id}",
        "rows": [],
    }


@register("trade.quote-leakage", "leak-quotes")
async def leak_quotes(registry, spec, step, ctx):
    offerings = ctx["bindings"].get("offerings") or [""]
    floors = ctx["bindings"].get("floors") or [5]
    accounts = ctx["bindings"].get("accounts") or [""]
    n = min(ctx["limit"], 5)
    qids = next_ids("SCN-TRD-Q-", n)
    lids = next_ids("SCN-TRD-QL-", n)
    headers, lines = [], []
    for i in range(n):
        floor = floors[i % len(floors)]
        unit = round(floor * 0.85, 2)
        headers.append({
            "Quote_ID": qids[i],
            "Account_ID": accounts[i % len(accounts)],
            "Owner_ID": "USER-001",
            "Status": "Submitted",
            "Validity_Date": iso_days(21),
            "Total_Net": unit * 200,
            "Margin_Pct": 9.5,
            "Discount_Pct": 22.0,
            "Approval_Chain_JSON": "[]",
            "Created_At": iso_days(-2),
            "Submitted_At": iso_days(-1),
        })
        lines.append({
            "Line_ID": lids[i],
            "Quote_ID": qids[i],
            "Offering_ID": offerings[i % len(offerings)],
            "Qty": 200,
            "Unit_Price": unit,
            "Discount_Pct": 22.0,
            "Promotion_ID": "",
            "Listing_Fee": 0,
            "Slotting_Fee": 0,
            "Margin_Pct_Line": 9.5,
        })
    return {
        "bindings": {},
        "planned": {"Quote_Header": n, "Quote_Line": n},
        "message": f"Plan {n} below-floor quotes",
        "rows": [
            {"plugin": "tpm", "table": "Quote_Header", "rows": headers},
            {"plugin": "tpm", "table": "Quote_Line", "rows": lines},
        ],
    }
