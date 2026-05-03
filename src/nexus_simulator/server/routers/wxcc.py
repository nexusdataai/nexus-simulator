"""
WXCC Simulator REST API — Phase 5 (activated).

Verbatim port of nexus-backend's `src/apis/wxcc_simulator_api.py`. The only
intentional differences from the source:

- The module-level ``_service`` singleton is replaced with a ``Request``-driven
  lookup of ``request.app.state.simulator.wxcc`` so the host's
  ``build_simulator(config)`` instance is used.
- Imports are rewritten to point at the in-tree WXCC plugin
  (``nexus_simulator.plugins.wxcc.*``).

Every fix, branch, early-return, decimal conversion, error path, and edge
case in the source is preserved.

PORT FIDELITY CHECKLIST — see docs/ROUTE_PARITY.md for the source-line map.
"""

from __future__ import annotations

import io  # noqa: F401  - retained for parity with the source's import block
import os
from datetime import datetime

from fastapi import APIRouter, File, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: F401  - parity
from loguru import logger

from ...plugins.wxcc.models import (
    AdminResponse,
    CallTypeEnum,
    CapturesQueryRequest,
    CapturesResponse,
    CreateTaskRequest,
    SeedDataRequest,
    SimulatorStatus,
    TasksResponse,
    UpdateTaskRequest,
    WXCCErrorResponse,  # noqa: F401  - parity with source's import block
)
from ...plugins.wxcc.service import WXCCSimulatorService

# Create router with prefix for WXCC v1 API
router = APIRouter()


def get_service(request: Request) -> WXCCSimulatorService:
    """Resolve the WXCC plugin off the wired ``Simulator`` on app state.

    Raises 503 when the WXCC plugin was not enabled in ``SimulatorConfig`` or
    when ``create_app`` was called without a ``simulator`` argument.
    """
    sim = getattr(request.app.state, "simulator", None)
    if sim is None or getattr(sim, "wxcc", None) is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "WXCC simulator plugin not configured. "
                "Pass WXCCPluginConfig in SimulatorConfig.wxcc and call build_simulator(config)."
            ),
        )
    return sim.wxcc


# Configuration
# WXCC_SIMULATOR_ENABLED is the only env var read by this plugin's HTTP
# surface; it is a feature-flag gate for hosts that mount the router but want
# to disable it without reconfiguring the underlying SimulatorConfig.
WXCC_SIMULATOR_ENABLED = os.getenv("WXCC_SIMULATOR_ENABLED", "true").lower() == "true"
WXCC_SIM_TOKEN = os.getenv("WXCC_SIM_TOKEN", "test-token-12345")


def verify_simulator_enabled():
    """Check if simulator is enabled."""
    if not WXCC_SIMULATOR_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="WXCC Simulator is disabled"
        )


def verify_auth(authorization: str | None = Header(None)) -> bool:
    """
    Verify Bearer token authentication.

    Matches WXCC authentication behavior.
    """
    if not authorization:
        return False

    if not authorization.startswith("Bearer "):
        return False

    token = authorization[7:]  # Remove "Bearer " prefix
    return token == WXCC_SIM_TOKEN


async def require_auth(request: Request, authorization: str | None = Header(None)):
    """Dependency that requires valid authentication."""
    if not verify_auth(authorization):
        service = get_service(request)
        error = service.create_auth_error()
        raise HTTPException(
            status_code=401,
            detail=error.model_dump()
        )


# ==========================================
# WXCC-Compatible Endpoints (matching real API)
# ==========================================

@router.get("/tasks", response_model=TasksResponse, tags=["WXCC API"])
async def get_tasks(
    request: Request,
    from_param: int | None = Query(None, alias="from", description="Start time in milliseconds"),
    to: int | None = Query(None, description="End time in milliseconds"),
    orgId: str | None = Query(None, description="Organization ID (optional for simulator)"),
    channelType: str = Query("telephony", description="Channel type filter"),
    pageSize: int = Query(100, description="Page size"),
    authorization: str | None = Header(None),
):
    """
    Get tasks from the simulator.

    Matches WXCC GET /v1/tasks endpoint behavior.
    For simulator admin UI, orgId and authorization are optional.

    Query Parameters:
    - from: Start time in milliseconds
    - to: End time in milliseconds
    - orgId: Organization ID (optional - uses default if not provided)
    - channelType: Channel type filter (default: telephony)
    - pageSize: Maximum results to return (default: 100)
    """
    verify_simulator_enabled()

    # Only require auth if authorization header is provided (for real WXCC compatibility)
    if authorization:
        await require_auth(request, authorization)

    service = get_service(request)

    # Use service's default org_id if not provided
    effective_org_id = orgId or service.org_id

    try:
        result = await service.get_tasks(
            from_time=from_param,
            to_time=to,
            org_id=effective_org_id,
            channel_type=channelType,
            page_size=pageSize,
        )
        return result
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/captures/query", response_model=CapturesResponse, tags=["WXCC API"])
async def query_captures(
    request: Request,
    payload: CapturesQueryRequest,
    authorization: str = Header(...),
):
    """
    Query recordings for task IDs.

    Matches WXCC POST /v1/captures/query endpoint behavior.
    """
    verify_simulator_enabled()
    await require_auth(request, authorization)

    service = get_service(request)

    try:
        result = await service.get_captures(payload.task_ids)
        return result
    except Exception as e:
        logger.error(f"Error querying captures: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/recordings/{recording_id}", tags=["WXCC API"])
async def stream_recording(
    request: Request,
    recording_id: str,
    authorization: str | None = Header(None),
):
    """
    Stream a recording file.

    This endpoint serves recording files, similar to the presigned URLs
    returned by the real WXCC API.

    Note: Authorization is optional for this endpoint to match
    presigned URL behavior.
    """
    verify_simulator_enabled()

    service = get_service(request)

    content, content_type = await service.get_recording_stream(recording_id)

    if content is None:
        raise HTTPException(status_code=404, detail="Recording not found")

    return Response(
        content=content,
        media_type=content_type or "audio/wav",
        headers={
            "Content-Disposition": f'attachment; filename="{recording_id}.wav"'
        }
    )


@router.get("/recordings/{recording_id}/url", tags=["WXCC API"])
async def get_recording_url(
    request: Request,
    recording_id: str,
    expires_in: int = Query(3600, description="URL expiration in seconds"),
    authorization: str = Header(...),
):
    """
    Get a presigned URL for direct S3 download.

    Returns a temporary URL that can be used to download the recording
    directly from S3, similar to real WXCC behavior.
    """
    verify_simulator_enabled()
    await require_auth(request, authorization)

    service = get_service(request)

    url = await service.get_recording_presigned_url(recording_id, expires_in)

    if url is None:
        raise HTTPException(status_code=404, detail="Recording not found")

    return {"url": url, "expires_in": expires_in}


# ==========================================
# Admin Endpoints (for test data management)
# ==========================================

@router.get("/status", response_model=SimulatorStatus, tags=["Simulator Admin"])
async def get_status(request: Request):
    """
    Get simulator status.

    Returns current configuration and statistics.
    """
    verify_simulator_enabled()

    service = get_service(request)
    return await service.get_status()


@router.get("/admin/tasks", tags=["Simulator Admin"])
async def list_all_tasks(
    request: Request,
    pageSize: int = Query(100, description="Page size"),
    status: str | None = Query(None, description="Filter by status"),
    direction: str | None = Query(None, description="Filter by direction (inbound/outbound)"),
):
    """
    List all tasks (admin endpoint - no auth required).

    Returns all tasks in the simulator without requiring authorization.
    This is for the simulator admin UI.
    """
    verify_simulator_enabled()

    service = get_service(request)

    # Get all tasks from the service
    all_tasks = await service.get_all_tasks()

    # Apply filters
    filtered_tasks = all_tasks
    if status:
        filtered_tasks = [t for t in filtered_tasks if t.get("status", "").lower() == status.lower()]
    if direction:
        filtered_tasks = [t for t in filtered_tasks if t.get("direction", "").lower() == direction.lower()]

    # Apply pagination
    tasks = filtered_tasks[:pageSize]

    return {
        "tasks": tasks,
        "total": len(filtered_tasks),
        "pageSize": pageSize,
        "hasMore": len(filtered_tasks) > pageSize
    }


@router.post("/tasks", response_model=AdminResponse, tags=["Simulator Admin"])
async def create_task(request: Request, payload: CreateTaskRequest):
    """
    Create a new mock task.

    Creates a task with the specified attributes. Optionally associates
    an existing S3 recording file using the `recording_file` field.
    """
    verify_simulator_enabled()

    service = get_service(request)
    return await service.create_task(payload)


@router.put("/tasks/{task_id}", response_model=AdminResponse, tags=["Simulator Admin"])
async def update_task(request: Request, task_id: str, payload: UpdateTaskRequest):
    """
    Update an existing task.

    Updates the specified fields of an existing task.
    """
    verify_simulator_enabled()

    service = get_service(request)
    return await service.update_task(task_id, payload)


@router.delete("/tasks/{task_id}", response_model=AdminResponse, tags=["Simulator Admin"])
async def delete_task(request: Request, task_id: str):
    """
    Delete a task and its recordings.

    Removes the task and any associated recording files from S3.
    """
    verify_simulator_enabled()

    service = get_service(request)
    return await service.delete_task(task_id)


@router.post("/tasks/{task_id}/recordings", response_model=AdminResponse, tags=["Simulator Admin"])
async def upload_recording(
    request: Request,
    task_id: str,
    file: UploadFile = File(..., description="WAV audio file"),
    participants: str | None = Query(None, description="Comma-separated participant phone numbers"),
    call_type: CallTypeEnum = Query(CallTypeEnum.INBOUND, description="Call type"),
):
    """
    Upload a recording file for a task.

    Uploads an audio file and associates it with the specified task.
    The file should be in WAV format.
    """
    verify_simulator_enabled()

    service = get_service(request)

    # Read file content
    content = await file.read()

    # Parse participants
    participant_list = []
    if participants:
        participant_list = [p.strip() for p in participants.split(",")]

    return await service.upload_recording(
        task_id=task_id,
        file_content=content,
        file_name=file.filename or "recording.wav",
        participants=participant_list,
        call_type=call_type,
    )


@router.post("/seed", response_model=AdminResponse, tags=["Simulator Admin"])
async def seed_data(request: Request, payload: SeedDataRequest):
    """
    Seed simulator with sample data.

    Creates the specified number of mock tasks with realistic data.
    Use this to quickly populate the simulator for testing.

    Request Body:
    - num_tasks: Number of tasks to create (1-100)
    - include_recordings: Whether to create mock recordings
    - days_back: Spread tasks over this many days
    - org_id: Optional organization ID to use
    """
    verify_simulator_enabled()

    service = get_service(request)
    return await service.seed_data(payload)


@router.post("/reset", response_model=AdminResponse, tags=["Simulator Admin"])
async def reset_data(request: Request):
    """
    Reset all simulator data.

    Deletes all tasks and recordings. Use with caution!
    """
    verify_simulator_enabled()

    service = get_service(request)
    return await service.reset_data()


# ==========================================
# Sample Recordings Management
# ==========================================

@router.get("/sample-recordings", tags=["Simulator Admin"])
async def list_sample_recordings(request: Request):
    """
    List all sample recordings available for the simulator.

    Returns list of sample recordings stored in S3 sample-recordings/ prefix.
    These files are used when seeding simulator data.
    """
    verify_simulator_enabled()

    service = get_service(request)
    return await service.list_sample_recordings()


@router.post("/sample-recordings", tags=["Simulator Admin"])
async def upload_sample_recording(request: Request, file: UploadFile = File(...)):
    """
    Upload a sample recording file.

    Supported formats: .mp3, .wav, .m4a, .ogg, .flac

    The uploaded file will be stored in S3 sample-recordings/ prefix
    and can be used when seeding simulator data.
    """
    verify_simulator_enabled()

    # Validate file extension
    filename = file.filename or "recording.mp3"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ['.mp3', '.wav', '.m4a', '.ogg', '.flac']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {ext}. Supported: .mp3, .wav, .m4a, .ogg, .flac"
        )

    # Read file content
    content = await file.read()

    # Validate file size (max 50MB)
    max_size = 50 * 1024 * 1024  # 50MB
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size: 50MB"
        )

    service = get_service(request)
    return await service.upload_sample_recording(filename, content, file.content_type)


@router.delete("/sample-recordings/{filename}", tags=["Simulator Admin"])
async def delete_sample_recording(request: Request, filename: str):
    """
    Delete a sample recording file.

    Removes the file from S3 sample-recordings/ prefix.
    """
    verify_simulator_enabled()

    service = get_service(request)
    return await service.delete_sample_recording(filename)


# ==========================================
# Health Check
# ==========================================

@router.get("/health", tags=["Simulator Admin"])
async def health_check(request: Request):
    """
    Health check for the simulator.

    Returns basic status information.
    """
    service = get_service(request)

    return {
        "status": "healthy" if service.enabled else "disabled",
        "enabled": WXCC_SIMULATOR_ENABLED,
        "bucket_configured": bool(service.bucket),
        "timestamp": datetime.utcnow().isoformat()
    }
