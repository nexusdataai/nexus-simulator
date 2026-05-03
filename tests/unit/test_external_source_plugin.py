"""Phase 8 unit tests for the External Source plugin.

Covers the data-layer surface (status, seed, objects, columns) end-to-end
against the in-process harness app. The upload + extraction path uses
``DocumentExtractionService`` which performs real OCR/LLM work and is
exercised separately under tests/integration with mocked extractors.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from nexus_simulator import (
    ExternalSourcePluginConfig,
    SimulatorConfig,
    build_simulator,
)
from nexus_simulator.adapters.memory import InMemoryCacheBackend
from nexus_simulator.base import BaseSimulator
from nexus_simulator.plugins.external_source import ExternalSourceSimulatorService
from nexus_simulator.testing import make_test_app

# ─── Plugin construction / wiring ────────────────────────────────────────


def test_external_source_inherits_basesimulator() -> None:
    svc = ExternalSourceSimulatorService(bucket="", prefix="external-test")
    assert isinstance(svc, BaseSimulator)
    assert svc.SERVICE_NAME == "external"


def test_build_simulator_wires_external_source() -> None:
    sim = build_simulator(
        SimulatorConfig(external_source=ExternalSourcePluginConfig(bucket=""))
    )
    assert sim.external_source is not None
    assert isinstance(sim.external_source, ExternalSourceSimulatorService)
    assert sim.external_source._cache is sim.cache
    assert isinstance(sim.cache, InMemoryCacheBackend)
    assert "external_source" in sim.registry


# ─── seed_data ─────────────────────────────────────────────────────────────


def test_external_source_seed_creates_priority_tables() -> None:
    sim = build_simulator(
        SimulatorConfig(external_source=ExternalSourcePluginConfig(bucket=""))
    )
    result = asyncio.run(sim.external_source.seed_data())
    assert result["success"] is True
    assert result["tables"] >= 5
    assert result["total_rows"] > 0


def test_external_source_seed_includes_uploads_and_signals() -> None:
    sim = build_simulator(
        SimulatorConfig(external_source=ExternalSourcePluginConfig(bucket=""))
    )
    asyncio.run(sim.external_source.seed_data())
    objs = asyncio.run(sim.external_source.get_object_list())
    table_names = {o["tableName"] for o in objs}
    # Contract_Document, Sustainability_Report (Google_Drive)
    assert "Contract_Document" in table_names
    # Market_Signal (Social_Listening)
    assert "Market_Signal" in table_names
    # Invoice_Upload, Lab_Report_Upload (File_Uploads)
    assert "Invoice_Upload" in table_names


# ─── Activated router ─────────────────────────────────────────────────────


@pytest.fixture
def app_with_seeded_external() -> Any:
    app = make_test_app()
    asyncio.run(app.state.simulator.external_source.seed_data())
    return app


@pytest.fixture
def client(app_with_seeded_external: Any) -> TestClient:
    return TestClient(app_with_seeded_external)


def test_status_returns_loaded(client: TestClient) -> None:
    r = client.get("/api/v1/external-simulator/status")
    assert r.status_code == 200
    assert r.json()["loaded"] is True


def test_objects_lists_uploads_and_signals(client: TestClient) -> None:
    r = client.get("/api/v1/external-simulator/objects")
    assert r.status_code == 200
    table_names = {o["tableName"] for o in r.json()["objects"]}
    assert "Contract_Document" in table_names
    assert "Market_Signal" in table_names


def test_object_records_returns_rows(client: TestClient) -> None:
    objs = client.get("/api/v1/external-simulator/objects").json()["objects"]
    sample = next(o for o in objs if o["tableName"] == "Market_Signal")
    schema = sample["schemaName"]
    r = client.get(f"/api/v1/external-simulator/objects/{schema}/Market_Signal?limit=2")
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 2


def test_object_columns_returns_schema(client: TestClient) -> None:
    objs = client.get("/api/v1/external-simulator/objects").json()["objects"]
    sample = next(o for o in objs if o["tableName"] == "Market_Signal")
    schema = sample["schemaName"]
    r = client.get(f"/api/v1/external-simulator/objects/{schema}/Market_Signal/columns")
    assert r.status_code == 200
    assert len(r.json()["columns"]) > 0


def test_health_reports_loaded(client: TestClient) -> None:
    r = client.get("/api/v1/external-simulator/health")
    assert r.status_code == 200
    body = r.json()
    assert body["loaded"] is True


def test_load_status_route(client: TestClient) -> None:
    r = client.get("/api/v1/external-simulator/load/status")
    assert r.status_code == 200
    assert "running" in r.json()
