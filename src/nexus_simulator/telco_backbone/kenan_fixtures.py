"""Load Kenan BP inbound feed samples from data/Telco-Data/kenan.js (exported JSON)."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def load_kenan_feed_fixtures() -> dict[str, Any]:
    raw: str | None = None
    try:
        pkg = resources.files("nexus_simulator.data.telco")
        ref = pkg / "kenan_feed_fixtures.json"
        if ref.is_file():
            raw = ref.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        pass
    if raw is None:
        p = Path(__file__).resolve().parents[1] / "data" / "telco" / "kenan_feed_fixtures.json"
        raw = p.read_text(encoding="utf-8")
    data = json.loads(raw)
    return dict(data.get("feeds") or {})


# Atlas product family (simulator) → Kenan BP feed name in kenan.js samples.
ATLAS_TO_KENAN_FEED: dict[str, str] = {
    "Mediation": "Usage CDRs (voice, SMS, data)",
    "Packet gateway (SGW / PGW / SMF / UPF)": "Usage CDRs (voice, SMS, data)",
    "MSC / MSS (2G / 3G voice)": "Usage CDRs (voice, SMS, data)",
    "IMS / VoLTE / VoWiFi": "Usage CDRs (voice, SMS, data)",
    "SMSC / USSD": "Usage CDRs (voice, SMS, data)",
    "Roaming (TAP / RAP)": "Roaming usage (TAP in / out)",
    "Online charging (OCS / CCS / CHF)": "Real-time usage (Flash mode)",
    "CRM / customer master": "Customers and accounts",
    "Order management": "Services and products (orders)",
    "Subscriptions / installed base": "Services and products (orders)",
    "Product catalog": "Product catalogue and rates",
    "Payments and collections": "Manual payments, adjustments, one-off charges",
    "Customer care / complaints": "Manual payments, adjustments, one-off charges",
}

# Extra Kenan payment files merged onto Payments and collections (atlas).
KENAN_EXTRA_FILES_ON_PAYMENTS: list[str] = [
    "Lockbox (cheque) payments",
    "Card payments (CPM)",
    "Direct debit (EFT)",
]