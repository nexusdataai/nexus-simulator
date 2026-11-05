"""Load static solution-scenario YAML from the catalog directory."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CATALOG_DIR = Path(__file__).resolve().parent / "catalog"

PLUGIN_FALLBACK_SCHEMA = {
    "sfdc": "sfdc_itxp2dev",
    "oracle": "oracle_erp",
    "sap": "sap_s4hana",
    "external": "external_sources",
    "tpm": "tpm_cpq",
    "sourcing": "sourcing_cpq",
    "bss": "bss_crm",
    "nss": "nss_core",
    "oss": "oss_network",
    "telco_golden": "telco_intelligence",
}


def _normalize_step(raw: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": raw.get("id") or f"step-{index + 1}",
        "title": raw.get("title") or raw.get("id") or f"Step {index + 1}",
        "plugin": raw.get("plugin"),
        "tables": list(raw.get("tables") or []),
        "action": (raw.get("action") or "append").lower(),
        "index": index,
    }


def _normalize_scenario(raw: dict[str, Any], solution_id: str, solution_title: str) -> dict[str, Any]:
    steps = [_normalize_step(s, i) for i, s in enumerate(raw.get("steps") or [])]
    plugins = sorted({s["plugin"] for s in steps if s.get("plugin")})
    return {
        "id": raw["id"],
        "solutionId": solution_id,
        "solutionTitle": solution_title,
        "title": raw.get("title") or raw["id"],
        "summary": raw.get("summary") or "",
        "kpis": list(raw.get("kpis") or []),
        "steps": steps,
        "plugins": plugins,
        "stepCount": len(steps),
    }


@lru_cache(maxsize=1)
def load_catalog() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(CATALOG_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        solution_id = data.get("solutionId") or path.stem
        title = data.get("title") or solution_id
        for raw in data.get("scenarios") or []:
            if not raw.get("id"):
                continue
            items.append(_normalize_scenario(raw, solution_id, title))
    return items


SOLUTION_ORDER = [
    "order-to-cash",
    "customer-360",
    "demand-forecasting",
    "inventory-optimization",
    "procurement-analytics",
    "production-quality",
    "supply-chain-risk",
    "esg-sustainability",
    "trade-cpq",
    "sourcing-cpq",
]


def list_solutions() -> list[dict[str, str]]:
    seen: dict[str, str] = {}
    for item in load_catalog():
        seen.setdefault(item["solutionId"], item["solutionTitle"])
    ordered = [k for k in SOLUTION_ORDER if k in seen]
    ordered.extend(k for k in seen if k not in ordered)
    return [{"id": k, "title": seen[k]} for k in ordered]


def list_scenarios(solution: str | None = None) -> list[dict[str, Any]]:
    items = load_catalog()
    if solution:
        items = [i for i in items if i["solutionId"] == solution]
    rank = {sid: i for i, sid in enumerate(SOLUTION_ORDER)}
    return sorted(items, key=lambda i: (rank.get(i["solutionId"], 99), i["id"]))


def get_scenario(scenario_id: str) -> dict[str, Any] | None:
    for item in load_catalog():
        if item["id"] == scenario_id:
            return item
    return None
