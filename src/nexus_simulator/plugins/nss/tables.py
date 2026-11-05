"""NSS table builders — aggregated network/subscriber signals."""

from __future__ import annotations

from typing import Dict, List

from nexus_simulator.plugins.telco_seed_pools import TelcoPools


def build_nss_tables(pools: TelcoPools) -> Dict[str, List[dict]]:
    import random
    from datetime import datetime, timedelta, timezone

    rng = random.Random(pools.seed)
    hist = pools.history_days

    def pick(pool):
        return rng.choice(pool) if pool else ""

    def datetime_str(start_days_ago=365, end_days_ago=0):
        delta = rng.randint(end_days_ago, max(start_days_ago, end_days_ago + 1))
        dt = datetime.now(timezone.utc) - timedelta(days=delta, hours=rng.randint(0, 23))
        return dt.isoformat()

    def day_offset(days_ago):
        return (datetime.now(timezone.utc).date() - timedelta(days=days_ago)).isoformat()

    data: Dict[str, List[dict]] = {}

    usage: List[dict] = []
    qoe: List[dict] = []
    location: List[dict] = []
    roaming: List[dict] = []
    app_mix: List[dict] = []
    uid = 0

    # Sample location/QoE every day; usage every day (main cost).
    for cid in pools.customer_ids:
        home = pools.home_cell_by_customer[cid]
        work = pools.work_cell_by_customer[cid]
        base_gb = rng.uniform(0.2, 8.0)
        base_voice = rng.uniform(5, 40)
        decline = cid in pools.persona_usage_decline_network or cid in pools.persona_usage_decline_policy
        policy = cid in pools.persona_usage_decline_policy

        for days_ago in range(hist):
            day = day_offset(days_ago)
            # Decline kicks in over the last 30 days.
            factor = 1.0
            if decline and days_ago < 30:
                factor = rng.uniform(0.35, 0.75) if not policy else rng.uniform(0.2, 0.5)
            elif days_ago >= 30:
                factor = 1.0

            data_gb = round(base_gb * factor * rng.uniform(0.85, 1.15), 3)
            voice = round(base_voice * factor * rng.uniform(0.8, 1.2), 1)
            uid += 1
            usage.append(
                {
                    "agg_id": f"USG-{uid:08d}",
                    "customer_id": cid,
                    "day": day,
                    "data_gb": data_gb,
                    "voice_mins": voice,
                    "sms_count": rng.randint(0, 20),
                }
            )

            qoe_base = rng.uniform(78, 96)
            if cid in pools.persona_usage_decline_network and days_ago < 30:
                qoe_base -= rng.uniform(8, 25)
            qoe.append(
                {
                    "qoe_id": f"QOE-{uid:08d}",
                    "customer_id": cid,
                    "day": day,
                    "throughput_mbps": round(max(1.0, qoe_base / 10 + rng.uniform(-2, 2)), 2),
                    "latency_ms": round(rng.uniform(20, 80) + (40 if qoe_base < 70 else 0), 1),
                    "stall_ratio": round(rng.uniform(0, 0.05) + (0.08 if qoe_base < 70 else 0), 3),
                    "qoe_score": round(max(30.0, min(100.0, qoe_base)), 1),
                }
            )

            location.append(
                {
                    "loc_id": f"LOC-{uid:08d}",
                    "customer_id": cid,
                    "day": day,
                    "home_cell_id": home,
                    "work_cell_id": work,
                    "dominant_cell_id": home if rng.random() < 0.7 else work,
                }
            )

            if rng.random() < 0.08:
                roaming.append(
                    {
                        "roam_id": f"ROM-{uid:08d}",
                        "customer_id": cid,
                        "day": day,
                        "roaming_gb": round(rng.uniform(0.05, 2.0), 3),
                        "country": pick(["AE", "SG", "US", "GB", "TH"]),
                    }
                )

            if days_ago < 30 and rng.random() < 0.4:
                app_mix.append(
                    {
                        "mix_id": f"MIX-{uid:08d}",
                        "customer_id": cid,
                        "day": day,
                        "video_share": round(rng.uniform(0.2, 0.6), 2),
                        "social_share": round(rng.uniform(0.1, 0.4), 2),
                        "gaming_share": round(rng.uniform(0.0, 0.25), 2),
                    }
                )

    data["Usage_Daily_Agg"] = usage
    data["Subscriber_QoE_Daily"] = qoe
    data["Location_Daily"] = location
    data["Roaming_Daily_Agg"] = roaming
    data["App_Usage_Mix_Daily"] = app_mix

    profiles: List[dict] = []
    for cid in pools.customer_ids:
        profiles.append(
            {
                "customer_id": cid,
                "provisioning_status": "active",
                "service_barring": cid in pools.persona_port_out and rng.random() < 0.2,
                "roaming_enabled": rng.random() < 0.85,
                "volte_enabled": rng.random() < 0.9,
                "home_cell_id": pools.home_cell_by_customer[cid],
            }
        )
    data["Subscriber_Network_Profile"] = profiles

    attach: List[dict] = []
    volte: List[dict] = []
    throttle: List[dict] = []
    device: List[dict] = []
    ussd: List[dict] = []
    eid = 0
    for cid in pools.customer_ids:
        n_attach = rng.randint(3, 12) if cid in pools.persona_usage_decline_network else rng.randint(0, 2)
        for _ in range(n_attach):
            eid += 1
            attach.append(
                {
                    "event_id": f"ATT-{eid:07d}",
                    "customer_id": cid,
                    "cell_id": pools.home_cell_by_customer[cid],
                    "reject_cause": pick(["congestion", "auth_fail", "timeout", "radio"]),
                    "occurred_at": datetime_str(30, 0),
                }
            )
        n_volte = rng.randint(2, 8) if cid in pools.persona_usage_decline_network else rng.randint(0, 1)
        for _ in range(n_volte):
            eid += 1
            volte.append(
                {
                    "event_id": f"VOL-{eid:07d}",
                    "customer_id": cid,
                    "failure_type": pick(["setup_fail", "drop", "handover_fail"]),
                    "occurred_at": datetime_str(30, 0),
                }
            )
        n_throttle = rng.randint(5, 15) if cid in pools.persona_usage_decline_policy else (
            rng.randint(1, 3) if rng.random() < 0.1 else 0
        )
        for _ in range(n_throttle):
            eid += 1
            throttle.append(
                {
                    "event_id": f"THR-{eid:07d}",
                    "customer_id": cid,
                    "policy_type": "fair_usage" if cid in pools.persona_usage_decline_policy else "speed_cap",
                    "fair_usage_limit_hit": cid in pools.persona_usage_decline_policy,
                    "occurred_at": datetime_str(30, 0),
                }
            )
        if rng.random() < 0.12 or cid in pools.persona_upsell_ready:
            eid += 1
            device.append(
                {
                    "event_id": f"DEV-{eid:07d}",
                    "customer_id": cid,
                    "imei": f"{rng.randint(10**14, 10**15 - 1)}",
                    "five_g_capable": rng.random() < 0.55,
                    "handset_age_months": rng.randint(1, 48),
                    "changed_at": datetime_str(180, 1),
                }
            )
        if pools.customer_plan[cid][3] == "prepaid" and rng.random() < 0.25:
            eid += 1
            ussd.append(
                {
                    "event_id": f"USSD-{eid:07d}",
                    "customer_id": cid,
                    "menu": "balance_check",
                    "occurred_at": datetime_str(30, 0),
                }
            )

    data["Attach_Failure_Event"] = attach
    data["VoLTE_Failure_Event"] = volte
    data["Policy_Throttle_Event"] = throttle
    data["Device_Change_Event"] = device
    data["USSD_Balance_Check"] = ussd
    return data
