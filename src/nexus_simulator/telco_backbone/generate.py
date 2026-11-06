"""Render backbone artifacts from fixtures + TelcoPools."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

from nexus_simulator.plugins.telco_seed_pools import TelcoPools
from nexus_simulator.telco_sources.identity import (
    atlas_cell_name,
    atlas_customer_id,
    atlas_imsi,
    atlas_msisdn,
    trace_customer_internal,
)
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


def _substitute_string(s: str, pools: TelcoPools, ctx: Dict[str, str]) -> str:
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
    return out


def _substitute_obj(obj: Any, pools: TelcoPools, ctx: Dict[str, Any]) -> Any:
    if isinstance(obj, str):
        return _substitute_string(obj, pools, ctx)
    if isinstance(obj, dict):
        return {k: _substitute_obj(v, pools, ctx) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_obj(v, pools, ctx) for v in obj]
    return obj


def generate_layer_backbone(
    layer: str,
    pools: TelcoPools,
    *,
    systems: Optional[Set[str]] = None,
    deliveries: Optional[Set[str]] = None,
) -> dict[str, Any]:
    """Produce backbone_bundle for one layer (BSS, OSS, or NSS)."""
    bundle: FixtureBundle = load_sample_fixtures()
    layer_upper = layer.upper()
    sys_map = bundle.systems_for_layer(layer_upper)
    if systems is not None:
        sys_map = {k: v for k, v in sys_map.items() if k in systems}
    dfilter = deliveries or {"Table", "File", "API", "Stream"}

    cid_map = _build_c100_mapping(pools)
    ctx: Dict[str, Any] = {"cid_map": cid_map}

    tables: Dict[str, List[dict]] = {}
    files: List[dict] = []
    vendor_api_index: Dict[str, dict] = {}
    streams: Dict[str, List[dict]] = {}

    for system_key, body in sys_map.items():
        dels = body.get("deliveries") or {}
        slug = _sanitize_table_identifier(system_key)[:60]

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
            table_name = _sanitize_table_identifier(str(t.get("name") or system_key))
            tables[table_name] = rows_out

        if "File" in dfilter and dels.get("File"):
            f = dels["File"]
            raw_content = str(f.get("content") or "")
            content = _substitute_string(raw_content, pools, ctx)
            files.append(
                {
                    "system_key": system_key,
                    "name": f.get("name") or f"{slug}.txt",
                    "path": f"incoming/{layer_upper.lower()}/{slug}/{f.get('name') or 'export.txt'}",
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
            streams[topic] = events

    return {
        "layer": layer_upper,
        "systems": list(sys_map.keys()),
        "tables": tables,
        "files": files,
        "vendor_api_index": vendor_api_index,
        "streams": streams,
    }
