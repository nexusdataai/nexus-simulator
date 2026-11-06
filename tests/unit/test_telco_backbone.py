"""Telco AI Backbone generation on BSS / NSS / OSS."""

from __future__ import annotations

import pytest

from nexus_simulator.config import BSSPluginConfig, NSSPluginConfig, OSSPluginConfig, SimulatorConfig
from nexus_simulator.factory import build_simulator
from nexus_simulator.plugins.telco_seed_pools import clear_telco_pools_cache, get_telco_pools


@pytest.fixture(autouse=True)
def _small_pools(monkeypatch):
    monkeypatch.setenv("TELCO_SUBSCRIBERS", "40")
    monkeypatch.setenv("TELCO_CELLS", "20")
    monkeypatch.setenv("TELCO_HISTORY_DAYS", "35")
    monkeypatch.setenv("TELCO_SEED", "7")
    clear_telco_pools_cache()
    yield
    clear_telco_pools_cache()


@pytest.mark.asyncio
async def test_backbone_catalog_has_vendors_and_merged_deliveries():
    sim = build_simulator(SimulatorConfig(bss=BSSPluginConfig()))
    cat = await sim.bss.get_backbone_catalog()
    assert cat.get("vendors")
    assert cat.get("vendor_default")
    assert any(s.get("slug") for s in cat.get("systems", []))


@pytest.mark.asyncio
async def test_bss_backbone_generate_populates_streams_and_tmf():
    sim = build_simulator(
        SimulatorConfig(
            bss=BSSPluginConfig(),
            nss=NSSPluginConfig(),
            oss=OSSPluginConfig(),
        )
    )
    svc = sim.bss
    assert svc is not None
    pools = get_telco_pools()
    summary = await svc.generate_backbone(pools=pools, include_legacy_tables=False)
    assert summary.get("backbone")
    bb = summary["backbone"]
    assert bb["tables"] >= 1
    assert bb["files"] >= 1
    assert bb["vendor_api_paths"] >= 1
    assert bb["stream_topics"] >= 1

    vidx = await svc.get_vendor_api_index()
    assert vidx

    streams = await svc.get_stream_topics()
    assert streams

    summ = await svc.get_backbone_summary()
    assert summ.get("run_id")
    assert summ["tables"]
    assert summ["apis"]
    assert summ["files"]
    assert summ["streams"]


@pytest.mark.asyncio
async def test_per_system_deliveries_limits_output():
    sim = build_simulator(SimulatorConfig(bss=BSSPluginConfig()))
    svc = sim.bss
    pools = get_telco_pools()
    summary = await svc.generate_backbone(
        pools=pools,
        include_legacy_tables=False,
        systems={"CRM / customer master"},
        system_deliveries={"CRM / customer master": {"Table"}},
    )
    bb = summary["backbone"]
    summ = bb.get("summary") or await svc.get_backbone_summary()
    assert summ["files"] == []
    assert summ["streams"] == []
    assert summ["apis"] == []
    assert len(summ["tables"]) >= 1


@pytest.mark.asyncio
async def test_seed_scenario_outage_on_oss():
    sim = build_simulator(
        SimulatorConfig(
            bss=BSSPluginConfig(),
            nss=NSSPluginConfig(),
            oss=OSSPluginConfig(),
        )
    )
    result = await sim.oss.seed_scenario("outage_backhaul")
    assert result.get("scenario") == "outage_backhaul"
    streams = await sim.oss.get_stream_topics()
    assert "nce.telemetry.interface" in streams
    assert "oss.enm.fm.alarms" in streams
