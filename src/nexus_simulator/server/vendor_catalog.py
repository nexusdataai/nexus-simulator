"""Official vendor API catalog built from loaded simulator tables."""

from __future__ import annotations

from typing import Any

SFDC_VERSION = "v61.0"
SFDC_DOCS = (
    "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/"
    "api_rest/quickstart_using_workbench.htm"
)
ORACLE_VERSION = "11.13.18.05"
ORACLE_DOCS = "https://docs.oracle.com/en/cloud/saas/financials/26b/farfa/op-receivablesinvoices-post.html"
SAP_DOCS = "https://api.sap.com/"

ORACLE_RESOURCES: dict[str, dict[str, str]] = {
    "Oracle_AR_Invoice": {
        "resource": "receivablesInvoices",
        "pk": "Invoice_ID",
        "docs": "https://docs.oracle.com/en/cloud/saas/financials/26b/farfa/op-receivablesinvoices-post.html",
    },
    "Oracle_AR_Credit_Note": {
        "resource": "receivablesCreditMemos",
        "pk": "Credit_Note_ID",
        "docs": ORACLE_DOCS,
    },
    "Oracle_AR_Payment": {
        "resource": "standardReceipts",
        "pk": "Payment_ID",
        "docs": ORACLE_DOCS,
    },
    "Oracle_AR_Customer": {
        "resource": "customerAccounts",
        "pk": "Customer_ID",
        "docs": ORACLE_DOCS,
    },
    "Oracle_AP_Invoice": {
        "resource": "invoices",
        "pk": "Invoice_ID",
        "docs": ORACLE_DOCS,
    },
    "Oracle_AP_Payment": {
        "resource": "payablesPayments",
        "pk": "Payment_ID",
        "docs": ORACLE_DOCS,
    },
    "Oracle_Purchase_Order": {
        "resource": "purchaseOrders",
        "pk": "PO_ID",
        "docs": "https://docs.oracle.com/en/cloud/saas/procurement/25c/fapra/api-purchase-orders.html",
    },
    "Oracle_Product_Master": {
        "resource": "itemsV2",
        "pk": "Product_ID",
        "docs": ORACLE_DOCS,
    },
    "Oracle_GL_Journal": {
        "resource": "journalEntries",
        "pk": "Journal_ID",
        "docs": ORACLE_DOCS,
    },
    "Oracle_GL_Period": {
        "resource": "accountingPeriods",
        "pk": "Period_ID",
        "docs": ORACLE_DOCS,
    },
    "Oracle_Fixed_Asset": {
        "resource": "assets",
        "pk": "Asset_ID",
        "docs": ORACLE_DOCS,
    },
    "Oracle_Budget": {
        "resource": "budgetProducts",
        "pk": "Budget_ID",
        "docs": ORACLE_DOCS,
    },
    "Oracle_Cost_Accounting": {
        "resource": "costAccountingOverheads",
        "pk": "Cost_ID",
        "docs": ORACLE_DOCS,
    },
}

SAP_ENTITIES: dict[str, dict[str, str]] = {
    "Material_Master": {"service": "API_PRODUCT_SRV", "entity": "A_Product", "pk": "Material_ID"},
    "Material_Plant": {"service": "API_PRODUCT_SRV", "entity": "A_ProductPlant", "pk": "Material_ID"},
    "Material_Storage": {"service": "API_PRODUCT_SRV", "entity": "A_ProductStorageLocation", "pk": "Material_ID"},
    "Vendor_Master": {"service": "API_BUSINESS_PARTNER", "entity": "A_Supplier", "pk": "Vendor_ID"},
    "Delivery_Document": {"service": "API_OUTBOUND_DELIVERY_SRV", "entity": "A_OutbDeliveryHeader", "pk": "Delivery_ID"},
    "Goods_Receipt": {"service": "API_MATERIAL_DOCUMENT_SRV", "entity": "A_MaterialDocumentHeader", "pk": "Receipt_ID"},
    "Production_Order": {"service": "API_PRODUCTION_ORDER_2_SRV", "entity": "A_ProductionOrder_2", "pk": "Order_ID"},
    "Purchase_Requisition": {"service": "API_PURCHASEREQ_PROCESS_SRV", "entity": "A_PurchaseReqn", "pk": "Requisition_ID"},
    "Quality_Inspection_Lot": {"service": "API_INSPECTIONLOT_SRV", "entity": "A_InspectionLot", "pk": "Lot_ID"},
    "Batch_Master": {"service": "API_BATCH_SRV", "entity": "A_Batch", "pk": "Batch_ID"},
    "Bill_of_Materials": {"service": "API_BILL_OF_MATERIAL_SRV", "entity": "A_BillOfMaterial", "pk": "BOM_ID"},
    "Inventory_Position": {"service": "API_MATERIAL_STOCK_SRV", "entity": "A_MatlStkInAcctMod", "pk": "Material_ID"},
    "Plant_Master": {"service": "API_PLANT", "entity": "A_Plant", "pk": "Plant_ID"},
    "Storage_Location": {"service": "API_STORAGELOCATION", "entity": "A_StorageLocation", "pk": "Storage_ID"},
    "Warehouse_Transfer": {"service": "API_WAREHOUSE_STOCK_TRANSFER", "entity": "A_WhseTransfer", "pk": "Transfer_ID"},
    "Return_Order": {"service": "API_CUSTOMER_RETURN_SRV", "entity": "A_CustomerReturn", "pk": "Return_ID"},
    "Shipment": {"service": "API_SHIPMENT", "entity": "A_Shipment", "pk": "Shipment_ID"},
    "Source_List": {"service": "API_PURCHASING_SRC_LIST", "entity": "A_PurchasingSourceList", "pk": "Source_List_ID"},
    "Production_Line": {"service": "API_WORK_CENTER", "entity": "A_WorkCenter", "pk": "Line_ID"},
    "Quality_Test_Result": {"service": "API_INSPECTIONLOT_SRV", "entity": "A_InspectionResult", "pk": "Result_ID"},
    "cspmb__Price_Item__c": {"service": "API_PRICE_ITEM", "entity": "cspmb__Price_Item__c", "pk": "Id"},
}

ORACLE_BY_RESOURCE = {v["resource"]: k for k, v in ORACLE_RESOURCES.items()}
SAP_BY_ENTITY: dict[tuple[str, str], str] = {
    (v["service"], v["entity"]): k for k, v in SAP_ENTITIES.items()
}


def pick_pk_column(table: str, sample: dict[str, Any] | None, hinted: str | None = None) -> str:
    cols = list(sample.keys()) if sample else []
    candidates = [hinted, "Id", f"{table}_ID", f"{table}Id", "ID"] if hinted else [
        "Id", f"{table}_ID", f"{table}Id", "ID"
    ]
    for cand in candidates:
        if cand and (not cols or cand in cols):
            if not cols or cand in cols:
                return cand
    return cols[0] if cols else (hinted or "Id")


def _sfdc_methods(sobject: str) -> list[dict[str, str]]:
    base = f"/services/data/{SFDC_VERSION}/sobjects/{sobject}"
    return [
        {"method": "GET", "path": base, "kind": "list"},
        {"method": "GET", "path": f"{base}/describe", "kind": "describe"},
        {"method": "GET", "path": f"{base}/{{id}}", "kind": "get"},
        {"method": "POST", "path": base, "kind": "create"},
        {"method": "PATCH", "path": f"{base}/{{id}}", "kind": "update"},
        {"method": "DELETE", "path": f"{base}/{{id}}", "kind": "delete"},
    ]


def _oracle_methods(resource: str) -> list[dict[str, str]]:
    base = f"/fscmRestApi/resources/{ORACLE_VERSION}/{resource}"
    return [
        {"method": "GET", "path": base, "kind": "list"},
        {"method": "GET", "path": f"{base}/{{id}}", "kind": "get"},
        {"method": "POST", "path": base, "kind": "create"},
        {"method": "PATCH", "path": f"{base}/{{id}}", "kind": "update"},
        {"method": "DELETE", "path": f"{base}/{{id}}", "kind": "delete"},
    ]


def _sap_methods(service: str, entity: str) -> list[dict[str, str]]:
    base = f"/sap/opu/odata/sap/{service}"
    return [
        {"method": "GET", "path": f"{base}/$metadata", "kind": "metadata"},
        {"method": "GET", "path": f"{base}/{entity}", "kind": "list"},
        {"method": "GET", "path": f"{base}/{entity}('{{id}}')", "kind": "get"},
        {"method": "POST", "path": f"{base}/{entity}", "kind": "create"},
        {"method": "PATCH", "path": f"{base}/{entity}('{{id}}')", "kind": "update"},
        {"method": "DELETE", "path": f"{base}/{entity}('{{id}}')", "kind": "delete"},
    ]


async def build_system_catalog(svc: Any, system: str) -> list[dict[str, Any]]:
    if hasattr(svc, "ensure_loaded"):
        await svc.ensure_loaded()
    objects = await svc.get_object_list() if hasattr(svc, "get_object_list") else []
    items: list[dict[str, Any]] = []
    for obj in objects:
        schema = obj.get("schemaName") or obj.get("schema_name") or ""
        table = obj.get("tableName") or obj.get("table_name") or ""
        if not table:
            continue
        rows = obj.get("rowCount") or obj.get("row_count") or 0
        cols = obj.get("columnCount") or obj.get("column_count") or 0
        if system == "sfdc":
            items.append({
                "id": f"sfdc.{table}",
                "system": "sfdc",
                "name": table,
                "table": table,
                "schema": schema,
                "rowCount": rows,
                "columnCount": cols,
                "pk": pick_pk_column(table, None),
                "docsUrl": SFDC_DOCS,
                "methods": _sfdc_methods(table),
            })
        elif system == "oracle":
            meta = ORACLE_RESOURCES.get(table, {
                "resource": table,
                "pk": pick_pk_column(table, None),
                "docs": ORACLE_DOCS,
            })
            items.append({
                "id": f"oracle.{meta['resource']}",
                "system": "oracle",
                "name": meta["resource"],
                "table": table,
                "schema": schema,
                "rowCount": rows,
                "columnCount": cols,
                "pk": meta.get("pk") or pick_pk_column(table, None),
                "docsUrl": meta.get("docs", ORACLE_DOCS),
                "methods": _oracle_methods(meta["resource"]),
            })
        elif system == "sap":
            meta = SAP_ENTITIES.get(table, {
                "service": "API_GENERIC",
                "entity": table,
                "pk": pick_pk_column(table, None),
            })
            items.append({
                "id": f"sap.{meta['service']}.{meta['entity']}",
                "system": "sap",
                "name": meta["entity"],
                "table": table,
                "schema": schema,
                "service": meta["service"],
                "rowCount": rows,
                "columnCount": cols,
                "pk": meta.get("pk") or pick_pk_column(table, None),
                "docsUrl": SAP_DOCS,
                "methods": _sap_methods(meta["service"], meta["entity"]),
            })
    items.sort(key=lambda i: (-int(i.get("rowCount") or 0), i.get("name") or ""))
    return items
