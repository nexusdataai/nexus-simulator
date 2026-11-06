"""Telco source artifacts plugin — Table / File / API / Stream delivery."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from loguru import logger

from nexus_simulator.base.simulator import BaseSimulator as BaseSimulatorService
from nexus_simulator.telco_sources.catalog import default_profile, resolve_profile
from nexus_simulator.telco_sources.generate import artifacts_to_table_map, generate_artifacts
from nexus_simulator.telco_sources.models import TelcoSourceProfile

sim_logger = logger.bind(component="telco-sources-simulator")

SCHEMA_BSS = "telco_bss_sources"
SCHEMA_OSS = "telco_oss_sources"
SCHEMA_NSS = "telco_nss_sources"
SERVER = "telco_sources_simulator"

CACHE_PROFILE = "telco_sources:profile"
CACHE_BUNDLE = "telco_sources:bundle"
CACHE_TMF_INDEX = "telco_sources:tmf_index"
CACHE_STREAMS = "telco_sources:streams"
CACHE_FILES = "telco_sources:files_manifest"


class TelcoSourcesSimulatorService(BaseSimulatorService):
    SERVICE_NAME = "telco_sources"
    PRIORITY_TABLES: list[str] = []

    def __init__(self, bucket: str = "", prefix: str = ""):
        super().__init__(bucket, prefix)
        if not self.prefix:
            self.prefix = os.getenv("TELCO_SOURCES_PREFIX", "telco-sources")
        if not self.bucket:
            self.bucket = os.getenv("TELCO_SOURCES_BUCKET", "")

    async def _cache_get_json(self, key: str) -> Any:
        raw = await self.cache.get(key)
        if not raw:
            return None
        if isinstance(raw, (dict, list)):
            return raw
        return json.loads(raw)

    async def _cache_set_json(self, key: str, value: Any) -> None:
        await self.cache.set(key, json.dumps(value))

    async def get_profile(self) -> TelcoSourceProfile:
        data = await self._cache_get_json(CACHE_PROFILE)
        if data:
            return resolve_profile(data)
        return default_profile()

    async def save_profile(self, profile: TelcoSourceProfile | dict) -> TelcoSourceProfile:
        prof = resolve_profile(profile if isinstance(profile, dict) else profile.to_dict())
        await self._cache_set_json(CACHE_PROFILE, prof.to_dict())
        return prof

    async def get_bundle(self) -> dict | None:
        return await self._cache_get_json(CACHE_BUNDLE)

    async def seed_data(self, **gen_kwargs: Any) -> Dict[str, Any]:
        profile = await self.get_profile()
        bundle = generate_artifacts(profile, **gen_kwargs)
        await self._cache_set_json(CACHE_BUNDLE, bundle.to_dict())
        await self._persist_indexes(bundle)
        table_map = artifacts_to_table_map(bundle)
        await self._write_layer_tables(table_map, bundle)
        file_count = len(await self._cache_get_json(CACHE_FILES) or [])
        return {
            "artifacts": len(bundle.artifacts),
            "tables": len(table_map),
            "files": file_count,
            "profile_id": bundle.profile_id,
        }

    async def _persist_indexes(self, bundle) -> None:
        tmf_index: dict[str, dict] = {}
        streams: dict[str, list] = {}
        files: list[dict] = []
        for art in bundle.artifacts:
            if art.delivery == "API" and art.api_path and art.api_body:
                tmf_index[art.api_path] = {
                    "method": art.api_method or "GET",
                    "body": art.api_body,
                    "system_key": art.system_key,
                }
            if art.delivery == "Stream" and art.stream_topic:
                streams.setdefault(art.stream_topic, []).extend(art.stream_events)
            if art.delivery == "File" and art.content is not None:
                path = art.file_path or f"incoming/{art.layer.lower()}/{art.name}"
                files.append(
                    {
                        "system_key": art.system_key,
                        "layer": art.layer,
                        "name": art.name,
                        "path": path,
                        "mime": art.mime,
                        "size": len(art.content.encode("utf-8")),
                    }
                )
                await self._write_file_artifact(path, art.content, art.mime)
        await self._cache_set_json(CACHE_TMF_INDEX, tmf_index)
        await self._cache_set_json(CACHE_STREAMS, streams)
        await self._cache_set_json(CACHE_FILES, files)

    async def _write_file_artifact(self, path: str, content: str, mime: str) -> None:
        key = f"files/{path}"
        if self.storage:
            await self.storage.put_bytes(key, content.encode("utf-8"))
        else:
            await self.cache.set(f"telco_sources:file:{path}", content)

    async def read_file_artifact(self, path: str) -> str | None:
        if self.storage:
            try:
                data = await self.storage.get_bytes(f"files/{path}")
                return data.decode("utf-8")
            except Exception:
                pass
        raw = await self.cache.get(f"telco_sources:file:{path}")
        return raw if isinstance(raw, str) else None

    async def get_tmf_index(self) -> dict:
        return (await self._cache_get_json(CACHE_TMF_INDEX)) or {}

    async def get_streams(self) -> dict:
        return (await self._cache_get_json(CACHE_STREAMS)) or {}

    async def get_files_manifest(self) -> list:
        return (await self._cache_get_json(CACHE_FILES)) or []

    async def _write_layer_tables(self, table_map: dict[str, list[dict]], bundle) -> None:
        """Register tables under layer-specific schemas."""
        layer_schema = {"BSS": SCHEMA_BSS, "OSS": SCHEMA_OSS, "NSS": SCHEMA_NSS}
        by_schema: dict[str, dict[str, list[dict]]] = {SCHEMA_BSS: {}, SCHEMA_OSS: {}, SCHEMA_NSS: {}}
        art_by_table = {}
        for art in bundle.artifacts:
            if art.delivery == "Table" and art.table_name:
                safe = (art.table_name or art.name).replace(".", "_").replace(":", "_").replace(" ", "_")
                art_by_table[safe] = art

        for safe, rows in table_map.items():
            art = art_by_table.get(safe)
            schema = layer_schema.get(art.layer if art else "BSS", SCHEMA_BSS)
            by_schema[schema][safe] = rows

        summaries = []
        for schema, data_map in by_schema.items():
            if not data_map:
                continue
            summary = await self._finalize_seed(schema, SERVER, data_map)
            summaries.append(summary)
        self._loaded = True
        return summaries

    async def seed_scenario(self, name: str) -> dict[str, Any]:
        """Inject scenario-specific stream/file events (e.g. outage_backhaul)."""
        bundle_data = await self.get_bundle()
        if not bundle_data:
            await self.seed_data()
            bundle_data = await self.get_bundle()
        streams = await self.get_streams()
        if name == "outage_backhaul":
            extra = {
                "ts": "2026-11-05T13:41:56.000+03:00",
                "key": "MW-RYD-0421-0388",
                "v": {"event": "LINK_DOWN", "alarm": "MW_RDI", "severity": "major"},
            }
            streams.setdefault("nce.telemetry.interface", []).append(extra)
            streams.setdefault("oss.enm.fm.alarms", []).append(
                {
                    "ts": "2026-11-05T13:42:07.000+03:00",
                    "key": "ALM-9930021",
                    "v": {"notificationType": "notifyNewAlarm", "specificProblem": "Cell Unavailable"},
                }
            )
        await self._cache_set_json(CACHE_STREAMS, streams)
        return {"scenario": name, "stream_topics": list(streams.keys())}
