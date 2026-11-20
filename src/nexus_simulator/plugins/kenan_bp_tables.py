"""Kenan BP 12–style billing tables (synthetic rows tied to TelcoPools)."""

from __future__ import annotations

from typing import Dict, List

from nexus_simulator.plugins.telco_seed_pools import TelcoPools


def build_kenan_bp_tables(pools: TelcoPools) -> Dict[str, List[dict]]:
    import random
    from datetime import datetime, timedelta, timezone

    rng = random.Random(pools.seed + 91)

    def pick(pool):
        return rng.choice(pool) if pool else ""

    def dt(days_ago: int) -> str:
        return (
            datetime.now(timezone.utc) - timedelta(days=days_ago, hours=rng.randint(0, 12))
        ).isoformat()

    def acct_no(cid: str) -> int:
        return 3_000_000 + int(cid.split("-")[-1])

    def subscr_no(cid: str) -> int:
        return 5_000_000 + int(cid.split("-")[-1])

    data: Dict[str, List[dict]] = {}

    cmf: List[dict] = []
    ext_map: List[dict] = []
    for cid in pools.customer_ids:
        plan_name, _, _, acct_type, spend = pools.customer_plan[cid]
        ano = acct_no(cid)
        cmf.append(
            {
                "account_no": ano,
                "parent_id": None,
                "bill_period": pick(["01", "05", "15"]),
                "account_type": acct_type,
                "bill_lname": f"Customer {cid}",
                "bill_address1": f"{pick(pools.customer_region[cid])} district",
                "currency_code": "SAR",
                "pay_method": pick(["invoice", "card", "direct_debit"]),
                "monthly_spend": spend,
                "plan_name": plan_name,
                "status": "active",
            }
        )
        ext_map.append(
            {
                "external_id": cid,
                "account_no": ano,
                "id_type": "CRM_CUSTOMER",
                "active_date": dt(pools.customer_tenure[cid] * 30),
            }
        )
    data["CMF"] = cmf
    data["EXTERNAL_ID_ACCT_MAP"] = ext_map

    service: List[dict] = []
    product: List[dict] = []
    for cid in pools.customer_ids:
        msisdn = f"91{9000000000 + int(cid.split('-')[-1])}"
        plan_name, _, quota, _, _ = pools.customer_plan[cid]
        sno = subscr_no(cid)
        service.append(
            {
                "subscr_no": sno,
                "account_no": acct_no(cid),
                "msisdn": msisdn,
                "active_date": dt(pools.customer_tenure[cid] * 30),
                "inactive_date": None,
                "status": "active",
            }
        )
        product.append(
            {
                "subscr_no": sno,
                "product_id": f"PO-{plan_name.replace(' ', '-')[:20]}",
                "offer_name": plan_name,
                "data_quota_gb": quota,
                "status": "active",
            }
        )
    data["SERVICE"] = service
    data["PRODUCT"] = product

    data["RATE_RC"] = [
        {"rate_id": "RC-POST-299", "usage_type": "MRC", "amount": 299.0, "currency": "SAR", "recurrence": "monthly"},
        {"rate_id": "RC-POST-499", "usage_type": "MRC", "amount": 499.0, "currency": "SAR", "recurrence": "monthly"},
        {"rate_id": "RC-ADD-STREAM", "usage_type": "MRC", "amount": 30.0, "currency": "SAR", "recurrence": "monthly"},
    ]
    data["RATE_USAGE"] = [
        {"rate_id": "U-DATA-1GB", "usage_type": "DATA", "amount": 0.05, "unit": "MB", "currency": "SAR"},
        {"rate_id": "U-VOICE-MIN", "usage_type": "VOICE", "amount": 0.12, "unit": "MIN", "currency": "SAR"},
        {"rate_id": "U-SMS", "usage_type": "SMS", "amount": 0.08, "unit": "EA", "currency": "SAR"},
    ]

    cdr: List[dict] = []
    cid0 = 0
    for cid in pools.customer_ids[: min(25, len(pools.customer_ids))]:
        for _ in range(rng.randint(3, 8)):
            cid0 += 1
            cdr.append(
                {
                    "cdr_id": f"CDR-{cid0:08d}",
                    "subscr_no": subscr_no(cid),
                    "usage_type": pick(["DATA", "VOICE", "SMS"]),
                    "rated_amount": round(rng.uniform(0.05, 45.0), 4),
                    "billable": True,
                    "start_time": dt(rng.randint(1, 30)),
                    "source_system": pick(
                        ["Packet gateway (SGW / PGW / SMF / UPF)", "IMS / VoLTE / VoWiFi", "SMSC / USSD"]
                    ),
                }
            )
    data["CDR_DATA"] = cdr

    invoices: List[dict] = []
    details: List[dict] = []
    inv = 0
    for cid in pools.customer_ids:
        spend = pools.customer_plan[cid][4]
        for month in (0, 1):
            inv += 1
            iid = f"BINV-{inv:07d}"
            amount = round(spend * rng.uniform(0.92, 1.08), 2)
            invoices.append(
                {
                    "bill_invoice_id": iid,
                    "account_no": acct_no(cid),
                    "bill_period": (datetime.now(timezone.utc).month - month) or 12,
                    "total_amount": amount,
                    "status": "open" if month == 0 else "closed",
                    "bill_date": dt(month * 30 + 2),
                }
            )
            details.append(
                {
                    "bill_invoice_id": iid,
                    "line_no": 1,
                    "charge_type": "MRC",
                    "amount": amount,
                    "description": pools.customer_plan[cid][0],
                }
            )
    data["BILL_INVOICE"] = invoices
    data["BILL_INVOICE_DETAIL"] = details

    bmf: List[dict] = []
    pay: List[dict] = []
    pid = 0
    for cid in pools.customer_ids:
        if rng.random() < 0.85:
            pid += 1
            amt = pools.customer_plan[cid][4]
            bmf.append(
                {
                    "bmf_id": f"BMF-{pid:07d}",
                    "account_no": acct_no(cid),
                    "source_type": pick([1, 2, 3]),
                    "amount": amt,
                    "posted_at": dt(rng.randint(1, 45)),
                }
            )
            pay.append(
                {
                    "payment_trans_id": f"PAYT-{pid:07d}",
                    "account_no": acct_no(cid),
                    "amount": amt,
                    "status": pick(["approved", "approved", "declined"]),
                    "trans_date": dt(rng.randint(1, 45)),
                }
            )
    data["BMF"] = bmf
    data["PAYMENT_TRANS"] = pay

    adj: List[dict] = []
    for i, cid in enumerate(c for c in pools.customer_ids if c in pools.persona_anomaly or rng.random() < 0.03):
        adj.append(
            {
                "adj_id": f"ADJ-{i + 1:06d}",
                "account_no": acct_no(cid),
                "amount": round(rng.uniform(-200, -10), 2),
                "reason": pick(["goodwill", "billing_dispute", "proration"]),
                "posted_at": dt(rng.randint(1, 60)),
            }
        )
    data["ADJ"] = adj

    return data