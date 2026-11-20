"""Aggregate live billing **input feed** artifacts from BSS / NSS / OSS simulators."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from nexus_simulator.telco_backbone.billing import (
    billing_system_keys_for_layer,
    is_billing_system,
)

_TELCO_SERVICES = ("bss", "nss", "oss")
_SVC_LAYER = {"bss": "BSS", "nss": "NSS", "oss": "OSS"}
_LAYER_SVC = {"BSS": "bss", "NSS": "nss", "OSS": "oss"}

ONTOLOGY_ETL_NOTE = (
    "Simulator emits inbound billing feeds only. Nexus Ontology ETL ingests these artifacts "
    "and hydrates Kenan BP final tables (CMF, CDR_DATA, BILL_INVOICE, …)."
)


@lru_cache(maxsize=1)
def load_billing_feeds() -> list[dict[str, Any]]:
    raw: str | None = None
    try:
        pkg = resources.files("nexus_simulator.data.telco")
        ref = pkg / "billing_feeds.json"
        if ref.is_file():
            raw = ref.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        pass
    if raw is None:
        p = Path(__file__).resolve().parents[1] / "data" / "telco" / "billing_feeds.json"
        raw = p.read_text(encoding="utf-8")
    data = json.loads(raw)
    return [f for f in (data.get("feeds") or []) if f.get("role") != "ontology_output"]


def _billing_input_obj(row: dict[str, Any]) -> bool:
    if row.get("schemaName") == "kenan_bp":
        return False
    apps = row.get("applications") or []
    return "billing" in apps


def _billing_sk(sk: str | None, layer: str) -> bool:
    if not sk:
        return False
    if is_billing_system(sk):
        return True
    return sk in billing_system_keys_for_layer(layer)


def _sk_matches(keys: set[str], sk: str | None) -> bool:
    if not sk or not keys:
        return False
    return sk in keys


def _delivery_set(feed: dict[str, Any]) -> set[str]:
    return {str(d).strip().upper() for d in (feed.get("delivery") or [])}


def enrich_input_feeds(
    feeds: list[dict[str, Any]],
    layers: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for feed in feeds:
        layer = str(feed.get("layer") or "").upper()
        svc = _LAYER_SVC.get(layer)
        bundle = layers.get(svc or "") if svc else None
        keys = {str(k) for k in (feed.get("atlas_system_keys") or [])}
        deliveries = _delivery_set(feed)
        artifacts: list[dict[str, Any]] = []

        if bundle and keys:
            if "TABLE" in deliveries:
                for t in bundle.get("tables") or []:
                    if _sk_matches(keys, t.get("system_key")):
                        artifacts.append({"kind": "table", **t})
            if "FILE" in deliveries:
                for f in bundle.get("files") or []:
                    if _sk_matches(keys, f.get("system_key")):
                        artifacts.append({"kind": "file", **f})
            if "API" in deliveries:
                for a in bundle.get("apis") or []:
                    if _sk_matches(keys, a.get("system_key")):
                        artifacts.append({"kind": "api", **a})
            if "STREAM" in deliveries:
                for s in bundle.get("streams") or []:
                    if _sk_matches(keys, s.get("system_key")):
                        artifacts.append({"kind": "stream", **s})

        ontology_lands_in = feed.get("ontology_lands_in") or feed.get("lands_in")
        out.append(
            {
                **feed,
                "ontology_lands_in": ontology_lands_in,
                "artifacts": artifacts,
                "artifact_count": len(artifacts),
            }
        )
    return out


async def _layer_bundle(service: str, svc: Any) -> dict[str, Any]:
    layer = _SVC_LAYER[service]
    tables: list[dict[str, Any]] = []
    if hasattr(svc, "get_object_list"):
        try:
            objs = await svc.get_object_list()
        except Exception:
            objs = []
        for o in objs:
            if isinstance(o, dict) and _billing_input_obj(o):
                tables.append(
                    {
                        "service": service,
                        "layer": layer,
                        "schemaName": o.get("schemaName"),
                        "tableName": o.get("tableName"),
                        "columnCount": o.get("columnCount"),
                        "rowCount": o.get("rowCount") or 0,
                        "system_key": o.get("system_key"),
                        "billing_target": o.get("billing_target"),
                        "applications": o.get("applications"),
                    }
                )

    files: list[dict] = []
    apis: list[dict] = []
    streams: list[dict] = []
    summary_tables: list[dict] = []
    run_id = None
    generated_at = None

    if hasattr(svc, "get_backbone_summary"):
        try:
            summary = await svc.get_backbone_summary()
        except Exception:
            summary = {}
        if isinstance(summary, dict):
            run_id = summary.get("run_id")
            generated_at = summary.get("generated_at")
            for f in summary.get("files") or []:
                if isinstance(f, dict) and _billing_sk(f.get("system_key"), layer):
                    files.append({**f, "service": service, "layer": layer})
            for a in summary.get("apis") or []:
                if isinstance(a, dict) and _billing_sk(a.get("system_key"), layer):
                    apis.append({**a, "service": service, "layer": layer})
            for s in summary.get("streams") or []:
                if isinstance(s, dict) and _billing_sk(s.get("system_key"), layer):
                    streams.append({**s, "service": service, "layer": layer})
            for t in summary.get("tables") or []:
                if isinstance(t, dict) and _billing_sk(t.get("system_key"), layer):
                    summary_tables.append(
                        {
                            "service": service,
                            "layer": layer,
                            "schemaName": t.get("schema"),
                            "tableName": t.get("table"),
                            "rowCount": t.get("rows") or 0,
                            "system_key": t.get("system_key"),
                        }
                    )

    catalog_systems: list[dict] = []
    if hasattr(svc, "get_backbone_catalog"):
        try:
            cat = await svc.get_backbone_catalog()
            for s in cat.get("systems") or []:
                if s.get("billing"):
                    sk = str(s.get("system_key") or "")
                    fam_tables = [x for x in tables if x.get("system_key") == sk]
                    fam_rows = sum(int(x.get("rowCount") or 0) for x in fam_tables)
                    catalog_systems.append(
                        {
                            "system_key": sk,
                            "slug": s.get("slug"),
                            "deliveries": s.get("deliveries"),
                            "billing_target": s.get("billing_target"),
                            "table_count": len(fam_tables),
                            "row_count": fam_rows,
                            "has_backbone_data": fam_rows > 0 or any(
                                (f.get("system_key") == sk for f in files)
                            ),
                        }
                    )
        except Exception:
            pass

    row_total = sum(int(t.get("rowCount") or 0) for t in tables)

    return {
        "service": service,
        "layer": layer,
        "run_id": run_id,
        "generated_at": generated_at,
        "tables": tables,
        "files": files,
        "apis": apis,
        "streams": streams,
        "atlas_tables": summary_tables,
        "systems": catalog_systems,
        "totals": {
            "tables": len(tables),
            "rows": row_total,
            "files": len(files),
            "apis": len(apis),
            "streams": len(streams),
        },
    }


async def build_billing_overview(simulator: Any, *, layer: str | None = None) -> dict[str, Any]:
    layers: dict[str, dict[str, Any]] = {}
    all_tables: list[dict[str, Any]] = []

    for name in _TELCO_SERVICES:
        svc = simulator.registry.get(name) if hasattr(simulator, "registry") else getattr(simulator, name, None)
        if svc is None:
            continue
        bundle = await _layer_bundle(name, svc)
        layers[name] = bundle
        all_tables.extend(bundle.get("tables") or [])

    lu = (layer or "").strip().upper()
    if lu == "BSS":
        filtered_services = ("bss",)
    elif lu == "OSS":
        filtered_services = ("oss",)
    elif lu == "NSS":
        filtered_services = ("nss",)
    else:
        filtered_services = _TELCO_SERVICES

    layer_table_counts = {ly: 0 for ly in _SVC_LAYER.values()}
    layer_row_counts = {ly: 0 for ly in _SVC_LAYER.values()}
    layer_file_counts = {ly: 0 for ly in _SVC_LAYER.values()}
    layer_api_counts = {ly: 0 for ly in _SVC_LAYER.values()}
    layer_stream_counts = {ly: 0 for ly in _SVC_LAYER.values()}
    for name in _TELCO_SERVICES:
        b = layers.get(name) or {}
        ly = _SVC_LAYER[name]
        t = b.get("totals") or {}
        layer_table_counts[ly] = int(t.get("tables") or 0)
        layer_row_counts[ly] = int(t.get("rows") or 0)
        layer_file_counts[ly] = int(t.get("files") or 0)
        layer_api_counts[ly] = int(t.get("apis") or 0)
        layer_stream_counts[ly] = int(t.get("streams") or 0)

    if lu in {"BSS", "OSS", "NSS"}:
        all_tables = [t for t in all_tables if t.get("layer") == lu]

    all_files: list[dict] = []
    all_apis: list[dict] = []
    all_streams: list[dict] = []
    for name in filtered_services:
        b = layers.get(name) or {}
        all_files.extend(b.get("files") or [])
        all_apis.extend(b.get("apis") or [])
        all_streams.extend(b.get("streams") or [])

    input_feeds = enrich_input_feeds(load_billing_feeds(), layers)

    return {
        "ontology_etl_note": ONTOLOGY_ETL_NOTE,
        "input_feeds": input_feeds,
        "layers": {k: layers[k] for k in filtered_services if k in layers},
        "tables": all_tables,
        "files": all_files,
        "apis": all_apis,
        "streams": all_streams,
        "totals": {
            "tables": len(all_tables),
            "rows": sum(int(t.get("rowCount") or 0) for t in all_tables),
            "files": len(all_files),
            "apis": len(all_apis),
            "streams": len(all_streams),
            "input_feeds": len(input_feeds),
            "input_feeds_with_data": sum(1 for f in input_feeds if (f.get("artifact_count") or 0) > 0),
            "by_layer": {
                "tables": layer_table_counts,
                "rows": layer_row_counts,
                "files": layer_file_counts,
                "apis": layer_api_counts,
                "streams": layer_stream_counts,
            },
        },
    }