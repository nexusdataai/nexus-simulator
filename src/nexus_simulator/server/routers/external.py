"""
External Source Simulator REST API — Phase 8 (activated).

Verbatim port of nexus-backend's `src/apis/external_source_simulator_api.py`.
The only intentional differences from the source:

- The module-level ``_service`` singleton is replaced with a ``Request``-driven
  lookup of ``request.app.state.simulator.external_source`` so the host's
  ``build_simulator(config)`` instance is used.
- Imports are rewritten to point at the in-tree External Source plugin
  (``nexus_simulator.plugins.external_source.*``); ``DocumentExtractionService``
  is now a sibling module under that plugin.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from loguru import logger

from ...plugins.external_source.service import ExternalSourceSimulatorService

router = APIRouter()


def get_service(request: Request) -> ExternalSourceSimulatorService:
    sim = getattr(request.app.state, "simulator", None)
    if sim is None or getattr(sim, "external_source", None) is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "External Source simulator plugin not configured. "
                "Pass ExternalSourcePluginConfig in SimulatorConfig.external_source "
                "and call build_simulator(config)."
            ),
        )
    return sim.external_source


@router.get("/status", tags=["External Simulator"])
async def get_status(request: Request):
    service = get_service(request)
    return service.get_status()


@router.get("/load/status", tags=["External Simulator"])
async def get_load_status(request: Request):
    service = get_service(request)
    return service.get_load_status()


@router.post("/load", tags=["External Simulator"])
async def load_data(request: Request):
    service = get_service(request)
    asyncio.create_task(service.load_from_s3())
    return {"success": True, "message": "Load started in background. Poll GET /status for updates."}


@router.post("/seed", tags=["External Simulator"])
async def seed_data(request: Request):
    service = get_service(request)
    asyncio.create_task(service.seed_data())
    return {"success": True, "message": "Seed started in background. Poll GET /status for updates."}


@router.post("/reset", tags=["External Simulator"])
async def reset_data(request: Request):
    service = get_service(request)
    if service.bucket:
        asyncio.create_task(service.load_from_s3())
    else:
        asyncio.create_task(service.seed_data())
    return {"success": True, "message": "Reset started. Poll GET /status for updates."}


@router.get("/sources", tags=["External Simulator"])
async def list_sources(request: Request):
    service = get_service(request)
    return {"sources": await service.get_sources_catalog()}


@router.get("/files", tags=["External Simulator"])
async def list_files(request: Request, source: str | None = Query(None)):
    service = get_service(request)
    if not service.loaded:
        return {"files": [], "message": "Simulator not loaded. Seed data first."}
    return {"files": await service.get_files_manifest(source)}


@router.get("/files/preview", tags=["External Simulator"])
async def preview_file(request: Request, path: str = Query(..., min_length=1)):
    service = get_service(request)
    if not service.loaded:
        raise HTTPException(status_code=400, detail="Simulator not loaded.")
    return await service.get_file_preview(path)


@router.get("/social", tags=["External Simulator"])
async def social_feed(request: Request, limit: int = Query(100, ge=1, le=500)):
    service = get_service(request)
    if not service.loaded:
        return {"items": [], "message": "Simulator not loaded. Seed data first."}
    return {"items": await service.get_social_feed(limit)}


@router.get("/objects", tags=["External Simulator"])
async def list_objects(request: Request):
    service = get_service(request)
    if service.loaded:
        return {"objects": await service.get_object_list()}
    return {"objects": [], "message": "Simulator not loaded. Click 'Seed Data' to generate synthetic data."}


@router.get("/objects/{schema}/{table}", tags=["External Simulator"])
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
    raise HTTPException(status_code=400, detail="Simulator not loaded.")


@router.get("/objects/{schema}/{table}/columns", tags=["External Simulator"])
async def get_object_columns(request: Request, schema: str, table: str):
    service = get_service(request)
    if not service.loaded:
        raise HTTPException(status_code=400, detail="Simulator not loaded")
    cols = await service.get_table_columns(schema, table)
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


@router.get("/health", tags=["External Simulator"])
async def health_check(request: Request):
    service = get_service(request)
    if service.loaded:
        return {
            "status": "healthy",
            "mode": "simulator",
            "enabled": service.enabled,
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


# ============================================================================
# Document Upload + Extraction Endpoints
# ============================================================================

UPLOAD_CONFIG = {
    "invoice": {"table": "Invoice_Upload", "prefix": "IU-", "s3_folder": "uploads/invoices", "id_field": "Upload_ID", "path_field": "File_Path"},
    "lab-report": {"table": "Lab_Report_Upload", "prefix": "LR-", "s3_folder": "uploads/lab_reports", "id_field": "Upload_ID", "path_field": "File_Path"},
    "contract": {"table": "Contract_Document", "prefix": "CTR-", "s3_folder": "uploads/contracts", "id_field": "Contract_ID", "path_field": "Document_Path"},
    "sustainability-report": {"table": "Sustainability_Report", "prefix": "SR-", "s3_folder": "uploads/sustainability", "id_field": "Report_ID", "path_field": "Document_Path"},
}

_extraction_service = None


def _get_extraction_service():
    global _extraction_service
    if _extraction_service is None:
        from ...plugins.external_source.extraction import DocumentExtractionService
        _extraction_service = DocumentExtractionService()
    return _extraction_service


async def _handle_upload(request: Request, file: UploadFile, doc_type: str):
    cfg = UPLOAD_CONFIG.get(doc_type)
    if not cfg:
        raise HTTPException(status_code=400, detail=f"Unknown document type: {doc_type}")

    service = get_service(request)
    if not service.loaded:
        raise HTTPException(status_code=400, detail="Simulator not loaded. Seed data first.")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")

    filename = file.filename or "unknown"
    s3_bucket = service.bucket
    s3_key = ""

    if s3_bucket:
        try:
            import boto3
            s3 = boto3.client("s3")
            s3_key = (
                f"{service.prefix}/{cfg['s3_folder']}/{filename}"
                if service.prefix
                else f"{cfg['s3_folder']}/{filename}"
            )
            s3.put_object(Bucket=s3_bucket, Key=s3_key, Body=content,
                          ContentType=file.content_type or "application/octet-stream")
            logger.info(f"Uploaded to s3://{s3_bucket}/{s3_key}")
        except Exception as e:
            logger.warning(f"S3 upload failed (continuing with extraction): {e}")

    extractor = _get_extraction_service()
    fields = await extractor.extract_document(content, filename, doc_type.replace("-", "_"), s3_bucket, s3_key)

    row_id = await service.next_id(cfg["table"], cfg["prefix"])
    file_path = f"/{cfg['s3_folder']}/{filename}"

    row = {cfg["id_field"]: row_id, cfg["path_field"]: file_path, **fields}
    row.pop("_raw_text", None)
    row.pop("_extraction_status", None)

    await service.insert_row(cfg["table"], row)

    return {
        "success": True,
        "filename": filename,
        "document_type": doc_type,
        "row_id": row_id,
        "extracted_fields": {k: v for k, v in row.items() if k not in (cfg["id_field"], cfg["path_field"])},
        "confidence": fields.get("Extraction_Confidence", 0),
        "s3_key": s3_key or None,
    }


@router.post("/upload/invoice", tags=["External Simulator"])
async def upload_invoice(request: Request, file: UploadFile = File(...)):
    return await _handle_upload(request, file, "invoice")


@router.post("/upload/lab-report", tags=["External Simulator"])
async def upload_lab_report(request: Request, file: UploadFile = File(...)):
    return await _handle_upload(request, file, "lab-report")


@router.post("/upload/contract", tags=["External Simulator"])
async def upload_contract(request: Request, file: UploadFile = File(...)):
    return await _handle_upload(request, file, "contract")


@router.post("/upload/sustainability-report", tags=["External Simulator"])
async def upload_sustainability_report(request: Request, file: UploadFile = File(...)):
    return await _handle_upload(request, file, "sustainability-report")
