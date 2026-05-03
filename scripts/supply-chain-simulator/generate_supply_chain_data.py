#!/usr/bin/env python3
"""
Supply Chain Simulator Data Generator

Generates realistic, cross-referenced synthetic data for all 40 tables
defined in supply-chain-schema.yaml, organized into per-system S3 layouts
for the Oracle ERP, SAP, and SFDC simulators.

Usage:
    # Local output (recommended for first run)
    python generate_supply_chain_data.py --local-dir ./supply-chain-dump --scale medium

    # Upload directly to S3
    python generate_supply_chain_data.py --s3-bucket my-bucket --scale medium

    # Small scale for quick testing
    python generate_supply_chain_data.py --local-dir ./supply-chain-dump --scale small
"""

import argparse
import hashlib
import json
import math
import os
import random
import string
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

SCALE_FACTORS = {
    "small": 0.2,
    "medium": 1.0,
    "large": 4.0,
}

SFDC_SCHEMA = "sfdc_itxp2dev"
SAP_SCHEMA = "sap_s4hana"
ORACLE_SCHEMA = "oracle_erp"

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

COMMODITY_NAMES = ["Sugar", "Aluminum", "PET_Resin", "Glass", "Citric_Acid", "CO2", "Natural_Flavors",
                   "Caffeine", "Water_Treatment", "Corrugated_Board"]

SOCIAL_PLATFORMS = ["Twitter", "Facebook", "Instagram", "LinkedIn", "Reddit", "TikTok"]
MARKET_EVENT_TYPES = ["Weather", "Geopolitical", "Regulatory", "Port_Disruption", "Strike",
                      "Raw_Material_Shortage", "Demand_Spike"]
SEVERITIES = ["Low", "Medium", "High", "Critical"]


def _uid() -> str:
    return str(uuid.uuid4())[:12]


def _date(start_days_ago: int = 365, end_days_ago: int = 0) -> str:
    delta = random.randint(end_days_ago, start_days_ago)
    return (datetime.now(timezone.utc) - timedelta(days=delta)).strftime("%Y-%m-%d")


def _datetime_str(start_days_ago: int = 365, end_days_ago: int = 0) -> str:
    delta = random.randint(end_days_ago, start_days_ago)
    dt = datetime.now(timezone.utc) - timedelta(days=delta, hours=random.randint(0, 23), minutes=random.randint(0, 59))
    return dt.isoformat()


def _money(low: float = 10, high: float = 10000) -> float:
    return round(random.uniform(low, high), 2)


def _pct(low: float = 0, high: float = 100) -> float:
    return round(random.uniform(low, high), 1)


def _gtin() -> str:
    return "".join(random.choices(string.digits, k=13))


def _gln() -> str:
    return "".join(random.choices(string.digits, k=13))


def _sscc() -> str:
    return "".join(random.choices(string.digits, k=18))


def _scaled(base: int, factor: float) -> int:
    return max(1, int(base * factor))


class SupplyChainDataGenerator:
    def __init__(self, scale: str = "medium", seed: int = 42):
        random.seed(seed)
        self.factor = SCALE_FACTORS.get(scale, 1.0)
        self.data: Dict[str, Dict[str, List[dict]]] = {
            "sfdc": {},
            "sap": {},
            "oracle": {},
            "other": {},
        }
        self._id_pools: Dict[str, List[str]] = {}

    def _pool(self, name: str) -> List[str]:
        return self._id_pools.get(name, [])

    def _pick(self, name: str) -> str:
        pool = self._id_pools.get(name, [])
        return random.choice(pool) if pool else _uid()

    def generate_all(self):
        self._gen_sfdc()
        self._gen_sap()
        self._gen_oracle()
        self._gen_other()

    # ─── SFDC Domain 1-2 ────────────────────────────────────────────────

    def _gen_sfdc(self):
        n_accounts = _scaled(200, self.factor)
        accounts = []
        account_ids = []
        for i in range(n_accounts):
            aid = f"ACC-{i+1:05d}"
            account_ids.append(aid)
            accounts.append({
                "Account_ID": aid,
                "Name": f"{random.choice(['ABC','XYZ','Global','Pacific','Metro','Star','Prime'])} {random.choice(['Foods','Beverages','Markets','Retail','Trading','Corp'])} {i+1}",
                "Channel_Type": random.choice(CHANNEL_TYPES),
                "Region": random.choice(REGIONS),
                "Tier": random.choice(TIERS),
                "Credit_Limit": _money(50000, 5000000),
                "Payment_Terms": random.choice(["Net 30", "Net 45", "Net 60", "Net 90"]),
                "Status": random.choice(ACCOUNT_STATUSES),
                "Owner_ID": f"USR-{random.randint(1,50):04d}",
            })
        self._id_pools["account"] = account_ids
        self.data["sfdc"]["Account"] = accounts

        n_contacts = _scaled(400, self.factor)
        contacts = []
        for i in range(n_contacts):
            contacts.append({
                "Contact_ID": f"CON-{i+1:05d}",
                "Account_ID": random.choice(account_ids),
                "Name": f"{random.choice(['John','Jane','Ali','Wei','Siti','Raj','Mei'])} {random.choice(['Smith','Lee','Ahmad','Chen','Kumar','Tan','Nguyen'])}",
                "Email": f"contact{i+1}@example.com",
                "Phone": f"+65{random.randint(80000000,99999999)}",
                "Role": random.choice(CONTACT_ROLES),
                "Primary_Flag": i % 3 == 0,
            })
        self.data["sfdc"]["Contact"] = contacts

        n_campaigns = _scaled(30, self.factor)
        campaigns = []
        for i in range(n_campaigns):
            start = _date(180, 30)
            campaigns.append({
                "Campaign_ID": f"CMP-{i+1:04d}",
                "Name": f"{random.choice(CAMPAIGN_TYPES)} Campaign Q{random.randint(1,4)} {2025+random.randint(0,1)}",
                "Type": random.choice(CAMPAIGN_TYPES),
                "Start_Date": start,
                "End_Date": (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=random.randint(14, 90))).strftime("%Y-%m-%d"),
                "Budget": _money(5000, 500000),
                "Target_Segment": random.choice(CHANNEL_TYPES),
                "Status": random.choice(["Planned", "Active", "Completed"]),
            })
        self.data["sfdc"]["Campaign"] = campaigns

        n_opps = _scaled(500, self.factor)
        opp_ids = []
        opps = []
        for i in range(n_opps):
            oid = f"OPP-{i+1:06d}"
            opp_ids.append(oid)
            opps.append({
                "Opportunity_ID": oid,
                "Account_ID": random.choice(account_ids),
                "Total_Value": _money(1000, 500000),
                "Stage": random.choice(OPP_STAGES),
                "Close_Date": _date(180, 0),
                "Delivery_Date": _date(90, 0),
                "Region": random.choice(REGIONS),
            })
        self._id_pools["opportunity"] = opp_ids
        self.data["sfdc"]["Opportunity"] = opps

        n_lines = _scaled(1500, self.factor)
        lines = []
        for i in range(n_lines):
            lines.append({
                "Line_ID": f"OLI-{i+1:06d}",
                "Opportunity_ID": random.choice(opp_ids),
                "Product_ID": self._pick("material"),
                "Quantity": random.randint(10, 5000),
                "Unit_Price": _money(0.50, 50),
                "Discount_Pct": _pct(0, 25),
                "Delivery_Priority": random.choice(DELIVERY_PRIORITIES),
            })
        self.data["sfdc"]["Opportunity_Line_Item"] = lines

        n_overrides = _scaled(500, self.factor)
        overrides = []
        for i in range(n_overrides):
            year = random.choice([2025, 2026])
            overrides.append({
                "Override_ID": f"FO-{i+1:05d}",
                "Product_ID": self._pick("material"),
                "Region": random.choice(REGIONS),
                "Period": f"{year}-W{random.randint(1,52):02d}",
                "Override_Qty": random.randint(100, 50000),
                "Justification": random.choice([
                    "Festive season expected uplift", "Trade promotion confirmed",
                    "New retailer onboarding", "Competitor stock-out in region",
                    "Weather-driven demand spike", "Historical pattern adjustment",
                ]),
                "Submitted_By": f"USR-{random.randint(1,50):04d}",
                "Status": random.choice(["Pending", "Approved", "Approved", "Approved", "Rejected"]),
            })
        self.data["sfdc"]["Forecast_Override"] = overrides

        n_leads = _scaled(100, self.factor)
        leads = []
        for i in range(n_leads):
            status = random.choice(["New", "Contacted", "Qualified", "Converted"])
            leads.append({
                "Lead_ID": f"LD-{i+1:05d}",
                "First_Name": f"Lead{i+1}", "Last_Name": f"Prospect{i+1}",
                "Company": f"Company {random.randint(1,200)}",
                "Email": f"lead{i+1}@prospect.com",
                "Phone": f"+65{random.randint(80000000, 99999999)}",
                "Status": status,
                "Lead_Source": random.choice(["Web", "Referral", "Trade_Show", "Cold_Call", "Partner"]),
                "Industry": random.choice(["Food_Beverage", "Retail", "HORECA", "Distribution"]),
                "Region": random.choice(REGIONS),
                "Annual_Revenue": _money(50000, 10000000),
                "Converted_Account_ID": random.choice(account_ids) if status == "Converted" and account_ids else "",
            })
        self.data["sfdc"]["Lead"] = leads

    # ─── SAP Domains 3-7 ────────────────────────────────────────────────

    def _gen_sap(self):
        self._gen_sap_plants()
        self._gen_sap_materials()
        self._gen_sap_inventory()
        self._gen_sap_production()
        self._gen_sap_procurement()
        self._gen_sap_logistics()

    def _gen_sap_plants(self):
        n_plants = _scaled(10, self.factor)
        plants = []
        plant_ids = []
        for i in range(n_plants):
            pid = f"PLT-{i+1:03d}"
            plant_ids.append(pid)
            plants.append({
                "Plant_ID": pid,
                "GLN": _gln(),
                "Name": f"{random.choice(['Alpha','Beta','Gamma','Delta','Omega'])} {random.choice(PLANT_TYPES).replace('_',' ')} {random.choice(CITIES)}",
                "Address": f"{random.randint(1,999)} Industrial Ave, {random.choice(CITIES)}",
                "Type": random.choice(PLANT_TYPES),
                "Location_Lat": round(random.uniform(-6, 15), 6),
                "Location_Long": round(random.uniform(100, 125), 6),
                "Capacity_Units_Per_Day": random.randint(5000, 100000),
                "Operating_Shifts": random.choice([1, 2, 3]),
                "Status": random.choice(["Active", "Active", "Active", "Under_Maintenance"]),
            })
        self._id_pools["plant"] = plant_ids
        self.data["sap"]["Plant_Master"] = plants

        n_storage = _scaled(40, self.factor)
        storage_locs = []
        storage_ids = []
        for i in range(n_storage):
            sid = f"SL-{i+1:04d}"
            storage_ids.append(sid)
            storage_locs.append({
                "Storage_Location_ID": sid,
                "Plant_ID": random.choice(plant_ids),
                "Type": random.choice(STORAGE_TYPES),
                "Capacity": random.randint(1000, 50000),
                "Temperature_Controlled": random.choice([True, False]),
            })
        self._id_pools["storage_location"] = storage_ids
        self.data["sap"]["Storage_Location"] = storage_locs

        n_lines = _scaled(25, self.factor)
        prod_lines = []
        line_ids = []
        for i in range(n_lines):
            lid = f"LINE-{i+1:03d}"
            line_ids.append(lid)
            prod_lines.append({
                "Line_ID": lid,
                "Plant_ID": random.choice(plant_ids),
                "Name": f"Line {i+1} - {random.choice(['Filling','Bottling','Canning','Mixing','Packaging'])}",
                "Technology": random.choice(["High Speed Fill", "Aseptic", "Hot Fill", "Cold Fill", "Dry Pack"]),
                "Capacity_Units_Per_Hour": random.randint(500, 10000),
                "Changeover_Time_Min": random.randint(15, 120),
                "OEE_Target": _pct(75, 95),
                "Status": random.choice(["Active", "Active", "Under_Maintenance"]),
            })
        self._id_pools["production_line"] = line_ids
        self.data["sap"]["Production_Line"] = prod_lines

    def _gen_sap_materials(self):
        plant_ids = self._pool("plant")
        n_materials = _scaled(300, self.factor)
        materials = []
        material_ids = []
        for i in range(n_materials):
            mid = f"MAT-{i+1:05d}"
            material_ids.append(mid)
            cat = random.choice(BEVERAGE_CATEGORIES)
            materials.append({
                "Material_ID": mid,
                "GTIN": _gtin(),
                "Description": f"{random.choice(BEVERAGE_BRANDS)} {cat} {random.choice(PACK_SIZES)}",
                "Category": cat,
                "Sub_Category": f"{cat}_Sub_{random.randint(1,5)}",
                "Brand": random.choice(BEVERAGE_BRANDS),
                "Pack_Size": random.choice(PACK_SIZES),
                "Pack_Config": random.choice(PACK_CONFIGS),
                "Unit_of_Measure": random.choice(["EA", "CS", "PAL"]),
                "Shelf_Life_Days": random.randint(90, 730),
                "Weight_KG": round(random.uniform(0.3, 15), 2),
                "Volume_L": round(random.uniform(0.33, 2), 2),
                "Status": random.choice(["Active", "Active", "Active", "Discontinued", "Seasonal", "New_Launch"]),
                "Recycled_Content_Pct": _pct(0, 100),
                "Recyclability_Score": round(random.uniform(1, 10), 1),
            })
        self._id_pools["material"] = material_ids
        self.data["sap"]["Material_Master"] = materials

        n_mp = _scaled(600, self.factor)
        mat_plants = []
        for i in range(n_mp):
            mat_plants.append({
                "Material_ID": random.choice(material_ids),
                "Plant_ID": random.choice(plant_ids),
                "MRP_Type": random.choice(["MRP", "Reorder_Point", "Forecast_Based"]),
                "Reorder_Point": random.randint(50, 5000),
                "Safety_Stock": random.randint(20, 2000),
                "Lead_Time_Days": random.randint(1, 30),
                "Lot_Size": random.randint(100, 10000),
                "Procurement_Type": random.choice(["In_House_Production", "External_Procurement"]),
                "ABC_Classification": random.choice(["A", "A", "B", "B", "C"]),
            })
        self.data["sap"]["Material_Plant"] = mat_plants

        n_ms = _scaled(900, self.factor)
        mat_storage = []
        for i in range(n_ms):
            mat_storage.append({
                "Material_ID": random.choice(material_ids),
                "Plant_ID": random.choice(plant_ids),
                "Storage_Location": self._pick("storage_location"),
                "Unrestricted_Stock": random.randint(0, 10000),
                "Blocked_Stock": random.randint(0, 500),
                "In_Quality_Stock": random.randint(0, 300),
            })
        self.data["sap"]["Material_Storage"] = mat_storage

        n_bom = _scaled(400, self.factor)
        boms = []
        for i in range(n_bom):
            fg = random.choice(material_ids)
            comp = random.choice(material_ids)
            while comp == fg:
                comp = random.choice(material_ids)
            boms.append({
                "BOM_ID": f"BOM-{i+1:05d}",
                "Finished_Material_ID": fg,
                "Component_Material_ID": comp,
                "Component_Qty": round(random.uniform(0.01, 50), 3),
                "Unit_of_Measure": random.choice(["KG", "L", "EA", "M"]),
                "Scrap_Pct": _pct(0, 10),
                "Valid_From": _date(365, 180),
                "Valid_To": _date(0, 0),
            })
        self.data["sap"]["Bill_of_Materials"] = boms

    def _gen_sap_inventory(self):
        material_ids = self._pool("material")
        plant_ids = self._pool("plant")

        n_prod = _scaled(500, self.factor)
        prod_orders = []
        prod_order_ids = []
        for i in range(n_prod):
            pid = f"PO-{i+1:06d}"
            prod_order_ids.append(pid)
            planned = random.randint(100, 10000)
            produced = int(planned * random.uniform(0.7, 1.05))
            prod_orders.append({
                "Order_ID": pid,
                "Material_ID": random.choice(material_ids),
                "Plant_ID": random.choice(plant_ids),
                "Qty_Planned": planned,
                "Qty_Produced": produced,
                "Qty_Scrapped": max(0, int(planned * random.uniform(0, 0.05))),
                "Production_Line": self._pick("production_line"),
                "Shift": random.choice(["Morning", "Afternoon", "Night"]),
                "Start_Date": _date(180, 30),
                "End_Date": _date(30, 0),
                "Status": random.choice(["Planned", "Released", "In_Progress", "Confirmed", "Closed"]),
                "Yield_Pct": _pct(85, 100),
            })
        self._id_pools["production_order"] = prod_order_ids
        self.data["sap"]["Production_Order"] = prod_orders

        n_batches = _scaled(800, self.factor)
        batches = []
        batch_ids = []
        for i in range(n_batches):
            bid = f"BAT-{i+1:06d}"
            batch_ids.append(bid)
            prod_date = _date(180, 10)
            shelf = random.randint(90, 730)
            batches.append({
                "Batch_ID": bid,
                "Material_ID": random.choice(material_ids),
                "Production_Date": prod_date,
                "Expiry_Date": (datetime.strptime(prod_date, "%Y-%m-%d") + timedelta(days=shelf)).strftime("%Y-%m-%d"),
                "Shelf_Life_Remaining_Days": random.randint(10, shelf),
                "Status": random.choice(["Unrestricted", "Unrestricted", "Unrestricted", "Restricted", "Blocked", "In_Quality"]),
                "Production_Order_ID": random.choice(prod_order_ids) if prod_order_ids else _uid(),
                "Plant_ID": random.choice(plant_ids),
            })
        self._id_pools["batch"] = batch_ids
        self.data["sap"]["Batch_Master"] = batches

        n_inv = _scaled(1200, self.factor)
        inv_positions = []
        for i in range(n_inv):
            inv_positions.append({
                "Material_ID": random.choice(material_ids),
                "Plant_ID": random.choice(plant_ids),
                "Storage_Location": self._pick("storage_location"),
                "Batch_ID": random.choice(batch_ids) if batch_ids else _uid(),
                "Unrestricted_Qty": random.randint(0, 10000),
                "Reserved_Qty": random.randint(0, 2000),
                "In_Transit_Qty": random.randint(0, 1000),
                "Blocked_Qty": random.randint(0, 500),
                "Valuation_Price": _money(0.50, 100),
                "Last_Count_Date": _date(60, 0),
            })
        self.data["sap"]["Inventory_Position"] = inv_positions

        n_transfers = _scaled(200, self.factor)
        transfers = []
        for i in range(n_transfers):
            from_p = random.choice(plant_ids)
            to_p = random.choice(plant_ids)
            while to_p == from_p and len(plant_ids) > 1:
                to_p = random.choice(plant_ids)
            transfers.append({
                "Transfer_ID": f"WT-{i+1:05d}",
                "From_Plant": from_p,
                "To_Plant": to_p,
                "Material_ID": random.choice(material_ids),
                "Batch_ID": random.choice(batch_ids) if batch_ids else _uid(),
                "Qty": random.randint(50, 5000),
                "Status": random.choice(["Planned", "Approved", "In_Transit", "Received", "Cancelled"]),
                "Ship_Date": _date(60, 10),
                "ETA": _date(10, 0),
            })
        self.data["sap"]["Warehouse_Transfer"] = transfers

    def _gen_sap_production(self):
        batch_ids = self._pool("batch")

        n_qil = _scaled(300, self.factor)
        inspections = []
        inspection_ids = []
        for i in range(n_qil):
            iid = f"QIL-{i+1:05d}"
            inspection_ids.append(iid)
            tc = random.randint(3, 20)
            pc = random.randint(int(tc * 0.7), tc)
            inspections.append({
                "Inspection_ID": iid,
                "Batch_ID": random.choice(batch_ids) if batch_ids else _uid(),
                "Material_ID": self._pick("material"),
                "Inspection_Type": random.choice(["In_Process", "Final", "Incoming_Material", "Stability"]),
                "Test_Count": tc,
                "Pass_Count": pc,
                "Fail_Count": tc - pc,
                "Result": random.choice(["Accepted", "Accepted", "Accepted", "Rejected", "Conditionally_Accepted"]),
                "Inspector_ID": f"INS-{random.randint(1,20):03d}",
                "Date": _date(90, 0),
            })
        self._id_pools["inspection"] = inspection_ids
        self.data["sap"]["Quality_Inspection_Lot"] = inspections

        n_qtr = _scaled(900, self.factor)
        test_results = []
        test_names = ["Brix", "pH", "Carbonation", "Color", "Viscosity", "Microbial", "Heavy_Metals", "Turbidity", "Dissolved_O2", "Fill_Volume"]
        for i in range(n_qtr):
            lower = round(random.uniform(0, 50), 2)
            upper = round(lower + random.uniform(1, 20), 2)
            measured = round(random.uniform(lower - 2, upper + 2), 2)
            test_results.append({
                "Result_ID": f"QTR-{i+1:06d}",
                "Inspection_ID": random.choice(inspection_ids) if inspection_ids else _uid(),
                "Test_Name": random.choice(test_names),
                "Measured_Value": measured,
                "Unit": random.choice(["mg/L", "ppm", "NTU", "°Bx", "pH", "CFU/mL", "mL"]),
                "Spec_Lower_Limit": lower,
                "Spec_Upper_Limit": upper,
                "Pass_Flag": lower <= measured <= upper,
            })
        self.data["sap"]["Quality_Test_Result"] = test_results

    def _gen_sap_procurement(self):
        material_ids = self._pool("material")
        plant_ids = self._pool("plant")

        n_vendors = _scaled(80, self.factor)
        vendors = []
        vendor_ids = []
        for i in range(n_vendors):
            vid = f"VND-{i+1:04d}"
            vendor_ids.append(vid)
            vendors.append({
                "Vendor_ID": vid,
                "Name": f"{random.choice(['Apex','Global','Premier','United','Pacific','Oriental'])} {random.choice(['Ingredients','Packaging','Logistics','Materials','Supplies'])} {random.choice(['Pte Ltd','Co','Corp','GmbH','Inc'])}",
                "Country": random.choice(COUNTRIES),
                "City": random.choice(CITIES),
                "Category": random.choice(VENDOR_CATEGORIES),
                "Lead_Time_Days": random.randint(2, 45),
                "Payment_Terms": random.choice(["Net 30", "Net 45", "Net 60"]),
                "Risk_Rating": round(random.uniform(1, 10), 1),
                "Status": random.choice(["Active", "Active", "Active", "Probation", "Suspended"]),
                "Certification": random.choice(["ISO_9001", "FSSC_22000", "ISO_14001", "GMP", "HACCP", "None"]),
            })
        self._id_pools["vendor"] = vendor_ids
        self.data["sap"]["Vendor_Master"] = vendors

        n_sl = _scaled(200, self.factor)
        source_lists = []
        for i in range(n_sl):
            source_lists.append({
                "Source_ID": f"SRC-{i+1:05d}",
                "Material_ID": random.choice(material_ids),
                "Vendor_ID": random.choice(vendor_ids),
                "Valid_From": _date(365, 180),
                "Valid_To": _date(0, 0),
                "Priority": random.choice(["Primary", "Primary", "Secondary", "Emergency"]),
                "Fixed_Vendor_Flag": random.choice([True, False]),
            })
        self.data["sap"]["Source_List"] = source_lists

        n_pr = _scaled(300, self.factor)
        purchase_reqs = []
        for i in range(n_pr):
            purchase_reqs.append({
                "Requisition_ID": f"PR-{i+1:05d}",
                "Material_ID": random.choice(material_ids),
                "Qty": random.randint(50, 10000),
                "Plant_ID": random.choice(plant_ids),
                "Requested_By": f"USR-{random.randint(1,50):04d}",
                "Delivery_Date": _date(60, 0),
                "Status": random.choice(["Open", "Approved", "Converted_to_PO", "Rejected"]),
            })
        self.data["sap"]["Purchase_Requisition"] = purchase_reqs

    def _gen_sap_logistics(self):
        account_ids = self._pool("account")
        material_ids = self._pool("material")
        batch_ids = self._pool("batch")
        opp_ids = self._pool("opportunity")

        n_del = _scaled(600, self.factor)
        deliveries = []
        delivery_ids = []
        for i in range(n_del):
            did = f"DEL-{i+1:06d}"
            delivery_ids.append(did)
            deliveries.append({
                "Delivery_ID": did,
                "Sales_Order_ID": random.choice(opp_ids) if opp_ids else _uid(),
                "Ship_To_Account_ID": random.choice(account_ids) if account_ids else _uid(),
                "Material_ID": random.choice(material_ids),
                "Batch_ID": random.choice(batch_ids) if batch_ids else _uid(),
                "Qty": random.randint(10, 5000),
                "Ship_Date": _date(120, 10),
                "Planned_Arrival": _date(10, 0),
                "Actual_Arrival": _date(10, 0) if random.random() > 0.2 else None,
                "Carrier": random.choice(["DHL", "FedEx", "TNT", "Maersk", "Local Fleet", "Third Party"]),
                "POD_Status": random.choice(["Pending", "Signed", "Signed", "Signed", "Disputed", "Not_Delivered"]),
                "SSCC": _sscc(),
            })
        self._id_pools["delivery"] = delivery_ids
        self.data["sap"]["Delivery_Document"] = deliveries

        n_ship = _scaled(300, self.factor)
        shipments = []
        shipment_ids = []
        for i in range(n_ship):
            sid = f"SHP-{i+1:05d}"
            shipment_ids.append(sid)
            shipments.append({
                "Shipment_ID": sid,
                "Route": f"Route-{random.choice(CITIES)}-{random.choice(CITIES)}",
                "Vehicle_ID": f"VEH-{random.randint(1,100):03d}",
                "Driver": f"Driver-{random.randint(1,50):03d}",
                "Load_Weight_KG": round(random.uniform(500, 25000), 1),
                "Departure_Time": _datetime_str(60, 5),
                "Arrival_Time": _datetime_str(5, 0),
                "Status": random.choice(["Loading", "In_Transit", "Delivered", "Delayed"]),
                "Cost": _money(200, 15000),
            })
        self._id_pools["shipment"] = shipment_ids
        self.data["sap"]["Shipment"] = shipments

        n_returns = _scaled(100, self.factor)
        returns = []
        for i in range(n_returns):
            returns.append({
                "Return_ID": f"RET-{i+1:05d}",
                "Delivery_ID": random.choice(delivery_ids) if delivery_ids else _uid(),
                "Material_ID": random.choice(material_ids),
                "Qty": random.randint(1, 500),
                "Return_Reason": random.choice(["Damaged", "Expired", "Wrong_Item", "Overstock", "Quality_Issue"]),
                "Condition": random.choice(["Resaleable", "Damaged", "Expired", "Contaminated"]),
                "Disposition": random.choice(["Restock", "Destroy", "Rework", "Donate", "Vendor_Return"]),
                "Credit_Note_ID": f"CN-{i+1:05d}",
            })
        self.data["sap"]["Return_Order"] = returns

        po_ids = self._pool("oracle_po")
        n_grn = _scaled(400, self.factor)
        goods_receipts = []
        for i in range(n_grn):
            qty_ord = random.randint(100, 10000)
            qty_recv = int(qty_ord * random.uniform(0.9, 1.0))
            goods_receipts.append({
                "GRN_ID": f"GRN-{i+1:05d}",
                "PO_ID": random.choice(po_ids) if po_ids else f"PO-{random.randint(1,500):06d}",
                "Material_ID": random.choice(material_ids),
                "Vendor_ID": self._pick("vendor"),
                "Qty_Ordered": qty_ord,
                "Qty_Received": qty_recv,
                "Qty_Rejected": max(0, random.randint(0, int(qty_ord * 0.03))),
                "Receipt_Date": _date(90, 0),
                "Quality_Check_Status": random.choice(["Pending", "Passed", "Passed", "Passed", "Failed", "Waived"]),
            })
        self.data["sap"]["Goods_Receipt"] = goods_receipts

        material_ids = self._pool("material")
        n_pi = _scaled(200, self.factor)
        price_items = []
        for i in range(n_pi):
            price_items.append({
                "Price_Item_ID": f"PI-{i+1:05d}",
                "Product_ID": random.choice(material_ids) if material_ids else _uid(),
                "Price_Type": random.choice(["List", "Contract", "Promo", "Volume_Discount"]),
                "Unit_Price": _money(0.5, 100),
                "Currency": random.choice(CURRENCIES),
                "Valid_From": _date(365, 180),
                "Valid_To": _date(180, 0),
                "Volume_Min": random.randint(0, 100),
                "Volume_Max": random.randint(1000, 50000),
                "Discount_Pct": round(random.uniform(0, 25), 1),
                "Region": random.choice(REGIONS),
            })
        self.data["sap"]["cspmb__Price_Item__c"] = price_items

    # ─── Oracle Domains 8-9 ─────────────────────────────────────────────

    def _gen_oracle(self):
        self._gen_oracle_po_first()
        self._gen_oracle_finance()
        self._gen_oracle_operations()

    def _gen_oracle_po_first(self):
        vendor_ids = self._pool("vendor")
        material_ids = self._pool("material")
        plant_ids = self._pool("plant")

        n_po = _scaled(500, self.factor)
        pos = []
        po_ids = []
        for i in range(n_po):
            pid = f"OPO-{i+1:06d}"
            po_ids.append(pid)
            qty = random.randint(100, 20000)
            up = _money(0.5, 100)
            pos.append({
                "PO_ID": pid,
                "Vendor_ID": random.choice(vendor_ids) if vendor_ids else _uid(),
                "Material_ID": random.choice(material_ids) if material_ids else _uid(),
                "Plant_ID": random.choice(plant_ids) if plant_ids else _uid(),
                "Qty": qty,
                "Unit_Price": up,
                "Total_Amount": round(qty * up, 2),
                "Delivery_Date": _date(90, 0),
                "Status": random.choice(["Draft", "Approved", "Sent", "Partially_Received", "Fully_Received", "Closed"]),
                "Contract_ID": f"CTR-{random.randint(1,50):03d}",
            })
        self._id_pools["oracle_po"] = po_ids
        self.data["oracle"]["Oracle_Purchase_Order"] = pos

    def _gen_oracle_finance(self):
        account_ids = self._pool("account")
        delivery_ids = self._pool("delivery")

        n_cust = len(account_ids) if account_ids else _scaled(200, self.factor)
        customers = []
        customer_ids = []
        for i in range(n_cust):
            cid = account_ids[i] if i < len(account_ids) else f"CUST-{i+1:05d}"
            customer_ids.append(cid)
            customers.append({
                "Customer_ID": cid,
                "Customer_Name": f"Customer {cid}",
                "Credit_Limit": _money(50000, 5000000),
                "AR_Balance": _money(0, 500000),
                "Collection_Priority": random.choice(["High", "Medium", "Low"]),
                "Payment_Terms": random.choice(["Net 30", "Net 45", "Net 60", "Net 90"]),
                "Currency": random.choice(CURRENCIES[:3]),
                "Status": random.choice(["Active", "Active", "Active", "On_Hold", "Inactive"]),
            })
        self._id_pools["oracle_customer"] = customer_ids
        self.data["oracle"]["Oracle_AR_Customer"] = customers

        n_inv = _scaled(800, self.factor)
        invoices = []
        invoice_ids = []
        for i in range(n_inv):
            iid = f"INV-{i+1:06d}"
            invoice_ids.append(iid)
            amt = _money(100, 200000)
            invoices.append({
                "Invoice_ID": iid,
                "Customer_ID": random.choice(customer_ids),
                "Linked_Delivery_ID": random.choice(delivery_ids) if delivery_ids else _uid(),
                "Invoice_Date": _date(180, 10),
                "Due_Date": _date(60, 0),
                "Total_Amount": amt,
                "Tax_Amount": round(amt * random.uniform(0.05, 0.12), 2),
                "Status": random.choice(["Open", "Partially_Paid", "Paid", "Paid", "Overdue", "Disputed", "Written_Off"]),
            })
        self._id_pools["ar_invoice"] = invoice_ids
        self.data["oracle"]["Oracle_AR_Invoice"] = invoices

        n_pay = _scaled(600, self.factor)
        payments = []
        for i in range(n_pay):
            payments.append({
                "Payment_ID": f"PAY-{i+1:06d}",
                "Invoice_ID": random.choice(invoice_ids),
                "Customer_ID": random.choice(customer_ids),
                "Amount": _money(100, 200000),
                "Payment_Date": _date(120, 0),
                "Payment_Method": random.choice(["Bank_Transfer", "Check", "Wire", "ACH", "Credit_Card"]),
                "Applied_Flag": random.choice([True, True, True, False]),
            })
        self.data["oracle"]["Oracle_AR_Payment"] = payments

        n_cn = _scaled(80, self.factor)
        credit_notes = []
        for i in range(n_cn):
            credit_notes.append({
                "Credit_Note_ID": f"CN-{i+1:05d}",
                "Customer_ID": random.choice(customer_ids),
                "Invoice_ID": random.choice(invoice_ids),
                "Amount": _money(50, 50000),
                "Reason": random.choice(["Return", "Price_Adjustment", "Dispute_Resolution", "Damaged_Goods", "Promotional_Credit"]),
                "Status": random.choice(["Open", "Applied", "Closed"]),
                "Approval_Status": random.choice(["Pending", "Approved", "Rejected"]),
            })
        self.data["oracle"]["Oracle_AR_Credit_Note"] = credit_notes

        n_journals = _scaled(500, self.factor)
        journals = []
        for i in range(n_journals):
            amt = _money(100, 500000)
            journals.append({
                "Journal_ID": f"JRN-{i+1:06d}",
                "Period_Name": f"2025-{random.randint(1,12):02d}",
                "Journal_Status": random.choice(["Posted", "Posted", "Unposted", "Reversed"]),
                "Debit_Amount": amt if random.random() > 0.5 else 0,
                "Credit_Amount": amt if random.random() <= 0.5 else 0,
                "Account_Code": f"{random.randint(1000,9999)}-{random.randint(100,999)}",
                "Description": random.choice(["Revenue recognition", "COGS entry", "Depreciation", "Salary accrual", "Inventory adjustment", "Tax provision"]),
                "Source_Module": random.choice(["AR", "AP", "GL", "FA", "INV"]),
            })
        self.data["oracle"]["Oracle_GL_Journal"] = journals

        periods = []
        for year in [2024, 2025]:
            for month in range(1, 13):
                periods.append({
                    "Period_ID": f"PER-{year}-{month:02d}",
                    "Period_Name": f"{year}-{month:02d}",
                    "Year": year,
                    "Status": "Closed" if (year == 2024 or month < datetime.now().month - 1) else "Open",
                    "Close_Date": f"{year}-{month:02d}-{28}" if year == 2024 else None,
                })
        self.data["oracle"]["Oracle_GL_Period"] = periods

    def _gen_oracle_operations(self):
        po_ids = self._pool("oracle_po")
        vendor_ids = self._pool("vendor")
        material_ids = self._pool("material")
        plant_ids = self._pool("plant")

        n_ap_inv = _scaled(400, self.factor)
        ap_invoices = []
        ap_invoice_ids = []
        for i in range(n_ap_inv):
            aid = f"API-{i+1:06d}"
            ap_invoice_ids.append(aid)
            amt = _money(100, 200000)
            ap_invoices.append({
                "Invoice_ID": aid,
                "Vendor_ID": random.choice(vendor_ids) if vendor_ids else _uid(),
                "PO_ID": random.choice(po_ids) if po_ids else _uid(),
                "Invoice_Date": _date(180, 10),
                "Due_Date": _date(60, 0),
                "Total_Amount": amt,
                "Tax_Amount": round(amt * random.uniform(0.05, 0.12), 2),
                "Status": random.choice(["Pending", "Validated", "Approved", "Paid", "On_Hold", "Disputed"]),
                "Three_Way_Match_Status": random.choice(["Matched", "Matched", "Qty_Mismatch", "Price_Mismatch", "GRN_Missing", "Under_Review"]),
            })
        self._id_pools["ap_invoice"] = ap_invoice_ids
        self.data["oracle"]["Oracle_AP_Invoice"] = ap_invoices

        n_ap_pay = _scaled(350, self.factor)
        ap_payments = []
        for i in range(n_ap_pay):
            ap_payments.append({
                "Payment_ID": f"APP-{i+1:06d}",
                "Invoice_ID": random.choice(ap_invoice_ids),
                "Vendor_ID": random.choice(vendor_ids) if vendor_ids else _uid(),
                "Amount": _money(100, 200000),
                "Payment_Date": _date(120, 0),
                "Payment_Method": random.choice(["Bank_Transfer", "Check", "Wire", "ACH"]),
                "Check_Number": f"CHK-{random.randint(10000,99999)}" if random.random() > 0.7 else None,
                "Bank_Account": f"BA-{random.randint(1,5):02d}",
            })
        self.data["oracle"]["Oracle_AP_Payment"] = ap_payments

        n_cost = _scaled(300, self.factor)
        costs = []
        for i in range(n_cost):
            mc = _money(0.10, 20)
            lc = _money(0.05, 5)
            oc = _money(0.02, 3)
            fc = _money(0.01, 2)
            costs.append({
                "Cost_ID": f"CST-{i+1:05d}",
                "Material_ID": random.choice(material_ids) if material_ids else _uid(),
                "Plant_ID": random.choice(plant_ids) if plant_ids else _uid(),
                "Cost_Type": random.choice(["Standard", "Actual"]),
                "Material_Cost": mc,
                "Labor_Cost": lc,
                "Overhead_Cost": oc,
                "Freight_Cost": fc,
                "Total_Unit_Cost": round(mc + lc + oc + fc, 2),
                "Period": f"2025-{random.randint(1,12):02d}",
            })
        self.data["oracle"]["Oracle_Cost_Accounting"] = costs

        n_assets = _scaled(50, self.factor)
        assets = []
        for i in range(n_assets):
            acq_cost = _money(10000, 5000000)
            assets.append({
                "Asset_ID": f"AST-{i+1:04d}",
                "Name": f"{random.choice(ASSET_CATEGORIES).replace('_',' ')} Unit {i+1}",
                "Category": random.choice(ASSET_CATEGORIES),
                "Plant_ID": random.choice(plant_ids) if plant_ids else _uid(),
                "Acquisition_Date": _date(1825, 30),
                "Acquisition_Cost": acq_cost,
                "Net_Book_Value": round(acq_cost * random.uniform(0.1, 0.9), 2),
                "Depreciation_Method": random.choice(["Straight_Line", "Declining_Balance", "Units_of_Production"]),
                "Status": random.choice(["In_Service", "In_Service", "In_Service", "Under_Maintenance", "Retired"]),
            })
        self.data["oracle"]["Oracle_Fixed_Asset"] = assets

        n_budgets = _scaled(40, self.factor)
        budgets = []
        for i in range(n_budgets):
            planned = _money(50000, 5000000)
            actual = round(planned * random.uniform(0.7, 1.3), 2)
            variance = round(actual - planned, 2)
            budgets.append({
                "Budget_ID": f"BUD-{i+1:04d}",
                "Cost_Center": random.choice(COST_CENTERS),
                "Period": f"2025-Q{random.randint(1,4)}",
                "Category": random.choice(BUDGET_CATEGORIES),
                "Planned_Amount": planned,
                "Actual_Amount": actual,
                "Variance_Amount": variance,
                "Variance_Pct": round((variance / planned) * 100, 1) if planned else 0,
            })
        self.data["oracle"]["Oracle_Budget"] = budgets

        material_ids = self._pool("material")
        products = []
        for mid in material_ids:
            products.append({
                "Product_ID": mid,
                "Product_Name": f"Product {mid[-5:]}",
                "Category": random.choice(BEVERAGE_CATEGORIES),
                "Unit_Cost": _money(0.3, 30),
                "List_Price": _money(0.5, 50),
                "Status": random.choice(["Active", "Active", "Active", "Discontinued"]),
                "Weight_KG": round(random.uniform(0.1, 25), 2),
                "Volume_Unit": random.choice(PACK_SIZES[:5]),
                "Tax_Code": random.choice(["GST_7", "GST_0", "EXEMPT"]),
            })
        self.data["oracle"]["Oracle_Product_Master"] = products

    # ─── Other Sources (Domains 10-12) ──────────────────────────────────

    def _gen_other(self):
        vendor_ids = self._pool("vendor")
        material_ids = self._pool("material")
        batch_ids = self._pool("batch")

        n_contracts = _scaled(50, self.factor)
        contracts = []
        for i in range(n_contracts):
            contracts.append({
                "Contract_ID": f"CTR-{i+1:03d}",
                "Vendor_ID": random.choice(vendor_ids) if vendor_ids else _uid(),
                "Document_Path": f"/contracts/vendor_{i+1}_agreement.pdf",
                "Effective_Date": _date(365, 60),
                "Expiry_Date": _date(0, 0),
                "Contracted_Price": _money(0.50, 100),
                "Volume_Commitment": random.randint(1000, 100000),
                "SLA_Terms": random.choice(["99% on-time delivery", "48h response time", "95% fill rate", "Zero defect policy"]),
                "Penalty_Clauses": random.choice(["2% per late day", "5% quality rebate", "Volume shortfall penalty", "None"]),
                "Auto_Renewal": random.choice([True, False]),
                "Extraction_Confidence": _pct(70, 99),
            })
        self.data["other"]["Contract_Document"] = contracts

        n_sust = _scaled(20, self.factor)
        sust_reports = []
        for i in range(n_sust):
            sust_reports.append({
                "Report_ID": f"SR-{i+1:03d}",
                "Document_Path": f"/sustainability/report_{i+1}.pdf",
                "Report_Type": random.choice(["Annual_Sustainability", "Carbon_Audit", "Water_Audit", "Packaging_Report"]),
                "Period": f"2025-Q{random.randint(1,4)}",
                "KPIs_Extracted": random.choice(["CO2 emissions, Water usage, Recycling rate", "Energy consumption, Waste reduction"]),
                "Targets": random.choice(["30% reduction by 2030", "Carbon neutral by 2035", "100% recyclable packaging"]),
                "Actuals": random.choice(["18% reduction achieved", "45% renewable energy", "72% recyclable packaging"]),
                "Framework": random.choice(["GRI", "SASB", "CDP", "TCFD"]),
            })
        self.data["other"]["Sustainability_Report"] = sust_reports

        n_signals = _scaled(200, self.factor)
        signals = []
        for i in range(n_signals):
            signals.append({
                "Signal_ID": f"MS-{i+1:05d}",
                "Source": random.choice(["News_Feed", "Social_Media", "Government", "Weather_Service", "Industry_Report"]),
                "Event_Type": random.choice(MARKET_EVENT_TYPES + ["Demand_Spike", "Competitor_Action"]),
                "Location": random.choice(COUNTRIES),
                "Affected_Commodity": random.choice(COMMODITY_NAMES),
                "Severity": random.choice(SEVERITIES),
                "Timestamp": _datetime_str(365, 0),
            })
        self.data["other"]["Market_Signal"] = signals

        n_sentiment = _scaled(200, self.factor)
        sentiments = []
        for i in range(n_sentiment):
            sentiments.append({
                "Sentiment_ID": f"BS-{i+1:05d}",
                "Brand": random.choice(BEVERAGE_BRANDS),
                "Product_Category": random.choice(BEVERAGE_CATEGORIES),
                "Topic": random.choice(["Taste", "Packaging", "Price", "Availability", "Sustainability", "Health"]),
                "Platform": random.choice(SOCIAL_PLATFORMS),
                "Sentiment_Score": round(random.uniform(-1, 1), 3),
                "Mention_Count": random.randint(10, 50000),
                "Period": f"2025-W{random.randint(1,52):02d}",
            })
        self.data["other"]["Brand_Sentiment"] = sentiments

        n_prices = _scaled(100, self.factor)
        prices = []
        for i in range(n_prices):
            prices.append({
                "Price_ID": f"CP-{i+1:05d}",
                "Commodity": random.choice(COMMODITY_NAMES),
                "Price_Per_Unit": _money(0.10, 500),
                "Currency": random.choice(["USD", "SGD"]),
                "Unit": random.choice(["KG", "MT", "L", "EA"]),
                "Date": _date(180, 0),
                "Source": random.choice(["Bloomberg", "Reuters", "ICIS", "Platts", "Internal"]),
                "Change_Pct_30D": round(random.uniform(-15, 15), 1),
            })
        self.data["other"]["Commodity_Price"] = prices

        n_uploads = _scaled(50, self.factor)
        inv_uploads = []
        for i in range(n_uploads):
            inv_uploads.append({
                "Upload_ID": f"IU-{i+1:04d}",
                "File_Path": f"/uploads/invoices/invoice_{i+1}.pdf",
                "Vendor_Name_Extracted": f"Vendor {random.randint(1,80)}",
                "Invoice_Number_Extracted": f"EXT-INV-{random.randint(10000,99999)}",
                "Amount_Extracted": _money(100, 200000),
                "Line_Items": f"{random.randint(1,20)} items extracted",
                "Extraction_Confidence": _pct(60, 99),
                "Matched_PO_ID": self._pick("oracle_po"),
                "Validation_Status": random.choice(["Pending", "Validated", "Rejected", "Manual_Review"]),
            })
        self.data["other"]["Invoice_Upload"] = inv_uploads

        n_labs = _scaled(30, self.factor)
        lab_reports = []
        for i in range(n_labs):
            lab_reports.append({
                "Upload_ID": f"LR-{i+1:04d}",
                "File_Path": f"/uploads/lab_reports/lab_{i+1}.pdf",
                "Material_ID": random.choice(material_ids) if material_ids else _uid(),
                "Batch_ID": random.choice(batch_ids) if batch_ids else _uid(),
                "Tests_Extracted": f"{random.randint(3,15)} tests",
                "Results": random.choice(["All pass", "2 deviations noted", "1 failure - microbial", "All within spec"]),
                "Spec_Compliance": random.choice([True, True, True, False]),
                "Extraction_Confidence": _pct(65, 99),
                "Inspector_Name": f"Inspector {random.randint(1,20)}",
            })
        self.data["other"]["Lab_Report_Upload"] = lab_reports

        n_cv = _scaled(60, self.factor)
        doc_ids = [f"DOC-{i+1:04d}" for i in range(n_cv)]
        content_versions = []
        for i, did in enumerate(doc_ids):
            content_versions.append({
                "ContentVersion_ID": f"CV-{i+1:04d}",
                "Document_ID": did,
                "Title": random.choice([f"Vendor Contract {i+1}", f"Sustainability Report Q{random.randint(1,4)}", f"Invoice Scan {i+1}", f"Lab Certificate {i+1}", f"SLA Agreement {i+1}"]),
                "File_Type": random.choice(["pdf", "xlsx", "docx", "pdf", "pdf"]),
                "Version_Number": random.randint(1, 5),
                "Created_Date": _date(365, 0),
                "File_Size_KB": random.randint(50, 5000),
                "Description": random.choice(["Vendor agreement", "Quarterly report", "Compliance doc", "Test results", "Contract amendment"]),
                "Owner": f"User {random.randint(1, 20)}",
            })
        self.data["other"]["ContentVersion"] = content_versions

        account_ids = self._pool("account")
        n_cdl = _scaled(80, self.factor)
        content_links = []
        for i in range(n_cdl):
            etype = random.choice(["Account", "Vendor", "Contract"])
            linked = random.choice(account_ids) if etype == "Account" and account_ids else self._pick("vendor") if etype == "Vendor" else f"CTR-{random.randint(1,50):03d}"
            content_links.append({
                "Link_ID": f"CDL-{i+1:04d}",
                "Document_ID": random.choice(doc_ids),
                "Linked_Entity_ID": linked,
                "Linked_Entity_Type": etype,
                "Share_Type": random.choice(["View", "Edit", "View", "View"]),
                "Created_Date": _date(180, 0),
            })
        self.data["other"]["ContentDocumentLink"] = content_links

    # ─── Output helpers ─────────────────────────────────────────────────

    def _build_columns_metadata(self, rows: List[dict], table_name: str) -> List[dict]:
        if not rows:
            return []
        sample = rows[0]
        cols = []
        for idx, (k, v) in enumerate(sample.items()):
            dt = "text"
            if isinstance(v, bool):
                dt = "boolean"
            elif isinstance(v, int):
                dt = "integer"
            elif isinstance(v, float):
                dt = "numeric"
            cols.append({
                "columnName": k,
                "dataType": dt,
                "isNullable": True,
                "ordinalPosition": idx + 1,
            })
        return cols

    def _build_system_output(self, system_key: str, schema_name: str, server_name: str) -> dict:
        tables_data = self.data.get(system_key, {})
        servers = [{"serverName": server_name, "wrapperType": "simulator", "serverOptions": {}}]

        tables_meta = []
        columns_files = {}
        data_files = {}

        for table_name, rows in tables_data.items():
            tables_meta.append({
                "schemaName": schema_name,
                "tableName": table_name,
                "serverName": server_name,
                "columnCount": len(rows[0]) if rows else 0,
            })
            cols = self._build_columns_metadata(rows, table_name)
            columns_files[f"{schema_name}.{table_name}"] = cols
            data_files[f"{schema_name}.{table_name}"] = rows

        total_rows = sum(len(r) for r in tables_data.values())
        manifest = {
            "dump_timestamp": datetime.now(timezone.utc).isoformat(),
            "source_url": "generated",
            "schema": schema_name,
            "total_tables": len(tables_meta),
            "tables_with_columns": len(columns_files),
            "tables_with_data": len(data_files),
            "total_rows_dumped": total_rows,
            "data_tables": {t: len(r) for t, r in tables_data.items()},
            "elapsed_seconds": 0,
        }

        return {
            "manifest": manifest,
            "servers": servers,
            "tables": tables_meta,
            "columns": columns_files,
            "data": data_files,
        }

    def get_outputs(self) -> Dict[str, dict]:
        return {
            "sfdc": self._build_system_output("sfdc", SFDC_SCHEMA, "sfdc_simulator"),
            "sap": self._build_system_output("sap", SAP_SCHEMA, "sap_simulator"),
            "oracle": self._build_system_output("oracle", ORACLE_SCHEMA, "oracle_erp_simulator"),
            "other": self._build_system_output("other", "external_sources", "external_simulator"),
        }


def save_system_output(output: dict, prefix: str, local_dir: Optional[str], s3_bucket: Optional[str], s3_prefix: str, aws_profile: Optional[str]):
    def _save(key: str, data: Any):
        if local_dir:
            path = Path(local_dir) / prefix / key
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f, default=str, indent=2)
        if s3_bucket:
            session = boto3.Session(profile_name=aws_profile) if aws_profile else boto3.Session()
            s3 = session.client("s3")
            full_key = f"{s3_prefix}/{key}" if s3_prefix else key
            s3.put_object(
                Bucket=s3_bucket, Key=full_key,
                Body=json.dumps(data, default=str, indent=2),
                ContentType="application/json",
            )

    _save("manifest.json", output["manifest"])
    _save("servers.json", output["servers"])
    _save("tables.json", output["tables"])
    for name, cols in output["columns"].items():
        _save(f"columns/{name}.json", cols)
    for name, rows in output["data"].items():
        _save(f"data/{name}.json", rows)


def main():
    parser = argparse.ArgumentParser(description="Generate supply chain simulator data")
    parser.add_argument("--scale", default="medium", choices=["small", "medium", "large"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--local-dir", help="Local directory for output")
    parser.add_argument("--s3-bucket", help="S3 bucket for upload")
    parser.add_argument("--aws-profile", default=os.getenv("AWS_PROFILE"))
    parser.add_argument("--systems", default="all", help="Comma-separated: sfdc,sap,oracle,other or all")
    args = parser.parse_args()

    if not args.local_dir and not args.s3_bucket:
        print("ERROR: Provide --local-dir or --s3-bucket")
        sys.exit(1)

    if args.s3_bucket and not BOTO3_AVAILABLE:
        print("ERROR: boto3 required for S3 upload")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Supply Chain Data Generator")
    print(f"  Scale: {args.scale} (factor: {SCALE_FACTORS[args.scale]}x)")
    print(f"  Seed: {args.seed}")
    if args.local_dir:
        print(f"  Output: {args.local_dir}")
    if args.s3_bucket:
        print(f"  S3: {args.s3_bucket}")
    print(f"{'='*60}\n")

    gen = SupplyChainDataGenerator(scale=args.scale, seed=args.seed)
    gen.generate_all()
    outputs = gen.get_outputs()

    systems = args.systems.split(",") if args.systems != "all" else ["sfdc", "sap", "oracle", "other"]
    system_config = {
        "sfdc": ("sfdc-simulator", "sfdc-simulator"),
        "sap": ("sap-simulator", "sap-simulator"),
        "oracle": ("oracle-erp-simulator", "oracle-erp-simulator"),
        "other": ("external-sources", "external-sources"),
    }

    for sys_key in systems:
        if sys_key not in outputs:
            continue
        output = outputs[sys_key]
        folder, s3_pfx = system_config[sys_key]
        total_rows = output["manifest"]["total_rows_dumped"]
        total_tables = output["manifest"]["total_tables"]
        print(f"  [{sys_key.upper()}] {total_tables} tables, {total_rows:,} rows")
        save_system_output(output, folder, args.local_dir, args.s3_bucket, s3_pfx, args.aws_profile)

    print(f"\n  Done!\n")


if __name__ == "__main__":
    main()
