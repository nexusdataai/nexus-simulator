"""
SAP Simulator REST API — Phase 7 (activated).

Verbatim port of nexus-backend's `src/apis/sap_simulator_api.py`. The only
intentional differences from the source:

- The module-level ``_service`` singleton is replaced with a ``Request``-driven
  lookup of ``request.app.state.simulator.oracle_erp`` so the host's
  ``build_simulator(config)`` instance is used.
- Imports are rewritten to point at the in-tree Oracle ERP plugin
  (``nexus_simulator.plugins.oracle_erp.*``).
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger

from ...plugins.sap.models import AdminResponse, SimulatorStatus  # noqa: F401  - parity
from ...plugins.sap.service import SAPSimulatorService

router = APIRouter()

_PLUGIN_NAME = "sap"
_PLUGIN_TAG = "SAP Simulator"


def get_service(request: Request) -> SAPSimulatorService:
    sim = getattr(request.app.state, "simulator", None)
    if sim is None or getattr(sim, _PLUGIN_NAME, None) is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"{_PLUGIN_TAG} plugin not configured. Pass SAPPluginConfig in "
                "SimulatorConfig.sap and call build_simulator(config)."
            ),
        )
    return getattr(sim, _PLUGIN_NAME)


@router.get("/status", tags=[_PLUGIN_TAG])
async def get_status(request: Request):
    service = get_service(request)
    status = service.get_status()
    if not service.loaded and service.bucket:
        manifest = service._s3_get_json("manifest.json")
        if manifest:
            status["dump_timestamp"] = manifest.get("dump_timestamp")
            status["dump_available"] = True
            status["dump_tables"] = manifest.get("total_tables", 0)
            status["dump_rows"] = manifest.get("total_rows_dumped", 0)
    return status


@router.get("/load/status", tags=[_PLUGIN_TAG])
async def get_load_status(request: Request):
    service = get_service(request)
    return service.get_load_status()


@router.post("/load", response_model=AdminResponse, tags=[_PLUGIN_TAG])
async def load_data(request: Request):
    service = get_service(request)
    asyncio.create_task(service.load_from_s3())
    return AdminResponse(success=True, message="Load started in background. Poll GET /status for updates.")


@router.post("/reset", response_model=AdminResponse, tags=[_PLUGIN_TAG])
async def reset_data(request: Request):
    service = get_service(request)
    asyncio.create_task(service.load_from_s3())
    return AdminResponse(success=True, message="Reset started. Poll GET /status for updates.")


@router.get("/objects", tags=[_PLUGIN_TAG])
async def list_objects(request: Request):
    service = get_service(request)
    if service.loaded:
        return {"objects": await service.get_object_list()}
    return {"objects": [], "message": "Simulator not loaded. Click 'Load Data' to load from S3."}


@router.get("/objects/{schema}/{table}", tags=[_PLUGIN_TAG])
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
    raise HTTPException(status_code=400, detail="Simulator not loaded. Click 'Load Data' first.")


@router.get("/objects/{schema}/{table}/columns", tags=[_PLUGIN_TAG])
async def get_object_columns(request: Request, schema: str, table: str):
    service = get_service(request)
    if service.loaded:
        cols = await service.get_table_columns(schema, table)
    else:
        raise HTTPException(status_code=400, detail="Simulator not loaded")

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


@router.get("/dump/status", tags=[_PLUGIN_TAG])
async def get_dump_status(request: Request):
    service = get_service(request)
    return service.get_dump_status() if hasattr(service, "get_dump_status") else {"running": False}


@router.post("/restart-pods", response_model=AdminResponse, tags=[_PLUGIN_TAG])
async def restart_pods(request: Request):
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


@router.get("/health", tags=[_PLUGIN_TAG])
async def health_check(request: Request):
    service = get_service(request)
    if service.loaded:
        return {
            "status": "healthy" if service.loaded else "not_loaded",
            "mode": "simulator",
            "enabled": service.enabled,
            "bucket_configured": bool(service.bucket),
            "loaded": service.loaded,
            "timestamp": datetime.utcnow().isoformat(),
        }

    return {
        "status": "degraded",
        "mode": "simulator",
        "enabled": False,
        "loaded": False,
        "timestamp": datetime.utcnow().isoformat(),
    }
