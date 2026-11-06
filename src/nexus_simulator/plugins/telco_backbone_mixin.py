"""Shared Telco AI Backbone storage + generation for BSS / NSS / OSS."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from loguru import logger

from nexus_simulator.plugins.telco_seed_pools import TelcoPools, get_telco_pools, telco_rng_seed
from nexus_simulator.telco_backbone.fixtures import load_sample_fixtures
from nexus_simulator.telco_backbone.generate import generate_layer_backbone

if TYPE_CHECKING:
    from nexus_simulator.base.simulator import BaseSimulator

sim_logger = logger.bind(component="telco-backbone")


class TelcoBackboneMixin:
    """Expect host class to be BaseSimulator with SERVICE_NAME in {bss,nss,oss}."""

    backbone_layer: str = ""

    def _layer_upper(self) -> str:
        return (getattr(self, "backbone_layer", None) or self.SERVICE_NAME or "").upper()

    def _meta_prefix(self) -> str:
        return f"backbone:{self._layer_upper()}:"

    async def _cache_set_json(self, key: str, value: Any) -> None:
        await self.cache.set(key, json.dumps(value))

    async def _cache_get_json(self, key: str) -> Any:
        raw = await self.cache.get(key)
        if not raw:
            return None
        if isinstance(raw, (dict, list)):
            return raw
        return json.loads(raw)

    def _atlas_schema_name(self) -> str:
        su = self._layer_upper()
        return {"BSS": "telco_atlas_bss", "OSS": "telco_atlas_oss", "NSS": "telco_atlas_nss"}.get(
            su, f"telco_atlas_{su.lower()}"
        )

    async def get_backbone_catalog(self) -> dict[str, Any]:
        bundle = load_sample_fixtures()
        layer = self._layer_upper()
        systems = bundle.systems_for_layer(layer)
        return {
            "layer": layer,
            "systems": [
                {
                    "system_key": k,
                    "deliveries": list((v.get("deliveries") or {}).keys()),
                }
                for k, v in systems.items()
            ],
        }

    async def generate_backbone(
        self,
        *,
        pools: Optional[TelcoPools] = None,
        systems: Optional[Set[str]] = None,
        deliveries: Optional[Set[str]] = None,
        include_legacy_tables: bool = True,
    ) -> dict[str, Any]:
        """Build atlas tables + files + tmf + streams; merge with optional legacy seed."""
        layer = self._layer_upper()
        pool = pools or get_telco_pools(seed=telco_rng_seed())
        backbone = generate_layer_backbone(layer, pool, systems=systems, deliveries=deliveries)

        await self._cache_set_json(self._meta_prefix() + "bundle", backbone)

        # TMF paths are unique per samples
        await self._cache_set_json(self._meta_prefix() + "tmf_index", backbone.get("tmf_index") or {})
        await self._cache_set_json(self._meta_prefix() + "streams", backbone.get("streams") or {})

        files = backbone.get("files") or []
        for f in files:
            path = f.get("path") or ""
            content = f.get("content") or ""
            key = f"telco_backbone:file:{self.SERVICE_NAME}:{path}"
            await self.cache.set(key, content)
        await self._cache_set_json(self._meta_prefix() + "files_manifest", files)

        atlas_schema = self._atlas_schema_name()
        atlas_tables: Dict[str, List[dict]] = dict(backbone.get("tables") or {})

        # Merge with legacy tables in one catalog pass
        from importlib import import_module

        svc_name = self.SERVICE_NAME
        build_fn_name = f"build_{svc_name}_tables"
        mod = import_module(f"nexus_simulator.plugins.{svc_name}.tables")
        build_fn = getattr(mod, build_fn_name)
        legacy_map = build_fn(pool) if include_legacy_tables else {}
        base_schema = getattr(self, "LEGACY_SCHEMA", None) or {
            "bss": "bss_crm",
            "nss": "nss_core",
            "oss": "oss_network",
        }.get(svc_name, f"{svc_name}_core")

        merged: Dict[str, Dict[str, List[dict]]] = {base_schema: legacy_map, atlas_schema: atlas_tables}
        server = getattr(self, "SERVER_NAME", f"{svc_name}_simulator")
        summary = await self._finalize_seed_multi(server, merged)
        summary["backbone"] = {
            "systems": len(backbone.get("systems") or []),
            "tables": len(atlas_tables),
            "files": len(files),
            "tmf_paths": len(backbone.get("tmf_index") or {}),
            "stream_topics": len(backbone.get("streams") or {}),
        }
        sim_logger.info("Backbone generated for {}: {}", layer, summary["backbone"])
        return summary

    async def get_backbone_artifacts(self) -> dict[str, Any]:
        return (await self._cache_get_json(self._meta_prefix() + "bundle")) or {}

    async def get_tmf_index(self) -> dict[str, Any]:
        return (await self._cache_get_json(self._meta_prefix() + "tmf_index")) or {}

    async def get_stream_topics(self) -> dict[str, List[dict]]:
        return (await self._cache_get_json(self._meta_prefix() + "streams")) or {}

    async def get_files_manifest(self) -> List[dict]:
        return (await self._cache_get_json(self._meta_prefix() + "files_manifest")) or []

    async def read_backbone_file(self, path: str) -> Optional[str]:
        key = f"telco_backbone:file:{self.SERVICE_NAME}:{path}"
        raw = await self.cache.get(key)
        if isinstance(raw, str):
            return raw
        return None

    async def seed_scenario(self, name: str) -> dict[str, Any]:
        """Inject scenario-specific stream events (e.g. outage_backhaul).

        Mirrors the legacy telco_sources scenario hook so ontology flows work when
        only BSS/NSS/OSS are registered.
        """
        streams = await self.get_stream_topics()
        if not streams:
            pool = get_telco_pools(seed=telco_rng_seed())
            await self.generate_backbone(pools=pool, include_legacy_tables=True)
            streams = await self.get_stream_topics()
        if name == "outage_backhaul":
            extra_nce = {
                "ts": "2026-11-05T13:41:56.000+03:00",
                "key": "MW-RYD-0421-0388",
                "v": {"event": "LINK_DOWN", "alarm": "MW_RDI", "severity": "major"},
            }
            extra_alarm = {
                "ts": "2026-11-05T13:42:07.000+03:00",
                "key": "ALM-9930021",
                "v": {
                    "notificationType": "notifyNewAlarm",
                    "specificProblem": "Cell Unavailable",
                },
            }
            streams.setdefault("nce.telemetry.interface", []).append(extra_nce)
            streams.setdefault("oss.enm.fm.alarms", []).append(extra_alarm)
        await self._cache_set_json(self._meta_prefix() + "streams", streams)
        bundle = await self._cache_get_json(self._meta_prefix() + "bundle")
        if isinstance(bundle, dict):
            bundle["streams"] = streams
            await self._cache_set_json(self._meta_prefix() + "bundle", bundle)
        return {"scenario": name, "stream_topics": list(streams.keys())}
