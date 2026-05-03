"""
SFDC Simulator REST API — Phase 6 (activated).

Verbatim port of nexus-backend's `src/apis/sfdc_simulator_api.py`. The only
intentional differences from the source:

- The module-level ``_service`` singleton is replaced with a ``Request``-driven
  lookup of ``request.app.state.simulator.sfdc`` so the host's
  ``build_simulator(config)`` instance is used.
- Imports are rewritten to point at the in-tree SFDC plugin
  (``nexus_simulator.plugins.sfdc.*``) and the in-tree FDW models
  (``nexus_simulator.models.fdw``).

The live-FDW pass-through (``_fdw_discovery``, ``_fdw_query``,
``_fdw_connection_manager``) is unchanged. The host (typically nexus-backend)
calls ``configure_fdw(...)`` at startup to wire those services in. Standalone
deployments leave them as ``None`` and the router serves cache-only data.

PORT FIDELITY CHECKLIST — see docs/ROUTE_PARITY.md for the source-line map.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger

from ...plugins.sfdc.models import AdminResponse, DumpRequest, SimulatorStatus  # noqa: F401  - parity
from ...plugins.sfdc.service import SFDCSimulatorService

router = APIRouter()

# Live-FDW services injected by the host application via configure_fdw(...).
_fdw_discovery: Any | None = None
_fdw_query: Any | None = None
_fdw_connection_manager: Any | None = None


def get_service(request: Request) -> SFDCSimulatorService:
    """Resolve the SFDC plugin off the wired ``Simulator`` on app state."""
    sim = getattr(request.app.state, "simulator", None)
    if sim is None or getattr(sim, "sfdc", None) is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "SFDC simulator plugin not configured. "
                "Pass SFDCPluginConfig in SimulatorConfig.sfdc and call build_simulator(config)."
            ),
        )
    return sim.sfdc


def configure_fdw(discovery_service=None, query_service=None, connection_manager=None) -> None:
    """Wire live FDW services so endpoints work in real mode."""
    global _fdw_discovery, _fdw_query, _fdw_connection_manager
    _fdw_discovery = discovery_service
    _fdw_query = query_service
    _fdw_connection_manager = connection_manager


def _is_simulator_active(service: SFDCSimulatorService | None) -> bool:
    return service is not None and service.loaded


@router.get("/status", tags=["SFDC Simulator"])
async def get_status(request: Request):
    service = get_service(request)
    status = service.get_status()
    if not service.loaded and service.bucket:
        manifest = await service._storage.get_json("manifest.json") if service._storage else None
        if manifest:
            status["dump_timestamp"] = manifest.get("dump_timestamp")
            status["dump_available"] = True
            status["dump_tables"] = manifest.get("total_tables", 0)
            status["dump_rows"] = manifest.get("total_rows_dumped", 0)

    if not _is_simulator_active(service) and _fdw_discovery is not None:
        try:
            servers = await _fdw_discovery.list_foreign_servers()
            tables = await _fdw_discovery.list_foreign_tables()
            health_info = {}
            if _fdw_connection_manager is not None:
                health_info = await _fdw_connection_manager.health_check()
            status["fdw_connected"] = health_info.get("status") == "healthy"
            status["fdw_latency_ms"] = health_info.get("latency_ms")
            status["server_count"] = len(servers)
            if not service.loaded:
                status["table_count"] = len(tables)
                status["tables_with_data"] = len(tables)
        except Exception as e:
            logger.warning(f"FDW status check failed: {e}")

    return status


@router.get("/load/status", tags=["SFDC Simulator"])
async def get_load_status(request: Request):
    """Poll load progress (in-memory, per-pod)."""
    service = get_service(request)
    return service.get_load_status()


@router.post("/load", response_model=AdminResponse, tags=["SFDC Simulator"])
async def load_data(request: Request):
    """Load data from S3 dump (background task on main event loop)."""
    service = get_service(request)
    asyncio.create_task(service.load_from_s3())
    return AdminResponse(success=True, message="Load started in background. Poll GET /status for updates.")


@router.post("/reset", response_model=AdminResponse, tags=["SFDC Simulator"])
async def reset_data(request: Request):
    service = get_service(request)
    asyncio.create_task(service.load_from_s3())
    return AdminResponse(success=True, message="Reset started. Poll GET /status for updates.")


@router.get("/objects", tags=["SFDC Simulator"])
async def list_objects(request: Request):
    service = get_service(request)
    if service.loaded:
        return {"objects": await service.get_object_list()}

    if _fdw_discovery is not None:
        try:
            tables = await _fdw_discovery.list_foreign_tables()
            objects = []
            for t in tables:
                objects.append({
                    "schemaName": t.schema_name,
                    "tableName": t.table_name,
                    "columnCount": t.column_count,
                    "rowCount": None,
                })
            return {"objects": objects, "source": "live_fdw"}
        except Exception as e:
            logger.warning(f"FDW list objects failed: {e}")
            return {"objects": [], "message": f"FDW query failed: {e}"}

    return {"objects": [], "message": "Simulator not loaded. Click 'Load Data' to load from S3."}


@router.get("/objects/{schema}/{table}", tags=["SFDC Simulator"])
async def get_object_records(
    request: Request,
    schema: str,
    table: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    service = get_service(request)
    if service.loaded:
        return await service.get_object_records(schema, table, limit, offset)

    if _fdw_query is not None:
        try:
            from ...models.fdw import QueryRequest
            query = QueryRequest(table=table, schema_name=schema, limit=limit, offset=offset)
            result = await _fdw_query.execute_query(query)
            return {
                "schemaName": schema,
                "tableName": table,
                "rows": result.rows,
                "total": result.metadata.row_count if result.metadata else len(result.rows),
                "limit": limit,
                "offset": offset,
            }
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"FDW query failed: {e}") from e

    raise HTTPException(status_code=400, detail="Simulator not loaded. Click 'Load Data' first.")


@router.get("/objects/{schema}/{table}/columns", tags=["SFDC Simulator"])
async def get_object_columns(request: Request, schema: str, table: str):
    service = get_service(request)
    if service.loaded:
        cols = await service.get_table_columns(schema, table)
    elif _fdw_discovery is not None:
        try:
            cols = await _fdw_discovery.get_table_columns(schema, table)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"FDW column lookup failed: {e}") from e
    else:
        raise HTTPException(status_code=400, detail="Simulator not loaded. Click 'Load Data' first.")

    return {
        "schemaName": schema,
        "tableName": table,
        "columns": [
            {
                "columnName": c.column_name,
                "dataType": c.data_type,
                "isNullable": c.is_nullable,
                "ordinalPosition": c.ordinal_position,
            }
            for c in cols
        ],
    }


@router.post("/dump", response_model=AdminResponse, tags=["SFDC Simulator"])
async def dump_from_live(request: Request, payload: DumpRequest):
    """Start a dump from a live FDW runtime. Runs as background task, poll GET /dump/status."""
    service = get_service(request)
    if not service.bucket:
        raise HTTPException(status_code=400, detail="SFDC_SIMULATOR_BUCKET not configured")

    if hasattr(service, "get_dump_status"):
        current = service.get_dump_status()
        if current.get("running"):
            return AdminResponse(success=False, message="A dump is already in progress.")
        service._set_dump_status(True, {"message": "Starting..."})

    async def _run_dump():
        try:
            await service.dump_from_live_fdw(
                source_url=payload.source_url, schema=payload.schema,
                tables=payload.tables, dump_all=payload.dump_all, limit=payload.limit,
            )
        except Exception as e:
            logger.error(f"Live FDW dump failed: {e}")
            if hasattr(service, "_set_dump_status"):
                service._set_dump_status(False, {"success": False, "message": str(e)})

    asyncio.create_task(_run_dump())

    return AdminResponse(
        success=True,
        message="Dump started in background. Poll GET /dump/status for progress.",
    )


@router.get("/dump/status", tags=["SFDC Simulator"])
async def get_dump_status(request: Request):
    """Poll dump progress (reads from S3, works across all pods)."""
    service = get_service(request)
    return service.get_dump_status() if hasattr(service, "get_dump_status") else {"running": False}


@router.post("/restart-pods", response_model=AdminResponse, tags=["SFDC Simulator"])
async def restart_pods(request: Request):
    """Restart backend pods to apply mode changes (rolling restart via K8s API)."""
    import os
    try:
        namespace = os.getenv("NAMESPACE", "")
        if not namespace:
            cap = os.getenv("CAPABILITY_NAME", "call-processing")
            env = os.getenv("ENVIRONMENT", "dev")
            namespace = f"{cap}-{env}"

        from kubernetes import client
        from kubernetes import config as k8s_config
        try:
            k8s_config.load_incluster_config()
        except Exception:
            k8s_config.load_kube_config()

        apps_v1 = client.AppsV1Api()
        deployment_name = f"{namespace}-backend"

        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": datetime.utcnow().isoformat() + "Z"
                        }
                    }
                }
            }
        }
        apps_v1.patch_namespaced_deployment(deployment_name, namespace, body)
        logger.info(f"Triggered rolling restart for {deployment_name} in {namespace}")

        return AdminResponse(
            success=True,
            message=f"Rolling restart triggered for {deployment_name}. Pods will restart over the next ~60s.",
        )
    except ImportError:
        logger.warning("kubernetes package not available, cannot restart pods")
        return AdminResponse(success=False, message="kubernetes package not installed in this environment")
    except Exception as e:
        logger.error(f"Failed to restart pods: {e}")
        return AdminResponse(success=False, message=str(e))


@router.get("/health", tags=["SFDC Simulator"])
async def health_check(request: Request):
    service = get_service(request)
    if _is_simulator_active(service):
        return {
            "status": "healthy" if service.loaded else "not_loaded",
            "mode": "simulator",
            "enabled": service.enabled,
            "bucket_configured": bool(service.bucket),
            "loaded": service.loaded,
            "timestamp": datetime.utcnow().isoformat(),
        }

    fdw_healthy = False
    if _fdw_connection_manager is not None:
        try:
            health = await _fdw_connection_manager.health_check()
            fdw_healthy = health.get("status") == "healthy"
        except Exception:
            pass

    return {
        "status": "healthy" if fdw_healthy else "degraded",
        "mode": "real",
        "enabled": False,
        "fdw_connected": fdw_healthy,
        "loaded": False,
        "timestamp": datetime.utcnow().isoformat(),
    }
