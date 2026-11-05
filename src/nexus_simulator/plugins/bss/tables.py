"""BSS table builders — pure functions over TelcoPools."""

from __future__ import annotations

from typing import Dict, List

from nexus_simulator.plugins.telco_seed_pools import (
    CARE_REASONS,
    OFFER_NAMES,
    PAGE_TYPES,
    VAS_NAMES,
    TelcoPools,
)


def build_bss_tables(pools: TelcoPools) -> Dict[str, List[dict]]:
    import random
    from datetime import datetime, timedelta, timezone

    rng = random.Random(pools.seed)

    def pick(pool):
        return rng.choice(pool) if pool else ""

    def date_str(start_days_ago=365, end_days_ago=0):
        delta = rng.randint(end_days_ago, max(start_days_ago, end_days_ago + 1))
        return (datetime.now(timezone.utc) - timedelta(days=delta)).strftime("%Y-%m-%d")

    def datetime_str(start_days_ago=365, end_days_ago=0):
        delta = rng.randint(end_days_ago, max(start_days_ago, end_days_ago + 1))
        dt = datetime.now(timezone.utc) - timedelta(days=delta, hours=rng.randint(0, 23))
        return dt.isoformat()

    def day_offset(days_ago):
        return (datetime.now(timezone.utc).date() - timedelta(days=days_ago)).isoformat()

    data: Dict[str, List[dict]] = {}

    profiles: List[dict] = []
    for cid in pools.customer_ids:
        plan_name, plan_tier, quota, acct, spend = pools.customer_plan[cid]
        profiles.append(
            {
                "customer_id": cid,
                "msisdn": f"91{9000000000 + int(cid.split('-')[-1])}",
                "account_type": acct,
                "segment": pools.customer_segment[cid],
                "region_code": pools.customer_region[cid],
                "tenure_months": pools.customer_tenure[cid],
                "plan_name": plan_name,
                "plan_tier": plan_tier,
                "plan_data_quota_gb": quota,
                "monthly_spend": spend,
                "status": "suspended" if cid in pools.persona_port_out and rng.random() < 0.3 else "active",
                "activated_at": date_str(pools.customer_tenure[cid] * 30, 30),
                "is_eligible": True,
            }
        )
    data["Subscriber_Profile"] = profiles

    plan_history: List[dict] = []
    hist_id = 0
    for cid in pools.customer_ids:
        if cid in pools.persona_upsell_ready and rng.random() < 0.4:
            hist_id += 1
            plan_history.append(
                {
                    "history_id": f"PH-{hist_id:06d}",
                    "customer_id": cid,
                    "from_plan": "Postpaid 399",
                    "to_plan": pools.customer_plan[cid][0],
                    "change_type": "upgrade",
                    "changed_at": datetime_str(90, 10),
                }
            )
        elif cid in pools.persona_usage_decline_network and rng.random() < 0.35:
            hist_id += 1
            plan_history.append(
                {
                    "history_id": f"PH-{hist_id:06d}",
                    "customer_id": cid,
                    "from_plan": "Postpaid 999",
                    "to_plan": pools.customer_plan[cid][0],
                    "change_type": "downgrade",
                    "changed_at": datetime_str(90, 5),
                }
            )
        elif rng.random() < 0.08:
            hist_id += 1
            plan_history.append(
                {
                    "history_id": f"PH-{hist_id:06d}",
                    "customer_id": cid,
                    "from_plan": pools.customer_plan[cid][0],
                    "to_plan": pools.customer_plan[cid][0],
                    "change_type": "addon_drop",
                    "changed_at": datetime_str(90, 1),
                }
            )
    data["Subscription_Plan_History"] = plan_history

    contracts: List[dict] = []
    for i, cid in enumerate(pools.customer_ids):
        if pools.customer_plan[cid][3] == "prepaid":
            continue
        days_left = rng.randint(5, 45) if cid in pools.persona_port_out else rng.randint(30, 700)
        contracts.append(
            {
                "contract_id": f"CTR-{i + 1:06d}",
                "customer_id": cid,
                "contract_end_date": _date_plus(pools, days_left),
                "days_to_contract_end": days_left,
                "device_instalments_left": rng.randint(0, 18),
                "status": "active",
            }
        )
    data["Contract"] = contracts

    invoices: List[dict] = []
    inv_id = 0
    for cid in pools.customer_ids:
        spend = pools.customer_plan[cid][4]
        for months_ago in (0, 1, 2):
            inv_id += 1
            shock = cid in pools.persona_anomaly and months_ago == 0
            amount = round(spend * (1.6 if shock else rng.uniform(0.9, 1.1)), 2)
            invoices.append(
                {
                    "invoice_id": f"INV-{inv_id:07d}",
                    "customer_id": cid,
                    "cycle_month": day_offset(months_ago * 30)[:7],
                    "bill_amount": amount,
                    "due_date": day_offset(months_ago * 30 - 10),
                    "status": "open" if months_ago == 0 else "paid",
                }
            )
    data["Invoice"] = invoices

    payments: List[dict] = []
    pay_id = 0
    for cid in pools.customer_ids:
        failures = 2 if cid in pools.persona_port_out else (1 if rng.random() < 0.05 else 0)
        for _ in range(failures):
            pay_id += 1
            payments.append(
                {
                    "payment_id": f"PAY-{pay_id:07d}",
                    "customer_id": cid,
                    "amount": pools.customer_plan[cid][4],
                    "status": "failed",
                    "paid_at": datetime_str(30, 1),
                    "dunning_stage": rng.randint(1, 3),
                }
            )
        if rng.random() < 0.7:
            pay_id += 1
            payments.append(
                {
                    "payment_id": f"PAY-{pay_id:07d}",
                    "customer_id": cid,
                    "amount": pools.customer_plan[cid][4],
                    "status": "ok",
                    "paid_at": datetime_str(40, 5),
                    "dunning_stage": 0,
                }
            )
    data["Payment"] = payments

    recharges: List[dict] = []
    rec_id = 0
    for cid in pools.customer_ids:
        if pools.customer_plan[cid][3] != "prepaid":
            continue
        gap = rng.randint(20, 45) if cid in pools.persona_usage_decline_network else rng.randint(1, 25)
        for k in range(rng.randint(1, 4)):
            rec_id += 1
            recharges.append(
                {
                    "recharge_id": f"RCH-{rec_id:07d}",
                    "customer_id": cid,
                    "amount": pools.customer_plan[cid][4],
                    "recharged_at": datetime_str(gap + k * 28, gap + k * 28 - 1),
                }
            )
    data["Prepaid_Recharge"] = recharges

    care: List[dict] = []
    care_id = 0
    for cid in pools.customer_ids:
        n = 0
        if cid in pools.persona_usage_decline_network:
            n = rng.randint(2, 6)
        elif cid in pools.persona_port_out:
            n = rng.randint(1, 4)
        elif rng.random() < 0.15:
            n = 1
        for _ in range(n):
            care_id += 1
            reason = (
                "network_quality"
                if cid in pools.persona_usage_decline_network
                else ("port_out" if cid in pools.persona_port_out else pick(CARE_REASONS))
            )
            care.append(
                {
                    "interaction_id": f"CARE-{care_id:07d}",
                    "customer_id": cid,
                    "channel": pick(["call", "chat", "app", "store"]),
                    "reason": reason,
                    "resolved": rng.random() < 0.55,
                    "agent_id": pick(pools.care_agent_ids),
                    "opened_at": datetime_str(30, 0),
                }
            )
    data["Care_Interaction"] = care

    disputes: List[dict] = []
    for i, cid in enumerate(c for c in pools.customer_ids if c in pools.persona_anomaly or rng.random() < 0.02):
        disputes.append(
            {
                "dispute_id": f"DSP-{i + 1:06d}",
                "customer_id": cid,
                "amount": round(rng.uniform(50, 800), 2),
                "status": pick(["open", "resolved", "open"]),
                "opened_at": datetime_str(60, 1),
            }
        )
    data["Billing_Dispute"] = disputes

    mnp: List[dict] = []
    for i, cid in enumerate(sorted(pools.persona_port_out)):
        mnp.append(
            {
                "request_id": f"MNP-{i + 1:06d}",
                "customer_id": cid,
                "requested_at": datetime_str(20, 0),
                "status": pick(["requested", "in_progress", "completed"]),
                "porting_code_issued": True,
            }
        )
    data["MNP_Port_Out_Request"] = mnp

    sim_swaps: List[dict] = []
    swap_id = 0
    for cid in pools.customer_ids:
        n = rng.randint(2, 4) if cid in pools.persona_anomaly else (1 if rng.random() < 0.03 else 0)
        for _ in range(n):
            swap_id += 1
            sim_swaps.append(
                {
                    "event_id": f"SIM-{swap_id:07d}",
                    "customer_id": cid,
                    "swapped_at": datetime_str(30, 0),
                    "reason": pick(["lost", "upgrade", "fraud_check", "voluntary"]),
                }
            )
    data["SIM_Swap_Event"] = sim_swaps

    campaigns: List[dict] = []
    camp_id = 0
    for cid in pools.customer_ids:
        n_sent = rng.randint(2, 5) if cid in pools.persona_upsell_ready else rng.randint(0, 2)
        for _ in range(n_sent):
            camp_id += 1
            accepted = cid in pools.persona_upsell_ready and rng.random() < 0.15
            campaigns.append(
                {
                    "offer_event_id": f"COE-{camp_id:07d}",
                    "customer_id": cid,
                    "offer_id": pick(pools.offer_ids),
                    "offer_name": pick(OFFER_NAMES),
                    "sent_at": datetime_str(90, 1),
                    "accepted": accepted,
                    "channel": pick(["sms", "app", "email", "call"]),
                }
            )
    data["Campaign_Offer"] = campaigns

    vas: List[dict] = []
    vas_id = 0
    for cid in pools.customer_ids:
        if rng.random() < 0.35:
            vas_id += 1
            cancelled = cid in pools.persona_usage_decline_network and rng.random() < 0.4
            vas.append(
                {
                    "vas_id": f"VAS-{vas_id:06d}",
                    "customer_id": cid,
                    "vas_name": pick(VAS_NAMES),
                    "status": "cancelled" if cancelled else "active",
                    "started_at": datetime_str(180, 30),
                    "cancelled_at": datetime_str(30, 1) if cancelled else None,
                }
            )
    data["VAS_Subscription"] = vas

    retail: List[dict] = []
    for i, cid in enumerate(c for c in pools.customer_ids if c in pools.persona_upsell_ready or rng.random() < 0.05):
        retail.append(
            {
                "visit_id": f"VIS-{i + 1:06d}",
                "customer_id": cid,
                "store_id": f"STR-{rng.randint(1, 80):03d}",
                "visited_at": datetime_str(60, 0),
                "reason": pick(["sim_replace", "plan_upgrade", "device", "payment"]),
            }
        )
    data["Retail_Visit"] = retail

    sessions: List[dict] = []
    sess_id = 0
    for cid in pools.customer_ids:
        n = rng.randint(3, 12)
        if cid in pools.persona_port_out:
            n += rng.randint(2, 5)
        if cid in pools.persona_upsell_ready:
            n += rng.randint(1, 4)
        for _ in range(n):
            sess_id += 1
            page = "cancel" if cid in pools.persona_port_out and rng.random() < 0.35 else (
                "plan_compare" if cid in pools.persona_upsell_ready and rng.random() < 0.4 else pick(PAGE_TYPES)
            )
            sessions.append(
                {
                    "session_id": f"APP-{sess_id:07d}",
                    "customer_id": cid,
                    "page_type": page,
                    "session_at": datetime_str(30, 0),
                    "duration_sec": rng.randint(10, 600),
                }
            )
    data["App_Web_Session"] = sessions

    return data


def _date_plus(_pools: TelcoPools, days_ahead: int) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc).date() + timedelta(days=days_ahead)).isoformat()
