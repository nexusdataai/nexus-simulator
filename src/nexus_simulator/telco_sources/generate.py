"""Orchestrate artifact generation from profile + pools."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from nexus_simulator.plugins.telco_seed_pools import TelcoPools, get_telco_pools
from nexus_simulator.telco_sources.builders.phase_a import PHASE_A_BUILDERS
from nexus_simulator.telco_sources.builders.template import build_template_system
from nexus_simulator.telco_sources.catalog import default_profile, resolve_profile
from nexus_simulator.telco_sources.identity import (
    atlas_cell_name,
    atlas_customer_id,
    atlas_imsi,
    atlas_msisdn,
    trace_customer_internal,
)
from nexus_simulator.telco_sources.models import (
    Artifact,
    ArtifactBundle,
    Delivery,
    Layer,
    SystemConfig,
    TelcoSourceProfile,
)


def _enabled_systems(profile: TelcoSourceProfile) -> list[SystemConfig]:
    if profile.systems:
        return [s for s in profile.systems if s.enabled]
    from nexus_simulator.telco_sources.catalog import catalog_systems

    return [
        SystemConfig(
            layer=e["layer"],
            system_key=e["system_key"],
            enabled=True,
            deliveries=list(e.get("deliveries") or []),
        )
        for e in catalog_systems()
        if e.get("phase_a")
    ]


def _filter_delivery(artifacts: list[Artifact], allowed: Iterable[Delivery] | None) -> list[Artifact]:
    if not allowed:
        return artifacts
    allow = set(allowed)
    return [a for a in artifacts if a.delivery in allow]


def build_lineage(pools: TelcoPools) -> dict[str, Any]:
    trace = trace_customer_internal(pools)
    home = pools.home_cell_by_customer.get(trace, pools.cell_ids[0] if pools.cell_ids else "")
    cell = atlas_cell_name(pools, home, trace=True)
    return {
        "customer_id": atlas_customer_id(pools, trace),
        "internal_customer_id": trace,
        "msisdn": atlas_msisdn(pools, trace),
        "imsi": atlas_imsi(pools, trace),
        "home_cell": cell,
        "site_id": "RYD-0421",
        "enb": "ENB104210",
    }


def generate_artifacts(
    profile: TelcoSourceProfile | dict | None = None,
    *,
    pools: TelcoPools | None = None,
    layers: list[Layer] | None = None,
    systems: list[str] | None = None,
    deliveries: list[Delivery] | None = None,
    refresh_identity: bool = False,
    all_systems: bool = False,
) -> ArtifactBundle:
    if refresh_identity:
        from nexus_simulator.plugins import telco_seed_pools as tsp

        tsp._POOLS_CACHE.clear()
    prof = resolve_profile(profile if isinstance(profile, dict) else (profile.to_dict() if profile else None))
    if all_systems:
        from nexus_simulator.telco_sources.catalog import profile_all_systems_enabled

        prof = profile_all_systems_enabled(prof)
    pool = pools or get_telco_pools()
    artifacts: list[Artifact] = []
    layer_filter = set(layers) if layers else None
    system_filter = set(systems) if systems else None

    for sc in _enabled_systems(prof):
        if layer_filter and sc.layer not in layer_filter:
            continue
        if system_filter and sc.system_key not in system_filter:
            continue
        allowed = list(sc.deliveries) if sc.deliveries else None
        builder = PHASE_A_BUILDERS.get(sc.system_key)
        if builder:
            built = builder(pool, prof)
        else:
            entry_del = allowed or ["Table", "File", "API", "Stream"]
            built = build_template_system(sc.system_key, sc.layer, list(entry_del), pool, prof)
        artifacts.extend(_filter_delivery(built, deliveries or allowed))

    return ArtifactBundle(
        generated_at=datetime.now(timezone.utc).isoformat(),
        profile_id=prof.profile_id,
        artifacts=artifacts,
        lineage=build_lineage(pool),
    )


def artifacts_to_table_map(bundle: ArtifactBundle) -> dict[str, list[dict]]:
    """Convert Table artifacts to FDW row dicts keyed by sanitized table name."""
    tables: dict[str, list[dict]] = {}
    for art in bundle.artifacts:
        if art.delivery != "Table" or not art.columns:
            continue
        key = art.table_name or art.name
        safe = key.replace(".", "_").replace(":", "_").replace(" ", "_")
        rows = []
        for row in art.rows:
            rows.append(dict(zip(art.columns, row)))
        tables[safe] = rows
    return tables
