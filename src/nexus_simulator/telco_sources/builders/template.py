"""Phase B — minimal template artifacts for remaining atlas systems."""

from __future__ import annotations

from typing import List

from nexus_simulator.plugins.telco_seed_pools import TelcoPools
from nexus_simulator.telco_sources.catalog import catalog_systems
from nexus_simulator.telco_sources.identity import atlas_customer_id, trace_customer_internal
from nexus_simulator.telco_sources.models import Artifact, TelcoSourceProfile


def build_template_system(
    system_key: str,
    layer: str,
    deliveries: list[str],
    pools: TelcoPools,
    profile: TelcoSourceProfile,
) -> List[Artifact]:
    out: List[Artifact] = []
    trace_c = atlas_customer_id(pools, trace_customer_internal(pools))
    slug = system_key[:40].replace(" ", "_")
    if "Table" in deliveries:
        out.append(
            Artifact(
                system_key,
                layer,  # type: ignore[arg-type]
                "Table",
                f"{slug}_TABLE",
                table_name=f"SIM.{slug.upper()}",
                columns=["ID", "CUSTOMER_ID", "PAYLOAD"],
                rows=[[f"ROW-1", trace_c, f"synthetic-{slug}"]],
            )
        )
    if "File" in deliveries:
        out.append(
            Artifact(
                system_key,
                layer,  # type: ignore[arg-type]
                "File",
                f"{slug}.csv",
                mime="text/csv",
                content=f"id,customer_id\n1,{trace_c}\n",
                file_path=f"incoming/{layer.lower()}/{slug}.csv",
            )
        )
    if "API" in deliveries:
        out.append(
            Artifact(
                system_key,
                layer,  # type: ignore[arg-type]
                "API",
                f"{slug}_api",
                api_method="GET",
                api_path=f"/tmf-api/simulated/v1/{slug}/{trace_c}",
                api_body={"id": trace_c, "@type": "SimulatedResource", "system": system_key},
            )
        )
    if "Stream" in deliveries:
        out.append(
            Artifact(
                system_key,
                layer,  # type: ignore[arg-type]
                "Stream",
                f"sim.{slug}",
                stream_topic=f"sim.{slug}",
                stream_events=[{"ts": pools.datetime_str(1, 0), "key": trace_c, "v": {"system": system_key}}],
            )
        )
    return out


def all_template_keys() -> dict[str, dict]:
    return {e["system_key"]: e for e in catalog_systems()}
