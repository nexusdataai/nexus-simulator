"""Unit tests for ``build_simulator``."""

from __future__ import annotations

from typing import Any

import pytest

from nexus_simulator import (
    SimulatorConfig,
    WXCCPluginConfig,
    build_simulator,
    register_simulator,
)
from nexus_simulator.adapters.memory import InMemoryCacheBackend
from nexus_simulator.adapters.redis import RedisCacheBackend
from nexus_simulator.base import BaseSimulator
from nexus_simulator.registry import _clear_registered_factories


class _Sim(BaseSimulator):
    SERVICE_NAME = "custom"

    async def seed_data(self) -> dict[str, Any]:
        return {"success": True, "message": "seed", "tables": 0, "total_rows": 0}


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    _clear_registered_factories()
    yield
    _clear_registered_factories()


def test_build_simulator_with_empty_config_returns_disabled_simulator() -> None:
    sim = build_simulator(SimulatorConfig())
    assert sim.wxcc is None
    assert sim.sfdc is None
    assert sim.oracle_erp is None
    assert sim.sap is None
    assert sim.external_source is None
    assert sim.registry.all() == {}


def test_build_simulator_uses_in_memory_cache_when_redis_url_unset() -> None:
    sim = build_simulator(SimulatorConfig())
    assert isinstance(sim.cache, InMemoryCacheBackend)


def test_build_simulator_uses_redis_cache_when_url_set() -> None:
    sim = build_simulator(SimulatorConfig(redis_url="redis://example:6379/0"))
    assert isinstance(sim.cache, RedisCacheBackend)
    # Until first call we shouldn't have probed; sticky-unavailable starts at False
    assert sim.cache._unavailable is False


def test_build_simulator_wires_out_of_tree_plugins_via_registry() -> None:
    """``register_simulator`` factories run inside ``build_simulator``."""

    cache_holder: dict[str, Any] = {}

    def _factory(cfg: SimulatorConfig) -> _Sim:
        s = _Sim(cache=cache_holder.get("cache"))  # cache wiring lands per-plugin in phase 5+
        return s

    register_simulator("custom", _factory)
    sim = build_simulator(SimulatorConfig(wxcc=WXCCPluginConfig(bucket="b")))
    assert "custom" in sim.registry
    assert isinstance(sim.registry.get("custom"), _Sim)


def test_build_simulator_skips_factories_returning_none() -> None:
    register_simulator("disabled", lambda cfg: None)  # type: ignore[arg-type, return-value]
    sim = build_simulator(SimulatorConfig())
    assert "disabled" not in sim.registry
