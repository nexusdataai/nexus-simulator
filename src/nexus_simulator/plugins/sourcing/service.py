"""
Sourcing Simulator Service (Buy-Side / Sourcing CPQ).

Redis-backed FDW simulator hosting the Domain 14 (Sourcing RFx/Award)
virtual entities used by the Sourcing CPQ module. Joins existing SAP
(Vendor_Master, Source_List, Material_Master, Plant_Master) and Social
Listening (Commodity_Price) master data via shared ID pools.
"""

import json
import os
from typing import Any, Dict, List

from loguru import logger

from nexus_simulator.base.simulator import BaseSimulator as BaseSimulatorService

sim_logger = logger.bind(component="sourcing-simulator")


class SourcingSimulatorService(BaseSimulatorService):

    SERVICE_NAME = "sourcing"

    PRIORITY_TABLES = [
        "RFx_Event",
        "RFx_Line",
        "RFx_Invitation",
        "Vendor_Quote",
        "Vendor_Quote_Line",
        "Should_Cost_Model",
        "Sourcing_Scenario",
        "Sourcing_Award",
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
            self.bucket = config.sourcing_simulator_bucket
            self.prefix = self.prefix or config.sourcing_simulator_prefix
        except Exception:
            pass
        if not self.bucket:
            self.bucket = os.getenv("SOURCING_SIMULATOR_BUCKET", "")
        if not self.prefix:
            self.prefix = os.getenv("SOURCING_SIMULATOR_PREFIX", "sourcing-simulator")

    async def seed_data(self) -> Dict[str, Any]:
        """Generate synthetic Sourcing CPQ data and store in Redis."""
        import random as _r
        from nexus_simulator.plugins.supply_chain_seed_pools import (
            vendor_ids, material_ids, plant_ids,
            rfx_event_ids, rfx_line_ids, rfx_invitation_ids,
            vendor_quote_ids, vendor_quote_line_ids,
            should_cost_ids, sourcing_scenario_ids, sourcing_award_ids,
            commodity_codes,
            RFX_TYPES, RFX_STATUSES, RFX_CATEGORIES, INCOTERMS,
            VENDOR_QUOTE_STATUSES, AWARD_STATUSES, INVITATION_STATUSES,
            CURRENCIES,
            date_str, datetime_str, money, pct, pick,
        )

        _r.seed(42)
        sim_logger.info("Seeding Sourcing simulator data")

        SCHEMA = "sourcing_cpq"
        SERVER = "sourcing_simulator"
        data_map: Dict[str, List[dict]] = {}

        events: List[dict] = []
        for eid in rfx_event_ids:
            etype = pick(RFX_TYPES)
            category = pick(RFX_CATEGORIES)
            events.append({
                "Event_ID": eid,
                "Type": etype,
                "Buyer_Plant_ID": pick(plant_ids),
                "Category": category,
                "Status": pick(RFX_STATUSES),
                "Open_Date": date_str(120, 30),
                "Close_Date": date_str(0, 0),
                "Owner_ID": f"BUYER-{_r.randint(1, 15):03d}",
                "Title": f"{etype} for {category} {eid[-4:]}",
            })
        data_map["RFx_Event"] = events

        rfx_lines: List[dict] = []
        for lid in rfx_line_ids:
            rfx_lines.append({
                "Line_ID": lid,
                "Event_ID": pick(rfx_event_ids),
                "Material_ID": pick(material_ids) if _r.random() < 0.85 else "",
                "Service_Code": pick(commodity_codes) if _r.random() < 0.15 else "",
                "Qty_Target": _r.randint(500, 200_000),
                "Plant_ID": pick(plant_ids),
                "Required_Cert": ",".join(_r.sample(
                    ["ISO_9001", "FSSC_22000", "ISO_14001", "Organic", "Fair_Trade"],
                    k=_r.randint(0, 3),
                )),
                "Incoterm": pick(INCOTERMS),
                "Currency": pick(CURRENCIES),
            })
        data_map["RFx_Line"] = rfx_lines

        invitations: List[dict] = []
        for iid in rfx_invitation_ids:
            invitations.append({
                "Invitation_ID": iid,
                "Event_ID": pick(rfx_event_ids),
                "Vendor_ID": pick(vendor_ids),
                "Status": pick(INVITATION_STATUSES),
                "Invited_At": datetime_str(90, 5),
            })
        data_map["RFx_Invitation"] = invitations

        vendor_quotes: List[dict] = []
        for vqid in vendor_quote_ids:
            vendor_quotes.append({
                "Vendor_Quote_ID": vqid,
                "Event_ID": pick(rfx_event_ids),
                "Vendor_ID": pick(vendor_ids),
                "Submitted_At": datetime_str(60, 0),
                "Total_Value": money(10_000, 1_500_000),
                "Validity_Date": date_str(0, 0),
                "Status": pick(VENDOR_QUOTE_STATUSES),
            })
        data_map["Vendor_Quote"] = vendor_quotes

        vq_lines: List[dict] = []
        for lid in vendor_quote_line_ids:
            unit = money(0.5, 80)
            tiers = [
                {"qty_threshold": 500, "unit_price": round(unit, 2)},
                {"qty_threshold": 5000, "unit_price": round(unit * 0.93, 2)},
                {"qty_threshold": 25000, "unit_price": round(unit * 0.87, 2)},
            ]
            compliance: List[str] = []
            if _r.random() < 0.85:
                compliance.append("certs_met")
            if _r.random() < 0.7:
                compliance.append("incoterm_matched")
            if _r.random() < 0.6:
                compliance.append("payment_terms_met")
            vq_lines.append({
                "Line_ID": lid,
                "Vendor_Quote_ID": pick(vendor_quote_ids),
                "RFx_Line_ID": pick(rfx_line_ids),
                "Unit_Price": round(unit, 2),
                "Lead_Time_Days": _r.randint(7, 90),
                "MOQ": _r.randint(100, 5000),
                "Payment_Terms": pick(["Net_30", "Net_45", "Net_60", "Net_90"]),
                "Tiered_Pricing_JSON": json.dumps(tiers),
                "Compliance_Flags": ",".join(compliance),
            })
        data_map["Vendor_Quote_Line"] = vq_lines

        should_costs: List[dict] = []
        for sid in should_cost_ids:
            modeled = money(0.4, 60)
            should_costs.append({
                "Model_ID": sid,
                "Material_ID": pick(material_ids),
                "Commodity_Index_Refs": ",".join(_r.sample(commodity_codes, k=_r.randint(1, 3))),
                "Labor_Index": round(_r.uniform(0.8, 1.4), 3),
                "Overhead": round(_r.uniform(0.05, 4.0), 2),
                "Freight": round(_r.uniform(0.02, 2.5), 2),
                "Modeled_Cost": round(modeled, 2),
                "Confidence": round(_r.uniform(0.55, 0.95), 2),
                "Generated_At": datetime_str(60, 0),
            })
        data_map["Should_Cost_Model"] = should_costs

        scenarios: List[dict] = []
        scenario_names = ["Cost Optimal", "Risk Balanced", "Diversified", "Sustainability Priority"]
        for scid in sourcing_scenario_ids:
            n_splits = _r.randint(1, 4)
            splits: List[dict] = []
            remaining = 100
            for s in range(n_splits):
                share = remaining if s == n_splits - 1 else _r.randint(15, max(15, remaining - 15 * (n_splits - s - 1)))
                splits.append({
                    "vendor_id": pick(vendor_ids),
                    "qty_pct": share,
                    "unit_price": money(0.5, 60),
                    "plant_id": pick(plant_ids),
                })
                remaining -= share
            concentration = max((s["qty_pct"] for s in splits), default=100)
            scenarios.append({
                "Scenario_ID": scid,
                "Event_ID": pick(rfx_event_ids),
                "Name": pick(scenario_names),
                "Split_JSON": json.dumps(splits),
                "Modeled_Savings": round(_r.uniform(-2.0, 12.0), 2),
                "Modeled_Risk_Score": round(_r.uniform(15, 85), 1),
                "Concentration_Pct": concentration,
                "Generated_At": datetime_str(45, 0),
            })
        data_map["Sourcing_Scenario"] = scenarios

        awards: List[dict] = []
        for aid in sourcing_award_ids:
            status = pick(AWARD_STATUSES)
            chain = [
                {"role": "ProcurementManager", "status": "approved", "at": datetime_str(30, 0)},
            ]
            if status in ("Approved", "Issued"):
                chain.append({"role": "ProcurementDirector", "status": "approved", "at": datetime_str(20, 0)})
            awards.append({
                "Award_ID": aid,
                "Event_ID": pick(rfx_event_ids),
                "Scenario_ID": pick(sourcing_scenario_ids),
                "Status": status,
                "Approval_Chain_JSON": json.dumps(chain),
                "Approved_At": datetime_str(20, 0) if status in ("Approved", "Issued") else "",
                "Issued_At": datetime_str(10, 0) if status == "Issued" else "",
            })
        data_map["Sourcing_Award"] = awards

        try:
            from nexus_simulator.plugins.diagnostic_seed import apply_sentinels
            apply_sentinels("sourcing", data_map)
        except Exception:
            pass

        return await self._finalize_seed(SCHEMA, SERVER, data_map)
