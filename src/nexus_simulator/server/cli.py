"""``nexus-simulator`` console script.

Boots either the FastAPI reference server or runs a one-shot per-plugin seed.
``SimulatorConfig`` is loaded from environment variables for now (matching
nexus-backend's env var contract); a future release may add ``--config
path/to.yaml`` as well.

Commands:
    serve       Run the HTTP reference server.
    run-seed    Execute a plugin-seed YAML end-to-end (uses the testing harness).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s - %(message)s",
    )


def _build_simulator_config():
    """Construct a ``SimulatorConfig`` from environment variables.

    Every field falls back to sensible defaults so ``nexus-simulator serve``
    works out of the box in a container with no env vars set (in-memory
    adapters will be used once ``build_simulator`` is fully implemented).
    Per-plugin configs are only populated when the matching ``*_BUCKET`` env
    var is set; that gates which plugins activate at startup.
    """
    from ..config import (
        ExternalSourcePluginConfig,
        OracleERPPluginConfig,
        SAPPluginConfig,
        SFDCPluginConfig,
        SimulatorConfig,
        WXCCPluginConfig,
    )

    def _wxcc():
        bucket = os.environ.get("WXCC_SIMULATOR_BUCKET", "")
        if not bucket and os.environ.get("WXCC_SIMULATOR_ENABLED", "true").lower() == "false":
            return None
        return WXCCPluginConfig(
            bucket=bucket,
            prefix=os.environ.get("WXCC_SIMULATOR_PREFIX", "wxcc-simulator"),
            org_id=os.environ.get("WXCC_SIM_ORG_ID", "sim-org-001"),
            base_url=os.environ.get("WXCC_SIMULATOR_BASE_URL", "http://localhost:8000"),
            bearer_token=os.environ.get("WXCC_SIM_TOKEN", "test-token-12345"),
            enabled=os.environ.get("WXCC_SIMULATOR_ENABLED", "true").lower() != "false",
        )

    def _sfdc():
        bucket = os.environ.get("SFDC_SIMULATOR_BUCKET", "")
        if not bucket:
            return None
        return SFDCPluginConfig(
            bucket=bucket,
            prefix=os.environ.get("SFDC_SIMULATOR_PREFIX", "sfdc-simulator"),
        )

    def _oracle_erp():
        bucket = os.environ.get("ORACLE_ERP_SIMULATOR_BUCKET", "")
        if not bucket:
            return None
        return OracleERPPluginConfig(
            bucket=bucket,
            prefix=os.environ.get("ORACLE_ERP_SIMULATOR_PREFIX", "oracle-erp-simulator"),
        )

    def _sap():
        bucket = os.environ.get("SAP_SIMULATOR_BUCKET", "")
        if not bucket:
            return None
        return SAPPluginConfig(
            bucket=bucket,
            prefix=os.environ.get("SAP_SIMULATOR_PREFIX", "sap-simulator"),
        )

    def _external_source():
        bucket = os.environ.get("EXTERNAL_SIMULATOR_BUCKET", "")
        if not bucket:
            return None
        return ExternalSourcePluginConfig(
            bucket=bucket,
            prefix=os.environ.get("EXTERNAL_SIMULATOR_PREFIX", "external-simulator"),
        )

    return SimulatorConfig(
        region=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
        role_arn=os.environ.get("AWS_ROLE_ARN"),
        redis_url=os.environ.get("REDIS_URL"),
        wxcc=_wxcc(),
        sfdc=_sfdc(),
        oracle_erp=_oracle_erp(),
        sap=_sap(),
        external_source=_external_source(),
    )


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .app import create_app

    simulator = None
    try:
        from ..factory import build_simulator

        simulator = build_simulator(_build_simulator_config())
    except Exception as exc:
        logging.getLogger(__name__).exception("build_simulator failed: %s", exc)
        return 1

    app = create_app(simulator=simulator, cors_origins=args.cors_origin or None)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
        access_log=not args.no_access_log,
    )
    return 0


def _cmd_run_seed(args: argparse.Namespace) -> int:
    try:
        from ..testing import SeedYAMLRunner
    except ImportError as exc:
        print(
            f"run-seed requires the harness extra: pip install 'nexus-simulator[harness]' ({exc})",
            file=sys.stderr,
        )
        return 2

    runner = SeedYAMLRunner()
    result = runner.run(args.path)
    print(result.summary())
    return 0 if result.ok else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nexus-simulator")
    parser.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        help="Logging level (default: INFO)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the HTTP reference server")
    serve.add_argument("--http", action="store_true", default=True, help="Serve HTTP (default)")
    serve.add_argument("--host", default=os.environ.get("API_HOST", "0.0.0.0"))
    serve.add_argument("--port", type=int, default=int(os.environ.get("API_PORT", "8000")))
    serve.add_argument("--cors-origin", action="append", default=[], help="Allowed CORS origin (repeatable)")
    serve.add_argument("--no-access-log", action="store_true")
    serve.set_defaults(func=_cmd_serve)

    run = sub.add_parser("run-seed", help="Execute a plugin-seed YAML end-to-end")
    run.add_argument("path", help="Path to a plugin-seed YAML file")
    run.set_defaults(func=_cmd_run_seed)

    args = parser.parse_args(argv)
    _configure_logging(args.log_level)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
