"""
Shared ID pools for supply chain simulator seed data.

Ensures consistent cross-system references: SFDC Account IDs match Oracle AR_Customer IDs,
SAP Material IDs are used in SFDC Opportunity_Line_Items, Oracle PO IDs in SAP Goods_Receipt, etc.

All simulators import from this module to share the same deterministic ID pools.
"""

import random
import string
from datetime import datetime, timedelta, timezone

_seed_initialized = False

REGIONS = ["North", "South", "East", "West", "Central"]
COUNTRIES = ["Singapore", "Malaysia", "Thailand", "Indonesia", "Philippines", "Vietnam"]
CITIES = ["Singapore", "Kuala Lumpur", "Bangkok", "Jakarta", "Manila", "Ho Chi Minh City"]
CURRENCIES = ["SGD", "MYR", "THB", "IDR", "PHP", "VND", "USD"]

BEVERAGE_CATEGORIES = ["Carbonated", "Juice", "Water", "Energy", "Sports", "Tea", "Snacks"]
BEVERAGE_BRANDS = ["StarFizz", "TropicBurst", "AquaPure", "PowerVolt", "ActiveHydro", "ZenBrew", "CrunchBites"]
PACK_SIZES = ["330ml", "500ml", "1L", "1.5L", "2L", "6-pack", "12-pack", "24-pack"]
PACK_CONFIGS = ["Can", "PET Bottle", "Glass Bottle", "Tetra Pak", "Pouch"]

VENDOR_CATEGORIES = ["Raw_Material", "Packaging", "Co_Packer", "Logistics", "Services", "Equipment"]
PLANT_TYPES = ["Manufacturing", "Distribution_Center", "Depot", "Co_Packer"]
STORAGE_TYPES = ["Raw_Material", "WIP", "Finished_Goods", "Cold_Chain", "Quarantine"]

CAMPAIGN_TYPES = ["Discount", "BOGO", "Bundle", "Display", "Sampling"]
CHANNEL_TYPES = ["Modern_Trade", "General_Trade", "HORECA", "E-commerce", "Institutional"]
TIERS = ["Platinum", "Gold", "Silver", "Bronze"]
CONTACT_ROLES = ["Buyer", "Finance", "Logistics", "Decision_Maker", "Influencer"]
ACCOUNT_STATUSES = ["Active", "Active", "Active", "Active", "Inactive", "Suspended"]
OPP_STAGES = ["Prospect", "Negotiation", "Closed_Won", "Closed_Won", "Closed_Won", "Closed_Lost", "Fulfilled"]
DELIVERY_PRIORITIES = ["Standard", "Express", "Critical"]
ASSET_CATEGORIES = ["Production_Line", "Warehouse_Equipment", "Vehicle", "Refrigeration", "IT_Systems"]
COST_CENTERS = ["Manufacturing", "Logistics", "Procurement", "Quality", "R&D", "Sales", "Admin"]
BUDGET_CATEGORIES = ["OPEX", "CAPEX"]


def _ensure_seed():
    global _seed_initialized
    if not _seed_initialized:
        random.seed(42)
        _seed_initialized = True


def _ids(prefix: str, count: int, width: int = 5) -> list[str]:
    return [f"{prefix}{i+1:0{width}d}" for i in range(count)]


account_ids: list[str] = _ids("ACC-", 200)
contact_ids: list[str] = _ids("CON-", 400)
opportunity_ids: list[str] = _ids("OPP-", 500)
campaign_ids: list[str] = _ids("CMP-", 30, 3)
material_ids: list[str] = _ids("MAT-", 300)
plant_ids: list[str] = _ids("PLT-", 10, 3)
storage_ids: list[str] = _ids("SL-", 40, 3)
production_line_ids: list[str] = _ids("PL-", 25, 3)
batch_ids: list[str] = _ids("BAT-", 800)
vendor_ids: list[str] = _ids("VND-", 80, 3)
po_ids: list[str] = _ids("PO-", 500)
delivery_ids: list[str] = _ids("DEL-", 600)
invoice_ids: list[str] = _ids("INV-", 800)
production_order_ids: list[str] = _ids("PRD-", 500)
inspection_ids: list[str] = _ids("QIL-", 300)


def date_str(start_days_ago: int = 365, end_days_ago: int = 0) -> str:
    _ensure_seed()
    delta = random.randint(end_days_ago, max(start_days_ago, end_days_ago + 1))
    return (datetime.now(timezone.utc) - timedelta(days=delta)).strftime("%Y-%m-%d")


def datetime_str(start_days_ago: int = 365, end_days_ago: int = 0) -> str:
    _ensure_seed()
    delta = random.randint(end_days_ago, max(start_days_ago, end_days_ago + 1))
    dt = datetime.now(timezone.utc) - timedelta(days=delta, hours=random.randint(0, 23))
    return dt.isoformat()


def money(low: float = 10, high: float = 10000) -> float:
    _ensure_seed()
    return round(random.uniform(low, high), 2)


def pct(low: float = 0, high: float = 100) -> float:
    _ensure_seed()
    return round(random.uniform(low, high), 1)


def gtin() -> str:
    _ensure_seed()
    return "".join(random.choices(string.digits, k=13))


def pick(pool: list[str]) -> str:
    _ensure_seed()
    return random.choice(pool) if pool else ""
