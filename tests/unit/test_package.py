"""Smoke tests for the public Phase 0/1/2 surface.

Pinned today because:
- The public re-exports under ``nexus_simulator`` are part of the stable
  surface during the alpha series.
- The reference server must mount five plugin routers under fixed prefixes;
  changing those silently would break host integrations.
"""

from __future__ import annotations

import pytest


def test_version_is_alpha() -> None:
    import nexus_simulator

    assert nexus_simulator.__version__.startswith("0.1.0a")


def test_public_reexports() -> None:
    from nexus_simulator import (
        ExternalSourcePluginConfig,
        OracleERPPluginConfig,
        PluginNotEnabled,
        SAPPluginConfig,
        SFDCPluginConfig,
        Simulator,
        SimulatorConfig,
        SimulatorError,
        SimulatorNotConfigured,
        SimulatorRegistry,
        StorageError,
        WXCCPluginConfig,
        build_simulator,
        register_simulator,
    )

    assert all(
        cls is not None
        for cls in (
            ExternalSourcePluginConfig,
            OracleERPPluginConfig,
            PluginNotEnabled,
            SAPPluginConfig,
            SFDCPluginConfig,
            Simulator,
            SimulatorConfig,
            SimulatorError,
            SimulatorNotConfigured,
            SimulatorRegistry,
            StorageError,
            WXCCPluginConfig,
            build_simulator,
            register_simulator,
        )
    )


def test_simulator_config_defaults_disable_all_plugins() -> None:
    from nexus_simulator import SimulatorConfig

    cfg = SimulatorConfig()
    assert cfg.region is None
    assert cfg.role_arn is None
    assert cfg.redis_url is None
    assert cfg.wxcc is None
    assert cfg.sfdc is None
    assert cfg.oracle_erp is None
    assert cfg.sap is None
    assert cfg.external_source is None


def test_per_plugin_config_defaults() -> None:
    from nexus_simulator import (
        ExternalSourcePluginConfig,
        OracleERPPluginConfig,
        SAPPluginConfig,
        SFDCPluginConfig,
        WXCCPluginConfig,
    )

    assert WXCCPluginConfig().prefix == "wxcc-simulator"
    assert WXCCPluginConfig().org_id == "sim-org-001"
    assert SFDCPluginConfig().prefix == "sfdc-simulator"
    assert OracleERPPluginConfig().prefix == "oracle-erp-simulator"
    assert SAPPluginConfig().prefix == "sap-simulator"
    assert ExternalSourcePluginConfig().prefix == "external-simulator"


def test_build_simulator_returns_a_simulator() -> None:
    from nexus_simulator import SimulatorConfig, build_simulator
    from nexus_simulator.factory import Simulator

    sim = build_simulator(SimulatorConfig())
    assert isinstance(sim, Simulator)
    # Phase 3: in-tree plugins still land in phases 5+, so all are None today.
    assert sim.wxcc is None
    assert sim.sfdc is None
    assert sim.oracle_erp is None
    assert sim.sap is None
    assert sim.external_source is None
    assert sim.cache is not None  # in-memory by default


def test_simulator_registry_is_empty_by_default() -> None:
    from nexus_simulator import SimulatorRegistry

    reg = SimulatorRegistry()
    assert reg.get("wxcc") is None
    assert reg.all() == {}
    assert reg.names() == []
    assert "wxcc" not in reg


def test_register_simulator_is_idempotent_within_a_test() -> None:
    from nexus_simulator import register_simulator
    from nexus_simulator.registry import (
        _clear_registered_factories,
        get_registered_factories,
    )

    _clear_registered_factories()
    register_simulator("custom", lambda cfg: None)  # type: ignore[arg-type, return-value]
    assert "custom" in get_registered_factories()

    with pytest.raises(ValueError, match="already registered"):
        register_simulator("custom", lambda cfg: None)  # type: ignore[arg-type, return-value]

    _clear_registered_factories()


def test_error_hierarchy() -> None:
    from nexus_simulator import (
        CacheError,
        PluginNotEnabled,
        QueryError,
        SimulatorError,
        SimulatorNotConfigured,
        StorageError,
    )

    assert issubclass(SimulatorNotConfigured, SimulatorError)
    assert issubclass(PluginNotEnabled, SimulatorError)
    assert issubclass(StorageError, SimulatorError)
    assert issubclass(CacheError, SimulatorError)
    assert issubclass(QueryError, SimulatorError)

    assert SimulatorError().code == "simulator_error"
    assert SimulatorNotConfigured().code == "simulator_not_configured"
    assert PluginNotEnabled().code == "plugin_not_enabled"
    assert StorageError().code == "storage_error"
    assert CacheError().code == "cache_error"
    assert QueryError().code == "query_error"


def test_contracts_are_protocols() -> None:
    from typing import get_type_hints

    from nexus_simulator.contracts import (
        CacheBackend,
        FDWQueryPort,
        RecordingsBackend,
        StorageBackend,
    )

    for proto in (StorageBackend, CacheBackend, FDWQueryPort, RecordingsBackend):
        assert hasattr(proto, "_is_runtime_protocol") or hasattr(proto, "_is_protocol")
        get_type_hints(proto)


def test_base_simulator_is_an_abc() -> None:
    import abc

    from nexus_simulator.base import BaseSimulator

    assert issubclass(BaseSimulator, abc.ABC)
    # seed_data is the lone abstract method until Phase 3 lands
    assert "seed_data" in BaseSimulator.__abstractmethods__
