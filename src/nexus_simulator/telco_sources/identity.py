"""Atlas-style display IDs correlated to TelcoPools."""

from __future__ import annotations

from nexus_simulator.plugins.telco_seed_pools import TelcoPools


def atlas_customer_id(pools: TelcoPools, internal_id: str) -> str:
    """Map CUST-000001 style ids to atlas C-100245 thread for the first subscribers."""
    try:
        idx = pools.customer_ids.index(internal_id)
    except ValueError:
        num = internal_id.split("-")[-1]
        return f"C-{100200 + int(num)}"
    return f"C-{100245 + idx}"


def atlas_msisdn(pools: TelcoPools, internal_id: str) -> str:
    idx = pools.customer_ids.index(internal_id) if internal_id in pools.customer_ids else 0
    return f"96659{1234567 + idx}"


def atlas_imsi(pools: TelcoPools, internal_id: str) -> str:
    idx = pools.customer_ids.index(internal_id) if internal_id in pools.customer_ids else 0
    return f"001011234567{890 + idx}"


def atlas_cell_name(pools: TelcoPools, cell_internal: str, *, trace: bool = False) -> str:
    if trace and cell_internal == pools.home_cell_by_customer.get(pools.customer_ids[0], ""):
        return "RYD-0421-L18-1"
    num = cell_internal.replace("CELL-", "")
    return f"RYD-{num}-L18-1"


def atlas_site_id(pools: TelcoPools, cell_internal: str) -> str:
    return "RYD-0421" if cell_internal == pools.home_cell_by_customer.get(pools.customer_ids[0], "") else f"SITE-{cell_internal[-4:]}"


def atlas_enb(cell_name: str) -> str:
    if cell_name.startswith("RYD-0421"):
        return "ENB104210"
    return "ENB104388"


def trace_customer_internal(pools: TelcoPools) -> str:
    return pools.customer_ids[0] if pools.customer_ids else "CUST-000001"
