"""
Oracle ERP Simulator Service

Redis-backed FDW simulator for Oracle ERP data.
Extends BaseSimulatorService for storage, query, and S3 load.
"""

import os
from typing import Any

from loguru import logger

from ...base import BaseSimulator as BaseSimulatorService

sim_logger = logger.bind(component="oracle-erp-simulator")


class OracleERPSimulatorService(BaseSimulatorService):

    SERVICE_NAME = "oracle"

    PRIORITY_TABLES = [
        "Oracle_AR_Customer", "Oracle_AR_Invoice", "Oracle_AR_Payment",
        "Oracle_AR_Credit_Note", "Oracle_GL_Journal", "Oracle_GL_Period",
        "Oracle_AP_Invoice", "Oracle_AP_Payment", "Oracle_Purchase_Order",
        "Oracle_Cost_Accounting", "Oracle_Fixed_Asset", "Oracle_Budget",
    ]

    def __init__(self, bucket: str = "", prefix: str = ""):
        super().__init__(bucket, prefix)
        self._refresh_config()

    def _refresh_config(self):
        # Library port: nexus-backend's SSM and config_provider branches are
        # dropped; the host supplies bucket/prefix via the per-plugin config
        # passed to build_simulator. Env-var fallback remains for direct
        # construction (no kwargs).
        if not self.bucket:
            self.bucket = os.getenv("ORACLE_ERP_SIMULATOR_BUCKET", "")
        if not self.prefix:
            self.prefix = os.getenv("ORACLE_ERP_SIMULATOR_PREFIX", "oracle-erp-simulator")


    async def seed_data(self) -> dict[str, Any]:
        """Generate synthetic Oracle ERP data and store in Redis."""
        import random as _r

        from .._seed_pools import (
            ASSET_CATEGORIES,
            BUDGET_CATEGORIES,
            COST_CENTERS,
            CURRENCIES,
            account_ids,
            date_str,
            delivery_ids,
            invoice_ids,
            material_ids,
            money,
            pick,
            plant_ids,
            po_ids,
            vendor_ids,
        )
        _r.seed(42)
        sim_logger.info("Seeding Oracle ERP simulator data")

        SCHEMA = "oracle_erp"
        SERVER = "oracle_erp_simulator"
        data_map: dict[str, list[dict]] = {}

        pos = []
        for _i, pid in enumerate(po_ids):
            pos.append({"PO_ID": pid, "Vendor_ID": pick(vendor_ids), "Material_ID": pick(material_ids), "Plant_ID": pick(plant_ids),
                         "Quantity": _r.randint(50, 10000), "Unit_Price": money(0.5, 100), "Total_Amount": money(100, 500000),
                         "PO_Date": date_str(365, 0), "Status": pick(["Open", "Closed", "Partially_Received"]),
                         "Contract_ID": f"CTR-{_r.randint(1,50):03d}" if _r.random() > 0.4 else "", "Currency": pick(CURRENCIES)})
        data_map["Oracle_Purchase_Order"] = pos

        ar_customers = []
        for aid in account_ids:
            ar_customers.append({"Customer_ID": aid, "Customer_Name": f"Customer {aid[-3:]}", "Credit_Limit": money(10000, 5000000),
                                  "Payment_Terms": pick(["Net_30", "Net_60", "Net_90", "COD"]), "Currency": pick(CURRENCIES),
                                  "Status": pick(["Active", "Active", "Suspended", "Inactive"])})
        data_map["Oracle_AR_Customer"] = ar_customers

        ar_invoices = []
        for _i, iid in enumerate(invoice_ids):
            ar_invoices.append({"Invoice_ID": iid, "Customer_ID": pick(account_ids), "Invoice_Date": date_str(365, 0),
                                 "Due_Date": date_str(300, 0), "Amount": money(500, 200000), "Status": pick(["Open", "Paid", "Overdue", "Partial"]),
                                 "Linked_Delivery_ID": pick(delivery_ids), "Currency": pick(CURRENCIES)})
        data_map["Oracle_AR_Invoice"] = ar_invoices

        ar_payments = []
        for i in range(600):
            ar_payments.append({"Payment_ID": f"PAY-{i+1:05d}", "Invoice_ID": pick(invoice_ids), "Customer_ID": pick(account_ids),
                                 "Amount": money(500, 200000), "Payment_Date": date_str(300, 0),
                                 "Payment_Method": pick(["Wire", "Check", "ACH", "Bank_Transfer"]), "Applied_Flag": pick([True, True, False])})
        data_map["Oracle_AR_Payment"] = ar_payments

        credit_notes = []
        for i in range(80):
            credit_notes.append({"Credit_Note_ID": f"CN-{i+1:04d}", "Customer_ID": pick(account_ids), "Invoice_ID": pick(invoice_ids),
                                  "Amount": money(50, 50000), "Reason": pick(["Pricing_Error", "Return", "Damaged_Goods", "Promo_Rebate"]),
                                  "Date": date_str(180, 0), "Status": pick(["Applied", "Pending", "Voided"])})
        data_map["Oracle_AR_Credit_Note"] = credit_notes

        gl_journals = []
        for i in range(500):
            gl_journals.append({"Journal_ID": f"JE-{i+1:05d}", "Period": f"2025-{_r.randint(1,12):02d}",
                                 "Account_Code": f"{_r.randint(1000,9999)}", "Debit": money(0, 500000), "Credit": money(0, 500000),
                                 "Description": pick(["Revenue", "COGS", "SGA", "Depreciation", "Tax", "Intercompany"]),
                                 "Cost_Center": pick(COST_CENTERS), "Posted_Date": date_str(365, 0)})
        data_map["Oracle_GL_Journal"] = gl_journals

        gl_periods = []
        for year in [2024, 2025]:
            for month in range(1, 13):
                gl_periods.append({"Period_ID": f"FP-{year}-{month:02d}", "Fiscal_Year": year, "Period": month,
                                    "Status": "Closed" if (year == 2024 or month < 6) else "Open",
                                    "Start_Date": f"{year}-{month:02d}-01", "End_Date": f"{year}-{month:02d}-28"})
        data_map["Oracle_GL_Period"] = gl_periods

        ap_invoices = []
        for i in range(400):
            ap_invoices.append({"AP_Invoice_ID": f"API-{i+1:05d}", "Vendor_ID": pick(vendor_ids), "PO_ID": pick(po_ids),
                                 "Amount": money(100, 300000), "Invoice_Date": date_str(365, 0), "Due_Date": date_str(300, 0),
                                 "Status": pick(["Approved", "Pending", "Paid", "On_Hold"]), "Currency": pick(CURRENCIES)})
        data_map["Oracle_AP_Invoice"] = ap_invoices

        ap_payments = []
        for i in range(350):
            ap_payments.append({"AP_Payment_ID": f"APP-{i+1:05d}", "AP_Invoice_ID": f"API-{_r.randint(1,400):05d}",
                                 "Vendor_ID": pick(vendor_ids), "Amount": money(100, 300000), "Payment_Date": date_str(300, 0),
                                 "Payment_Method": pick(["Wire", "Check", "ACH"]), "Status": pick(["Cleared", "Pending", "Void"])})
        data_map["Oracle_AP_Payment"] = ap_payments

        cost_acct = []
        for i in range(300):
            cost_acct.append({"Cost_Entry_ID": f"CA-{i+1:05d}", "Material_ID": pick(material_ids), "Plant_ID": pick(plant_ids),
                               "Cost_Type": pick(["Standard", "Actual", "Planned"]), "Amount": money(0.1, 5000),
                               "Period": f"2025-{_r.randint(1,12):02d}", "Cost_Center": pick(COST_CENTERS)})
        data_map["Oracle_Cost_Accounting"] = cost_acct

        assets = []
        for i in range(50):
            assets.append({"Asset_ID": f"FA-{i+1:04d}", "Asset_Name": f"Asset {pick(ASSET_CATEGORIES)} {i+1}",
                            "Category": pick(ASSET_CATEGORIES), "Plant_ID": pick(plant_ids),
                            "Acquisition_Date": date_str(1800, 30), "Original_Cost": money(5000, 2000000),
                            "Depreciation_Method": pick(["Straight_Line", "Declining_Balance"]),
                            "Net_Book_Value": money(1000, 1500000)})
        data_map["Oracle_Fixed_Asset"] = assets

        budgets = []
        for i in range(40):
            budgets.append({"Budget_ID": f"BUD-{i+1:03d}", "Department": pick(COST_CENTERS),
                             "Category": pick(BUDGET_CATEGORIES), "Fiscal_Year": pick([2024, 2025]),
                             "Approved_Amount": money(50000, 5000000), "Spent_Amount": money(10000, 4000000),
                             "Status": pick(["Active", "Closed", "Draft"])})
        data_map["Oracle_Budget"] = budgets

        products = []
        for mid in material_ids:
            products.append({"Product_ID": mid, "Product_Name": f"Product {mid[-5:]}",
                              "Category": pick(["Carbonated", "Juice", "Water", "Energy", "Sports", "Tea", "Snacks"]),
                              "Unit_Cost": money(0.3, 30), "List_Price": money(0.5, 50),
                              "Status": pick(["Active", "Active", "Active", "Discontinued"]),
                              "Weight_KG": round(_r.uniform(0.1, 25), 2),
                              "Volume_Unit": pick(["330ml", "500ml", "1L", "1.5L", "2L"]),
                              "Tax_Code": pick(["GST_7", "GST_0", "EXEMPT", "GST_7", "GST_7"])})
        data_map["Oracle_Product_Master"] = products

        from nexus_simulator.plugins.diagnostic_seed import apply_sentinels
        apply_sentinels("oracle", data_map)

        return await self._finalize_seed(SCHEMA, SERVER, data_map)
