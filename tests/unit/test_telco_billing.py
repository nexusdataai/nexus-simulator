"""Billing module metadata and Kenan BP seed profile."""

from __future__ import annotations

import pytest

from nexus_simulator.config import BSSPluginConfig, SimulatorConfig
from nexus_simulator.factory import build_simulator
from nexus_simulator.plugins.telco_seed_pools import clear_telco_pools_cache, get_telco_pools
from nexus_simulator.telco_backbone.billing import billing_system_keys_for_layer, is_billing_system


@pytest.fixture(autouse=True)
def _small_pools(monkeypatch):
    monkeypatch.setenv("TELCO_SUBSCRIBERS", "25")
    monkeypatch.setenv("TELCO_CELLS", "12")
    monkeypatch.setenv("TELCO_HISTORY_DAYS", "14")
    monkeypatch.setenv("TELCO_SEED", "11")
    monkeypatch.setenv("TELCO_BACKBONE_PROFILE", "billing")
    clear_telco_pools_cache()
    yield
    clear_telco_pools_cache()


def test_billing_system_keys_cover_kenan_feeds():
    assert is_billing_system("Billing / invoicing")
    bss = billing_system_keys_for_layer("BSS")
    assert "CRM / customer master" in bss
    assert len(bss) >= 10
    nss = billing_system_keys_for_layer("NSS")
    assert "Packet gateway (SGW / PGW / SMF / UPF)" in nss


@pytest.mark.asyncio
async def test_bss_billing_seed_marks_tables_and_kenan():
    sim = build_simulator(SimulatorConfig(bss=BSSPluginConfig()))
    svc = sim.bss
    assert svc is not None
    pools = get_telco_pools()
    await svc.generate_backbone(pools=pools, include_legacy_tables=True)
    objects = await svc.get_object_list()
    billing = [o for o in objects if (o.get("applications") or []) and "billing" in o["applications"]]
    assert billing
    kenan = [o for o in objects if o.get("schemaName") == "kenan_bp"]
    assert kenan
    assert any(o.get("tableName") == "CMF" for o in kenan)