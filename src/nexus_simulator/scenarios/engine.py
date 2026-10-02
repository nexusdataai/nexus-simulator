"""Overlay engine: preview, run one/all steps, revert tagged rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .catalog import PLUGIN_FALLBACK_SCHEMA, get_scenario
from .helpers import PLUGIN_LABELS, row_pk, summarize_bindings, tag_row

RUN_TTL = 7 * 24 * 3600
RUN_KEY = "sim:scenario:run:{id}"
RUN_INDEX = "sim:scenario:runs"


class OverlayError(Exception):
    pass


def _schema(svc: Any, plugin: str) -> str:
    status = svc.get_status() if hasattr(svc, "get_status") else {}
    return (status or {}).get("schema") or PLUGIN_FALLBACK_SCHEMA.get(plugin, "")


async def _svc(registry, plugin: str):
    svc = registry.get(plugin)
    if svc is None:
        raise OverlayError(f"{plugin} simulator not initialised")
    if hasattr(svc, "ensure_loaded"):
        await svc.ensure_loaded()
    return svc


async def load_table(registry, plugin: str, table: str) -> list[dict[str, Any]]:
    svc = await _svc(registry, plugin)
    schema = _schema(svc, plugin)
    rows = await svc._get_table_data(schema, table)
    return list(rows or [])


class OverlayEngine:
    def __init__(self, simulator: Any):
        self.simulator = simulator
        self.registry = simulator.registry
        self.cache = simulator.cache

    async def preview(self, scenario_id: str, limit: int = 10) -> dict[str, Any]:
        spec = get_scenario(scenario_id)
        if spec is None:
            raise OverlayError(f"unknown scenario: {scenario_id}")
        from .builders import run_step

        ctx = {"bindings": {}, "limit": limit, "preview": True, "run_id": "preview"}
        steps = []
        for step in spec["steps"]:
            result = await run_step(self.registry, spec, step, ctx)
            ctx["bindings"].update(result.get("bindings") or {})
            steps.append({
                "id": step["id"],
                "title": step["title"],
                "plugin": step["plugin"],
                "tables": step["tables"],
                "action": step["action"],
                "planned": result.get("planned") or {},
                "sampleBindings": {k: (v[:3] if isinstance(v, list) else v) for k, v in (result.get("bindings") or {}).items()},
                "message": result.get("message") or "",
            })
        return {"scenario": spec, "steps": steps}

    async def start_run(self, scenario_id: str, limit: int = 10) -> dict[str, Any]:
        spec = get_scenario(scenario_id)
        if spec is None:
            raise OverlayError(f"unknown scenario: {scenario_id}")
        run = {
            "runId": str(uuid4()),
            "scenarioId": scenario_id,
            "solutionId": spec["solutionId"],
            "status": "ready",
            "limit": limit,
            "bindings": {},
            "completedSteps": [],
            "results": [],
            "writes": [],
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        await self._store(run)
        return run

    async def run_step(self, run_id: str, step_id: str | None = None) -> dict[str, Any]:
        run = await self.get_run(run_id)
        if run is None:
            raise OverlayError(f"run not found: {run_id}")
        spec = get_scenario(run["scenarioId"])
        if spec is None:
            raise OverlayError(f"unknown scenario: {run['scenarioId']}")
        pending = [s for s in spec["steps"] if s["id"] not in run["completedSteps"]]
        if not pending:
            run["status"] = "completed"
            await self._store(run)
            return run
        if step_id:
            step = next((s for s in pending if s["id"] == step_id), None)
            if step is None:
                raise OverlayError(f"step {step_id} is not pending")
            priors = [s for s in pending if s["index"] < step["index"] and s["action"] == "select"]
            targets = [*priors, step]
        else:
            targets = pending
        from .builders import run_step as build_step

        ctx = {"bindings": dict(run.get("bindings") or {}), "limit": run.get("limit") or 10, "preview": False, "run_id": run_id}
        for step in targets:
            bindings_before = dict(ctx.get("bindings") or {})
            result = await build_step(self.registry, spec, step, ctx)
            ctx["bindings"].update(result.get("bindings") or {})
            written = await self._apply_writes(spec["id"], run_id, step, result.get("rows") or [])
            new_bindings = {
                k: v for k, v in (ctx.get("bindings") or {}).items()
                if bindings_before.get(k) != v
            }
            run["completedSteps"].append(step["id"])
            run["results"].append({
                "stepId": step["id"],
                "stepTitle": step["title"],
                "action": step["action"],
                "plugin": step["plugin"],
                "pluginLabel": PLUGIN_LABELS.get(step["plugin"], step["plugin"]),
                "tables": step["tables"],
                "ok": True,
                "message": result.get("message") or "",
                "planned": result.get("planned") or {},
                "bound": summarize_bindings(new_bindings),
                "written": written,
            })
            run["writes"].extend(written)
        run["bindings"] = ctx["bindings"]
        run["summary"] = _run_summary(run)
        run["status"] = "completed" if len(run["completedSteps"]) == len(spec["steps"]) else "in_progress"
        await self._store(run)
        return run

    async def revert(self, run_id: str) -> dict[str, Any]:
        run = await self.get_run(run_id)
        if run is None:
            raise OverlayError(f"run not found: {run_id}")
        tables: dict[tuple[str, str], None] = {}
        for write in run.get("writes") or []:
            tables[(write["plugin"], write["table"])] = None
        removed = []
        for plugin, table in tables:
            svc = await _svc(self.registry, plugin)
            schema = _schema(svc, plugin)
            rows = list(await svc._get_table_data(schema, table) or [])
            kept = [r for r in rows if r.get("_scenario_run_id") != run_id]
            dropped = len(rows) - len(kept)
            if dropped:
                await svc.write_table(schema, table, kept)
            removed.append({
                "plugin": plugin,
                "pluginLabel": PLUGIN_LABELS.get(plugin, plugin),
                "schema": schema,
                "table": table,
                "action": "delete",
                "deleted": dropped,
                "beforeCount": len(rows),
                "afterCount": len(kept),
            })
        run["status"] = "reverted"
        run["reverted"] = removed
        run["summary"] = _run_summary(run)
        await self._store(run)
        return run

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        return await self.cache.get_json(RUN_KEY.format(id=run_id))

    async def list_runs(self) -> list[dict[str, Any]]:
        ids = await self.cache.get_json(RUN_INDEX) or []
        runs = []
        for rid in ids:
            run = await self.get_run(rid)
            if run:
                runs.append(run)
        return runs

    async def _apply_writes(self, scenario_id: str, run_id: str, step: dict[str, Any], rows_by_table: list[dict[str, Any]]) -> list[dict[str, Any]]:
        written = []
        for item in rows_by_table:
            plugin = item["plugin"]
            table = item["table"]
            raw_rows = list(item.get("rows") or [])
            rows = [tag_row(r, scenario_id, run_id, step["index"]) for r in raw_rows]
            svc = await _svc(self.registry, plugin)
            schema = _schema(svc, plugin)
            before_count = len(await svc._get_table_data(schema, table) or [])
            if not rows:
                written.append({
                    "plugin": plugin,
                    "pluginLabel": PLUGIN_LABELS.get(plugin, plugin),
                    "schema": schema,
                    "table": table,
                    "action": step.get("action") or "append",
                    "added": 0,
                    "updated": 0,
                    "deleted": 0,
                    "beforeCount": before_count,
                    "afterCount": before_count,
                    "recordIds": [],
                })
                continue
            after_count = await svc.append_rows(schema, table, rows)
            written.append({
                "plugin": plugin,
                "pluginLabel": PLUGIN_LABELS.get(plugin, plugin),
                "schema": schema,
                "table": table,
                "action": "append",
                "added": len(rows),
                "updated": 0,
                "deleted": 0,
                "beforeCount": before_count,
                "afterCount": after_count,
                "recordIds": [pk for r in rows if (pk := row_pk(r))][:8],
            })
        return written

    async def _store(self, run: dict[str, Any]) -> None:
        await self.cache.set_json(RUN_KEY.format(id=run["runId"]), run, ttl_seconds=RUN_TTL)
        ids = await self.cache.get_json(RUN_INDEX) or []
        if run["runId"] not in ids:
            ids = [run["runId"], *ids][:50]
            await self.cache.set_json(RUN_INDEX, ids, ttl_seconds=RUN_TTL)


def _run_summary(run: dict[str, Any]) -> dict[str, Any]:
    writes = run.get("writes") or []
    reverted = run.get("reverted") or []
    tables: list[dict[str, Any]] = []
    for w in writes:
        added = w.get("added", w.get("count", 0))
        if not added:
            continue
        tables.append({
            "plugin": w.get("plugin"),
            "pluginLabel": w.get("pluginLabel"),
            "schema": w.get("schema"),
            "table": w.get("table"),
            "added": added,
            "beforeCount": w.get("beforeCount"),
            "afterCount": w.get("afterCount"),
            "recordIds": w.get("recordIds") or [],
        })
    return {
        "totalAdded": sum(w.get("added", w.get("count", 0)) for w in writes),
        "totalDeleted": sum(r.get("deleted", r.get("removed", 0)) for r in reverted),
        "tablesTouched": len({(w.get("plugin"), w.get("table")) for w in writes if w.get("added", w.get("count", 0))}),
        "tables": tables,
        "reverted": reverted,
    }
