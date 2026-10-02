"""
SAP Simulator Service

Redis-backed FDW simulator for SAP S/4HANA data.
Extends BaseSimulatorService for storage, query, and S3 load.
"""

import os
from typing import Any

from loguru import logger

from ...base import BaseSimulator as BaseSimulatorService

sim_logger = logger.bind(component="sap-simulator")


class SAPSimulatorService(BaseSimulatorService):

    SERVICE_NAME = "sap"

    PRIORITY_TABLES = [
        "Material_Master", "Material_Plant", "Material_Storage", "Bill_of_Materials",
        "Inventory_Position", "Batch_Master", "Plant_Master", "Storage_Location",
        "Warehouse_Transfer", "Production_Order", "Production_Line",
        "Quality_Inspection_Lot", "Quality_Test_Result",
        "Vendor_Master", "Source_List", "Purchase_Requisition", "Goods_Receipt",
        "Delivery_Document", "Shipment", "Return_Order",
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
            self.bucket = os.getenv("SAP_SIMULATOR_BUCKET", "")
        if not self.prefix:
            self.prefix = os.getenv("SAP_SIMULATOR_PREFIX", "sap-simulator")


    async def seed_data(self) -> dict[str, Any]:
        """Generate synthetic SAP S/4HANA data and store in Redis."""
        import random as _r

        from .._seed_pools import (
            BEVERAGE_BRANDS,
            BEVERAGE_CATEGORIES,
            CITIES,
            COUNTRIES,
            CURRENCIES,
            DELIVERY_PRIORITIES,
            PACK_CONFIGS,
            PACK_SIZES,
            PLANT_TYPES,
            REGIONS,
            STORAGE_TYPES,
            VENDOR_CATEGORIES,
            account_ids,
            batch_ids,
            date_str,
            delivery_ids,
            gtin,
            inspection_ids,
            material_ids,
            money,
            opportunity_ids,
            pct,
            pick,
            plant_ids,
            po_ids,
            production_line_ids,
            production_order_ids,
            storage_ids,
            vendor_ids,
        )
        _r.seed(42)
        sim_logger.info("Seeding SAP simulator data")

        SCHEMA = "sap_s4hana"
        SERVER = "sap_simulator"
        data_map: dict[str, list[dict]] = {}

        plants = []
        for pid in plant_ids:
            plants.append({"Plant_ID": pid, "Plant_Name": f"Plant {pid[-3:]}", "Type": pick(PLANT_TYPES),
                            "Region": pick(REGIONS), "Country": pick(COUNTRIES), "Capacity": _r.randint(1000, 50000),
                            "Status": pick(["Active", "Active", "Active", "Maintenance"])})
        data_map["Plant_Master"] = plants

        storages = []
        for sid in storage_ids:
            storages.append({"Storage_Location_ID": sid, "Plant_ID": pick(plant_ids), "Type": pick(STORAGE_TYPES),
                              "Capacity": _r.randint(500, 20000), "Utilization_Pct": pct(20, 95)})
        data_map["Storage_Location"] = storages

        prod_lines = []
        for plid in production_line_ids:
            prod_lines.append({"Line_ID": plid, "Plant_ID": pick(plant_ids), "Line_Name": f"Line {plid[-3:]}",
                                "Product_Category": pick(BEVERAGE_CATEGORIES), "Capacity_Units_Per_Hour": _r.randint(500, 5000),
                                "Status": pick(["Running", "Running", "Idle", "Maintenance"])})
        data_map["Production_Line"] = prod_lines

        materials = []
        for mid in material_ids:
            materials.append({"Material_ID": mid, "Material_Name": f"{pick(BEVERAGE_BRANDS)} {pick(BEVERAGE_CATEGORIES)} {pick(PACK_SIZES)}",
                               "Category": pick(BEVERAGE_CATEGORIES), "Pack_Size": pick(PACK_SIZES), "Pack_Config": pick(PACK_CONFIGS),
                               "GTIN": gtin(), "Unit_Cost": money(0.3, 30), "Shelf_Life_Days": _r.randint(30, 730),
                               "Status": pick(["Active", "Active", "Active", "Discontinued"])})
        data_map["Material_Master"] = materials

        mat_plants = []
        for _i in range(600):
            mat_plants.append({"Material_ID": pick(material_ids), "Plant_ID": pick(plant_ids),
                                "Safety_Stock": _r.randint(50, 5000), "Reorder_Point": _r.randint(100, 3000),
                                "MRP_Type": pick(["MRP", "Reorder_Point", "Manual"]), "Lead_Time_Days": _r.randint(1, 30),
                                "Lot_Size": _r.randint(100, 10000),
                                "ABC_Classification": pick(["A", "A", "B", "B", "B", "C", "C"])})
        data_map["Material_Plant"] = mat_plants

        mat_storages = []
        for _i in range(900):
            mat_storages.append({"Material_ID": pick(material_ids), "Plant_ID": pick(plant_ids),
                                  "Storage_Location": pick(storage_ids), "Max_Capacity": _r.randint(1000, 50000),
                                  "Current_Stock": _r.randint(0, 30000)})
        data_map["Material_Storage"] = mat_storages

        boms = []
        for i in range(400):
            boms.append({"BOM_ID": f"BOM-{i+1:05d}", "Finished_Material_ID": pick(material_ids),
                          "Component_Material_ID": pick(material_ids), "Quantity_Per": round(_r.uniform(0.01, 10), 3),
                          "Unit": pick(["KG", "L", "EA", "MT"]), "Scrap_Pct": pct(0, 5)})
        data_map["Bill_of_Materials"] = boms

        prod_orders = []
        for pid in production_order_ids:
            prod_orders.append({"Production_Order_ID": pid, "Material_ID": pick(material_ids), "Plant_ID": pick(plant_ids),
                                 "Production_Line": pick(production_line_ids), "Quantity": _r.randint(100, 50000),
                                 "Start_Date": date_str(90, 0), "End_Date": date_str(60, 0),
                                 "Status": pick(["Released", "In_Progress", "Completed", "Completed"]), "Yield_Pct": pct(85, 100)})
        data_map["Production_Order"] = prod_orders

        batches = []
        for bid in batch_ids:
            batches.append({"Batch_ID": bid, "Material_ID": pick(material_ids), "Production_Order_ID": pick(production_order_ids),
                             "Plant_ID": pick(plant_ids), "Production_Date": date_str(180, 0),
                             "Expiry_Date": date_str(0, 0), "Quantity": _r.randint(100, 20000),
                             "Status": pick(["Released", "Restricted", "Blocked", "Quality_Hold"])})
        data_map["Batch_Master"] = batches

        inv_pos = []
        for i in range(1200):
            inv_pos.append({"Inventory_ID": f"INV-{i+1:05d}", "Material_ID": pick(material_ids), "Plant_ID": pick(plant_ids),
                             "Storage_Location": pick(storage_ids), "Batch_ID": pick(batch_ids),
                             "Quantity_On_Hand": _r.randint(0, 30000), "Quantity_Reserved": _r.randint(0, 5000),
                             "In_Transit_Qty": _r.randint(0, 2000), "Valuation_Price": money(0.3, 50),
                             "Unit_Value": money(0.3, 50), "Last_Count_Date": date_str(90, 0)})
        data_map["Inventory_Position"] = inv_pos

        transfers = []
        for i in range(200):
            transfers.append({"Transfer_ID": f"WT-{i+1:05d}", "From_Plant": pick(plant_ids), "To_Plant": pick(plant_ids),
                               "Material_ID": pick(material_ids), "Batch_ID": pick(batch_ids),
                               "Quantity": _r.randint(50, 5000), "Request_Date": date_str(60, 0),
                               "Status": pick(["Planned", "In_Transit", "Received", "Received"])})
        data_map["Warehouse_Transfer"] = transfers

        qil = []
        for iid in inspection_ids:
            qil.append({"Inspection_ID": iid, "Batch_ID": pick(batch_ids), "Material_ID": pick(material_ids),
                          "Inspection_Type": pick(["Incoming", "In_Process", "Final", "Stability"]),
                          "Inspection_Date": date_str(120, 0), "Result": pick(["Pass", "Pass", "Pass", "Fail", "Conditional"]),
                          "Inspector": f"Inspector {_r.randint(1,20)}"})
        data_map["Quality_Inspection_Lot"] = qil

        qtrs = []
        for i in range(900):
            qtrs.append({"Test_Result_ID": f"QTR-{i+1:05d}", "Inspection_ID": pick(inspection_ids),
                          "Test_Name": pick(["pH", "Brix", "Turbidity", "Microbial", "Color", "Taste", "Carbonation", "Viscosity"]),
                          "Spec_Min": round(_r.uniform(0, 50), 1), "Spec_Max": round(_r.uniform(50, 100), 1),
                          "Actual_Value": round(_r.uniform(0, 100), 2), "Pass_Fail": pick(["Pass", "Pass", "Pass", "Fail"])})
        data_map["Quality_Test_Result"] = qtrs

        vendors = []
        for vid in vendor_ids:
            vendors.append({"Vendor_ID": vid, "Vendor_Name": f"Supplier {vid[-3:]}",
                             "Category": pick(VENDOR_CATEGORIES), "Country": pick(COUNTRIES), "Region": pick(REGIONS),
                             "Payment_Terms": pick(["Net_30", "Net_60", "Net_90"]),
                             "Rating": pick(["A", "A", "B", "B", "C"]), "Status": pick(["Active", "Active", "Inactive"])})
        data_map["Vendor_Master"] = vendors

        source_list = []
        for i in range(200):
            source_list.append({"Source_ID": f"SRC-{i+1:05d}", "Material_ID": pick(material_ids), "Vendor_ID": pick(vendor_ids),
                                 "Valid_From": date_str(365, 180), "Valid_To": date_str(180, 0),
                                 "Priority": _r.randint(1, 5), "Status": pick(["Active", "Active", "Expired"])})
        data_map["Source_List"] = source_list

        pr = []
        for i in range(300):
            pr.append({"PR_ID": f"PR-{i+1:05d}", "Material_ID": pick(material_ids), "Plant_ID": pick(plant_ids),
                         "Quantity": _r.randint(50, 10000), "Requested_Date": date_str(90, 0),
                         "Status": pick(["Open", "Approved", "Converted_to_PO", "Rejected"]),
                         "Requestor": f"Buyer {_r.randint(1,15)}"})
        data_map["Purchase_Requisition"] = pr

        gr = []
        for i in range(400):
            gr.append({"GR_ID": f"GR-{i+1:05d}", "PO_ID": pick(po_ids), "Material_ID": pick(material_ids),
                         "Vendor_ID": pick(vendor_ids), "Quantity_Received": _r.randint(50, 10000),
                         "Quantity_Accepted": _r.randint(40, 9500), "Receipt_Date": date_str(120, 0),
                         "Quality_Status": pick(["Accepted", "Accepted", "Accepted", "Rejected", "Conditional"])})
        data_map["Goods_Receipt"] = gr

        deliveries = []
        for did in delivery_ids:
            deliveries.append({"Delivery_ID": did, "Sales_Order_ID": pick(opportunity_ids),
                                "Ship_To_Account_ID": pick(account_ids), "Material_ID": pick(material_ids),
                                "Batch_ID": pick(batch_ids), "Quantity": _r.randint(10, 5000),
                                "Delivery_Date": date_str(120, 0), "Status": pick(["Created", "Shipped", "Delivered", "Delivered"]),
                                "Priority": pick(DELIVERY_PRIORITIES)})
        data_map["Delivery_Document"] = deliveries

        shipments = []
        for i in range(300):
            shipments.append({"Shipment_ID": f"SHP-{i+1:05d}", "Carrier": pick(["DHL", "FedEx", "Local_Fleet", "Third_Party"]),
                               "Origin_Plant": pick(plant_ids), "Destination": pick(CITIES),
                               "Departure_Date": date_str(90, 0), "Arrival_Date": date_str(60, 0),
                               "Status": pick(["In_Transit", "Delivered", "Delivered", "Delayed"]),
                               "Weight_KG": _r.randint(100, 30000)})
        data_map["Shipment"] = shipments

        returns = []
        for i in range(100):
            returns.append({"Return_ID": f"RET-{i+1:04d}", "Delivery_ID": pick(delivery_ids),
                             "Material_ID": pick(material_ids), "Quantity": _r.randint(1, 500),
                             "Reason": pick(["Damaged", "Wrong_Item", "Quality_Issue", "Customer_Return", "Expired"]),
                             "Return_Date": date_str(90, 0), "Status": pick(["Open", "Processed", "Credited"])})
        data_map["Return_Order"] = returns

        price_items = []
        for i in range(200):
            price_items.append({"Price_Item_ID": f"PI-{i+1:05d}", "Product_ID": pick(material_ids),
                                 "Price_Type": pick(["List", "Contract", "Promo", "Volume_Discount"]),
                                 "Unit_Price": money(0.5, 100), "Currency": pick(CURRENCIES),
                                 "Valid_From": date_str(365, 180), "Valid_To": date_str(180, 0),
                                 "Volume_Min": _r.randint(0, 100), "Volume_Max": _r.randint(1000, 50000),
                                 "Discount_Pct": round(_r.uniform(0, 25), 1), "Region": pick(REGIONS)})
        data_map["cspmb__Price_Item__c"] = price_items

        from nexus_simulator.plugins.diagnostic_seed import apply_sentinels
        apply_sentinels("sap", data_map)

        return await self._finalize_seed(SCHEMA, SERVER, data_map)
