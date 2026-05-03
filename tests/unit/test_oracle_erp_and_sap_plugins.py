"""Phase 7 unit tests for Oracle ERP + SAP plugins.

Both plugins are thin BaseSimulator subclasses sharing the same FDW surface,
so this module exercises them in parallel via parametrization.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from nexus_simulator import (
    OracleERPPluginConfig,
    SAPPluginConfig,
    SimulatorConfig,
    build_simulator,
)
from nexus_simulator.adapters.memory import InMemoryCacheBackend
from nexus_simulator.base import BaseSimulator
from nexus_simulator.plugins.oracle_erp import OracleERPSimulatorService
from nexus_simulator.plugins.sap import SAPSimulatorService
from nexus_simulator.testing import make_test_app

# ─── Plugin construction / wiring ────────────────────────────────────────


@pytest.mark.parametrize(
    "plugin_attr,cls,cfg_field",
    [
        ("oracle_erp", OracleERPSimulatorService, "oracle_erp"),
        ("sap", SAPSimulatorService, "sap"),
    ],
)
def test_plugin_inherits_basesimulator(plugin_attr: str, cls: type, cfg_field: str) -> None:
    inst = cls(bucket="", prefix=f"{cfg_field}-test")
    assert isinstance(inst, BaseSimulator)
    assert inst.SERVICE_NAME == ("oracle" if plugin_attr == "oracle_erp" else "sap")


def test_oracle_erp_service_name() -> None:
    assert OracleERPSimulatorService.SERVICE_NAME == "oracle"


def test_sap_service_name() -> None:
    assert SAPSimulatorService.SERVICE_NAME == "sap"


def test_build_simulator_wires_oracle_erp() -> None:
    sim = build_simulator(
        SimulatorConfig(oracle_erp=OracleERPPluginConfig(bucket=""))
    )
    assert sim.oracle_erp is not None
    assert isinstance(sim.oracle_erp, OracleERPSimulatorService)
    assert sim.oracle_erp._cache is sim.cache
    assert "oracle_erp" in sim.registry


def test_build_simulator_wires_sap() -> None:
    sim = build_simulator(SimulatorConfig(sap=SAPPluginConfig(bucket="")))
    assert sim.sap is not None
    assert isinstance(sim.sap, SAPSimulatorService)
    assert sim.sap._cache is sim.cache
    assert "sap" in sim.registry


def test_build_simulator_can_enable_both_at_once() -> None:
    sim = build_simulator(
        SimulatorConfig(
            oracle_erp=OracleERPPluginConfig(bucket=""),
            sap=SAPPluginConfig(bucket=""),
        )
    )
    assert sim.oracle_erp is not None
    assert sim.sap is not None
    # Both share the same in-memory cache
    assert sim.oracle_erp._cache is sim.cache
    assert sim.sap._cache is sim.cache
    assert isinstance(sim.cache, InMemoryCacheBackend)


# ─── seed_data → query roundtrip ─────────────────────────────────────────


def test_oracle_erp_seed_creates_priority_tables() -> None:
    sim = build_simulator(SimulatorConfig(oracle_erp=OracleERPPluginConfig(bucket="")))
    result = asyncio.run(sim.oracle_erp.seed_data())
    assert result["success"] is True
    assert result["tables"] >= 5
    assert result["total_rows"] > 0


def test_sap_seed_creates_priority_tables() -> None:
    sim = build_simulator(SimulatorConfig(sap=SAPPluginConfig(bucket="")))
    result = asyncio.run(sim.sap.seed_data())
    assert result["success"] is True
    assert result["tables"] >= 10
    assert result["total_rows"] > 0


# ─── Activated routers ───────────────────────────────────────────────────


@pytest.fixture
def app_with_seeded_plugins() -> Any:
    app = make_test_app()
    asyncio.run(app.state.simulator.oracle_erp.seed_data())
    asyncio.run(app.state.simulator.sap.seed_data())
    return app


@pytest.fixture
def client(app_with_seeded_plugins: Any) -> TestClient:
    return TestClient(app_with_seeded_plugins)


@pytest.mark.parametrize(
    "prefix", ["/api/v1/oracle-erp-simulator", "/api/v1/sap-simulator"]
)
def test_status_returns_loaded_state(client: TestClient, prefix: str) -> None:
    r = client.get(f"{prefix}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["loaded"] is True
    assert body["table_count"] > 0


@pytest.mark.parametrize(
    "prefix", ["/api/v1/oracle-erp-simulator", "/api/v1/sap-simulator"]
)
def test_objects_lists_tables(client: TestClient, prefix: str) -> None:
    r = client.get(f"{prefix}/objects")
    assert r.status_code == 200
    body = r.json()
    assert len(body["objects"]) > 0


@pytest.mark.parametrize(
    "prefix,sample_table",
    [
        ("/api/v1/oracle-erp-simulator", "Oracle_AR_Customer"),
        ("/api/v1/sap-simulator", "Material_Master"),
    ],
)
def test_object_records_pages(client: TestClient, prefix: str, sample_table: str) -> None:
    objs = client.get(f"{prefix}/objects").json()["objects"]
    sample = next(o for o in objs if o["tableName"] == sample_table)
    schema = sample["schemaName"]
    r = client.get(f"{prefix}/objects/{schema}/{sample_table}?limit=2")
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 2


@pytest.mark.parametrize(
    "prefix", ["/api/v1/oracle-erp-simulator", "/api/v1/sap-simulator"]
)
def test_health_reports_loaded_simulator(client: TestClient, prefix: str) -> None:
    r = client.get(f"{prefix}/health")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "simulator"
    assert body["loaded"] is True
