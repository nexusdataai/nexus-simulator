"""Roll CustomerGolden rows from BSS / NSS / OSS in-memory tables."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

SCHEMA_NAME = "telco_intelligence"
TABLE_NAME = "Telco_Customer_Gold_Data"
SERVER_NAME = "telco_golden_simulator"


def _index_by(rows: List[dict], key: str) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        out[str(r.get(key, ""))].append(r)
    return out


def _sum_field(rows: List[dict], field: str) -> float:
    return float(sum(float(r.get(field) or 0) for r in rows))


def _avg_field(rows: List[dict], field: str) -> float:
    if not rows:
        return 0.0
    return float(mean(float(r.get(field) or 0) for r in rows))


def map_oss_to_subscriber(
    home_cell_id: str,
    alarms: List[dict],
    maintenance: List[dict],
    config_changes: List[dict],
) -> Dict[str, Any]:
    cell_alarms = [a for a in alarms if a.get("cell_id") == home_cell_id]
    cell_maint = [m for m in maintenance if m.get("cell_id") == home_cell_id]
    cell_cfg = [c for c in config_changes if c.get("cell_id") == home_cell_id]
    return {
        "cell_outage_hours_30d": round(sum(float(a.get("duration_hours") or 0) for a in cell_alarms), 2),
        "cell_alarm_count_30d": len(cell_alarms),
        "maintenance_hours_30d": round(sum(float(m.get("duration_hours") or 0) for m in cell_maint), 2),
        "cell_config_change_flag": bool(cell_cfg),
    }


def rollup_golden(
    bss: Dict[str, List[dict]],
    nss: Dict[str, List[dict]],
    oss: Dict[str, List[dict]],
    *,
    tenant_id: str = "tenant-demo",
) -> List[dict]:
    profiles = {r["customer_id"]: r for r in bss.get("Subscriber_Profile", [])}
    contracts = _index_by(bss.get("Contract", []), "customer_id")
    invoices = _index_by(bss.get("Invoice", []), "customer_id")
    payments = _index_by(bss.get("Payment", []), "customer_id")
    recharges = _index_by(bss.get("Prepaid_Recharge", []), "customer_id")
    plan_hist = _index_by(bss.get("Subscription_Plan_History", []), "customer_id")
    care = _index_by(bss.get("Care_Interaction", []), "customer_id")
    disputes = _index_by(bss.get("Billing_Dispute", []), "customer_id")
    mnp = {r["customer_id"] for r in bss.get("MNP_Port_Out_Request", [])}
    sim_swaps = _index_by(bss.get("SIM_Swap_Event", []), "customer_id")
    offers = _index_by(bss.get("Campaign_Offer", []), "customer_id")
    sessions = _index_by(bss.get("App_Web_Session", []), "customer_id")

    usage = _index_by(nss.get("Usage_Daily_Agg", []), "customer_id")
    qoe = _index_by(nss.get("Subscriber_QoE_Daily", []), "customer_id")
    roaming = _index_by(nss.get("Roaming_Daily_Agg", []), "customer_id")
    attach = _index_by(nss.get("Attach_Failure_Event", []), "customer_id")
    volte = _index_by(nss.get("VoLTE_Failure_Event", []), "customer_id")
    throttle = _index_by(nss.get("Policy_Throttle_Event", []), "customer_id")
    net_prof = {r["customer_id"]: r for r in nss.get("Subscriber_Network_Profile", [])}

    alarms = oss.get("Network_Alarm", [])
    maintenance = oss.get("Planned_Maintenance", [])
    config_changes = oss.get("Config_Change", [])
    events = _index_by(oss.get("Network_Event", []), "cell_id")
    tickets = _index_by(oss.get("Trouble_Ticket", []), "cell_id")

    now = datetime.now(timezone.utc)
    snapshot = now.date().isoformat()
    rows: List[dict] = []

    # First pass for cohort usage medians.
    usage_by_cohort: Dict[str, List[float]] = defaultdict(list)
    prelim: List[dict] = []

    for cid, profile in profiles.items():
        u_rows = usage.get(cid, [])
        current = [r for r in u_rows if _day_ago(r.get("day"), snapshot) < 30]
        prior = [r for r in u_rows if 30 <= _day_ago(r.get("day"), snapshot) < 60]
        usage_current = _sum_field(current, "data_gb")
        usage_prior = _sum_field(prior, "data_gb")
        voice_current = _sum_field(current, "voice_mins")
        voice_prior = _sum_field(prior, "voice_mins")

        q_rows = qoe.get(cid, [])
        q_cur = [r for r in q_rows if _day_ago(r.get("day"), snapshot) < 30]
        q_pri = [r for r in q_rows if 30 <= _day_ago(r.get("day"), snapshot) < 60]
        qoe_current = _avg_field(q_cur, "qoe_score")
        qoe_prior = _avg_field(q_pri, "qoe_score")
        qoe_delta = round(qoe_current - qoe_prior, 2)

        home_cell = (net_prof.get(cid) or {}).get("home_cell_id") or ""
        oss_map = map_oss_to_subscriber(home_cell, alarms, maintenance, config_changes)

        inv = sorted(invoices.get(cid, []), key=lambda r: r.get("cycle_month") or "", reverse=True)
        bill_current = float(inv[0]["bill_amount"]) if inv else float(profile.get("monthly_spend") or 0)
        bill_prior = float(inv[1]["bill_amount"]) if len(inv) > 1 else bill_current
        bill_shock = bill_prior > 0 and bill_current > bill_prior * 1.35

        pays = payments.get(cid, [])
        failures = sum(1 for p in pays if p.get("status") == "failed")
        dunning = max((int(p.get("dunning_stage") or 0) for p in pays), default=0)

        recs = sorted(recharges.get(cid, []), key=lambda r: r.get("recharged_at") or "", reverse=True)
        recharge_gap: Optional[int] = None
        if profile.get("account_type") == "prepaid":
            if recs:
                recharge_gap = max(0, _day_ago((recs[0].get("recharged_at") or "")[:10], snapshot))
            else:
                recharge_gap = 45

        changes = plan_hist.get(cid, [])
        plan_change = "none"
        if changes:
            plan_change = changes[0].get("change_type") or "none"
            if plan_change == "addon_drop":
                plan_change = "downgrade"

        care_rows = care.get(cid, [])
        open_complaints = sum(1 for c in care_rows if not c.get("resolved")) + sum(
            1 for d in disputes.get(cid, []) if d.get("status") == "open"
        )

        thr = throttle.get(cid, [])
        fup = any(t.get("fair_usage_limit_hit") for t in thr)

        sess = sessions.get(cid, [])
        cancel_visits = sum(1 for s in sess if s.get("page_type") == "cancel")
        offer_rows = offers.get(cid, [])
        offers_sent = len(offer_rows)
        offers_accepted = sum(1 for o in offer_rows if o.get("accepted"))

        contract = (contracts.get(cid) or [None])[0]
        contract_end = contract.get("contract_end_date") if contract else None
        days_to_end = contract.get("days_to_contract_end") if contract else None

        network_issues = (
            len(attach.get(cid, []))
            + len(volte.get(cid, []))
            + len(events.get(home_cell, []))
            + len(tickets.get(home_cell, []))
        )
        network_flag = network_issues >= 3 or oss_map["cell_alarm_count_30d"] >= 3

        cohort_key = (
            f"{profile.get('segment')}|{profile.get('region_code')}|"
            f"{profile.get('account_type')}{profile.get('plan_tier')}"
        )
        usage_by_cohort[cohort_key].append(usage_current)

        prelim.append(
            {
                "customer_id": cid,
                "tenant_id": tenant_id,
                "snapshot_date": snapshot,
                "updated_at": now.isoformat(),
                "is_eligible": bool(profile.get("is_eligible", True)),
                "account_type": profile.get("account_type"),
                "segment": profile.get("segment"),
                "region_code": profile.get("region_code"),
                "tenure_months": int(profile.get("tenure_months") or 0),
                "plan_name": profile.get("plan_name"),
                "plan_tier": str(profile.get("plan_tier")),
                "plan_data_quota_gb": float(profile.get("plan_data_quota_gb") or 0),
                "monthly_spend": float(profile.get("monthly_spend") or 0),
                "spend": float(profile.get("monthly_spend") or 0),
                "contract_end_date": contract_end,
                "days_to_contract_end": days_to_end,
                "usage_current_gb": round(usage_current, 3),
                "usage_prior_gb": round(usage_prior, 3),
                "usage_current": round(usage_current, 3),
                "usage_prior": round(usage_prior, 3),
                "usage_voice_mins_current": round(voice_current, 1),
                "usage_voice_mins_prior": round(voice_prior, 1),
                "roaming_gb_30d": round(_sum_field(roaming.get(cid, []), "roaming_gb"), 3),
                "bill_amount_current": round(bill_current, 2),
                "bill_amount_prior": round(bill_prior, 2),
                "bill_shock_flag": bool(bill_shock),
                "recharge_gap_days": recharge_gap,
                "payment_failures_30d": failures,
                "dunning_stage": dunning,
                "plan_change_90d": plan_change,
                "network_issues_30d": network_issues,
                "network_issue_flag": bool(network_flag),
                "dropped_calls_30d": len(events.get(home_cell, [])),
                "volte_failures_30d": len(volte.get(cid, [])),
                "attach_failures_30d": len(attach.get(cid, [])),
                "qoe_score_current": round(qoe_current, 1),
                "qoe_score_prior": round(qoe_prior, 1),
                "qoe_delta": qoe_delta,
                "home_cell_id": home_cell,
                **oss_map,
                "throttling_events_30d": len(thr),
                "fair_usage_limit_hit_flag": bool(fup),
                "care_contacts_30d": len(care_rows),
                "open_complaints": open_complaints,
                "port_out_request_flag": cid in mnp,
                "sim_swap_events_30d": len(sim_swaps.get(cid, [])),
                "app_sessions_30d": len(sess),
                "cancellation_page_visits_30d": cancel_visits,
                "offers_sent_90d": offers_sent,
                "offers_accepted_90d": offers_accepted,
                "cohort_key": cohort_key,
            }
        )

    cohort_stats: Dict[str, tuple] = {}
    for key, vals in usage_by_cohort.items():
        if len(vals) < 2:
            cohort_stats[key] = (mean(vals) if vals else 0.0, 1.0)
        else:
            cohort_stats[key] = (mean(vals), max(pstdev(vals), 0.01))

    for row in prelim:
        mu, sigma = cohort_stats.get(row["cohort_key"], (row["usage_current_gb"], 1.0))
        row["usage_vs_cohort_zscore"] = round((row["usage_current_gb"] - mu) / sigma, 3)
        rows.append(row)

    return rows


def _day_ago(day: Optional[str], snapshot: str) -> int:
    if not day:
        return 999
    try:
        d0 = datetime.fromisoformat(snapshot).date()
        d1 = datetime.fromisoformat(str(day)[:10]).date()
        return (d0 - d1).days
    except ValueError:
        return 999
