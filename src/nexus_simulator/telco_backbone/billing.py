"""Billing module metadata aligned with Telco-Data / Kenan BP."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from nexus_simulator.telco_backbone.atlas_catalog import load_atlas_catalog


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    raw: str | None = None
    try:
        pkg = resources.files("nexus_simulator.data.telco")
        ref = pkg / "billing_modules.json"
        if ref.is_file():
            raw = ref.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        pass
    if raw is None:
        p = Path(__file__).resolve().parents[1] / "data" / "telco" / "billing_modules.json"
        raw = p.read_text(encoding="utf-8")
    return json.loads(raw)


def billing_system_targets() -> dict[str, str]:
    mod = (_load_raw().get("modules") or {}).get("billing") or {}
    sys = mod.get("systems") or {}
    return {str(k): str(v) for k, v in sys.items()}


def billing_system_keys() -> set[str]:
    return set(billing_system_targets().keys())


def billing_system_keys_for_layer(layer: str) -> set[str]:
    lu = layer.upper()
    atlas = load_atlas_catalog()
    layer_keys = set(atlas.systems_for_layer(lu).keys())
    return billing_system_keys() & layer_keys


def billing_target_for_system(system_key: str) -> str | None:
    return billing_system_targets().get(system_key)


def is_billing_system(system_key: str) -> bool:
    return system_key in billing_system_targets()


def telco_backbone_profile() -> str:
    """``billing`` limits default telco seed to Kenan-relevant families; ``full`` generates all atlas systems."""
    v = (os.getenv("TELCO_BACKBONE_PROFILE") or "billing").strip().lower()
    return "full" if v == "full" else "billing"


# Legacy CRM/OSS/NSS tables (bss_crm / nss_core / oss_network) → billing atlas system_key.
LEGACY_BILLING_TABLES: dict[str, dict[str, dict[str, str]]] = {
    "bss": {
        "Subscriber_Profile": {"system_key": "CRM / customer master"},
        "Subscription_Plan_History": {"system_key": "Order management"},
        "Contract": {"system_key": "Subscriptions / installed base"},
        "Invoice": {"system_key": "Billing / invoicing"},
        "Payment": {"system_key": "Payments and collections"},
        "Prepaid_Recharge": {"system_key": "Online charging (OCS / CCS / CHF)"},
        "Care_Interaction": {"system_key": "Customer care / complaints"},
        "Billing_Dispute": {"system_key": "Customer care / complaints"},
        "MNP_Port_Out_Request": {"system_key": "MNP / port-out"},
    },
    "nss": {
        "Usage_Daily_Agg": {"system_key": "Packet gateway (SGW / PGW / SMF / UPF)"},
        "Roaming_Daily_Agg": {"system_key": "Roaming (TAP / RAP)"},
        "USSD_Balance_Check": {"system_key": "SMSC / USSD"},
        "Policy_Throttle_Event": {"system_key": "Online charging (OCS / CCS / CHF)"},
    },
    "oss": {
        "Service_Activation_Result": {"system_key": "Service orchestration & activation"},
    },
}

KENAN_BILLING_TABLES: dict[str, dict[str, str]] = {
    "CMF": {"system_key": "CRM / customer master", "module": "kenan"},
    "EXTERNAL_ID_ACCT_MAP": {"system_key": "CRM / customer master", "module": "kenan"},
    "SERVICE": {"system_key": "Subscriptions / installed base", "module": "kenan"},
    "PRODUCT": {"system_key": "Subscriptions / installed base", "module": "kenan"},
    "RATE_USAGE": {"system_key": "Product catalog", "module": "kenan"},
    "RATE_RC": {"system_key": "Product catalog", "module": "kenan"},
    "CDR_DATA": {"system_key": "Mediation", "module": "kenan"},
    "BILL_INVOICE": {"system_key": "Billing / invoicing", "module": "kenan"},
    "BILL_INVOICE_DETAIL": {"system_key": "Billing / invoicing", "module": "kenan"},
    "BMF": {"system_key": "Payments and collections", "module": "kenan"},
    "PAYMENT_TRANS": {"system_key": "Payments and collections", "module": "kenan"},
    "ADJ": {"system_key": "Customer care / complaints", "module": "kenan"},
}


def catalog_entry_for_table(
    service: str,
    schema: str,
    table: str,
    *,
    system_key: str | None = None,
) -> dict[str, Any]:
    applications: list[str] = []
    billing_target: str | None = None
    sk = system_key
    if schema.startswith("kenan_"):
        meta = KENAN_BILLING_TABLES.get(table)
        if meta:
            sk = sk or meta.get("system_key")
            applications.append("billing")
            applications.append("kenan")
    if not sk:
        leg = (LEGACY_BILLING_TABLES.get(service) or {}).get(table)
        if leg:
            sk = leg.get("system_key")
    if sk and is_billing_system(sk):
        applications.append("billing")
        billing_target = billing_target_for_system(sk)
    out: dict[str, Any] = {}
    if applications:
        out["applications"] = sorted(set(applications))
    if sk:
        out["system_key"] = sk
    if billing_target:
        out["billing_target"] = billing_target
    return out