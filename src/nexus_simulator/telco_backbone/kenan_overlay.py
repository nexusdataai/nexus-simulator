"""Apply Kenan BP tab sample shapes onto Telco AI Backbone artifacts (billing input)."""

from __future__ import annotations

import copy
import re
from typing import Any

from nexus_simulator.plugins.telco_seed_pools import TelcoPools
from nexus_simulator.telco_backbone.kenan_fixtures import (
    ATLAS_TO_KENAN_FEED,
    KENAN_EXTRA_FILES_ON_PAYMENTS,
    load_kenan_feed_fixtures,
)
from nexus_simulator.telco_backbone.kenan_formats import (
    expand_kenan_delimited_file,
    expand_kenan_flash_events,
    expand_kenan_usage_file,
    kenan_table_rows,
    kenan_usage_subset,
)

# NSS file delivery for usage CDR feed → Kenan A01 row families (kenan.js samples).
USAGE_CDR_KENAN_PREFIXES: dict[str, tuple[str, ...]] = {
    "MSC / MSS (2G / 3G voice)": ("MSC1-", "MSC1"),
    "Packet gateway (SGW / PGW / SMF / UPF)": ("PGW",),
    "IMS / VoLTE / VoWiFi": ("MSC1-", "PGW"),
    "SMSC / USSD": ("SMSC-", "SMSC"),
}


def _sanitize_table_identifier(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_")


def apply_kenan_billing_overlays(
    layer: str,
    pools: TelcoPools,
    *,
    tables: dict[str, list[dict]],
    table_sources: dict[str, str],
    files: list[dict],
    streams: dict[str, list[dict]],
    stream_sources: dict[str, str],
    systems_in_run: set[str],
) -> None:
    """Replace or augment atlas deliveries with Kenan BP inbound samples where mapped."""
    kenan = load_kenan_feed_fixtures()
    layer_l = layer.upper()
    seen_file_keys: set[tuple[str, str]] = {(str(f.get("system_key")), str(f.get("name"))) for f in files}

    def add_file(system_key: str, spec: dict[str, Any], *, force: bool = False) -> None:
        if not spec:
            return
        name = str(spec.get("name") or "kenan_export.dat")
        key = (system_key, name)
        if key in seen_file_keys and not force:
            return
        slug = _sanitize_table_identifier(system_key)[:60]
        content = str(spec.get("content") or "")
        if name.endswith(".dat") or content.startswith("HDR"):
            content = expand_kenan_usage_file(content, pools)
        else:
            content = expand_kenan_delimited_file(content, pools)
        entry = {
            "system_key": system_key,
            "name": name,
            "path": f"incoming/{layer_l.lower()}/{slug}/{name}",
            "content": content,
            "kenan_feed": True,
        }
        if force and key in seen_file_keys:
            files[:] = [f for f in files if not (f.get("system_key") == system_key and f.get("name") == name)]
        files.append(entry)
        seen_file_keys.add(key)

    def set_table(system_key: str, delivery: dict[str, Any]) -> None:
        rows = kenan_table_rows(delivery, pools)
        if not rows:
            return
        tname = _sanitize_table_identifier(str(delivery.get("name") or system_key))
        tables[tname] = rows
        table_sources[tname] = system_key

    for system_key in systems_in_run:
        feed_name = ATLAS_TO_KENAN_FEED.get(system_key)
        if not feed_name:
            continue
        feed = kenan.get(feed_name)
        if not feed:
            continue
        dels = feed.get("deliveries") or {}

        if system_key == "Mediation" and dels.get("File"):
            files[:] = [f for f in files if f.get("system_key") != system_key]
            seen_file_keys.difference_update({k for k in seen_file_keys if k[0] == system_key})
            add_file(system_key, dels["File"], force=True)
        elif system_key == "Roaming (TAP / RAP)" and dels.get("File"):
            files[:] = [f for f in files if f.get("system_key") != system_key]
            seen_file_keys.difference_update({k for k in seen_file_keys if k[0] == system_key})
            add_file(system_key, dels["File"], force=True)
        elif system_key == "Packet gateway (SGW / PGW / SMF / UPF)":
            usage = kenan.get("Usage CDRs (voice, SMS, data)", {}).get("deliveries", {}).get("File")
            if usage:
                alt = copy.deepcopy(usage)
                alt["name"] = str(usage.get("name") or "MSC1_USG.dat")
                add_file(system_key, alt, force=True)

        if system_key in {"Mediation", "Roaming (TAP / RAP)", "Packet gateway (SGW / PGW / SMF / UPF)"} and dels.get("Table"):
            set_table(system_key, dels["Table"])

        if system_key == "Online charging (OCS / CCS / CHF)" and dels.get("Stream"):
            s = dels["Stream"]
            topic = str(s.get("topic") or "MCAP socket · IPC message queue")
            events = expand_kenan_flash_events(copy.deepcopy(s.get("events") or []), pools)
            streams[topic] = events
            stream_sources[topic] = system_key

        if dels.get("Table") and system_key in {
            "CRM / customer master",
            "Order management",
            "Subscriptions / installed base",
            "Product catalog",
            "Customer care / complaints",
            "Billing / invoicing",
        }:
            set_table(system_key, dels["Table"])

        if system_key == "Payments and collections":
            for extra in KENAN_EXTRA_FILES_ON_PAYMENTS:
                xf = kenan.get(extra, {}).get("deliveries", {}).get("File")
                if xf:
                    add_file(system_key, xf)
            if dels.get("Table"):
                set_table(system_key, dels["Table"])

    usage_kenan = kenan.get("Usage CDRs (voice, SMS, data)", {}).get("deliveries", {}).get("File")
    usage_raw = str((usage_kenan or {}).get("content") or "")
    if usage_raw:
        for system_key, prefixes in USAGE_CDR_KENAN_PREFIXES.items():
            if system_key not in systems_in_run:
                continue
            files[:] = [f for f in files if f.get("system_key") != system_key]
            seen_file_keys.difference_update({k for k in seen_file_keys if k[0] == system_key})
            slug = _sanitize_table_identifier(system_key)[:60]
            fname = {
                "MSC / MSS (2G / 3G voice)": "MSC1_USG_20261113220000.dat",
                "Packet gateway (SGW / PGW / SMF / UPF)": "MSC1_USG_20261113220000.dat",
                "IMS / VoLTE / VoWiFi": "MSC1_USG_IMS_20261113220000.dat",
                "SMSC / USSD": "MSC1_USG_SMSC_20261113220000.dat",
            }.get(system_key, "MSC1_USG_20261113220000.dat")
            body = kenan_usage_subset(usage_raw, pools, prefixes=prefixes, source="MEDIATION")
            files.append(
                {
                    "system_key": system_key,
                    "name": fname,
                    "path": f"incoming/{layer_l.lower()}/{slug}/{fname}",
                    "content": body,
                    "kenan_feed": True,
                }
            )
            seen_file_keys.add((system_key, fname))