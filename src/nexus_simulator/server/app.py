"""FastAPI app factory for the Nexus Simulator reference server.

The factory composes the routers that belong to the library: health/readiness,
WXCC, SFDC, Oracle ERP, SAP, External Source. Each plugin router is mounted
under the same prefix nexus-backend uses today (see ``mcp_http_gateway.py``
lines 1508–1554) so UIs and MCP clients work unchanged when a host app swaps
its own simulator routes for the library's.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from .routers import external as external_router
from .routers import health as health_router
from .routers import oracle_erp as oracle_erp_router
from .routers import sap as sap_router
from .routers import sfdc as sfdc_router
from .routers import wxcc as wxcc_router

logger = logging.getLogger(__name__)

WXCC_PREFIX = "/api/v1/simulator"
SFDC_PREFIX = "/api/v1/sfdc-simulator"
ORACLE_ERP_PREFIX = "/api/v1/oracle-erp-simulator"
SAP_PREFIX = "/api/v1/sap-simulator"
EXTERNAL_PREFIX = "/api/v1/external-simulator"


def create_app(simulator: Any | None = None, *, cors_origins: list[str] | None = None) -> FastAPI:
    """Build the reference FastAPI app.

    Args:
        simulator: A ``Simulator`` instance produced by
            ``nexus_simulator.factory.build_simulator``. When ``None``, routes
            that require plugins return 503 (configuration missing). For tests,
            use ``nexus_simulator.testing.make_test_app`` which wires an
            in-memory simulator automatically.
        cors_origins: Optional list of allowed CORS origins. ``None`` disables CORS.

    Returns:
        A configured ``FastAPI`` instance. The caller is responsible for
        running it (``uvicorn``, test client, etc.).
    """
    app = FastAPI(
        title="Nexus Simulator",
        version=__version__,
        description=(
            "Pluggable simulator library. Reference server exposing the "
            "canonical HTTP surface ported from nexus-backend's per-plugin "
            "simulator APIs (WXCC, SFDC, Oracle ERP, SAP, External Source)."
        ),
    )

    app.state.simulator = simulator

    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health_router.router, tags=["health"])
    app.include_router(wxcc_router.router, prefix=WXCC_PREFIX, tags=["WXCC Simulator"])
    app.include_router(sfdc_router.router, prefix=SFDC_PREFIX, tags=["SFDC Simulator"])
    app.include_router(oracle_erp_router.router, prefix=ORACLE_ERP_PREFIX, tags=["Oracle ERP Simulator"])
    app.include_router(sap_router.router, prefix=SAP_PREFIX, tags=["SAP Simulator"])
    app.include_router(external_router.router, prefix=EXTERNAL_PREFIX, tags=["External Simulator"])

    logger.info("Nexus Simulator reference server app created (version %s)", __version__)
    return app
