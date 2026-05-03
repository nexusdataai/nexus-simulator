"""
External Source Simulator Service

Redis-backed simulator for Google Drive, Social Listening, and File Uploads.
Extends BaseSimulatorService for storage, query, and S3 load.
"""

import json
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

try:
    import boto3  # noqa: F401  - parity with source's import block; used indirectly via BaseSimulator._s3_client
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from ...base import BaseSimulator as BaseSimulatorService
from ...models.fdw import (
    ColumnInfo,
)

sim_logger = logger.bind(component="external-simulator")

SCHEMA = "external_sources"
SERVER_NAME = "external_simulator"

TABLE_SYSTEM_MAP = {
    "Contract_Document": "Google_Drive",
    "Sustainability_Report": "Google_Drive",
    "ContentVersion": "Google_Drive",
    "ContentDocumentLink": "Google_Drive",
    "Market_Signal": "Social_Listening",
    "Brand_Sentiment": "Social_Listening",
    "Commodity_Price": "Social_Listening",
    "Invoice_Upload": "File_Uploads",
    "Lab_Report_Upload": "File_Uploads",
}


class ExternalSourceSimulatorService(BaseSimulatorService):

    SERVICE_NAME = "external"
    PRIORITY_TABLES = list(TABLE_SYSTEM_MAP.keys())

    def __init__(self, bucket: str = "", prefix: str = ""):
        super().__init__(bucket, prefix)
        self._refresh_config()

    def _refresh_config(self):
        # Library port: nexus-backend's SSM and config_provider branches dropped;
        # the host supplies bucket/prefix via ExternalSourcePluginConfig.
        if not self.bucket:
            self.bucket = os.getenv("EXTERNAL_SIMULATOR_BUCKET", "")
        if not self.prefix:
            self.prefix = os.getenv("EXTERNAL_SIMULATOR_PREFIX", "external-sources")


    async def ensure_loaded(self):
        if not self._loaded:
            if self.bucket:
                await self.load_from_s3()
            else:
                await self.seed_data()

    async def seed_data(self) -> dict[str, Any]:
        """Generate synthetic external source data and store in Redis."""
        sim_logger.info("Seeding external simulator data")
        random.seed(42)

        data_map: dict[str, list[dict]] = {}

        self._seed_google_drive(data_map)
        self._seed_social_listening(data_map)
        self._seed_file_uploads(data_map)

        return await self._finalize_seed(SCHEMA, SERVER_NAME, data_map)

    def _date(self, days_back_max: int, days_back_min: int = 0) -> str:
        d = datetime.now() - timedelta(days=random.randint(days_back_min, max(days_back_max, days_back_min + 1)))
        return d.strftime("%Y-%m-%d")

    def _datetime_str(self, days_back: int) -> str:
        d = datetime.now(timezone.utc) - timedelta(days=random.randint(0, days_back), hours=random.randint(0, 23))
        return d.isoformat()

    def _money(self, lo: float, hi: float) -> float:
        return round(random.uniform(lo, hi), 2)

    def _pct(self, lo: int, hi: int) -> float:
        return round(random.uniform(lo, hi), 1)

    def _seed_google_drive(self, data_map: dict[str, list[dict]]):
        vendors = [f"VND-{i+1:03d}" for i in range(80)]
        contracts = []
        for i in range(50):
            contracts.append({
                "Contract_ID": f"CTR-{i+1:03d}", "Vendor_ID": random.choice(vendors),
                "Document_Path": f"/contracts/vendor_{i+1}_agreement.pdf",
                "Effective_Date": self._date(365, 60), "Expiry_Date": self._date(0),
                "Contracted_Price": self._money(0.50, 100), "Volume_Commitment": random.randint(1000, 100000),
                "SLA_Terms": random.choice(["99% on-time delivery", "48h response time", "95% fill rate", "Zero defect policy"]),
                "Penalty_Clauses": random.choice(["2% per late day", "5% quality rebate", "Volume shortfall penalty", "None"]),
                "Auto_Renewal": random.choice([True, False]), "Extraction_Confidence": self._pct(70, 99),
            })
        data_map["Contract_Document"] = contracts

        reports = []
        for i in range(20):
            reports.append({
                "Report_ID": f"SR-{i+1:03d}", "Document_Path": f"/sustainability/report_{i+1}.pdf",
                "Report_Type": random.choice(["Annual", "Quarterly", "Audit"]),
                "Period": f"2025-Q{random.randint(1,4)}",
                "KPIs_Extracted": random.choice(["CO2 emissions, Water usage, Recycling rate", "Energy consumption, Waste reduction"]),
                "Targets": random.choice(["30% reduction by 2030", "Carbon neutral by 2035", "100% recyclable packaging"]),
                "Actuals": random.choice(["18% reduction achieved", "45% renewable energy", "72% recyclable packaging"]),
                "Framework": random.choice(["GRI", "SASB", "CDP", "TCFD"]),
            })
        data_map["Sustainability_Report"] = reports

        doc_ids = [f"DOC-{i+1:04d}" for i in range(60)]
        content_versions = []
        for i, did in enumerate(doc_ids):
            content_versions.append({
                "ContentVersion_ID": f"CV-{i+1:04d}", "Document_ID": did,
                "Title": random.choice([f"Vendor Contract {i+1}", f"Sustainability Report Q{random.randint(1,4)}",
                    f"Invoice Scan {i+1}", f"Lab Certificate {i+1}", f"SLA Agreement {i+1}"]),
                "File_Type": random.choice(["pdf", "xlsx", "docx", "pdf", "pdf"]),
                "Version_Number": random.randint(1, 5), "Created_Date": self._date(365, 0),
                "File_Size_KB": random.randint(50, 5000),
                "Description": random.choice(["Vendor agreement", "Quarterly report", "Compliance doc", "Test results", "Contract amendment"]),
                "Owner": f"User {random.randint(1, 20)}",
            })
        data_map["ContentVersion"] = content_versions

        content_links = []
        account_ids = [f"ACC-{i+1:05d}" for i in range(200)]
        vendor_ids_local = [f"VND-{i+1:03d}" for i in range(80)]
        for i in range(80):
            entity_type = random.choice(["Account", "Vendor", "Contract"])
            linked_id = random.choice(account_ids) if entity_type == "Account" else random.choice(vendor_ids_local) if entity_type == "Vendor" else f"CTR-{random.randint(1,50):03d}"
            content_links.append({
                "Link_ID": f"CDL-{i+1:04d}", "Document_ID": random.choice(doc_ids),
                "Linked_Entity_ID": linked_id, "Linked_Entity_Type": entity_type,
                "Share_Type": random.choice(["View", "Edit", "View", "View"]),
                "Created_Date": self._date(180, 0),
            })
        data_map["ContentDocumentLink"] = content_links

    def _seed_social_listening(self, data_map: dict[str, list[dict]]):
        commodities = ["Sugar", "Aluminum", "PET_Resin", "Glass", "CO2", "Concentrate"]
        countries = ["Singapore", "Malaysia", "Thailand", "Indonesia", "Philippines"]
        event_types = ["Supply_Disruption", "Regulatory_Change", "Weather_Event", "Port_Congestion", "Labor_Strike", "Demand_Spike", "Competitor_Action"]
        brands = ["StarFizz", "TropicBurst", "AquaPure", "PowerVolt", "ZenBrew"]
        categories = ["Carbonated", "Juice", "Water", "Energy", "Tea"]
        platforms = ["Twitter_X", "Reddit", "Instagram", "News", "Review_Site", "Industry_Forum"]

        signals = []
        for i in range(200):
            signals.append({
                "Signal_ID": f"MS-{i+1:05d}",
                "Source": random.choice(["News", "Social_Media", "Government", "Weather_Service", "Port_Authority"]),
                "Event_Type": random.choice(event_types), "Location": random.choice(countries),
                "Severity": random.choice(["Low", "Low", "Medium", "Medium", "High", "Critical"]),
                "Affected_Commodity": random.choice(commodities), "Timestamp": self._datetime_str(365),
            })
        data_map["Market_Signal"] = signals

        sentiments = []
        for i in range(200):
            sentiments.append({
                "Sentiment_ID": f"BS-{i+1:05d}", "Brand": random.choice(brands),
                "Product_Category": random.choice(categories), "Platform": random.choice(platforms),
                "Sentiment_Score": round(random.uniform(-1, 1), 3),
                "Topic": random.choice(["Taste", "Packaging", "Price", "Availability", "Sustainability", "Health"]),
                "Mention_Count": random.randint(10, 50000), "Period": f"2025-W{random.randint(1,52):02d}",
            })
        data_map["Brand_Sentiment"] = sentiments

        prices = []
        for i in range(100):
            prices.append({
                "Price_ID": f"CP-{i+1:05d}", "Commodity": random.choice(commodities),
                "Price_Per_Unit": self._money(0.10, 500), "Currency": random.choice(["USD", "SGD"]),
                "Unit": random.choice(["KG", "MT", "L", "EA"]), "Date": self._date(180),
                "Source": random.choice(["Bloomberg", "Reuters", "ICIS", "Platts", "Internal"]),
                "Change_Pct_30D": round(random.uniform(-15, 15), 1),
            })
        data_map["Commodity_Price"] = prices

    def _seed_file_uploads(self, data_map: dict[str, list[dict]]):
        po_ids = [f"PO-{i+1:04d}" for i in range(100)]
        material_ids = [f"MAT-{i+1:05d}" for i in range(300)]
        batch_ids = [f"BAT-{i+1:05d}" for i in range(200)]

        invoices = []
        for i in range(50):
            invoices.append({
                "Upload_ID": f"IU-{i+1:04d}", "File_Path": f"/uploads/invoices/invoice_{i+1}.pdf",
                "Vendor_Name_Extracted": f"Vendor {random.randint(1,80)}",
                "Invoice_Number_Extracted": f"EXT-INV-{random.randint(10000,99999)}",
                "Amount_Extracted": self._money(100, 200000),
                "Line_Items": f"{random.randint(1,20)} items extracted",
                "Extraction_Confidence": self._pct(60, 99),
                "Matched_PO_ID": random.choice(po_ids),
                "Validation_Status": random.choice(["Pending", "Validated", "Needs_Review", "Rejected"]),
            })
        data_map["Invoice_Upload"] = invoices

        labs = []
        for i in range(30):
            labs.append({
                "Upload_ID": f"LR-{i+1:04d}", "File_Path": f"/uploads/lab_reports/lab_{i+1}.pdf",
                "Material_ID": random.choice(material_ids), "Batch_ID": random.choice(batch_ids),
                "Tests_Extracted": f"{random.randint(3,15)} tests",
                "Results": random.choice(["All pass", "2 deviations noted", "1 failure - microbial", "All within spec"]),
                "Spec_Compliance": random.choice([True, True, True, False]),
                "Extraction_Confidence": self._pct(65, 99),
                "Inspector_Name": f"Inspector {random.randint(1,20)}",
            })
        data_map["Lab_Report_Upload"] = labs

    # ─── Extra methods specific to External simulator ────────────────────

    async def save_to_s3(self) -> dict[str, Any]:
        """Persist current state back to S3 so other pods can load it."""
        if not self.bucket:
            return {"success": False, "message": "No S3 bucket configured"}

        s3 = self._s3_client()
        prefix = self.prefix.rstrip("/") + "/"

        tables_json = [{"schemaName": t.schema_name, "tableName": t.table_name,
                         "serverName": t.server_name, "columnCount": t.column_count} for t in self._tables]

        servers_json = [{"serverName": sv.server_name, "wrapperType": sv.wrapper_type,
                         "serverOptions": sv.server_options} for sv in self._servers]

        manifest = {"total_tables": len(tables_json), "dump_timestamp": datetime.now(timezone.utc).isoformat(), "source": "save_to_s3"}

        s3.put_object(Bucket=self.bucket, Key=f"{prefix}manifest.json", Body=json.dumps(manifest), ContentType="application/json")
        s3.put_object(Bucket=self.bucket, Key=f"{prefix}servers.json", Body=json.dumps(servers_json), ContentType="application/json")
        s3.put_object(Bucket=self.bucket, Key=f"{prefix}tables.json", Body=json.dumps(tables_json), ContentType="application/json")

        rows_saved = 0
        for t in self._tables:
            schema, tname = t.schema_name, t.table_name
            rows = await self._get_table_data(schema, tname)
            if rows:
                s3.put_object(Bucket=self.bucket, Key=f"{prefix}data/{schema}.{tname}.json",
                              Body=json.dumps(rows, default=str), ContentType="application/json")
                rows_saved += len(rows)

                cols = self._columns.get((schema, tname), [])
                if not cols and rows:
                    cols = [ColumnInfo(column_name=k, data_type="text", is_nullable=True, ordinal_position=i)
                            for i, k in enumerate(rows[0].keys())]
                col_json = [{"columnName": c.column_name, "dataType": c.data_type,
                             "isNullable": c.is_nullable, "ordinalPosition": c.ordinal_position} for c in cols]
                s3.put_object(Bucket=self.bucket, Key=f"{prefix}columns/{schema}.{tname}.json",
                              Body=json.dumps(col_json), ContentType="application/json")

        sim_logger.info(f"Saved {len(tables_json)} tables, {rows_saved} rows to S3")
        return {"success": True, "tables": len(tables_json), "rows": rows_saved}

    async def insert_row(self, table_name: str, row: dict) -> None:
        """Insert a row into a table (updates Redis)."""
        rows = await self._get_table_data(SCHEMA, table_name)
        rows.append(row)
        await self._store_table(SCHEMA, table_name, rows)
        sim_logger.info(f"Inserted row into {table_name}, total now {len(rows)}")

    async def next_id(self, table_name: str, prefix: str) -> str:
        rows = await self._get_table_data(SCHEMA, table_name)
        max_num = 0
        for r in rows:
            for v in r.values():
                s = str(v)
                if s.startswith(prefix):
                    try:
                        num = int(s[len(prefix):])
                        max_num = max(max_num, num)
                    except ValueError:
                        pass
                    break
        return f"{prefix}{max_num + 1:04d}"
