"""Render backbone artifacts from fixtures + TelcoPools."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from nexus_simulator.plugins.telco_seed_pools import TelcoPools
from nexus_simulator.telco_sources.identity import (
    atlas_cell_name,
    atlas_customer_id,
    atlas_imsi,
    atlas_msisdn,
    trace_customer_internal,
)
from nexus_simulator.telco_backbone.atlas_catalog import load_atlas_catalog
from nexus_simulator.telco_backbone.file_enrichment import billing_file_min_rows, enrich_file_content
from nexus_simulator.telco_backbone.fixtures import FixtureBundle, load_sample_fixtures
from nexus_simulator.telco_backbone.vendor_paths import normalize_vendor_route_path, vendor_lookup_key


def _sanitize_table_identifier(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_")


def _customer_id_sequence(pools: TelcoPools) -> List[str]:
    trace = trace_customer_internal(pools)
    idx = pools.customer_ids.index(trace) if trace in pools.customer_ids else 0
    n = len(pools.customer_ids)
    out = []
    for k in range(max(n, 8)):
        cid = pools.customer_ids[(idx + k) % n]
        out.append(atlas_customer_id(pools, cid))
    return out


def _build_c100_mapping(pools: TelcoPools) -> Dict[str, str]:
    """Map atlas sample C-100245.. -> pool-derived ids."""
    seq = _customer_id_sequence(pools)
    m: Dict[str, str] = {}
    base = 245
    for i, atlas_id in enumerate(seq[:20]):
        m[f"C-{100245 + i}"] = atlas_id
        m[f"C-{base + i}"] = atlas_id  # some samples use C-100249 style
    return m


def _substitute_string(s: str, pools: TelcoPools, ctx: Dict[str, Any]) -> str:
    if not s:
        return s
    trace = trace_customer_internal(pools)
    msisdn = atlas_msisdn(pools, trace)
    imsi = atlas_imsi(pools, trace)
    home_cell = pools.home_cell_by_customer.get(trace, pools.cell_ids[0] if pools.cell_ids else "CELL-0001")
    cell_disp = atlas_cell_name(pools, home_cell, trace=True)

    rep = {
        "966591234567": msisdn,
        "966597654321": msisdn,  # collapse second sample line to same thread for consistency
        "966593344556": msisdn,
        "001011234567890": imsi,
        "001017654321000": imsi,
        "001013344556677": imsi,
        "RYD-0421-L18-1": cell_disp,
        "RYD-0421-L18-2": cell_disp.replace("-L18-1", "-L18-2") if "-L18-1" in cell_disp else cell_disp,
    }
    for old, new in ctx.get("cid_map", {}).items():
        rep[old] = new
    out = s
    for old, new in rep.items():
        out = out.replace(old, new)
    # dated filenames 20261105 -> today yyyymmdd
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = re.sub(r"20261105", today, out)
    if ctx.get("vendor_label"):
        out = out.replace("{vendor}", str(ctx["vendor_label"]))
        out = out.replace("{vendor_code}", str(ctx.get("vendor_code") or ""))
    return out


def _substitute_obj(obj: Any, pools: TelcoPools, ctx: Dict[str, Any]) -> Any:
    if isinstance(obj, str):
        return _substitute_string(obj, pools, ctx)
    if isinstance(obj, dict):
        return {k: _substitute_obj(v, pools, ctx) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_obj(v, pools, ctx) for v in obj]
    return obj


def _allowed_modalities_fixture_atlas(
    fixture_body: dict[str, Any], atlas_row: dict[str, Any] | None
) -> Set[str]:
    fx = set((fixture_body.get("deliveries") or {}).keys())
    if not atlas_row:
        return fx
    at = set(atlas_row.get("deliveries") or [])
    if not at:
        return fx
    return fx & at


def _dfilter_for_system(
    system_key: str,
    allowed: Set[str],
    *,
    deliveries: Optional[Set[str]],
    system_deliveries: Optional[Dict[str, Set[str]]],
) -> Set[str]:
    if system_deliveries and system_key in system_deliveries:
        return allowed & set(system_deliveries[system_key])
    if deliveries is not None:
        return allowed & set(deliveries)
    return allowed


def generate_layer_backbone(
    layer: str,
    pools: TelcoPools,
    *,
    systems: Optional[Set[str]] = None,
    deliveries: Optional[Set[str]] = None,
    system_deliveries: Optional[Dict[str, Set[str]]] = None,
    system_vendors: Optional[Dict[str, str]] = None,
    vendor_code: Optional[str] = None,
) -> dict[str, Any]:
    """Produce backbone_bundle for one layer (BSS, OSS, or NSS)."""
    bundle: FixtureBundle = load_sample_fixtures()
    atlas = load_atlas_catalog()
    atlas_by_layer = atlas.systems_for_layer(layer)
    layer_upper = layer.upper()
    sys_map = bundle.systems_for_layer(layer_upper)
    if systems is not None:
        sys_map = {k: v for k, v in sys_map.items() if k in systems}

    global_vid = (vendor_code or "").strip().upper()[:1] or None
    sv_map = {k: str(v).strip().upper()[:1] for k, v in (system_vendors or {}).items() if v}

    cid_map = _build_c100_mapping(pools)

    tables: Dict[str, List[dict]] = {}
    table_sources: Dict[str, str] = {}
    files: List[dict] = []
    vendor_api_index: Dict[str, dict] = {}
    streams: Dict[str, List[dict]] = {}
    stream_sources: Dict[str, str] = {}
    per_system_vendor: Dict[str, str] = {}

    def _resolve_system_vendor(sk: str) -> tuple[str | None, str]:
        letter = sv_map.get(sk) or global_vid
        if not letter:
            return None, ""
        label = str(atlas.vendors.get(letter, letter) or "")
        return letter, label

    for system_key, body in sys_map.items():
        dels = body.get("deliveries") or {}
        slug = _sanitize_table_identifier(system_key)[:60]
        atlas_row = atlas_by_layer.get(system_key)
        allowed = _allowed_modalities_fixture_atlas(body, atlas_row)
        dfilter = _dfilter_for_system(
            system_key,
            allowed,
            deliveries=deliveries,
            system_deliveries=system_deliveries,
        )
        if not dfilter:
            continue

        sys_vid, sys_label = _resolve_system_vendor(system_key)
        per_system_vendor[system_key] = sys_vid or ""
        ctx: Dict[str, Any] = {
            "cid_map": cid_map,
            "vendor_code": sys_vid,
            "vendor_label": sys_label,
        }

        if "Table" in dfilter and dels.get("Table"):
            t = dels["Table"]
            cols = list(t.get("cols") or [])
            rows_in = copy.deepcopy(t.get("rows") or [])
            rows_out: List[dict] = []
            seq_ids = _customer_id_sequence(pools)
            for ri, row in enumerate(rows_in):
                if isinstance(row, list) and cols:
                    row_copy = list(row)
                    # substitute first column if CUSTOMER_ID pattern
                    if cols and "CUSTOMER" in cols[0].upper() and row_copy:
                        old_c = str(row_copy[0])
                        if old_c in cid_map:
                            row_copy[0] = cid_map[old_c]
                        elif old_c.startswith("C-"):
                            idx_alt = ri % len(seq_ids)
                            row_copy[0] = seq_ids[idx_alt]
                    if "MSISDN" in cols:
                        mi = cols.index("MSISDN")
                        row_copy[mi] = atlas_msisdn(pools, pools.customer_ids[ri % len(pools.customer_ids)])
                    if "IMSI" in cols:
                        ii = cols.index("IMSI")
                        row_copy[ii] = atlas_imsi(pools, pools.customer_ids[ri % len(pools.customer_ids)])
                    rdict = dict(zip(cols, row_copy))
                    rows_out.append(rdict)
            min_tbl = billing_file_min_rows(pools)
            if rows_out and len(rows_out) < min_tbl:
                template = rows_out[0]
                seq = _customer_id_sequence(pools)
                while len(rows_out) < min_tbl:
                    ri = len(rows_out)
                    dup = copy.deepcopy(template)
                    cid = pools.customer_ids[ri % len(pools.customer_ids)]
                    for k in list(dup):
                        ku = k.upper()
                        if "CUSTOMER" in ku or ku in {"ACCOUNT_ID", "CUSTOMER_ID"}:
                            dup[k] = seq[ri % len(seq)]
                        elif ku == "MSISDN":
                            dup[k] = atlas_msisdn(pools, cid)
                        elif ku == "IMSI":
                            dup[k] = atlas_imsi(pools, cid)
                        elif ku.endswith("_ID") and isinstance(dup[k], str) and "-" in dup[k]:
                            prefix = str(dup[k]).split("-", 1)[0]
                            dup[k] = f"{prefix}-{7700000 + ri}"
                    rows_out.append(dup)
            table_name = _sanitize_table_identifier(str(t.get("name") or system_key))
            tables[table_name] = rows_out
            table_sources[table_name] = system_key

        if "File" in dfilter and dels.get("File"):
            f = dels["File"]
            raw_content = str(f.get("content") or "")
            content = _substitute_string(raw_content, pools, ctx)
            fname = str(f.get("name") or f"{slug}.txt")
            content = enrich_file_content(fname, content, pools, system_key=system_key)
            files.append(
                {
                    "system_key": system_key,
                    "name": fname,
                    "path": f"incoming/{layer_upper.lower()}/{slug}/{fname}",
                    "content": content,
                }
            )

        if "API" in dfilter and dels.get("API"):
            a = dels["API"]
            path = str(a.get("path") or "")
            method = str(a.get("method") or "GET")
            api_body = _substitute_obj(copy.deepcopy(a.get("body") or {}), pools, ctx)
            route_path = normalize_vendor_route_path(path)
            if route_path:
                lk = vendor_lookup_key(method, route_path)
                vendor_api_index[lk] = {
                    "method": method.upper(),
                    "route_path": route_path,
                    "body": api_body,
                    "system_key": system_key,
                    "fixture_path": path,
                }

        if "Stream" in dfilter and dels.get("Stream"):
            s = dels["Stream"]
            topic = str(s.get("topic") or f"{layer_upper.lower()}.{slug}")
            events = _substitute_obj(copy.deepcopy(s.get("events") or []), pools, ctx)
            min_ev = max(4, min(billing_file_min_rows(pools) // 2, 40))
            if events and len(events) < min_ev:
                base = list(events)
                while len(events) < min_ev:
                    ei = len(events)
                    ev = copy.deepcopy(base[ei % len(base)])
                    cid = pools.customer_ids[ei % len(pools.customer_ids)]
                    msisdn = atlas_msisdn(pools, cid)
                    if isinstance(ev, dict):
                        ev["key"] = msisdn
                        v = ev.get("v")
                        if isinstance(v, dict) and "imsi" in str(ev.get("key", "")).lower():
                            ev["key"] = f"imsi-{atlas_imsi(pools, cid)}"
                    events.append(ev)
            streams[topic] = events
            stream_sources[topic] = system_key

    used_letters = sorted({v for v in per_system_vendor.values() if v})
    if len(used_letters) == 1:
        run_vid = used_letters[0]
        run_label = str(atlas.vendors.get(run_vid, run_vid))
    elif len(used_letters) > 1:
        run_vid = None
        parts = [f"{atlas.vendors.get(c, c)} ({c})" for c in used_letters]
        run_label = "Mixed: " + ", ".join(parts)
    else:
        run_vid = global_vid
        run_label = str(atlas.vendors.get(run_vid, vendor_code or "") or "") if run_vid else ""

    from nexus_simulator.telco_backbone.kenan_overlay import apply_kenan_billing_overlays

    apply_kenan_billing_overlays(
        layer_upper,
        pools,
        tables=tables,
        table_sources=table_sources,
        files=files,
        streams=streams,
        stream_sources=stream_sources,
        systems_in_run=set(sys_map.keys()),
    )

    return {
        "layer": layer_upper,
        "systems": list(sys_map.keys()),
        "vendor_code": run_vid,
        "vendor_label": run_label,
        "per_system_vendor": per_system_vendor,
        "table_sources": table_sources,
        "tables": tables,
        "files": files,
        "vendor_api_index": vendor_api_index,
        "streams": streams,
        "stream_sources": stream_sources,
    }
