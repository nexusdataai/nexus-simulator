#!/usr/bin/env python3
"""
Supply Chain Data Adequacy Validator

Read-only check of all simulator data against supply-chain-schema.yaml requirements.
Reports per-system table counts, row counts, and per-use-case readiness.

Usage:
    python validate_data_adequacy.py --base-url http://localhost:8000
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "enterprise-knowledge" / "supply-chain-schema.yaml"

SYSTEM_SCHEMA_MAP = {
    "Salesforce": "sfdc_itxp2dev",
    "SAP": "sap_s4hana",
    "Oracle": "oracle_erp",
    "Google_Drive": "external_sources",
    "Social_Listening": "external_sources",
    "File_Uploads": "external_sources",
}

APP_ENTITY_MAP = {
    "Demand Forecasting": [
        "Opportunity", "Opportunity_Line_Item", "Account", "Campaign",
        "Forecast_Override", "Material_Master", "Material_Plant",
        "Inventory_Position", "Market_Signal",
    ],
    "Inventory Optimization": [
        "Material_Master", "Material_Plant", "Inventory_Position",
        "Batch_Master", "Plant_Master", "Storage_Location",
        "Warehouse_Transfer", "Delivery_Document", "Shipment",
        "Opportunity", "Oracle_Cost_Accounting",
    ],
    "Order-to-Cash": [
        "Opportunity", "Opportunity_Line_Item", "Account",
        "Delivery_Document", "Oracle_AR_Invoice", "Oracle_AR_Payment",
        "Oracle_AR_Credit_Note", "Oracle_AR_Customer", "Oracle_GL_Journal",
        "Goods_Receipt", "Return_Order",
    ],
    "Supply Chain Risk": [
        "Vendor_Master", "Source_List", "Oracle_Purchase_Order",
        "Goods_Receipt", "Material_Master", "Contract_Document",
        "Market_Signal", "Commodity_Price", "Oracle_AP_Invoice",
        "Quality_Inspection_Lot",
    ],
    "Customer 360": [
        "Account", "Contact", "Opportunity", "Opportunity_Line_Item",
        "Campaign", "Delivery_Document", "Return_Order",
        "Oracle_AR_Customer", "Oracle_AR_Invoice",
        "Oracle_Cost_Accounting", "Brand_Sentiment",
    ],
    "Procurement Analytics": [
        "Vendor_Master", "Source_List", "Purchase_Requisition",
        "Oracle_Purchase_Order", "Goods_Receipt", "Oracle_AP_Invoice",
        "Oracle_AP_Payment", "Material_Master", "Contract_Document",
        "Invoice_Upload", "Commodity_Price",
    ],
    "Production & Quality": [
        "Production_Order", "Production_Line", "Bill_of_Materials",
        "Material_Master", "Material_Plant", "Batch_Master",
        "Quality_Inspection_Lot", "Quality_Test_Result",
        "Lab_Report_Upload", "Inventory_Position", "Oracle_Cost_Accounting",
    ],
    "ESG & Sustainability": [
        "Plant_Master", "Production_Order", "Bill_of_Materials",
        "Material_Master", "Shipment", "Delivery_Document",
        "Oracle_Cost_Accounting", "Oracle_Fixed_Asset",
        "Sustainability_Report", "Brand_Sentiment",
    ],
}

SIMULATOR_STATUS_ENDPOINTS = {
    "Salesforce": "/api/v1/sfdc-simulator/status",
    "Oracle": "/api/v1/oracle-erp-simulator/status",
    "SAP": "/api/v1/sap-simulator/status",
}

SIMULATOR_TABLES_ENDPOINTS = {
    "Salesforce": "/api/v1/sfdc-simulator/tables",
    "Oracle": "/api/v1/oracle-erp-simulator/tables",
    "SAP": "/api/v1/sap-simulator/tables",
}


def load_schema_entities() -> List[Dict[str, Any]]:
    if not YAML_AVAILABLE:
        print("WARNING: pyyaml not installed, cannot parse schema YAML")
        return []
    if not SCHEMA_PATH.exists():
        print(f"WARNING: Schema not found at {SCHEMA_PATH}")
        return []
    with open(SCHEMA_PATH) as f:
        schema = yaml.safe_load(f)
    entities = []
    for domain in schema.get("domains", []):
        system = domain.get("system", "Unknown")
        for table in domain.get("tables", []):
            entities.append({
                "name": table.get("fdw_table", ""),
                "system": system,
                "virtual": table.get("virtual", False),
                "schema": SYSTEM_SCHEMA_MAP.get(system, "unknown"),
                "field_count": len(table.get("key_fields", [])),
            })
    return entities


def check_simulator(base_url: str, system: str) -> Dict[str, Any]:
    status_url = f"{base_url}{SIMULATOR_STATUS_ENDPOINTS.get(system, '')}"
    tables_url = f"{base_url}{SIMULATOR_TABLES_ENDPOINTS.get(system, '')}"
    result = {"loaded": False, "tables": {}, "total_rows": 0, "error": None}
    try:
        resp = requests.get(status_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            result["loaded"] = data.get("loaded", False)
            result["total_rows"] = data.get("total_rows", 0)
    except Exception as e:
        result["error"] = str(e)
        return result
    if result["loaded"]:
        try:
            resp = requests.get(tables_url, timeout=10)
            if resp.status_code == 200:
                tables = resp.json()
                if isinstance(tables, list):
                    for t in tables:
                        name = t.get("tableName", t.get("table_name", ""))
                        rows = t.get("rowCount", t.get("row_count", 0))
                        result["tables"][name] = rows
        except Exception:
            pass
    return result


def print_report(entities: List[Dict], simulators: Dict[str, Dict]):
    print(f"\n{'='*70}")
    print("  SUPPLY CHAIN DATA ADEQUACY REPORT")
    print(f"{'='*70}\n")

    print("--- Simulator Status ---\n")
    for sys_name, info in simulators.items():
        status = "LOADED" if info["loaded"] else "NOT LOADED"
        icon = "+" if info["loaded"] else "-"
        print(f"  [{icon}] {sys_name}: {status}")
        if info["error"]:
            print(f"      Error: {info['error']}")
        elif info["loaded"]:
            print(f"      Tables: {len(info['tables'])}, Total rows: {info['total_rows']}")

    print(f"\n--- Entity Coverage ({len(entities)} entities) ---\n")
    print(f"  {'Entity':<30} {'System':<15} {'Schema':<20} {'Rows':<8} {'Status'}")
    print(f"  {'-'*30} {'-'*15} {'-'*20} {'-'*8} {'-'*10}")

    entity_status = {}
    for ent in entities:
        name = ent["name"]
        system = ent["system"]
        schema = ent["schema"]
        rows = 0
        status = "MISSING"
        sim_key = {"Salesforce": "Salesforce", "SAP": "SAP", "Oracle": "Oracle"}.get(system)
        if sim_key and sim_key in simulators:
            sim = simulators[sim_key]
            if sim["loaded"] and name in sim["tables"]:
                rows = sim["tables"][name]
                status = "OK" if rows > 0 else "EMPTY"
            elif sim["loaded"]:
                status = "NOT IN SIM"
            else:
                status = "SIM DOWN"
        elif system in ("Google_Drive", "Social_Listening", "File_Uploads"):
            status = "EXTERNAL"

        icon = "+" if status == "OK" else ("-" if status in ("MISSING", "EMPTY", "NOT IN SIM") else "?")
        print(f"  [{icon}] {name:<28} {system:<15} {schema:<20} {rows:<8} {status}")
        entity_status[name] = status

    print(f"\n--- Use Case Readiness ---\n")
    for app, required in APP_ENTITY_MAP.items():
        ok = sum(1 for e in required if entity_status.get(e) in ("OK", "EXTERNAL"))
        total = len(required)
        pct = (ok / total * 100) if total else 0
        icon = "+" if pct >= 80 else ("-" if pct < 50 else "~")
        missing = [e for e in required if entity_status.get(e) not in ("OK", "EXTERNAL")]
        print(f"  [{icon}] {app}: {ok}/{total} entities ready ({pct:.0f}%)")
        if missing:
            print(f"      Missing: {', '.join(missing)}")

    print(f"\n{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description="Validate supply chain data adequacy")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--offline", action="store_true", help="Skip API calls, schema-only analysis")
    args = parser.parse_args()

    entities = load_schema_entities()
    if not entities:
        print("No entities loaded from schema. Check YAML path.")
        sys.exit(1)

    print(f"Loaded {len(entities)} entities from schema")

    simulators = {}
    if not args.offline and REQUESTS_AVAILABLE:
        for sys_name in ["Salesforce", "Oracle", "SAP"]:
            print(f"Checking {sys_name} simulator...")
            simulators[sys_name] = check_simulator(args.base_url, sys_name)
    else:
        for sys_name in ["Salesforce", "Oracle", "SAP"]:
            simulators[sys_name] = {"loaded": False, "tables": {}, "total_rows": 0, "error": "Offline mode"}

    print_report(entities, simulators)


if __name__ == "__main__":
    main()
