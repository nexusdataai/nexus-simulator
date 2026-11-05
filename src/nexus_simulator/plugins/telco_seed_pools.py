"""
Shared topology and persona pools for BSS / NSS / OSS / telco_golden seeders.

All telco plugins import from this module so joins on customer_id / home_cell_id
are deterministic across schemas.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Set, Tuple

REGION_CODES = ["MH", "KA", "DL", "TN", "GJ"]
SEGMENTS = ["consumer", "sme", "enterprise"]
ACCOUNT_TYPES = ["prepaid", "postpaid"]

# (plan_name, plan_tier, quota_gb, account_type, monthly_spend)
PLAN_CATALOG: List[Tuple[str, str, float, str, float]] = [
    ("Prepaid 199", "199", 1.5, "prepaid", 199.0),
    ("Prepaid 299", "299", 2.0, "prepaid", 299.0),
    ("Postpaid 399", "399", 40.0, "postpaid", 399.0),
    ("Postpaid 499", "499", 50.0, "postpaid", 499.0),
    ("Postpaid 999", "999", 150.0, "postpaid", 999.0),
]

VAS_NAMES = ["Disney+", "Netflix", "Hotstar", "Amazon Prime", "Spotify", "Cloud Backup"]
OFFER_NAMES = ["Upgrade to 499", "Double Data", "Device EMI Waiver", "Loyalty 100GB", "Family Add-on"]
CARE_REASONS = ["network_quality", "billing", "plan_change", "device", "port_out", "general"]
PAGE_TYPES = ["home", "plan_compare", "cancel", "recharge", "support"]


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def telco_subscriber_count() -> int:
    return max(10, _env_int("TELCO_SUBSCRIBERS", 500))


def telco_cell_count() -> int:
    return max(10, _env_int("TELCO_CELLS", 100))


def telco_history_days() -> int:
    return max(30, _env_int("TELCO_HISTORY_DAYS", 60))


def telco_rng_seed() -> int:
    return _env_int("TELCO_SEED", 42)


def _ids(prefix: str, count: int, width: int = 5) -> List[str]:
    return [f"{prefix}{i + 1:0{width}d}" for i in range(count)]


@dataclass
class TelcoPools:
    """Frozen-ish topology rebuilt from env each call to ``get_telco_pools``."""

    seed: int
    customer_ids: List[str]
    cell_ids: List[str]
    site_ids: List[str]
    offer_ids: List[str]
    care_agent_ids: List[str]
    home_cell_by_customer: Dict[str, str]
    work_cell_by_customer: Dict[str, str]
    cell_region: Dict[str, str]
    customer_region: Dict[str, str]
    customer_plan: Dict[str, Tuple[str, str, float, str, float]]
    customer_segment: Dict[str, str]
    customer_tenure: Dict[str, int]
    persona_usage_decline_network: Set[str]
    persona_usage_decline_policy: Set[str]
    persona_port_out: Set[str]
    persona_upsell_ready: Set[str]
    persona_anomaly: Set[str]
    persona_stable: Set[str]
    history_days: int
    _rng: random.Random = field(repr=False)

    def rng(self) -> random.Random:
        return self._rng

    def pick(self, pool: List[str]) -> str:
        return self._rng.choice(pool) if pool else ""

    def date_str(self, start_days_ago: int = 365, end_days_ago: int = 0) -> str:
        delta = self._rng.randint(end_days_ago, max(start_days_ago, end_days_ago + 1))
        return (datetime.now(timezone.utc) - timedelta(days=delta)).strftime("%Y-%m-%d")

    def datetime_str(self, start_days_ago: int = 365, end_days_ago: int = 0) -> str:
        delta = self._rng.randint(end_days_ago, max(start_days_ago, end_days_ago + 1))
        dt = datetime.now(timezone.utc) - timedelta(
            days=delta, hours=self._rng.randint(0, 23), minutes=self._rng.randint(0, 59)
        )
        return dt.isoformat()

    def day_offset(self, days_ago: int) -> str:
        return (datetime.now(timezone.utc).date() - timedelta(days=days_ago)).isoformat()


_POOLS_CACHE: Dict[Tuple[int, int, int, int], TelcoPools] = {}


def get_telco_pools(
    *,
    subscribers: int | None = None,
    cells: int | None = None,
    history_days: int | None = None,
    seed: int | None = None,
) -> TelcoPools:
    n_sub = subscribers if subscribers is not None else telco_subscriber_count()
    n_cell = cells if cells is not None else telco_cell_count()
    hist = history_days if history_days is not None else telco_history_days()
    rng_seed = seed if seed is not None else telco_rng_seed()
    cache_key = (n_sub, n_cell, hist, rng_seed)
    if cache_key in _POOLS_CACHE:
        return _POOLS_CACHE[cache_key]

    rng = random.Random(rng_seed)
    customer_ids = _ids("CUST-", n_sub, 6)
    cell_ids = _ids("CELL-", n_cell, 4)
    site_ids = _ids("SITE-", max(10, n_cell // 5), 3)
    offer_ids = _ids("OFR-", 40, 3)
    care_agent_ids = _ids("AGT-", 50, 3)

    cell_region = {cid: rng.choice(REGION_CODES) for cid in cell_ids}
    home_cell_by_customer: Dict[str, str] = {}
    work_cell_by_customer: Dict[str, str] = {}
    customer_region: Dict[str, str] = {}
    customer_plan: Dict[str, Tuple[str, str, float, str, float]] = {}
    customer_segment: Dict[str, str] = {}
    customer_tenure: Dict[str, int] = {}

    for cid in customer_ids:
        home = rng.choice(cell_ids)
        work = rng.choice(cell_ids)
        home_cell_by_customer[cid] = home
        work_cell_by_customer[cid] = work
        customer_region[cid] = cell_region[home]
        customer_plan[cid] = PLAN_CATALOG[rng.randrange(len(PLAN_CATALOG))]
        customer_segment[cid] = rng.choices(SEGMENTS, weights=[0.88, 0.10, 0.02], k=1)[0]
        customer_tenure[cid] = rng.randint(1, 120)

    # Persona assignment (approximate rates from the plan).
    shuffled = list(customer_ids)
    rng.shuffle(shuffled)
    n = len(shuffled)
    i = 0

    def take(frac: float) -> Set[str]:
        nonlocal i
        count = max(1, int(n * frac))
        chunk = set(shuffled[i : i + count])
        i += count
        return chunk

    persona_usage_decline_network = take(0.12)
    persona_usage_decline_policy = take(0.03)
    persona_port_out = take(0.008)
    persona_upsell_ready = take(0.05)
    persona_anomaly = take(0.02)
    assigned = (
        persona_usage_decline_network
        | persona_usage_decline_policy
        | persona_port_out
        | persona_upsell_ready
        | persona_anomaly
    )
    persona_stable = set(customer_ids) - assigned

    pools = TelcoPools(
        seed=rng_seed,
        customer_ids=customer_ids,
        cell_ids=cell_ids,
        site_ids=site_ids,
        offer_ids=offer_ids,
        care_agent_ids=care_agent_ids,
        home_cell_by_customer=home_cell_by_customer,
        work_cell_by_customer=work_cell_by_customer,
        cell_region=cell_region,
        customer_region=customer_region,
        customer_plan=customer_plan,
        customer_segment=customer_segment,
        customer_tenure=customer_tenure,
        persona_usage_decline_network=persona_usage_decline_network,
        persona_usage_decline_policy=persona_usage_decline_policy,
        persona_port_out=persona_port_out,
        persona_upsell_ready=persona_upsell_ready,
        persona_anomaly=persona_anomaly,
        persona_stable=persona_stable,
        history_days=hist,
        _rng=rng,
    )
    _POOLS_CACHE[cache_key] = pools
    return pools


def clear_telco_pools_cache() -> None:
    _POOLS_CACHE.clear()
