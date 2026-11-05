"""Register and dispatch per-scenario step builders."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from ..engine import OverlayError, load_table

Builder = Callable[[Any, dict[str, Any], dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]

_BUILDERS: dict[tuple[str, str], Builder] = {}


def register(scenario_id: str, step_id: str):
    def deco(fn: Builder) -> Builder:
        _BUILDERS[(scenario_id, step_id)] = fn
        return fn
    return deco


async def run_step(registry, spec: dict[str, Any], step: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    key = (spec["id"], step["id"])
    fn = _BUILDERS.get(key)
    if fn is None:
        raise OverlayError(f"no builder for {spec['id']}/{step['id']}")
    return await fn(registry, spec, step, ctx)


def _load():
    from . import (  # noqa: F401
        c360,
        demand,
        esg,
        inventory,
        o2c,
        procurement,
        production,
        risk,
        sourcing,
        telco,
        trade,
    )


_load()
