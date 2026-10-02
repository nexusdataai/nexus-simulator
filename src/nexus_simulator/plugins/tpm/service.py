"""
TPM Simulator Service (Sell-Side / Trade CPQ).

Redis-backed FDW simulator hosting the Domain 13 (Commercial Configure/Quote)
virtual entities used by the Trade CPQ module. Joins existing Salesforce
(Account, Campaign) and SAP (Material_Master, Plant_Master, Cost_Accounting)
master data via shared ID pools.
"""

import json
import os
from typing import Any, Dict, List

from loguru import logger

from nexus_simulator.base.simulator import BaseSimulator as BaseSimulatorService

sim_logger = logger.bind(component="tpm-simulator")


class TPMSimulatorService(BaseSimulatorService):

    SERVICE_NAME = "tpm"

    PRIORITY_TABLES = [
        "Product_Offering",
        "Offering_Component",
        "Price_Book",
        "Price_Book_Entry",
        "Quote_Header",
        "Quote_Line",
        "Quote_Promotion",
        "Serviceability_Footprint",
        "Configuration_Rule",
    ]

    def __init__(self, bucket: str = "", prefix: str = ""):
        super().__init__(bucket, prefix)
        self._refresh_config()

    def _refresh_config(self):
        if self.bucket:
            return
        try:
            from src.config.config_provider import get_config
            config = get_config()
            self.bucket = config.tpm_simulator_bucket
            self.prefix = self.prefix or config.tpm_simulator_prefix
        except Exception:
            pass
        if not self.bucket:
            self.bucket = os.getenv("TPM_SIMULATOR_BUCKET", "")
        if not self.prefix:
            self.prefix = os.getenv("TPM_SIMULATOR_PREFIX", "tpm-simulator")

    async def seed_data(self) -> Dict[str, Any]:
        """Generate synthetic Trade CPQ data and store in Redis."""
        import random as _r
        from nexus_simulator.plugins.supply_chain_seed_pools import (
            account_ids, material_ids, plant_ids, campaign_ids,
            offering_ids, offering_component_ids,
            price_book_ids, price_book_entry_ids,
            quote_ids, quote_line_ids, quote_promotion_ids,
            serviceability_ids, configuration_rule_ids,
            OFFERING_TYPES, OFFERING_COMPONENT_ROLES,
            QUOTE_STATUSES, PROMO_MECHANICS,
            CONFIGURATION_RULE_TYPES, CONFIGURATION_RULE_SEVERITY,
            CHANNEL_TYPES, TIERS, REGIONS, CURRENCIES,
            date_str, datetime_str, money, pct, pick,
        )

        _r.seed(42)
        sim_logger.info("Seeding TPM simulator data")

        SCHEMA = "tpm_cpq"
        SERVER = "tpm_simulator"
        data_map: Dict[str, List[dict]] = {}

        offerings: List[dict] = []
        for oid in offering_ids:
            otype = pick(OFFERING_TYPES)
            offerings.append({
                "Offering_ID": oid,
                "Name": f"{pick(['Premium', 'Value', 'Family', 'Promo', 'HORECA'])} {otype} {oid[-4:]}",
                "Type": otype,
                "Channel_Eligibility": ",".join(_r.sample(CHANNEL_TYPES, k=_r.randint(1, 3))),
                "Region_Eligibility": ",".join(_r.sample(REGIONS, k=_r.randint(1, 3))),
                "Status": pick(["Draft", "Active", "Active", "Active", "Retired"]),
                "Owner_ID": f"USER-{_r.randint(1, 40):03d}",
                "Valid_From": date_str(365, 30),
                "Valid_To": date_str(0, 0),
            })
        data_map["Product_Offering"] = offerings

        offering_components: List[dict] = []
        for cid in offering_component_ids:
            offering_components.append({
                "Component_ID": cid,
                "Offering_ID": pick(offering_ids),
                "Material_ID": pick(material_ids),
                "Qty": _r.randint(1, 24),
                "Component_Role": pick(OFFERING_COMPONENT_ROLES),
                "Substitutable_Flag": _r.random() < 0.35,
            })
        data_map["Offering_Component"] = offering_components

        price_books: List[dict] = []
        for pbid in price_book_ids:
            channel = pick(CHANNEL_TYPES)
            tier = pick(TIERS + ["All"])
            price_books.append({
                "Price_Book_ID": pbid,
                "Name": f"{channel} {tier} Price Book {pbid[-3:]}",
                "Channel_Type": channel,
                "Tier": tier,
                "Region": pick(REGIONS),
                "Currency": pick(CURRENCIES),
                "Valid_From": date_str(365, 30),
                "Valid_To": date_str(0, 0),
                "Status": pick(["Draft", "Active", "Active", "Active", "Archived"]),
            })
        data_map["Price_Book"] = price_books

        price_book_entries: List[dict] = []
        for eid in price_book_entry_ids:
            list_price = money(2, 80)
            cost = round(list_price * _r.uniform(0.5, 0.78), 2)
            floor = round(cost * _r.uniform(1.18, 1.35), 2)
            price_book_entries.append({
                "Entry_ID": eid,
                "Price_Book_ID": pick(price_book_ids),
                "Offering_ID": pick(offering_ids),
                "List_Price": list_price,
                "Floor_Price": floor,
                "Cost_Snapshot": cost,
            })
        data_map["Price_Book_Entry"] = price_book_entries

        quotes: List[dict] = []
        for qid in quote_ids:
            status = pick(QUOTE_STATUSES)
            discount = round(_r.uniform(0, 28), 1)
            margin = round(_r.uniform(8, 38), 1)
            chain = []
            if status not in ("Draft",):
                chain.append({"role": "RegionalSalesManager", "status": "approved", "at": datetime_str(60, 0)})
            if discount > 18 or margin < 15:
                chain.append({"role": "CommercialDirector",
                              "status": "approved" if status in ("Approved", "Won_Converted") else "pending",
                              "at": datetime_str(45, 0)})
            if margin < 12:
                chain.append({"role": "CFO",
                              "status": "approved" if status == "Won_Converted" else "pending",
                              "at": datetime_str(30, 0)})
            quotes.append({
                "Quote_ID": qid,
                "Account_ID": pick(account_ids),
                "Owner_ID": f"USER-{_r.randint(1, 40):03d}",
                "Status": status,
                "Validity_Date": date_str(0, 0),
                "Total_Net": money(2_000, 250_000),
                "Margin_Pct": margin,
                "Discount_Pct": discount,
                "Approval_Chain_JSON": json.dumps(chain),
                "Created_At": datetime_str(90, 0),
                "Submitted_At": datetime_str(80, 0) if status != "Draft" else "",
            })
        data_map["Quote_Header"] = quotes

        quote_lines: List[dict] = []
        for lid in quote_line_ids:
            qty = _r.randint(50, 8000)
            list_price = money(2, 80)
            discount = round(_r.uniform(0, 28), 1)
            unit_price = round(list_price * (1 - discount / 100), 2)
            margin_line = round(_r.uniform(8, 38), 1)
            quote_lines.append({
                "Line_ID": lid,
                "Quote_ID": pick(quote_ids),
                "Offering_ID": pick(offering_ids),
                "Qty": qty,
                "Unit_Price": unit_price,
                "Discount_Pct": discount,
                "Promotion_ID": pick(quote_promotion_ids) if _r.random() < 0.4 else "",
                "Listing_Fee": money(0, 8_000) if _r.random() < 0.25 else 0,
                "Slotting_Fee": money(0, 25_000) if _r.random() < 0.15 else 0,
                "Margin_Pct_Line": margin_line,
            })
        data_map["Quote_Line"] = quote_lines

        promotions: List[dict] = []
        for pid in quote_promotion_ids:
            mechanic = pick(PROMO_MECHANICS)
            promotions.append({
                "Promo_ID": pid,
                "Quote_ID": pick(quote_ids),
                "Campaign_ID": pick(campaign_ids),
                "Mechanic": mechanic,
                "Value": round(_r.uniform(2, 20), 1) if mechanic == "Discount" else round(_r.uniform(0.5, 5), 1),
                "Stacking_Group": pick(["TIER_DISC", "CAMPAIGN_DISC", "BUNDLE", "VOLUME", "DISPLAY"]),
            })
        data_map["Quote_Promotion"] = promotions

        footprints: List[dict] = []
        for fid in serviceability_ids:
            footprints.append({
                "Footprint_ID": fid,
                "Plant_ID": pick(plant_ids),
                "Region": pick(REGIONS),
                "Channel_Type": pick(CHANNEL_TYPES),
                "SLA_Days": _r.randint(1, 7),
                "Min_Order_Qty": _r.randint(50, 1000),
            })
        data_map["Serviceability_Footprint"] = footprints

        rule_seeds = [
            ("Compatibility", "channel == 'HORECA' and pack_size in ('330ml','500ml')",
             "Error", "HORECA accepts single-serve packs only"),
            ("MOQ", "qty >= moq_for_channel(channel)",
             "Error", "Minimum order quantity per channel"),
            ("Pack_Config", "modern_trade_palletizable(pack_config)",
             "Error", "Modern Trade requires SSCC-palletizable pack"),
            ("Exclusion", "not (mechanic == 'BOGO' and stacking_group == 'TIER_DISC')",
             "Error", "BOGO cannot stack with tier discount"),
            ("Required_Together", "anchor_present(lines)",
             "Warning", "Bundle should contain at least one Anchor component"),
            ("Channel_Eligibility", "channel in offering.channel_eligibility",
             "Error", "Offering not eligible for this channel"),
            ("Region_Restriction", "region in offering.region_eligibility",
             "Warning", "Offering not configured for this region"),
        ]
        rules: List[dict] = []
        for idx, (rule_type, expr, severity, desc) in enumerate(rule_seeds):
            rules.append({
                "Rule_ID": f"CRL-{idx+1:04d}",
                "Type": rule_type,
                "Expression": expr,
                "Severity": severity,
                "Description": desc,
            })
        # pad to configuration_rule_ids count with derivatives
        used = len(rules)
        for idx in range(used, len(configuration_rule_ids)):
            base = rule_seeds[idx % len(rule_seeds)]
            rules.append({
                "Rule_ID": configuration_rule_ids[idx],
                "Type": base[0],
                "Expression": base[1],
                "Severity": pick(CONFIGURATION_RULE_SEVERITY),
                "Description": f"{base[3]} (variant {idx})",
            })
        data_map["Configuration_Rule"] = rules

        try:
            from nexus_simulator.plugins.diagnostic_seed import apply_sentinels
            apply_sentinels("tpm", data_map)
        except Exception:
            pass

        return await self._finalize_seed(SCHEMA, SERVER, data_map)
