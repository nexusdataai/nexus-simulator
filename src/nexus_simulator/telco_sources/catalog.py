"""Load atlas catalog and default profiles."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import Delivery, Layer, SystemConfig, TelcoProductOffer, TelcoSourceProfile

_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "telco"
_CATALOG_PATH = _DATA_ROOT / "atlas_catalog.json"

ZAIN_PRESET_SYSTEMS: list[tuple[Layer, str, str, list[Delivery]]] = [
    ("OSS", "Element manager: Performance (PM)", "E", ["File"]),
    ("OSS", "Element manager: Fault (FM)", "E", ["Stream", "API"]),
    ("BSS", "Mediation", "H", ["File", "Stream"]),
    ("NSS", "Packet gateway (SGW / PGW / SMF / UPF)", "H", ["File", "Stream"]),
    ("OSS", "PM / statistics warehouse", "E", ["Table", "File"]),
    ("OSS", "Autonomous ops / analytics", "H", ["API", "Stream"]),
    ("BSS", "Customer care / complaints", "X", ["Table", "API"]),
    ("OSS", "Trouble tickets (network)", "X", ["Table", "API"]),
    ("OSS", "Change / planned work", "X", ["Table", "API"]),
    ("OSS", "Planning / cell inventory", "H", ["File", "Table", "API"]),
    ("OSS", "Transport / IP NMS", "H", ["Stream", "File"]),
]


@lru_cache(maxsize=1)
def load_atlas_catalog() -> dict[str, Any]:
    if not _CATALOG_PATH.is_file():
        return {"systems": [], "vendor_defaults": {"bss": "H", "oss": "E", "nss": "H"}}
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def catalog_systems() -> list[dict[str, Any]]:
    return list(load_atlas_catalog().get("systems") or [])


def default_profile() -> TelcoSourceProfile:
    cat = load_atlas_catalog()
    defaults = cat.get("vendor_defaults") or {"bss": "H", "oss": "E", "nss": "H"}
    systems: list[SystemConfig] = []
    for entry in catalog_systems():
        layer = entry["layer"]
        vendor = defaults.get(layer.lower(), "H")
        deliveries = list(entry.get("deliveries") or [])
        systems.append(
            SystemConfig(
                layer=layer,
                system_key=entry["system_key"],
                enabled=bool(entry.get("phase_a")),
                vendor=vendor,
                deliveries=deliveries,  # type: ignore[arg-type]
            )
        )
    products = default_products()
    return TelcoSourceProfile(
        profile_id="default",
        vendor_defaults=defaults,
        systems=systems,
        products=products,
    )


def default_products() -> list[TelcoProductOffer]:
    return [
        TelcoProductOffer(
            offer_id="PO-POST-299",
            name="Postpaid 299",
            price_sar=299.0,
            data_gb=25.0,
            linked_systems=["Product catalog", "Subscriptions / installed base"],
        ),
        TelcoProductOffer(
            offer_id="PO-POST-499",
            name="Postpaid 499",
            price_sar=499.0,
            data_gb=60.0,
            linked_systems=["Product catalog", "Subscriptions / installed base"],
        ),
        TelcoProductOffer(
            offer_id="PO-ADD-STREAMPLUS",
            name="StreamPlus VIP add-on",
            offer_type="add-on",
            price_sar=30.0,
            linked_systems=["Product catalog"],
        ),
    ]


def zain_profile() -> TelcoSourceProfile:
    base = default_profile()
    enabled_keys = {s[1] for s in ZAIN_PRESET_SYSTEMS}
    systems: list[SystemConfig] = []
    for entry in catalog_systems():
        layer = entry["layer"]
        key = entry["system_key"]
        preset = next((z for z in ZAIN_PRESET_SYSTEMS if z[1] == key), None)
        if preset:
            _, _, vendor, deliveries = preset
            systems.append(
                SystemConfig(
                    layer=layer,
                    system_key=key,
                    enabled=True,
                    vendor=vendor,
                    deliveries=deliveries,
                )
            )
        else:
            systems.append(
                SystemConfig(
                    layer=layer,
                    system_key=key,
                    enabled=key in enabled_keys,
                    vendor=base.vendor_defaults.get(layer.lower(), "H"),
                    deliveries=list(entry.get("deliveries") or []),
                )
            )
    return TelcoSourceProfile(
        profile_id="zain",
        vendor_defaults={"bss": "H", "oss": "E", "nss": "H"},
        systems=systems,
        products=base.products,
        preset="zain",
    )


def profile_all_systems_enabled(base: TelcoSourceProfile | None = None) -> TelcoSourceProfile:
    prof = base or default_profile()
    systems: list[SystemConfig] = []
    defaults = prof.vendor_defaults
    for entry in catalog_systems():
        layer = entry["layer"]
        systems.append(
            SystemConfig(
                layer=layer,
                system_key=entry["system_key"],
                enabled=True,
                vendor=defaults.get(layer.lower(), "H"),
                deliveries=list(entry.get("deliveries") or []),
            )
        )
    return TelcoSourceProfile(
        profile_id=prof.profile_id,
        vendor_defaults=prof.vendor_defaults,
        systems=systems,
        products=prof.products,
        preset=prof.preset,
    )


def resolve_profile(data: dict[str, Any] | None) -> TelcoSourceProfile:
    if not data:
        return default_profile()
    if data.get("preset") == "zain":
        prof = zain_profile()
        if data.get("systems") or data.get("products"):
            return TelcoSourceProfile.from_dict({**prof.to_dict(), **data})
        return prof
    return TelcoSourceProfile.from_dict(data)
