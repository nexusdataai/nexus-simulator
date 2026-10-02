"""Solution scenario overlay APIs."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ...scenarios.catalog import get_scenario, list_scenarios, list_solutions
from ...scenarios.engine import OverlayEngine, OverlayError

router = APIRouter(prefix="/api/v1/scenarios", tags=["Solution Scenarios"])


class RunBody(BaseModel):
    stepId: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=50)
    runId: Optional[str] = None


def _engine(request: Request) -> OverlayEngine:
    sim = getattr(request.app.state, "simulator", None)
    if sim is None:
        raise HTTPException(status_code=503, detail="simulator not initialised")
    return OverlayEngine(sim)


def _err(exc: OverlayError) -> HTTPException:
    code = 404 if "not found" in str(exc) or "unknown" in str(exc) else 400
    return HTTPException(status_code=code, detail=str(exc))


@router.get("")
async def list_all(solution: Optional[str] = Query(None)):
    items = list_scenarios(solution)
    return {"total": len(items), "solutions": list_solutions(), "items": items}


@router.get("/runs")
async def runs(request: Request):
    return {"items": await _engine(request).list_runs()}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request):
    run = await _engine(request).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return run


@router.post("/runs/{run_id}/revert")
async def revert_run(run_id: str, request: Request):
    try:
        return await _engine(request).revert(run_id)
    except OverlayError as exc:
        raise _err(exc) from exc


@router.get("/{scenario_id}")
async def get_one(scenario_id: str):
    spec = get_scenario(scenario_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"scenario not found: {scenario_id}")
    return spec


@router.post("/{scenario_id}/preview")
async def preview(scenario_id: str, request: Request, body: RunBody = Body(default_factory=RunBody)):
    try:
        return await _engine(request).preview(scenario_id, limit=body.limit)
    except OverlayError as exc:
        raise _err(exc) from exc


@router.post("/{scenario_id}/run")
async def run(scenario_id: str, request: Request, body: RunBody = Body(default_factory=RunBody)):
    engine = _engine(request)
    try:
        run = None
        if body.runId:
            run = await engine.get_run(body.runId)
            if run and run.get("scenarioId") != scenario_id:
                raise HTTPException(status_code=400, detail="run belongs to a different scenario")
        if run is None:
            run = await engine.start_run(scenario_id, limit=body.limit)
        return await engine.run_step(run["runId"], step_id=body.stepId)
    except OverlayError as exc:
        raise _err(exc) from exc
