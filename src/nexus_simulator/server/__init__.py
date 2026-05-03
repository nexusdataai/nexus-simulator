"""Reference server for the Nexus Simulator.

Ships the canonical FastAPI app factory, MCP server, and ``nexus-simulator
serve`` CLI. The server is importable by host applications that prefer to
mount the library's routers in their own FastAPI instance; it is also runnable
standalone for local development, container images, and Kubernetes pods.

Routes are documented in docs/ROUTE_PARITY.md. Each router file starts with a
port-fidelity checklist citing the nexus-backend source lines to port per
phase of the extraction.
"""

from .app import (
    EXTERNAL_PREFIX,
    ORACLE_ERP_PREFIX,
    SAP_PREFIX,
    SFDC_PREFIX,
    WXCC_PREFIX,
    create_app,
)

__all__ = [
    "create_app",
    "WXCC_PREFIX",
    "SFDC_PREFIX",
    "ORACLE_ERP_PREFIX",
    "SAP_PREFIX",
    "EXTERNAL_PREFIX",
]
