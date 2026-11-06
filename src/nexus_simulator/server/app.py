"""FastAPI app factory for the Nexus Simulator product server."""

from __future__ import annotations

import logging
from typing import Any

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .. import __version__
from . import connector_runtime
from .routers import bss as bss_router
from .routers import catalog as catalog_router
from .routers import external as external_router
from .routers import fdw as fdw_router
from .routers import health as health_router
from .routers import nss as nss_router
from .routers import oracle_erp as oracle_erp_router
from .routers import oss as oss_router
from .routers import sap as sap_router
from .routers import sfdc as sfdc_router
from .routers import sourcing as sourcing_router
from .routers import telco as telco_router
from .routers import telco_golden as telco_golden_router
from .routers import telco_sources as telco_sources_router
from .routers import telco_sources_admin as telco_sources_admin_router
from .routers import tmf_telco as tmf_telco_router
from .routers import tpm as tpm_router
from .routers import wxcc as wxcc_router
from .routers.connectors import external_connector_api
from .routers.connectors import oracle_erp_connector_api
from .routers.connectors import sap_connector_api
from .routers.connectors import sfdc_connector_api
from .routers import oracle_fusion as oracle_fusion_router
from .routers import sap_odata as sap_odata_router
from .routers import sfdc_rest as sfdc_rest_router
from .routers import scenarios as scenarios_router
from .routers import vendor_apis as vendor_apis_router

logger = logging.getLogger(__name__)

WXCC_PREFIX = "/api/v1/simulator"
SFDC_PREFIX = "/api/v1/sfdc-simulator"
ORACLE_ERP_PREFIX = "/api/v1/oracle-erp-simulator"
SAP_PREFIX = "/api/v1/sap-simulator"
EXTERNAL_PREFIX = "/api/v1/external-simulator"
TPM_PREFIX = "/api/v1/tpm-simulator"
SOURCING_PREFIX = "/api/v1/sourcing-simulator"
BSS_PREFIX = "/api/v1/bss-simulator"
NSS_PREFIX = "/api/v1/nss-simulator"
OSS_PREFIX = "/api/v1/oss-simulator"
TELCO_GOLDEN_PREFIX = "/api/v1/telco-golden-simulator"
TELCO_SOURCES_PREFIX = "/api/v1/telco-sources-simulator"


def create_app(simulator: Any | None = None, *, cors_origins: list[str] | None = None) -> FastAPI:
    """Build the product FastAPI app."""
    app = FastAPI(
        title="Nexus Simulator",
        version=__version__,
        description=(
            "Standalone Enterprise Data Simulator service. Hosts Redis/S3-backed "
            "FDW catalogs and simulated Salesforce / Oracle / SAP / external / CPQ APIs."
        ),
    )

    app.state.simulator = simulator
    connector_runtime.configure_runtime(simulator)

    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health_router.router, tags=["health"])
    app.include_router(catalog_router.router)
    app.include_router(fdw_router.router)
    app.include_router(wxcc_router.router, prefix=WXCC_PREFIX, tags=["WXCC Simulator"])
    app.include_router(sfdc_router.router, prefix=SFDC_PREFIX, tags=["SFDC Simulator"])
    app.include_router(oracle_erp_router.router, prefix=ORACLE_ERP_PREFIX, tags=["Oracle ERP Simulator"])
    app.include_router(sap_router.router, prefix=SAP_PREFIX, tags=["SAP Simulator"])
    app.include_router(external_router.router, prefix=EXTERNAL_PREFIX, tags=["External Simulator"])
    app.include_router(tpm_router.router, prefix=TPM_PREFIX, tags=["TPM Simulator"])
    app.include_router(sourcing_router.router, prefix=SOURCING_PREFIX, tags=["Sourcing Simulator"])
    app.include_router(bss_router.router, prefix=BSS_PREFIX, tags=["BSS Simulator"])
    app.include_router(nss_router.router, prefix=NSS_PREFIX, tags=["NSS Simulator"])
    app.include_router(oss_router.router, prefix=OSS_PREFIX, tags=["OSS Simulator"])
    app.include_router(telco_router.router)
    # Optional legacy plugins (enable via TELCO_*_SIMULATOR_ENABLED=true in CLI config)
    if simulator is not None and (
        getattr(simulator, "telco_golden", None) is not None
        or simulator.registry.get("telco_golden") is not None
    ):
        app.include_router(telco_golden_router.router, prefix=TELCO_GOLDEN_PREFIX, tags=["Telco Golden Simulator"])
    if simulator is not None and (
        getattr(simulator, "telco_sources", None) is not None
        or simulator.registry.get("telco_sources") is not None
    ):
        app.include_router(telco_sources_router.router)
        app.include_router(telco_sources_admin_router.router, prefix=TELCO_SOURCES_PREFIX, tags=["Telco Sources Simulator"])
    app.include_router(tmf_telco_router.router)

    _atlas_dir = Path(__file__).resolve().parents[3] / "data" / "Telco-Data"
    if _atlas_dir.is_dir():
        app.mount("/telco-atlas", StaticFiles(directory=str(_atlas_dir), html=True), name="telco-atlas")
    app.include_router(sfdc_connector_api.router)
    app.include_router(oracle_erp_connector_api.router)
    app.include_router(sap_connector_api.router)
    app.include_router(external_connector_api.router)
    app.include_router(vendor_apis_router.router)
    app.include_router(scenarios_router.router)
    app.include_router(sfdc_rest_router.router)
    app.include_router(oracle_fusion_router.router)
    app.include_router(sap_odata_router.router)

    @app.on_event("startup")
    async def _hydrate_plugins() -> None:
        if simulator is None:
            return
        for name, svc in simulator.registry.all().items():
            if name in ("simulator", "oracle_erp", "external_source", "bss", "nss", "oss"):
                continue
            try:
                if hasattr(svc, "ensure_loaded"):
                    await svc.ensure_loaded()
                if not getattr(svc, "loaded", False) and hasattr(svc, "seed_data"):
                    await svc.seed_data()
                if hasattr(svc, "rebuild_catalog_from_cache"):
                    await svc.rebuild_catalog_from_cache()
                logger.info(
                    "simulator plugin ready: %s loaded=%s tables=%s rows=%s",
                    name,
                    getattr(svc, "loaded", False),
                    getattr(svc, "_tables", None) and len(svc._tables),
                    getattr(svc, "_total_rows", None),
                )
            except Exception:
                logger.exception("simulator plugin hydrate failed: %s", name)

        # Telco plugins: BSS → NSS → OSS, then optional legacy sources → golden when registered.
        telco_order: list[str] = ["bss", "nss", "oss"]
        for extra in ("telco_sources", "telco_golden"):
            if simulator.registry.get(extra):
                telco_order.append(extra)
        for name in telco_order:
            svc = simulator.registry.get(name)
            if svc is None:
                continue
            try:
                if hasattr(svc, "ensure_loaded"):
                    await svc.ensure_loaded()
                if not getattr(svc, "loaded", False) and hasattr(svc, "seed_data"):
                    await svc.seed_data()
                if hasattr(svc, "rebuild_catalog_from_cache"):
                    await svc.rebuild_catalog_from_cache()
                logger.info(
                    "telco plugin ready: %s loaded=%s tables=%s rows=%s",
                    name,
                    getattr(svc, "loaded", False),
                    getattr(svc, "_tables", None) and len(svc._tables),
                    getattr(svc, "_total_rows", None),
                )
            except Exception:
                logger.exception("telco ordered hydrate failed: %s", name)

    logger.info("Nexus Simulator app created (version %s)", __version__)
    return app
