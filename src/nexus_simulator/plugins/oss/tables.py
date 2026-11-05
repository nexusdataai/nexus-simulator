"""OSS table builders — cell/site network operations data."""

from __future__ import annotations

from typing import Dict, List, Set

from nexus_simulator.plugins.telco_seed_pools import TelcoPools


def build_oss_tables(pools: TelcoPools) -> Dict[str, List[dict]]:
    import random
    from datetime import datetime, timedelta, timezone

    rng = random.Random(pools.seed)
    hist = min(pools.history_days, 45)

    def pick(pool):
        return rng.choice(pool) if pool else ""

    def datetime_str(start_days_ago=365, end_days_ago=0):
        delta = rng.randint(end_days_ago, max(start_days_ago, end_days_ago + 1))
        dt = datetime.now(timezone.utc) - timedelta(days=delta, hours=rng.randint(0, 23))
        return dt.isoformat()

    def day_offset(days_ago):
        return (datetime.now(timezone.utc).date() - timedelta(days=days_ago)).isoformat()

    data: Dict[str, List[dict]] = {}

    # Cells that need elevated issues (home cells of network-decline personas).
    hot_cells: Set[str] = {
        pools.home_cell_by_customer[cid] for cid in pools.persona_usage_decline_network
    }

    sites: List[dict] = []
    for i, sid in enumerate(pools.site_ids):
        sites.append(
            {
                "site_id": sid,
                "region_code": pick(list(set(pools.cell_region.values()))),
                "technology": pick(["LTE", "LTE", "NR", "UMTS"]),
                "status": "active",
            }
        )
    # map cells to sites
    cell_sites: List[dict] = []
    for i, cid in enumerate(pools.cell_ids):
        cell_sites.append(
            {
                "cell_id": cid,
                "site_id": pools.site_ids[i % len(pools.site_ids)],
                "region_code": pools.cell_region[cid],
                "technology": pick(["LTE", "LTE", "NR"]),
                "latitude": round(18.0 + rng.random() * 10, 5),
                "longitude": round(72.0 + rng.random() * 10, 5),
                "status": "active",
            }
        )
    data["Cell_Site"] = cell_sites

    alarms: List[dict] = []
    kpi: List[dict] = []
    events: List[dict] = []
    config: List[dict] = []
    maint: List[dict] = []
    tickets: List[dict] = []
    backhaul: List[dict] = []
    aid = 0

    cell_to_site = {
        cid: pools.site_ids[i % len(pools.site_ids)] for i, cid in enumerate(pools.cell_ids)
    }

    for cell_id in pools.cell_ids:
        hot = cell_id in hot_cells
        site_id = cell_to_site[cell_id]
        for days_ago in range(hist):
            day = day_offset(days_ago)
            drop = rng.uniform(0.5, 2.0)
            congestion = rng.uniform(0.05, 0.25)
            if hot and days_ago < 30:
                drop = rng.uniform(3.0, 12.0)
                congestion = rng.uniform(0.4, 0.9)
            kpi.append(
                {
                    "kpi_id": f"KPI-{cell_id}-{days_ago}",
                    "cell_id": cell_id,
                    "day": day,
                    "drop_rate_pct": round(drop, 2),
                    "congestion_ratio": round(congestion, 3),
                    "prb_util_pct": round(min(99.0, congestion * 100 + rng.uniform(10, 30)), 1),
                    "throughput_mbps": round(max(2.0, 80 - congestion * 60 + rng.uniform(-5, 5)), 1),
                }
            )

        n_alarms = rng.randint(4, 14) if hot else rng.randint(0, 2)
        for _ in range(n_alarms):
            aid += 1
            duration = rng.uniform(0.5, 8.0) if hot else rng.uniform(0.1, 1.5)
            alarms.append(
                {
                    "alarm_id": f"ALM-{aid:07d}",
                    "cell_id": cell_id,
                    "site_id": site_id,
                    "severity": pick(["critical", "major", "minor"] if hot else ["minor", "warning"]),
                    "alarm_type": pick(["cell_down", "high_drop", "interference", "power"]),
                    "started_at": datetime_str(30 if hot else 60, 0),
                    "duration_hours": round(duration, 2),
                }
            )

        if hot or rng.random() < 0.05:
            aid += 1
            events.append(
                {
                    "event_id": f"NEV-{aid:07d}",
                    "cell_id": cell_id,
                    "event_type": "dropped_call_cluster" if hot else "brief_outage",
                    "occurred_at": datetime_str(30, 0),
                    "impacted_calls": rng.randint(20, 200) if hot else rng.randint(1, 15),
                }
            )

        if hot and rng.random() < 0.35:
            aid += 1
            config.append(
                {
                    "change_id": f"CFG-{aid:07d}",
                    "cell_id": cell_id,
                    "change_type": pick(["antenna_tilt", "power_adjust", "neighbour_list"]),
                    "changed_at": datetime_str(40, 5),
                }
            )

        if rng.random() < (0.25 if hot else 0.04):
            aid += 1
            hours = rng.uniform(2, 12)
            maint.append(
                {
                    "window_id": f"MNT-{aid:07d}",
                    "cell_id": cell_id,
                    "started_at": datetime_str(30, 1),
                    "duration_hours": round(hours, 2),
                    "reason": pick(["hardware", "software", "optimisation"]),
                }
            )

        if hot or rng.random() < 0.06:
            aid += 1
            tickets.append(
                {
                    "ticket_id": f"TT-{aid:07d}",
                    "cell_id": cell_id,
                    "incident_type": pick(["outage", "degraded_throughput", "voice_quality"]),
                    "opened_at": datetime_str(30, 0),
                    "time_to_resolve_hours": round(rng.uniform(1, 48), 1),
                    "status": pick(["open", "resolved", "resolved"]),
                }
            )

        if rng.random() < (0.15 if hot else 0.02):
            aid += 1
            backhaul.append(
                {
                    "fault_id": f"BH-{aid:07d}",
                    "site_id": site_id,
                    "fault_type": pick(["fibre_cut", "microwave_fail", "capacity"]),
                    "started_at": datetime_str(30, 0),
                    "duration_hours": round(rng.uniform(0.5, 10), 2),
                }
            )

    data["Network_Alarm"] = alarms
    data["Cell_KPI_Daily"] = kpi
    data["Network_Event"] = events
    data["Config_Change"] = config
    data["Planned_Maintenance"] = maint
    data["Trouble_Ticket"] = tickets
    data["Backhaul_Fault"] = backhaul
    data["Site_Master"] = sites
    return data
