#!/usr/bin/env python3
"""Export machine-readable telco atlas catalog from data/Telco-Data/samples.js."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "Telco-Data" / "samples.js"
OUT = ROOT / "data" / "telco" / "atlas_catalog.json"

DELIVERIES = ("Table", "File", "API", "Stream")
LAYER_MARKERS = [
    ("BSS", re.compile(r"/\* =+ BSS =+ \*/")),
    ("OSS", re.compile(r"/\* =+ OSS =+ \*/")),
    ("NSS", re.compile(r"/\* =+ NSS")),
]


def slug(system_key: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", system_key.strip()).strip("_").lower()
    return s[:80]


def parse_samples(text: str) -> list[dict]:
    current_layer = "BSS"
    systems: list[dict] = []
    for marker_layer, pat in LAYER_MARKERS:
        pass  # layer updated when marker found in loop below

    pos = 0
    current_layer = "BSS"
    key_re = re.compile(r'\n"([^"]+)":\s*\{')

    while True:
        m = key_re.search(text, pos)
        if not m:
            break
        system_key = m.group(1)
        start = m.end()
        # find matching closing brace for this system block (naive depth)
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        block = text[start : i - 1]
        for marker_layer, pat in LAYER_MARKERS:
            if pat.search(text[: m.start()]):
                current_layer = marker_layer
        # recompute layer from last marker before this key
        layer = "BSS"
        for marker_layer, pat in LAYER_MARKERS:
            if pat.search(text[: m.start()]):
                layer = marker_layer
        deliveries = [d for d in DELIVERIES if re.search(rf"\b{d}:\s*\{{", block)]
        systems.append(
            {
                "system_key": system_key,
                "slug": slug(system_key),
                "layer": layer,
                "deliveries": deliveries,
                "phase_a": system_key
                in {
                    "CRM / customer master",
                    "Product catalog",
                    "Subscriptions / installed base",
                    "Online charging (OCS / CCS / CHF)",
                    "Mediation",
                    "Customer care / complaints",
                    "Element manager: Fault (FM)",
                    "Element manager: Performance (PM)",
                    "PM / statistics warehouse",
                    "Trouble tickets (network)",
                    "Planning / cell inventory",
                    "Packet gateway (SGW / PGW / SMF / UPF)",
                    "MME / AMF (mobility)",
                    "PCRF / PCF (policy)",
                },
            }
        )
        pos = i

    return systems


def main() -> None:
    text = SAMPLES.read_text(encoding="utf-8")
    systems = parse_samples(text)
    catalog = {
        "version": 1,
        "source": "data/Telco-Data/samples.js",
        "vendors": {
            "H": "Huawei",
            "N": "Nokia",
            "E": "Ericsson",
            "A": "Amdocs",
            "S": "Salesforce",
            "O": "Oracle",
            "X": "Others",
        },
        "vendor_defaults": {"bss": "H", "oss": "E", "nss": "H"},
        "systems": systems,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Wrote {len(systems)} systems to {OUT}")


if __name__ == "__main__":
    main()
