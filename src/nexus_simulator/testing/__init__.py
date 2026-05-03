"""Shipped testing harness for nexus-simulator.

Public API:
    make_test_simulator(**overrides) -> Simulator
    make_test_app(simulator=None) -> FastAPI
    make_test_mcp_server(simulator=None)
    TestHttpClient
    TestMCPClient
    SeedYAMLRunner, SeedRunResult

Install with the harness extra:
    pip install "nexus-simulator[harness]"

Any project using pytest automatically receives the fixtures registered by
``nexus_simulator.testing.fixtures`` (via the pytest11 entry point). See
tests/README.md for usage patterns.
"""

from __future__ import annotations

from .clients import TestHttpClient, TestMCPClient
from .factory import make_test_app, make_test_mcp_server, make_test_simulator
from .seeds import SeedRunResult, SeedYAMLRunner

__all__ = [
    "SeedRunResult",
    "SeedYAMLRunner",
    "TestHttpClient",
    "TestMCPClient",
    "make_test_app",
    "make_test_mcp_server",
    "make_test_simulator",
]
