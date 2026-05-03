"""Phase 2 server smoke tests.

Verifies:
- Health/readiness/version endpoints are live and shape-correct.
- All five plugin routers are mounted at their canonical prefixes.
- Every router endpoint returns 501 until its owning phase activates.
- The CLI entry point is registered and ``--help`` works.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient

from nexus_simulator.server.app import (
    EXTERNAL_PREFIX,
    ORACLE_ERP_PREFIX,
    SAP_PREFIX,
    SFDC_PREFIX,
    WXCC_PREFIX,
    create_app,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health_endpoint_is_live(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"].startswith("0.1.0a")


def test_readiness_reports_simulator_state(client: TestClient) -> None:
    r = client.get("/readiness")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is False  # no simulator wired in this test
    assert body["version"].startswith("0.1.0a")


def test_version_endpoint(client: TestClient) -> None:
    r = client.get("/version")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "nexus-simulator"
    assert body["version"].startswith("0.1.0a")


def test_canonical_prefixes_match_backend() -> None:
    """These prefixes must not change without a host migration plan."""
    assert WXCC_PREFIX == "/api/v1/simulator"
    assert SFDC_PREFIX == "/api/v1/sfdc-simulator"
    assert ORACLE_ERP_PREFIX == "/api/v1/oracle-erp-simulator"
    assert SAP_PREFIX == "/api/v1/sap-simulator"
    assert EXTERNAL_PREFIX == "/api/v1/external-simulator"


@pytest.mark.parametrize(
    "method,path",
    [
        # Only routes with no required headers / no UploadFile body, so we
        # exercise the 503 branch (FastAPI returns 422 first when a Header(...)
        # or UploadFile dep is missing — that's covered separately in
        # test_wxcc_plugin.test_captures_query_requires_authorization_header).
        ("GET", "/tasks"),
        ("GET", "/recordings/r1"),
        ("GET", "/status"),
        ("GET", "/admin/tasks"),
        ("POST", "/tasks"),
        ("PUT", "/tasks/t1"),
        ("DELETE", "/tasks/t1"),
        ("POST", "/seed"),
        ("POST", "/reset"),
        ("GET", "/sample-recordings"),
        ("DELETE", "/sample-recordings/foo.wav"),
        ("GET", "/health"),
    ],
)
def test_wxcc_routes_return_503_when_simulator_not_wired(
    client: TestClient, method: str, path: str
) -> None:
    """``create_app()`` with no simulator argument returns 503 on plugin routes.

    Phase 5 activated the WXCC plugin: with a wired simulator the routes serve
    real responses (covered by harness tests). The unwired ``create_app()``
    fixture used here intentionally has ``app.state.simulator = None`` so
    ``get_service`` raises 503.
    """
    full = WXCC_PREFIX + path
    body: dict[str, Any] = {}
    if method == "POST" and path == "/seed":
        body = {"num_tasks": 1, "include_recordings": False, "days_back": 1}
    elif method == "POST" and path == "/tasks":
        body = {"origin": "+1", "destination": "+2", "duration": 30}
    elif method == "PUT" and path == "/tasks/t1":
        body = {}
    r = client.request(method, full, json=body)
    assert r.status_code == 503, f"{method} {full}: got {r.status_code} {r.text[:120]}"


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/status"),
        ("GET", "/load/status"),
        ("POST", "/load"),
        ("POST", "/reset"),
        ("GET", "/objects"),
        ("GET", "/objects/public/accounts"),
        ("GET", "/objects/public/accounts/columns"),
        ("GET", "/dump/status"),
        # POST /dump requires a body matching DumpRequest; covered separately.
        # POST /restart-pods has no service dependency (k8s-only), skip from 503 set.
        ("GET", "/health"),
    ],
)
def test_sfdc_routes_return_503_when_simulator_not_wired(
    client: TestClient, method: str, path: str
) -> None:
    """Phase 6 activated SFDC: unwired ``create_app()`` returns 503."""
    full = SFDC_PREFIX + path
    r = client.request(method, full, json={})
    assert r.status_code == 503, f"{method} {full}: got {r.status_code}"


@pytest.mark.parametrize("prefix", [ORACLE_ERP_PREFIX, SAP_PREFIX])
@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/status"),
        ("GET", "/load/status"),
        ("POST", "/load"),
        ("POST", "/reset"),
        ("GET", "/objects"),
        ("GET", "/objects/public/foo"),
        ("GET", "/objects/public/foo/columns"),
        ("GET", "/dump/status"),
        ("GET", "/health"),
    ],
)
def test_oracle_and_sap_routes_return_503_when_simulator_not_wired(
    client: TestClient, prefix: str, method: str, path: str
) -> None:
    """Phase 7 activated Oracle ERP + SAP: unwired ``create_app()`` returns 503."""
    full = prefix + path
    r = client.request(method, full, json={})
    assert r.status_code == 503, f"{method} {full}: got {r.status_code}"


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/status"),
        ("GET", "/load/status"),
        ("POST", "/load"),
        ("POST", "/seed"),
        ("POST", "/reset"),
        ("GET", "/objects"),
        ("GET", "/objects/public/docs"),
        ("GET", "/objects/public/docs/columns"),
        ("GET", "/health"),
        # /upload/* routes require multipart UploadFile; covered separately.
    ],
)
def test_external_routes_return_503_when_simulator_not_wired(
    client: TestClient, method: str, path: str
) -> None:
    """Phase 8 activated External Source: unwired ``create_app()`` returns 503."""
    full = EXTERNAL_PREFIX + path
    r = client.request(method, full, json={})
    assert r.status_code == 503, f"{method} {full}: got {r.status_code}"


def test_openapi_spec_includes_all_routers(client: TestClient) -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    # 16 WXCC + 11 SFDC + 10 Oracle + 10 SAP + 13 External = 60
    # plus /health, /readiness, /version
    assert len(paths) >= 60
    assert any(p.startswith(WXCC_PREFIX) for p in paths)
    assert any(p.startswith(SFDC_PREFIX) for p in paths)
    assert any(p.startswith(ORACLE_ERP_PREFIX) for p in paths)
    assert any(p.startswith(SAP_PREFIX) for p in paths)
    assert any(p.startswith(EXTERNAL_PREFIX) for p in paths)
    assert "/health" in paths
    assert "/readiness" in paths
    assert "/version" in paths


def test_cli_entry_point() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "nexus_simulator.server.cli", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "serve" in out.stdout
    assert "run-seed" in out.stdout


def test_cli_serve_help() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "nexus_simulator.server.cli", "serve", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--host" in out.stdout
    assert "--port" in out.stdout


def test_mcp_server_skips_wxcc_when_simulator_unwired() -> None:
    """Phase 5 activated the MCP server; with no simulator the WXCC tool is
    skipped (no error). Validates the no-op branch in ``create_mcp_server``.
    """
    from nexus_simulator.server.mcp import create_mcp_server

    try:
        server = create_mcp_server()
    except ImportError:
        pytest.skip("fastmcp not installed in this environment")
    assert server is not None
