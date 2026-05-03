"""Unit tests for the testing harness (Phase 4).

Verifies that:

- ``make_test_simulator`` returns a fully wired ``Simulator`` (in-memory
  cache) with no AWS or Redis required.
- ``make_test_app`` returns a FastAPI app with the simulator attached.
- ``TestHttpClient`` wraps the in-process app via ASGI transport.
- ``SeedYAMLRunner`` validates known sample YAMLs and rejects malformed
  inputs with a structured ``SeedRunResult``.
- The shipped pytest fixtures (``simulator``, ``app``, ``http_client``,
  ``mcp_client``, ``seed_runner``, ``samples_dir``) are wired correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nexus_simulator.adapters.memory import InMemoryCacheBackend
from nexus_simulator.factory import Simulator
from nexus_simulator.testing import (
    SeedRunResult,
    SeedYAMLRunner,
    TestHttpClient,
    TestMCPClient,
    make_test_app,
    make_test_mcp_server,
    make_test_simulator,
)

# ─── Factory ──────────────────────────────────────────────────────────────


def test_make_test_simulator_returns_a_simulator_with_in_memory_cache() -> None:
    sim = make_test_simulator()
    assert isinstance(sim, Simulator)
    assert isinstance(sim.cache, InMemoryCacheBackend)
    # Phases 5–8 activated all five plugins.
    assert sim.wxcc is not None
    assert sim.sfdc is not None
    assert sim.oracle_erp is not None
    assert sim.sap is not None
    assert sim.external_source is not None


def test_make_test_simulator_accepts_overrides() -> None:
    sim = make_test_simulator(region="ap-southeast-1")
    assert sim.config.region == "ap-southeast-1"


def test_make_test_app_returns_fastapi_app_with_simulator_attached() -> None:
    app = make_test_app()
    assert app.state.simulator is not None
    assert isinstance(app.state.simulator, Simulator)


def test_make_test_mcp_server_returns_a_server_when_fastmcp_available() -> None:
    """Phase 5 activated the MCP server. ``make_test_mcp_server`` returns a
    FastMCP instance with the WXCC tool registered (tool registration uses
    the in-memory test simulator)."""
    try:
        server = make_test_mcp_server()
    except ImportError:
        pytest.skip("fastmcp not installed in this environment")
    assert server is not None


# ─── HTTP client ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_http_client_in_process(app) -> None:  # uses fixture from harness
    async with TestHttpClient(app) as client:
        r = await client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_http_client_readiness_reports_simulator_present(app) -> None:
    async with TestHttpClient(app) as client:
        r = await client.get("/readiness")
        assert r.status_code == 200
        # In the harness app, simulator is wired via make_test_simulator,
        # so ready=True (unlike the unwired ``create_app()`` baseline test).
        assert r.json()["ready"] is True


# ─── Shipped fixtures ─────────────────────────────────────────────────────


def test_simulator_fixture_is_a_simulator(simulator) -> None:
    assert isinstance(simulator, Simulator)


def test_simulator_config_fixture_is_a_config(simulator_config) -> None:
    from nexus_simulator import SimulatorConfig

    assert isinstance(simulator_config, SimulatorConfig)
    assert simulator_config.region == "us-east-1"
    assert simulator_config.wxcc is not None
    assert simulator_config.sfdc is not None


def test_app_fixture_has_routes(app) -> None:
    paths = {r.path for r in app.routes}
    assert "/health" in paths
    assert "/readiness" in paths
    assert "/version" in paths


def test_mcp_client_fixture_raises_on_call_pre_phase_5(mcp_client) -> None:
    assert isinstance(mcp_client, TestMCPClient)


def test_samples_dir_fixture_resolves(samples_dir) -> None:
    assert samples_dir.is_dir()
    assert any(p.suffix == ".yaml" for p in samples_dir.iterdir())


# ─── SeedYAMLRunner ───────────────────────────────────────────────────────


def test_seed_runner_returns_missing_for_absent_file() -> None:
    runner = SeedYAMLRunner()
    result = runner.run("/nonexistent/path.yaml")
    assert isinstance(result, SeedRunResult)
    assert result.ok is False
    assert result.status == "missing"


def test_seed_runner_validates_wxcc_sample(samples_dir: Path) -> None:
    runner = SeedYAMLRunner()
    result = runner.run(samples_dir / "wxcc-smoke.yaml")
    assert result.ok is True
    assert result.status == "validated"
    assert result.name == "wxcc-smoke"
    assert result.plugin == "wxcc"
    assert result.metrics["actions"] == 4


def test_seed_runner_validates_sfdc_and_external_samples(samples_dir: Path) -> None:
    runner = SeedYAMLRunner()
    for sample in ["sfdc-smoke.yaml", "external-smoke.yaml"]:
        result = runner.run(samples_dir / sample)
        assert result.ok is True, f"{sample}: {result.errors}"
        assert result.status == "validated"


def test_seed_runner_rejects_unknown_plugin(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "name: foo\nplugin: this_plugin_does_not_exist\nactions:\n  - kind: load\n"
    )
    result = SeedYAMLRunner().run(bad)
    assert result.ok is False
    assert result.status == "invalid_shape"
    assert any("plugin" in err for err in result.errors)


def test_seed_runner_rejects_missing_actions(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: foo\nplugin: wxcc\n")
    result = SeedYAMLRunner().run(bad)
    assert result.ok is False
    assert any("actions" in err for err in result.errors)


def test_seed_runner_rejects_invalid_yaml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(":\n  - this: ['unclosed\n")
    result = SeedYAMLRunner().run(bad)
    assert result.ok is False
    assert result.status == "invalid_yaml"


def test_seed_runner_rejects_top_level_list(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- a\n- b\n")
    result = SeedYAMLRunner().run(bad)
    assert result.ok is False
    assert result.status == "invalid_shape"


def test_seed_runner_with_app_returns_pending_phase_for_each_plugin(
    samples_dir: Path, app
) -> None:
    runner = SeedYAMLRunner(app=app)
    result = runner.run(samples_dir / "wxcc-smoke.yaml")
    assert result.ok is False
    assert result.status == "pending_phase_5"  # WXCC activates in phase 5
    assert result.plugin == "wxcc"


def test_seed_run_result_summary_renders() -> None:
    result = SeedRunResult(
        ok=True,
        status="validated",
        name="t",
        plugin="wxcc",
        actions=[{"kind": "load"}],
        metrics={"actions": 1},
    )
    summary = result.summary()
    assert "validated" in summary
    assert "wxcc" in summary
    assert "actions = 1" in summary
