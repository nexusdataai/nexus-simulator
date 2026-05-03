"""Phase 6 unit tests for the SFDC plugin."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from nexus_simulator import SFDCPluginConfig, SimulatorConfig, build_simulator
from nexus_simulator.adapters.memory import InMemoryCacheBackend
from nexus_simulator.plugins.sfdc import SFDCSimulatorService
from nexus_simulator.testing import make_test_app

# ─── Plugin construction / wiring ────────────────────────────────────────


def test_sfdc_service_inherits_basesimulator() -> None:
    from nexus_simulator.base import BaseSimulator

    svc = SFDCSimulatorService(bucket="", prefix="sfdc-test")
    assert isinstance(svc, BaseSimulator)
    assert svc.SERVICE_NAME == "sfdc"
    assert "Account" in svc.PRIORITY_TABLES


def test_build_simulator_wires_sfdc_with_shared_cache() -> None:
    sim = build_simulator(SimulatorConfig(sfdc=SFDCPluginConfig(bucket="", prefix="sfdc-test")))
    assert sim.sfdc is not None
    assert isinstance(sim.sfdc, SFDCSimulatorService)
    assert sim.sfdc._cache is sim.cache
    assert isinstance(sim.cache, InMemoryCacheBackend)
    assert "sfdc" in sim.registry


def test_build_simulator_skips_sfdc_when_config_absent() -> None:
    sim = build_simulator(SimulatorConfig())
    assert sim.sfdc is None
    assert "sfdc" not in sim.registry


# ─── seed_data → query roundtrip ─────────────────────────────────────────


def test_sfdc_seed_creates_priority_tables() -> None:
    sim = build_simulator(SimulatorConfig(sfdc=SFDCPluginConfig(bucket="")))
    result = asyncio.run(sim.sfdc.seed_data())
    assert result["success"] is True
    assert result["tables"] >= 5  # account, contact, campaign, opp, opp_line_item, contact_role, account_status
    assert result["total_rows"] > 0


def test_sfdc_get_object_list_after_seed() -> None:
    sim = build_simulator(SimulatorConfig(sfdc=SFDCPluginConfig(bucket="")))
    asyncio.run(sim.sfdc.seed_data())
    objs = asyncio.run(sim.sfdc.get_object_list())
    by_name = {o["tableName"]: o for o in objs}
    assert "Account" in by_name
    assert by_name["Account"]["rowCount"] > 0
    assert by_name["Account"]["schemaName"].startswith("sfdc")


def test_sfdc_execute_query_returns_rows() -> None:
    from nexus_simulator.models.fdw import QueryRequest

    sim = build_simulator(SimulatorConfig(sfdc=SFDCPluginConfig(bucket="")))
    asyncio.run(sim.sfdc.seed_data())
    schema = next(t.schema_name for t in sim.sfdc._tables if t.table_name == "Account")
    resp = asyncio.run(sim.sfdc.execute_query(QueryRequest(table="Account", schema_name=schema, limit=3)))
    assert len(resp.rows) == 3
    # SFDC rows have Account_ID and Account_Name
    assert "Account_ID" in resp.rows[0]


# ─── Activated router ────────────────────────────────────────────────────


@pytest.fixture
def app_with_seeded_sfdc() -> Any:
    app = make_test_app()
    asyncio.run(app.state.simulator.sfdc.seed_data())
    return app


@pytest.fixture
def client(app_with_seeded_sfdc: Any) -> TestClient:
    return TestClient(app_with_seeded_sfdc)


def test_status_returns_loaded_state(client: TestClient) -> None:
    r = client.get("/api/v1/sfdc-simulator/status")
    assert r.status_code == 200
    body = r.json()
    assert body["loaded"] is True
    assert body["table_count"] > 0
    assert body["total_rows"] > 0


def test_objects_lists_priority_tables(client: TestClient) -> None:
    r = client.get("/api/v1/sfdc-simulator/objects")
    assert r.status_code == 200
    body = r.json()
    table_names = {o["tableName"] for o in body["objects"]}
    assert "Account" in table_names


def test_object_records_pages(client: TestClient) -> None:
    # discover schema
    objs = client.get("/api/v1/sfdc-simulator/objects").json()["objects"]
    sample = next(o for o in objs if o["tableName"] == "Account")
    schema = sample["schemaName"]
    r = client.get(f"/api/v1/sfdc-simulator/objects/{schema}/Account?limit=2&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0


def test_object_columns_returns_schema(client: TestClient) -> None:
    objs = client.get("/api/v1/sfdc-simulator/objects").json()["objects"]
    sample = next(o for o in objs if o["tableName"] == "Account")
    schema = sample["schemaName"]
    r = client.get(f"/api/v1/sfdc-simulator/objects/{schema}/Account/columns")
    assert r.status_code == 200
    body = r.json()
    assert len(body["columns"]) > 0
    assert all("columnName" in c for c in body["columns"])


def test_health_reports_loaded_simulator(client: TestClient) -> None:
    r = client.get("/api/v1/sfdc-simulator/health")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "simulator"
    assert body["loaded"] is True


def test_load_status_returns_progress_dict(client: TestClient) -> None:
    r = client.get("/api/v1/sfdc-simulator/load/status")
    assert r.status_code == 200
    body = r.json()
    assert "running" in body
