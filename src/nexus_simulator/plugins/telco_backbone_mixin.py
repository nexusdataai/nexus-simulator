"""Shared Telco AI Backbone storage + generation for BSS / NSS / OSS."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from loguru import logger

from nexus_simulator.plugins.telco_seed_pools import TelcoPools, get_telco_pools, telco_rng_seed
from nexus_simulator.telco_backbone.atlas_catalog import default_vendor_for_layer, load_atlas_catalog
from nexus_simulator.telco_backbone.billing import (
    billing_system_keys_for_layer,
    billing_target_for_system,
    catalog_entry_for_table,
    is_billing_system,
    telco_backbone_profile,
)
from nexus_simulator.telco_backbone.fixtures import load_sample_fixtures
from nexus_simulator.telco_backbone.generate import generate_layer_backbone
from nexus_simulator.telco_backbone.stream_publisher import publish_backbone_streams
from nexus_simulator.telco_backbone.vendor_paths import vendor_lookup_key

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

    def _backbone_s3_base(self, run_id: str) -> str:
        """Relative key prefix under plugin storage (no trailing slash)."""
        layer = self._layer_upper().lower()
        return f"telco-backbone/{layer}/{run_id}"

    async def _clear_backbone_artifacts(self) -> int:
        """Remove backbone keys from cache (run state, files, vendor index)."""
        n = 0
        n += await self.cache.flush_prefix(self._meta_prefix())
        n += await self.cache.flush_prefix(f"telco_backbone:file:{self.SERVICE_NAME}:")
        return n

    async def reset(self) -> dict[str, Any]:  # type: ignore[override]
        await self._clear_backbone_artifacts()
        return await super().reset()

    async def get_backbone_catalog(self) -> dict[str, Any]:
        bundle = load_sample_fixtures()
        atlas = load_atlas_catalog()
        layer = self._layer_upper()
        lk = layer.lower()
        systems = bundle.systems_for_layer(layer)
        atlas_for_layer = atlas.systems_for_layer(layer)
        rows = []
        for k, v in sorted(systems.items(), key=lambda x: x[0].lower()):
            fx_del = list((v.get("deliveries") or {}).keys())
            ar = atlas_for_layer.get(k)
            slug = str(ar.get("slug") or "") if ar else ""
            av = list(ar.get("deliveries") or []) if ar else []
            if av:
                merged = sorted(set(fx_del) & set(av))
                if not merged:
                    merged = sorted(fx_del)
            else:
                merged = sorted(fx_del)
            bill = is_billing_system(k)
            row = {
                "system_key": k,
                "slug": slug,
                "deliveries": merged,
                "billing": bill,
            }
            if bill:
                row["billing_target"] = billing_target_for_system(k)
                row["applications"] = ["billing"]
            rows.append(row)
        return {
            "layer": layer,
            "vendors": dict(atlas.vendors),
            "vendor_default": default_vendor_for_layer(lk),
            "systems": rows,
            "billing_module": {"id": "billing", "label": "Billing"},
        }

    async def _write_backbone_to_storage(
        self,
        run_id: str,
        generated_at: str,
        backbone: dict[str, Any],
        merged_schemas: dict[str, dict[str, List[dict]]],
    ) -> dict[str, Any]:
        """Write manifest, files, API bodies, and table exports to S3 when bucket configured."""
        base = self._backbone_s3_base(run_id)
        storage = getattr(self, "_storage", None)
        bucket = getattr(self, "bucket", None) or ""
        if storage is None or not bucket:
            return {"s3_enabled": False}

        out: dict[str, Any] = {"s3_enabled": True, "base_key": f"s3://{bucket}/{self.prefix}/{base}" if self.prefix else f"s3://{bucket}/{base}", "run_id": run_id}

        ensure = getattr(storage, "ensure_bucket", None)
        if callable(ensure):
            await ensure()

        # Files
        files_written = 0
        for f in backbone.get("files") or []:
            rel = str(f.get("path") or "").lstrip("/")
            content = str(f.get("content") or "")
            key = f"{base}/files/{rel}"
            await storage.put_bytes(key, content.encode("utf-8"))
            files_written += 1

        # API bodies as JSON files + enriched vendor index
        vendor_src = dict(backbone.get("vendor_api_index") or {})
        api_idx_out: dict[str, Any] = {}
        apis_written = 0
        used_safe: set[str] = set()
        for lk, entry in vendor_src.items():
            if not isinstance(entry, dict):
                continue
            rp = str(entry.get("route_path") or "")
            if not rp:
                continue
            safe = rp.replace("/", "_").strip("_")[:100] or "api"
            orig = safe
            n = 0
            while safe in used_safe:
                n += 1
                safe = f"{orig}_{n}"
            used_safe.add(safe)
            body_key = f"{base}/apis/{safe}.json"
            body = entry.get("body")
            await storage.put_json(body_key, body if body is not None else {})
            api_idx_out[lk] = {
                **entry,
                "body_s3_key": body_key,
            }
            apis_written += 1

        # Table exports (all schemas in this seed)
        tables_export: dict[str, Any] = {}
        tbl_files = 0
        for schema_name, data_map in merged_schemas.items():
            for tname, rows in (data_map or {}).items():
                tk = f"{base}/tables/{schema_name}/{tname}.json"
                await storage.put_json(tk, rows)
                tbl_files += 1
                tables_export.setdefault(schema_name, {})[tname] = {"rows": len(rows or []), "s3_key": tk}

        manifest = {
            "run_id": run_id,
            "generated_at": generated_at,
            "layer": self._layer_upper(),
            "service": self.SERVICE_NAME,
            "bucket": bucket,
            "prefix": self.prefix,
            "base_relative": base,
            "files_written": files_written,
            "api_endpoints": apis_written,
            "table_files": tbl_files,
            "topics": list((backbone.get("streams") or {}).keys()),
            "tables": tables_export,
            "vendor_api_lookup_keys": list(api_idx_out.keys()),
        }
        manifest_key = f"{base}/manifest.json"
        await storage.put_json(manifest_key, manifest)
        out["manifest_key"] = manifest_key
        out["vendor_api_index"] = api_idx_out
        out["counts"] = {
            "files": files_written,
            "apis": apis_written,
            "table_files": tbl_files,
        }
        return out

    async def generate_backbone(
        self,
        *,
        pools: Optional[TelcoPools] = None,
        systems: Optional[Set[str]] = None,
        deliveries: Optional[Set[str]] = None,
        system_deliveries: Optional[Dict[str, Set[str]]] = None,
        system_vendors: Optional[Dict[str, str]] = None,
        vendor_code: Optional[str] = None,
        include_legacy_tables: bool = True,
        legacy_profile: str | None = None,
    ) -> dict[str, Any]:
        """Build atlas tables + files + vendor API index + streams; merge with optional legacy seed."""
        layer = self._layer_upper()
        svc_name = self.SERVICE_NAME
        pool = pools or get_telco_pools(seed=telco_rng_seed())
        profile = (legacy_profile or telco_backbone_profile()).strip().lower()
        if systems is None and profile == "billing":
            billing_keys = billing_system_keys_for_layer(layer)
            if billing_keys:
                systems = billing_keys
        default_vid = default_vendor_for_layer(svc_name)
        vid_in = (vendor_code or "").strip().upper()[:1] or None
        sys_arg = systems
        sd = system_deliveries
        sv_clean: dict[str, str] | None = None
        if system_vendors:
            sv_clean = {}
            for k, v in system_vendors.items():
                if not v:
                    continue
                letter = str(v).strip().upper()[:1]
                if letter:
                    sv_clean[k] = letter
        if sd:
            keys = set(sd.keys())
            sys_arg = sys_arg.union(keys) if sys_arg is not None else keys
        if sv_clean:
            keys_sv = set(sv_clean.keys())
            sys_arg = sys_arg.union(keys_sv) if sys_arg is not None else keys_sv
        del_arg = deliveries
        if sd and not del_arg:
            del_arg = None
        backbone = generate_layer_backbone(
            layer,
            pool,
            systems=sys_arg,
            deliveries=del_arg,
            system_deliveries=sd,
            system_vendors=sv_clean,
            vendor_code=vid_in or default_vid,
        )

        run_id = str(uuid.uuid4())
        generated_at = datetime.now(timezone.utc).isoformat()
        backbone["run_id"] = run_id
        backbone["generated_at"] = generated_at
        atlas_c = load_atlas_catalog()
        out_vid = backbone.get("vendor_code")
        if out_vid is None and isinstance(backbone.get("vendor_label"), str) and backbone["vendor_label"].startswith("Mixed:"):
            out_vid = None
        elif out_vid is None:
            out_vid = vid_in or default_vid
            backbone["vendor_label"] = atlas_c.vendors.get(out_vid, out_vid)
        backbone["vendor_code"] = out_vid

        await self._cache_set_json(self._meta_prefix() + "bundle", backbone)
        await self._cache_set_json(self._meta_prefix() + "vendor_api_index", backbone.get("vendor_api_index") or {})
        # Legacy key kept empty for BWC — /tmf-api no longer merges backbone from simulator
        await self._cache_set_json(self._meta_prefix() + "tmf_index", {})
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

        from importlib import import_module

        build_fn_name = f"build_{svc_name}_tables"
        mod = import_module(f"nexus_simulator.plugins.{svc_name}.tables")
        build_fn = getattr(mod, build_fn_name)
        legacy_map = build_fn(pool) if include_legacy_tables else {}
        if include_legacy_tables and profile == "billing":
            from nexus_simulator.telco_backbone.billing import LEGACY_BILLING_TABLES

            allowed = set((LEGACY_BILLING_TABLES.get(svc_name) or {}).keys())
            if allowed:
                legacy_map = {k: v for k, v in legacy_map.items() if k in allowed}
        base_schema = getattr(self, "LEGACY_SCHEMA", None) or {
            "bss": "bss_crm",
            "nss": "nss_core",
            "oss": "oss_network",
        }.get(svc_name, f"{svc_name}_core")

        merged: Dict[str, Dict[str, List[dict]]] = {base_schema: legacy_map, atlas_schema: atlas_tables}
        server = getattr(self, "SERVER_NAME", f"{svc_name}_simulator")
        summary = await self._finalize_seed_multi(server, merged)
        await self._persist_table_catalog(atlas_schema, base_schema, atlas_tables, tbl_src=backbone.get("table_sources"))

        s3_info = await self._write_backbone_to_storage(run_id, generated_at, backbone, merged)
        enriched_va = s3_info.pop("vendor_api_index", None) if isinstance(s3_info, dict) else None
        if enriched_va:
            await self._cache_set_json(self._meta_prefix() + "vendor_api_index", enriched_va)
            backbone["vendor_api_index"] = enriched_va

        stream_pub: dict[str, Any] = {}
        try:
            stream_pub = await publish_backbone_streams(layer, dict(backbone.get("streams") or {}))
        except Exception as e:  # noqa: BLE001
            sim_logger.warning("Stream publish skipped: {}", e)
            stream_pub = {"error": str(e)}

        va = backbone.get("vendor_api_index") or {}
        summary_detail = await self.get_backbone_summary()
        sm = summary
        sm["backbone"] = {
            "run_id": run_id,
            "generated_at": generated_at,
            "profile": profile,
            "vendor_code": backbone.get("vendor_code"),
            "vendor_label": backbone.get("vendor_label"),
            "systems": len(backbone.get("systems") or []),
            "tables": len(atlas_tables),
            "files": len(files),
            "vendor_api_paths": len(va),
            "stream_topics": len(backbone.get("streams") or {}),
            "stream_publish": stream_pub,
            "s3": s3_info,
            "sample_vendor_api_path": (next(iter(va.values()), {}) or {}).get("route_path"),
            "summary": summary_detail,
        }
        sim_logger.info("Backbone generated for {}: {}", layer, sm["backbone"])
        return sm

    async def get_backbone_artifacts(self) -> dict[str, Any]:
        return (await self._cache_get_json(self._meta_prefix() + "bundle")) or {}

    async def get_backbone_summary(self) -> dict[str, Any]:
        """Structured view for UI: Tables / APIs / Files / Streams."""
        bundle = await self.get_backbone_artifacts()
        if not bundle:
            return {
                "layer": self._layer_upper(),
                "run_id": None,
                "generated_at": None,
                "vendor_code": None,
                "vendor_label": None,
                "tables": [],
                "apis": [],
                "files": [],
                "streams": [],
            }
        layer = bundle.get("layer") or self._layer_upper()
        atlas_schema = self._atlas_schema_name()
        psv = bundle.get("per_system_vendor") or {}
        if not isinstance(psv, dict):
            psv = {}
        tbl_src = bundle.get("table_sources") or {}
        if not isinstance(tbl_src, dict):
            tbl_src = {}
        tbl_rows = []
        tmap = bundle.get("tables") or {}
        for tname, rows in tmap.items():
            sk = str(tbl_src.get(tname) or "")
            vc = psv.get(sk) if sk else None
            meta = catalog_entry_for_table(self.SERVICE_NAME, atlas_schema, tname, system_key=sk or None)
            tbl_rows.append(
                {
                    "schema": atlas_schema,
                    "table": tname,
                    "rows": len(rows or []),
                    "system_key": sk or None,
                    "vendor_code": vc,
                    **meta,
                }
            )
        api_rows = []
        for _lk, ent in (bundle.get("vendor_api_index") or {}).items():
            if not isinstance(ent, dict):
                continue
            sk_ent = ent.get("system_key")
            sk_s = str(sk_ent) if sk_ent else ""
            api_rows.append(
                {
                    "method": ent.get("method", "GET"),
                    "route_path": ent.get("route_path"),
                    "system_key": sk_ent,
                    "fixture_path": ent.get("fixture_path"),
                    "vendor_code": psv.get(sk_s) if sk_s else None,
                }
            )
        file_rows = []
        for f in bundle.get("files") or []:
            if not isinstance(f, dict):
                continue
            fsk = f.get("system_key")
            fs = str(fsk) if fsk else ""
            file_rows.append(
                {
                    "name": f.get("name"),
                    "path": f.get("path"),
                    "system_key": fsk,
                    "vendor_code": psv.get(fs) if fs else None,
                }
            )
        stream_rows = []
        strm_src = bundle.get("stream_sources") or {}
        if not isinstance(strm_src, dict):
            strm_src = {}
        for topic, events in (bundle.get("streams") or {}).items():
            sk_t = str(strm_src.get(topic) or "")
            stream_rows.append(
                {
                    "topic": topic,
                    "event_count": len(events or []),
                    "system_key": sk_t or None,
                    "vendor_code": psv.get(sk_t) if sk_t else None,
                }
            )
        return {
            "layer": layer,
            "run_id": bundle.get("run_id"),
            "generated_at": bundle.get("generated_at"),
            "vendor_code": bundle.get("vendor_code"),
            "vendor_label": bundle.get("vendor_label"),
            "tables": tbl_rows,
            "apis": api_rows,
            "files": file_rows,
            "streams": stream_rows,
        }

    async def get_vendor_api_index(self) -> dict[str, Any]:
        return (await self._cache_get_json(self._meta_prefix() + "vendor_api_index")) or {}

    async def get_tmf_index(self) -> dict[str, Any]:
        """Deprecated for backbone; returns empty. Legacy telco_sources may still expose TMF via router merge."""
        return {}

    async def get_stream_topics(self) -> dict[str, List[dict]]:
        return (await self._cache_get_json(self._meta_prefix() + "streams")) or {}

    async def get_files_manifest(self) -> List[dict]:
        return (await self._cache_get_json(self._meta_prefix() + "files_manifest")) or []

    async def resolve_vendor_api(self, method: str, route_suffix: str) -> Optional[dict[str, Any]]:
        """route_suffix = path after /vendor-api/ (no leading slash)."""
        idx = await self.get_vendor_api_index()
        m = (method or "GET").upper()
        path = route_suffix.lstrip("/")
        lk = vendor_lookup_key(m, path)
        entry = idx.get(lk)
        if not entry:
            lk_alt = vendor_lookup_key(m, route_suffix)
            entry = idx.get(lk_alt)
        if not entry and m == "GET":
            for k, v in idx.items():
                if not isinstance(v, dict):
                    continue
                if k.startswith("GET ") and path.endswith((v.get("route_path") or "").split("/")[-1]):
                    entry = v
                    break
        if not entry:
            return None
        body_key = entry.get("body_s3_key")
        storage = getattr(self, "_storage", None)
        bucket = getattr(self, "bucket", None) or ""
        if body_key and storage is not None and bucket:
            data = await storage.get_json(str(body_key))
            if data is not None:
                return {"method": entry.get("method", m), "body": data, "route_path": entry.get("route_path")}
        return {"method": entry.get("method", m), "body": entry.get("body"), "route_path": entry.get("route_path")}

    async def read_backbone_file(self, path: str) -> Optional[str]:
        storage = getattr(self, "_storage", None)
        b = getattr(self, "bucket", None) or ""
        arts = await self.get_backbone_artifacts()
        run_id = arts.get("run_id") if isinstance(arts, dict) else None
        if storage is not None and b and run_id:
            rel = path.lstrip("/")
            sk = f"{self._backbone_s3_base(str(run_id))}/files/{rel}"
            raw = await storage.get_bytes(sk)
            if raw is not None:
                try:
                    return raw.decode("utf-8")
                except UnicodeDecodeError:
                    return None
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
        layer = self._layer_upper()
        pub = await publish_backbone_streams(layer, streams)
        return {"scenario": name, "stream_topics": list(streams.keys()), "stream_publish": pub}

    async def _persist_table_catalog(
        self,
        atlas_schema: str,
        legacy_schema: str,
        atlas_tables: dict[str, list],
        *,
        tbl_src: dict | None,
    ) -> None:
        catalog: dict[str, dict] = {}
        src = tbl_src or {}
        for tname, _rows in (atlas_tables or {}).items():
            sk = str(src.get(tname) or "")
            key = f"{atlas_schema}.{tname}"
            catalog[key] = catalog_entry_for_table(
                self.SERVICE_NAME, atlas_schema, tname, system_key=sk or None
            )
        for t in self._tables or []:
            key = f"{t.schema_name}.{t.table_name}"
            if key in catalog:
                continue
            catalog[key] = catalog_entry_for_table(self.SERVICE_NAME, t.schema_name, t.table_name)

        await self._cache_set_json(self._meta_prefix() + "table_catalog", catalog)

    async def get_object_list(self) -> list[dict[str, Any]]:
        base = await super().get_object_list()
        raw = await self._cache_get_json(self._meta_prefix() + "table_catalog")
        cat: dict = raw if isinstance(raw, dict) else {}
        out: list[dict[str, Any]] = []
        for row in base:
            if str(row.get("schemaName") or "") == "kenan_bp":
                continue
            key = f"{row.get('schemaName')}.{row.get('tableName')}"
            meta = cat.get(key) or catalog_entry_for_table(
                self.SERVICE_NAME,
                str(row.get("schemaName") or ""),
                str(row.get("tableName") or ""),
            )
            merged = {**row, **meta}
            out.append(merged)
        return out
