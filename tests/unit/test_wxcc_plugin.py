"""Phase 5 unit tests for the WXCC plugin.

Covers:

- ``WXCCSimulatorService`` constructs from ``WXCCPluginConfig`` with no AWS.
- ``build_simulator(config)`` registers the plugin and exposes it on
  ``Simulator.wxcc`` and via ``Simulator.registry``.
- The activated WXCC router returns real (non-501) responses against a
  wired in-process app: ``GET /status`` and ``GET /admin/tasks`` are 200;
  ``POST /captures/query`` requires the ``Authorization`` header (401
  when missing); ``GET /recordings/{id}`` returns 404 when no recording is
  stored.
- ``SimulatorProcessor`` constructs and exposes the configured fields.
- The MCP scaffold ``create_mcp_server`` is callable and returns a server
  object when fastmcp is installed (or raises a clear ImportError otherwise).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from nexus_simulator import (
    SimulatorConfig,
    WXCCPluginConfig,
    build_simulator,
)
from nexus_simulator.plugins.wxcc import (
    SimulatorConfig as WXCCProcessorConfig,
)
from nexus_simulator.plugins.wxcc import (
    SimulatorProcessor,
    WXCCSimulatorService,
)
from nexus_simulator.testing import make_test_app

# ─── Plugin construction / wiring ────────────────────────────────────────


def test_wxcc_service_constructs_without_aws() -> None:
    svc = WXCCSimulatorService(bucket="", prefix="wxcc-test", region="us-east-1", org_id="sim-org-001")
    assert svc.bucket == ""
    assert svc.prefix == "wxcc-test"
    assert svc.org_id == "sim-org-001"
    assert svc.enabled is False  # bucket empty → disabled


def test_build_simulator_wires_wxcc_when_config_present() -> None:
    sim = build_simulator(
        SimulatorConfig(
            wxcc=WXCCPluginConfig(bucket="", prefix="wxcc-test", org_id="sim-org-001"),
        )
    )
    assert sim.wxcc is not None
    assert isinstance(sim.wxcc, WXCCSimulatorService)
    assert "wxcc" in sim.registry
    assert sim.registry.get("wxcc") is sim.wxcc


def test_build_simulator_skips_wxcc_when_config_absent() -> None:
    sim = build_simulator(SimulatorConfig())
    assert sim.wxcc is None
    assert "wxcc" not in sim.registry


# ─── Activated router (200 / 401 / 404 paths) ────────────────────────────


@pytest.fixture
def app() -> Any:
    return make_test_app()


@pytest.fixture
def client(app: Any) -> TestClient:
    return TestClient(app)


def test_status_returns_200_with_wired_simulator(client: TestClient) -> None:
    r = client.get("/api/v1/simulator/status")
    assert r.status_code == 200
    body = r.json()
    assert "enabled" in body
    assert body["org_id"] == "sim-org-001"
    assert body["bucket"] == ""  # in-memory test config
    assert body["prefix"] == "wxcc-test"
    assert body["task_count"] == 0


def test_admin_tasks_returns_empty_list(client: TestClient) -> None:
    r = client.get("/api/v1/simulator/admin/tasks")
    assert r.status_code == 200
    body = r.json()
    assert body["tasks"] == []
    assert body["total"] == 0
    assert body["pageSize"] == 100
    assert body["hasMore"] is False


def test_admin_tasks_supports_filters(client: TestClient) -> None:
    r = client.get("/api/v1/simulator/admin/tasks?status=completed&direction=inbound&pageSize=10")
    assert r.status_code == 200
    body = r.json()
    assert body["pageSize"] == 10


def test_health_endpoint_reports_disabled_state(client: TestClient) -> None:
    r = client.get("/api/v1/simulator/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"healthy", "disabled"}
    assert "bucket_configured" in body


def test_captures_query_requires_authorization_header(client: TestClient) -> None:
    """``Authorization`` is a required Header(...) on this route."""
    r = client.post("/api/v1/simulator/captures/query", json={"query": {"taskIds": ["t1"]}})
    # FastAPI returns 422 when a required header is missing.
    assert r.status_code == 422


def test_captures_query_rejects_invalid_bearer_token(client: TestClient) -> None:
    r = client.post(
        "/api/v1/simulator/captures/query",
        json={"query": {"taskIds": ["t1"]}},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert r.status_code == 401


def test_get_recording_returns_404_when_missing(client: TestClient) -> None:
    r = client.get("/api/v1/simulator/recordings/nonexistent")
    assert r.status_code == 404


def test_sample_recordings_validates_extension(client: TestClient) -> None:
    """Uploading a .txt file is rejected with 400 before any service call."""
    r = client.post(
        "/api/v1/simulator/sample-recordings",
        files={"file": ("not-audio.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400
    assert "Unsupported file format" in r.json()["detail"]


# ─── 503 path: routes return 503 when WXCC is disabled in config ──────────


def test_routes_return_503_when_wxcc_plugin_disabled() -> None:
    """A simulator with ``wxcc=None`` causes WXCC routes to 503."""
    from nexus_simulator import build_simulator
    from nexus_simulator.server.app import create_app

    sim = build_simulator(SimulatorConfig())  # all plugins None
    app = create_app(simulator=sim)
    c = TestClient(app)
    assert c.get("/api/v1/simulator/status").status_code == 503
    assert c.get("/api/v1/simulator/admin/tasks").status_code == 503


# ─── Processor (journey-stage helper) ────────────────────────────────────


def test_simulator_processor_constructs() -> None:
    cfg = WXCCProcessorConfig(
        num_tasks=5, days_back=3, include_recordings=True, org_id="sim-org-001"
    )
    proc = SimulatorProcessor(cfg)
    assert proc.config.num_tasks == 5
    assert proc.config.days_back == 3
    assert proc.config.org_id == "sim-org-001"


def test_simulator_processor_reuses_log_callback() -> None:
    captured: list[str] = []

    def log_cb(level: str, msg: str, step: str | None = None) -> None:
        captured.append(f"[{level}] {msg}")

    proc = SimulatorProcessor(WXCCProcessorConfig(), log_callback=log_cb)
    proc._log("INFO", "hello", None)
    assert captured == ["[INFO] hello"]


# ─── MCP server scaffold ──────────────────────────────────────────────────


def test_create_mcp_server_returns_a_server_when_simulator_wired() -> None:
    from nexus_simulator.server.mcp import create_mcp_server

    sim = build_simulator(
        SimulatorConfig(
            wxcc=WXCCPluginConfig(bucket="", prefix="wxcc-test", org_id="sim-org-001"),
        )
    )
    try:
        server = create_mcp_server(simulator=sim)
    except ImportError:
        pytest.skip("fastmcp not installed in this environment")
    assert server is not None
