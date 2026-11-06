"""Unit tests for telco source artifact generation."""

from __future__ import annotations

import pytest

from nexus_simulator.config import SimulatorConfig, TelcoSourcesPluginConfig
from nexus_simulator.factory import build_simulator
from nexus_simulator.plugins.telco_seed_pools import clear_telco_pools_cache, get_telco_pools
from nexus_simulator.telco_sources.catalog import catalog_systems, default_profile, load_atlas_catalog
from nexus_simulator.telco_sources.generate import generate_artifacts


@pytest.fixture(autouse=True)
def _small_pools(monkeypatch):
    monkeypatch.setenv("TELCO_SUBSCRIBERS", "20")
    monkeypatch.setenv("TELCO_CELLS", "10")
    monkeypatch.setenv("TELCO_SEED", "11")
    clear_telco_pools_cache()
    yield
    clear_telco_pools_cache()


def test_atlas_catalog_has_35_systems():
    cat = load_atlas_catalog()
    systems = cat.get("systems") or []
    assert len(systems) == 35
    assert any(s["system_key"] == "CRM / customer master" for s in systems)


def test_generate_phase_a_artifacts():
    bundle = generate_artifacts(default_profile())
    assert bundle.artifacts
    deliveries = {a.delivery for a in bundle.artifacts}
    assert "Table" in deliveries
    assert "File" in deliveries
    assert bundle.lineage.get("customer_id", "").startswith("C-")


@pytest.mark.asyncio
async def test_telco_sources_service_seed():
    sim = build_simulator(SimulatorConfig(telco_sources=TelcoSourcesPluginConfig()))
    svc = sim.telco_sources
    assert svc is not None
    summary = await svc.seed_data()
    assert summary["artifacts"] > 0
    index = await svc.get_tmf_index()
    assert any("/tmf-api/customerManagement" in k for k in index)
    bundle = await svc.get_bundle()
    assert bundle and bundle.get("lineage")
