"""Unit tests for BSS / NSS / OSS / telco_golden seed + rollup."""

from __future__ import annotations

import pytest

from nexus_simulator.config import (
    BSSPluginConfig,
    NSSPluginConfig,
    OSSPluginConfig,
    SimulatorConfig,
    TelcoGoldenPluginConfig,
)
from nexus_simulator.factory import build_simulator
from nexus_simulator.plugins.bss.tables import build_bss_tables
from nexus_simulator.plugins.nss.tables import build_nss_tables
from nexus_simulator.plugins.oss.tables import build_oss_tables
from nexus_simulator.plugins.telco_seed_pools import clear_telco_pools_cache, get_telco_pools
from nexus_simulator.telco_golden.rollup import TABLE_NAME, rollup_golden


@pytest.fixture(autouse=True)
def _small_pools(monkeypatch):
    monkeypatch.setenv("TELCO_SUBSCRIBERS", "40")
    monkeypatch.setenv("TELCO_CELLS", "20")
    monkeypatch.setenv("TELCO_HISTORY_DAYS", "35")
    monkeypatch.setenv("TELCO_SEED", "7")
    clear_telco_pools_cache()
    yield
    clear_telco_pools_cache()


def test_pools_deterministic_and_personas():
    a = get_telco_pools()
    clear_telco_pools_cache()
    b = get_telco_pools()
    assert a.customer_ids == b.customer_ids
    assert a.home_cell_by_customer == b.home_cell_by_customer
    assert a.persona_usage_decline_network == b.persona_usage_decline_network
    assert a.persona_port_out
    assert a.persona_usage_decline_policy
    assert a.persona_upsell_ready


def test_bss_tables_cover_personas():
    pools = get_telco_pools()
    data = build_bss_tables(pools)
    assert len(data["Subscriber_Profile"]) == len(pools.customer_ids)
    mnp_customers = {r["customer_id"] for r in data["MNP_Port_Out_Request"]}
    assert pools.persona_port_out.issubset(mnp_customers)
    assert data["Invoice"]
    assert data["Campaign_Offer"]


def test_nss_and_oss_correlate_network_decline():
    pools = get_telco_pools()
    nss = build_nss_tables(pools)
    oss = build_oss_tables(pools)
    assert nss["Usage_Daily_Agg"]
    assert nss["Policy_Throttle_Event"]
    policy_customers = {r["customer_id"] for r in nss["Policy_Throttle_Event"] if r.get("fair_usage_limit_hit")}
    assert pools.persona_usage_decline_policy & policy_customers

    hot_cells = {pools.home_cell_by_customer[c] for c in pools.persona_usage_decline_network}
    alarm_cells = {r["cell_id"] for r in oss["Network_Alarm"]}
    assert hot_cells & alarm_cells


def test_golden_rollup_has_required_columns_and_joins():
    pools = get_telco_pools()
    bss = build_bss_tables(pools)
    nss = build_nss_tables(pools)
    oss = build_oss_tables(pools)
    rows = rollup_golden(bss, nss, oss)
    assert len(rows) == len(pools.customer_ids)
    sample = rows[0]
    for col in (
        "customer_id",
        "usage_current_gb",
        "usage_prior_gb",
        "home_cell_id",
        "network_issue_flag",
        "fair_usage_limit_hit_flag",
        "usage_vs_cohort_zscore",
        "cohort_key",
    ):
        assert col in sample
    assert all(r.get("home_cell_id") for r in rows)

    port_rows = [r for r in rows if r["customer_id"] in pools.persona_port_out]
    assert port_rows and all(r["port_out_request_flag"] for r in port_rows)


@pytest.mark.asyncio
async def test_factory_seeds_telco_plugins():
    sim = build_simulator(
        SimulatorConfig(
            bss=BSSPluginConfig(),
            nss=NSSPluginConfig(),
            oss=OSSPluginConfig(),
            telco_golden=TelcoGoldenPluginConfig(),
        )
    )
    assert sim.registry.get("bss") is not None
    assert sim.registry.get("nss") is not None
    assert sim.registry.get("oss") is not None
    assert sim.registry.get("telco_golden") is not None

    await sim.bss.seed_data()
    await sim.nss.seed_data()
    await sim.oss.seed_data()
    summary = await sim.telco_golden.seed_data()
    assert sim.telco_golden.loaded
    objects = await sim.telco_golden.get_object_list()
    names = {o.get("tableName") or o.get("table_name") for o in objects}
    assert TABLE_NAME in names
    # summary shape from _finalize_seed varies; ensure seed returned something
    assert summary is not None
