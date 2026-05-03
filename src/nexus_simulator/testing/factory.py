"""Factories that assemble an in-memory simulator + app for tests."""

from __future__ import annotations

from typing import Any

from ..config import (
    ExternalSourcePluginConfig,
    OracleERPPluginConfig,
    SAPPluginConfig,
    SFDCPluginConfig,
    SimulatorConfig,
    WXCCPluginConfig,
)


def make_test_simulator(**overrides: Any) -> Any:
    """Build a ``Simulator`` suitable for tests.

    Defaults to a config that enables every in-tree plugin with empty bucket
    names so the in-memory storage adapter is selected. ``redis_url`` is left
    unset so the in-memory cache is selected too. No real AWS or Redis is
    contacted.

    Plugin ``WXCCPluginConfig`` / ``SFDCPluginConfig`` etc. are wired with
    safe defaults; pass ``wxcc=...`` / ``sfdc=...`` overrides to customize a
    single plugin without disabling the others.

    Args:
        **overrides: Replace any field of ``SimulatorConfig`` directly.
            ``extras`` is preserved for arbitrary test annotations.

    Returns:
        A fully wired ``Simulator`` with all five plugins enabled (plugins
        themselves are stubbed until their owning phase lands).
    """
    config_kwargs: dict[str, Any] = {
        "region": overrides.pop("region", "us-east-1"),
        "role_arn": overrides.pop("role_arn", None),
        "redis_url": overrides.pop("redis_url", None),
        "wxcc": overrides.pop("wxcc", WXCCPluginConfig(bucket="", prefix="wxcc-test")),
        "sfdc": overrides.pop("sfdc", SFDCPluginConfig(bucket="", prefix="sfdc-test")),
        "oracle_erp": overrides.pop(
            "oracle_erp", OracleERPPluginConfig(bucket="", prefix="oracle-erp-test")
        ),
        "sap": overrides.pop("sap", SAPPluginConfig(bucket="", prefix="sap-test")),
        "external_source": overrides.pop(
            "external_source", ExternalSourcePluginConfig(bucket="", prefix="external-test")
        ),
        "extras": overrides,
    }
    config = SimulatorConfig(**config_kwargs)

    from ..factory import build_simulator

    return build_simulator(config)


def make_test_app(simulator: Any | None = None) -> Any:
    """Return a FastAPI app configured for in-process testing.

    Creates a simulator via :func:`make_test_simulator` when none is supplied.
    """
    from ..server.app import create_app

    if simulator is None:
        simulator = make_test_simulator()
    return create_app(simulator=simulator)


def make_test_mcp_server(simulator: Any | None = None) -> Any:
    """Return an MCP server configured for in-process testing.

    Pre-phase-5 this raises ``NotImplementedError`` because the MCP server
    wiring lands with the WXCC tool activation.
    """
    from ..server.mcp import create_mcp_server

    if simulator is None:
        simulator = make_test_simulator()
    return create_mcp_server(simulator=simulator)
