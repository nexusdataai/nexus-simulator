"""
Shared ID pools for supply chain simulator seed data.

Ensures consistent cross-system references: SFDC Account IDs match Oracle AR_Customer IDs,
SAP Material IDs are used in SFDC Opportunity_Line_Items, Oracle PO IDs in SAP Goods_Receipt, etc.

All simulators import from this module to share the same deterministic ID pools.
"""

import random
import string
from datetime import datetime, timedelta, timezone
from typing import List

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


def _ids(prefix: str, count: int, width: int = 5) -> List[str]:
    return [f"{prefix}{i+1:0{width}d}" for i in range(count)]


account_ids: List[str] = _ids("ACC-", 200)
contact_ids: List[str] = _ids("CON-", 400)
opportunity_ids: List[str] = _ids("OPP-", 500)
campaign_ids: List[str] = _ids("CMP-", 30, 3)
material_ids: List[str] = _ids("MAT-", 300)
plant_ids: List[str] = _ids("PLT-", 10, 3)
storage_ids: List[str] = _ids("SL-", 40, 3)
production_line_ids: List[str] = _ids("PL-", 25, 3)
batch_ids: List[str] = _ids("BAT-", 800)
vendor_ids: List[str] = _ids("VND-", 80, 3)
po_ids: List[str] = _ids("PO-", 500)
delivery_ids: List[str] = _ids("DEL-", 600)
invoice_ids: List[str] = _ids("INV-", 800)
production_order_ids: List[str] = _ids("PRD-", 500)
inspection_ids: List[str] = _ids("QIL-", 300)

# Section 3.1 plan extensions for the four-views program
shift_ids: List[str] = ["SHIFT-A", "SHIFT-B", "SHIFT-C"]
defect_codes: List[str] = [
    "DEF-DENT", "DEF-LEAK", "DEF-LABEL", "DEF-FILL", "DEF-CAP",
    "DEF-WEIGHT", "DEF-COLOR", "DEF-MICRO", "DEF-EXPIRY", "DEF-PACK",
]
delay_reasons: List[str] = [
    "carrier_delay", "customs_hold", "weather", "stockout",
    "quality_hold", "address_issue", "transport_breakdown", "labour_strike",
]
downtime_reasons: List[str] = [
    "scheduled_maintenance", "unplanned_breakdown", "changeover", "material_shortage",
    "operator_break", "quality_hold", "power_outage",
]
tier2_vendor_ids: List[str] = _ids("VT2-", 60, 3)
commodity_codes: List[str] = [
    "SUGAR", "ALUMINIUM", "PET_RESIN", "CARDBOARD", "GLASS",
    "ENERGY_KWH", "WATER_M3", "PALM_OIL", "WHEAT", "COFFEE_BEAN",
    "TEA_LEAF", "JUICE_CONC", "DAIRY", "FRUCTOSE", "FUEL_DIESEL",
    "STEEL", "PAPER", "ELECTRICITY", "GAS", "WAREHOUSE_RENT",
]
churn_reasons: List[str] = [
    "price_increase", "service_quality", "competitor_offer",
    "product_discontinuation", "credit_issues", "merger_acquired",
]
account_health_buckets: List[str] = ["Healthy", "Watch", "AtRisk", "Critical"]

# ─── CPQ pools (Sell-Side Trade CPQ + Buy-Side Sourcing CPQ) ───────
offering_ids: List[str] = _ids("OFR-", 60, 5)
offering_component_ids: List[str] = _ids("OFC-", 200, 5)
price_book_ids: List[str] = _ids("PB-", 24, 4)
price_book_entry_ids: List[str] = _ids("PBE-", 600, 5)
quote_ids: List[str] = _ids("QT-", 250, 5)
quote_line_ids: List[str] = _ids("QTL-", 700, 5)
quote_promotion_ids: List[str] = _ids("QPR-", 120, 5)
serviceability_ids: List[str] = _ids("SVF-", 80, 5)
configuration_rule_ids: List[str] = _ids("CRL-", 40, 4)

rfx_event_ids: List[str] = _ids("RFX-", 60, 5)
rfx_line_ids: List[str] = _ids("RFL-", 240, 5)
rfx_invitation_ids: List[str] = _ids("RFI-", 300, 5)
vendor_quote_ids: List[str] = _ids("VQT-", 200, 5)
vendor_quote_line_ids: List[str] = _ids("VQL-", 600, 5)
should_cost_ids: List[str] = _ids("SCM-", 120, 5)
sourcing_scenario_ids: List[str] = _ids("SCN-", 150, 5)
sourcing_award_ids: List[str] = _ids("AWD-", 50, 5)

OFFERING_TYPES: List[str] = ["Single_SKU", "Multi_SKU_Bundle", "Listing_Pack", "Promo_Pack"]
OFFERING_COMPONENT_ROLES: List[str] = ["Anchor", "Anchor", "Add_On", "Add_On", "Free_Good"]
QUOTE_STATUSES: List[str] = [
    "Draft", "Draft", "In_Review", "Approved", "Approved",
    "Won_Converted", "Won_Converted", "Rejected", "Expired",
]
PROMO_MECHANICS: List[str] = ["Discount", "BOGO", "Bundle", "Display", "Sampling"]
CONFIGURATION_RULE_TYPES: List[str] = [
    "Compatibility", "MOQ", "Pack_Config", "Exclusion",
    "Required_Together", "Channel_Eligibility", "Region_Restriction",
]
CONFIGURATION_RULE_SEVERITY: List[str] = ["Error", "Error", "Warning", "Info"]

RFX_TYPES: List[str] = ["RFI", "RFP", "RFQ", "RFQ", "Reverse_Auction"]
RFX_STATUSES: List[str] = [
    "Draft", "Published", "Bidding", "Bidding",
    "Evaluation", "Awarded", "Awarded", "Cancelled",
]
RFX_CATEGORIES: List[str] = ["Raw_Material", "Packaging", "Co_Packer", "Logistics", "Services", "Equipment"]
INCOTERMS: List[str] = ["FOB", "CIF", "DAP", "DDP", "EXW", "FCA"]
VENDOR_QUOTE_STATUSES: List[str] = [
    "Draft", "Submitted", "Submitted", "Under_Evaluation",
    "Awarded", "Rejected", "Withdrawn",
]
AWARD_STATUSES: List[str] = ["Pending_Approval", "Approved", "Approved", "Issued", "Cancelled"]
INVITATION_STATUSES: List[str] = ["Invited", "Accepted", "Submitted", "Submitted", "Declined", "Withdrawn"]


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


def pick(pool: List[str]) -> str:
    _ensure_seed()
    return random.choice(pool) if pool else ""
