"""Pytest fixtures provided by the nexus-simulator harness.

Registered as a pytest plugin via the ``pytest11`` entry point in
``pyproject.toml``; anyone installing ``nexus-simulator[harness]`` gets these
fixtures automatically.

Fixtures:
    simulator_config   SimulatorConfig with sane test defaults
    simulator          Simulator instance (in-memory adapters)
    app                FastAPI app wired with the test simulator
    http_client        Async httpx client bound to the in-process app
    mcp_client         In-process MCP client (pre-phase-5 raises on use)
    seed_runner        SeedYAMLRunner bound to the test app
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

from ..config import (
    ExternalSourcePluginConfig,
    OracleERPPluginConfig,
    SAPPluginConfig,
    SFDCPluginConfig,
    SimulatorConfig,
    WXCCPluginConfig,
)
from .clients import TestHttpClient, TestMCPClient
from .factory import make_test_app, make_test_mcp_server, make_test_simulator
from .seeds import SeedYAMLRunner


@pytest.fixture
def simulator_config() -> SimulatorConfig:
    return SimulatorConfig(
        region="us-east-1",
        wxcc=WXCCPluginConfig(bucket="", prefix="wxcc-test"),
        sfdc=SFDCPluginConfig(bucket="", prefix="sfdc-test"),
        oracle_erp=OracleERPPluginConfig(bucket="", prefix="oracle-erp-test"),
        sap=SAPPluginConfig(bucket="", prefix="sap-test"),
        external_source=ExternalSourcePluginConfig(bucket="", prefix="external-test"),
    )


@pytest.fixture
def simulator(simulator_config: SimulatorConfig) -> Any:
    return make_test_simulator()


@pytest.fixture
def app(simulator: Any) -> Any:
    return make_test_app(simulator=simulator)


@pytest_asyncio.fixture
async def http_client(app: Any) -> AsyncIterator[Any]:
    async with TestHttpClient(app) as client:
        yield client


@pytest.fixture
def mcp_client(simulator: Any) -> TestMCPClient:
    try:
        server = make_test_mcp_server(simulator=simulator)
    except NotImplementedError:
        server = None
    return TestMCPClient(mcp_server=server)


@pytest.fixture
def seed_runner(app: Any) -> SeedYAMLRunner:
    return SeedYAMLRunner(app=app)
