"""Kenan BP 12.0 inbound file layouts (HDR / A01 / TRA) and Flash usage records."""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any

from nexus_simulator.plugins.telco_seed_pools import TelcoPools
from nexus_simulator.telco_backbone.file_enrichment import billing_file_min_rows
from nexus_simulator.telco_sources.identity import atlas_imsi, atlas_msisdn


def _pad_record(line: str, width: int) -> str:
    if len(line) >= width:
        return line[:width]
    return line + (" " * (width - len(line)))


def expand_kenan_usage_file(content: str, pools: TelcoPools) -> str:
    """HDR + A01 (fixed width) + TRA — pool-expanded from the kenan.js template."""
    lines = [ln for ln in content.splitlines() if ln.strip()]
    if not lines:
        return content
    hdr = next((ln for ln in lines if ln.startswith("HDR")), lines[0])
    tra = next((ln for ln in lines if ln.startswith("TRA")), lines[-1])
    a01 = [ln for ln in lines if ln.startswith("A01")]
    if not a01:
        return content
    width = max(len(ln) for ln in a01)
    target = billing_file_min_rows(pools)
    body: list[str] = []
    for i in range(target):
        tpl = a01[i % len(a01)]
        line = tpl
        cid = pools.customer_ids[i % len(pools.customer_ids)]
        msisdn = atlas_msisdn(pools, cid)
        imsi = atlas_imsi(pools, cid)
        line = re.sub(r"196659\d{6,9}", f"1{msisdn}", line)
        line = re.sub(r"96659\d{6,9}", msisdn, line)
        line = re.sub(r"00101\d{12,15}", imsi, line)
        line = _pad_record(line, width)
        body.append(line)
    batch = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    n = len(body)
    src = "MEDIATION" if "MEDIATION" in hdr else "TIP"
    hdr_out = f"HDR{batch}0415000000{n:06d}{src.ljust(15)}5.2                 "
    tra_out = f"TRA{batch}0415000000{n:06d}{src.ljust(15)}5.2                 "
    return "\n".join([hdr_out, *body, tra_out]) + "\n"


def kenan_usage_subset(
    content: str,
    pools: TelcoPools,
    *,
    prefixes: tuple[str, ...],
    source: str = "MEDIATION",
) -> str:
    """Build a Kenan usage file containing only A01 rows matching ``prefixes`` (e.g. MSC1, PGW)."""
    full = expand_kenan_usage_file(content, pools)
    lines = [ln for ln in full.splitlines() if ln.strip()]
    width = max((len(ln) for ln in lines if ln.startswith("A01")), default=415)
    body = [ln for ln in lines if ln.startswith("A01") and any(p in ln for p in prefixes)]
    if not body:
        tpl = [ln for ln in lines if ln.startswith("A01")]
        body = tpl or lines[1:-1]
    target = max(8, billing_file_min_rows(pools) // 2)
    while len(body) < target and body:
        i = len(body)
        tpl = body[i % len(body)]
        cid = pools.customer_ids[i % len(pools.customer_ids)]
        msisdn = atlas_msisdn(pools, cid)
        imsi = atlas_imsi(pools, cid)
        line = re.sub(r"196659\d{6,9}", f"1{msisdn}", tpl)
        line = re.sub(r"96659\d{6,9}", msisdn, line)
        line = re.sub(r"00101\d{12,15}", imsi, line)
        body.append(_pad_record(line, width))
    batch = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    n = len(body)
    hdr_out = f"HDR{batch}0415000000{n:06d}{source.ljust(15)}5.2                 "
    tra_out = f"TRA{batch}0415000000{n:06d}{source.ljust(15)}5.2                 "
    return "\n".join([hdr_out, *body, tra_out]) + "\n"


def expand_kenan_flash_events(events: list[dict[str, Any]], pools: TelcoPools) -> list[dict[str, Any]]:
    """Kenan Flash mode — one A01-shaped JSON record per IPC message."""
    if not events:
        return events
    min_ev = max(4, min(billing_file_min_rows(pools) // 2, 40))
    out = copy.deepcopy(events)
    base = list(events)
    types = (101, 201, 301, 101)
    while len(out) < min_ev:
        i = len(out)
        ev = copy.deepcopy(base[i % len(base)])
        cid = pools.customer_ids[i % len(pools.customer_ids)]
        msisdn = atlas_msisdn(pools, cid)
        ev["key"] = msisdn
        v = ev.get("v")
        if isinstance(v, dict):
            v["type_id_usg"] = types[i % len(types)]
            v["trans_dt"] = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            v["rec"] = "A01"
        out.append(ev)
    return out


def expand_kenan_delimited_file(content: str, pools: TelcoPools) -> str:
    """Lockbox / CPM / EFT fixed-width payment files (repeat detail lines)."""
    from nexus_simulator.telco_backbone.file_enrichment import enrich_file_content

    return enrich_file_content("kenan_pay.txt", content, pools)


def kenan_table_rows(delivery: dict[str, Any], pools: TelcoPools) -> list[dict]:
    """Convert Kenan sample table (cols + rows) to list of dicts."""
    cols = list(delivery.get("cols") or [])
    rows_in = delivery.get("rows") or []
    if not cols:
        return []
    rows_out: list[dict] = []
    for ri, row in enumerate(rows_in):
        if isinstance(row, list):
            rows_out.append(dict(zip(cols, row)))
    target = billing_file_min_rows(pools)
    if rows_out and len(rows_out) < target:
        template = rows_out[0]
        while len(rows_out) < target:
            dup = copy.deepcopy(template)
            cid = pools.customer_ids[len(rows_out) % len(pools.customer_ids)]
            msisdn = atlas_msisdn(pools, cid)
            for k in list(dup):
                ku = k.lower()
                if "msisdn" in ku or "external_id" in ku and "type" not in ku:
                    dup[k] = msisdn
                if "account_no" in ku and dup[k].isdigit():
                    dup[k] = str(3000245 + (len(rows_out) % 50))
            rows_out.append(dup)
    return rows_out