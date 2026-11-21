"""Expand billing backbone file bodies using TelcoPools (row volume for demos / ETL)."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

from nexus_simulator.plugins.telco_seed_pools import TelcoPools
from nexus_simulator.telco_sources.identity import atlas_imsi, atlas_msisdn


def billing_file_min_rows(pools: TelcoPools) -> int:
    """Minimum data rows per billing input file (excluding header)."""
    try:
        floor = int(os.getenv("TELCO_BILLING_FILE_MIN_ROWS", "25"))
    except ValueError:
        floor = 25
    return max(8, min(floor, len(pools.customer_ids) * max(1, min(pools.history_days, 14))))


def _customers(pools: TelcoPools, n: int) -> Iterable[tuple[str, str, str]]:
    ids = pools.customer_ids
    for i in range(n):
        cid = ids[i % len(ids)]
        yield cid, atlas_msisdn(pools, cid), atlas_imsi(pools, cid)


def _expand_delimited(content: str, delim: str, target: int, pools: TelcoPools) -> str:
    lines = [ln for ln in content.splitlines() if ln.strip()]
    if len(lines) < 1:
        return content
    header = lines[0]
    body = lines[1:]
    if len(body) >= target:
        return content
    out = [header]
    out.extend(body)
    cols = header.split(delim)
    need = target - len(body)
    base_dt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    for i, (cid, msisdn, imsi) in enumerate(_customers(pools, need)):
        seed = body[i % len(body)] if body else header
        row = seed
        row = re.sub(r"96659\d{6,9}", msisdn, row)
        row = re.sub(r"00101\d{12,15}", imsi, row)
        row = re.sub(r"C-\d{6}", cid.replace("CUST-", "C-") if cid.startswith("CUST") else cid, row)
        if "EVENT_ID" in header or "event_id" in header:
            parts = row.split(delim)
            if parts:
                parts[0] = f"E{8800000000 + i}"
                row = delim.join(parts)
        elif cols and len(cols) > 1 and "record_id" in header.lower():
            parts = row.split(delim)
            parts[0] = f"MD-{10000 + i:05d}"
            parts[3] = imsi
            parts[4] = msisdn
            parts[5] = (base_dt - timedelta(minutes=i * 3)).strftime("%Y-%m-%dT%H:%M:%S+03:00")
            row = delim.join(parts)
        elif "request_id" in header:
            parts = row.split(delim)
            parts[0] = f"PR-2026-{450000 + i:06d}"
            parts[1] = msisdn
            row = delim.join(parts)
        out.append(row)
    return "\n".join(out) + ("\n" if content.endswith("\n") else "")


def _expand_csv(content: str, target: int, pools: TelcoPools) -> str:
    return _expand_delimited(content, ",", target, pools)


def _expand_cdr_dump(content: str, target: int, pools: TelcoPools) -> str:
    """Append decoded CDR-style records for MSC/PGW/IMS dumps."""
    blocks = [b.strip() for b in re.split(r"\n(?=-- File:|\w+Record \{)", content) if b.strip()]
    if not blocks:
        return content
    header = blocks[0]
    if len(blocks) - 1 >= target:
        return content
    out_parts = [content.rstrip()]
    template = blocks[-1] if len(blocks) > 1 else blocks[0]
    need = target - max(0, len(blocks) - 1)
    for i, (_cid, msisdn, imsi) in enumerate(_customers(pools, need)):
        blk = template
        blk = re.sub(r"servedIMSI\s+\d+", f"servedIMSI            {imsi}", blk)
        blk = re.sub(r"servedMSISDN\s+\d+", f"servedMSISDN          {msisdn}", blk)
        blk = re.sub(r"recordSequenceNumber\s+\d+", f"recordSequenceNumber  {451 + i}", blk)
        out_parts.append("\n" + blk.strip())
    return "\n".join(out_parts) + "\n"


def _expand_tap_dump(content: str, target: int, pools: TelcoPools) -> str:
    if content.count("gprsCall") >= target:
        return content
    insert_at = content.rfind("auditControlInfo")
    if insert_at < 0:
        return content
    extra = []
    for i, (_cid, msisdn, imsi) in enumerate(_customers(pools, target - 1)):
        extra.append(
            f"  gprsCall {{\n"
            f"    imsi                 {imsi}\n"
            f"    callEventStartTimeStamp 202611041830{i:02d}+0400\n"
            f"    dataVolumeIncoming   {399112334 + i * 1000}\n"
            f"    dataVolumeOutgoing   {20044211 + i * 500}\n"
            f"    apn                  internet.nimbus\n"
            f"    charge               0.000000 (bundle)\n"
            f"  }}\n"
        )
    head = content[:insert_at].rstrip()
    tail = content[insert_at:]
    return head + "\n" + "".join(extra) + tail


def enrich_file_content(
    filename: str,
    content: str,
    pools: TelcoPools,
    *,
    system_key: str = "",
) -> str:
    """Return content with enough rows for billing feed demos and downstream ETL."""
    if not content or not content.strip():
        return content
    target = billing_file_min_rows(pools)
    lower = filename.lower()
    first = content.lstrip().split("\n", 1)[0]
    if "|" in first:
        return _expand_delimited(content, "|", target, pools)
    if "," in first and (lower.endswith(".csv") or "msisdn" in first.lower() or "imsi" in first.lower()):
        return _expand_csv(content, target, pools)
    if lower.endswith(".dat") or "moCallRecord" in content or "pGWRecord" in content or content.strip().startswith("-- File:"):
        return _expand_cdr_dump(content, target, pools)
    if "TAP3" in content or "TransferBatch" in content:
        return _expand_tap_dump(content, target, pools)
    if lower.endswith(".json") or lower.endswith(".jsonl"):
        lines = [ln for ln in content.splitlines() if ln.strip()]
        if len(lines) >= target:
            return content
        out = list(lines)
        while len(out) < target and lines:
            out.append(lines[len(out) % len(lines)])
        return "\n".join(out) + ("\n" if content.endswith("\n") else "")
    return content