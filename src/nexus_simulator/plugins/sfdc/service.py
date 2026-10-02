"""
SFDC Simulator Service

Redis-backed FDW simulator for Salesforce CRM data.
Extends BaseSimulatorService for storage, query, and S3 load.
Adds SFDC-specific seed data and live FDW dump.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from loguru import logger

try:
    import boto3  # noqa: F401  - parity with source's import block; used indirectly via BaseSimulator._s3_client
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from ...base import BaseSimulator as BaseSimulatorService

sim_logger = logger.bind(component="sfdc-simulator")


class SFDCSimulatorService(BaseSimulatorService):

    SERVICE_NAME = "sfdc"

    PRIORITY_TABLES = [
        "Account", "Lead", "Opportunity", "Contact",
        "RecordType", "cspmb__Price_Item__c",
        "ContentVersion", "ContentDocumentLink", "Note",
    ]

    def __init__(self, bucket: str = "", prefix: str = ""):
        super().__init__(bucket, prefix)
        # Library port: env-var fallbacks remain so direct construction works;
        # the host typically supplies bucket/prefix via SFDCPluginConfig (build_simulator).
        self.bucket = bucket or os.getenv("SFDC_SIMULATOR_BUCKET", "")
        self.prefix = prefix or os.getenv("SFDC_SIMULATOR_PREFIX", "sfdc-simulator")

    async def seed_data(self) -> dict[str, Any]:
        """Generate synthetic SFDC data and store in Redis."""
        import random as _r

        from .._seed_pools import (
            ACCOUNT_STATUSES,
            BEVERAGE_BRANDS,
            BEVERAGE_CATEGORIES,
            CAMPAIGN_TYPES,
            CHANNEL_TYPES,
            CONTACT_ROLES,
            COUNTRIES,
            OPP_STAGES,
            PACK_SIZES,
            REGIONS,
            TIERS,
            account_ids,
            campaign_ids,
            contact_ids,
            date_str,
            material_ids,
            money,
            opportunity_ids,
            pick,
        )
        _r.seed(42)
        sim_logger.info("Seeding SFDC simulator data")

        SCHEMA = "sfdc_itxp2dev"
        SERVER = "sfdc_simulator"
        data_map: dict[str, list[dict]] = {}

        accounts = []
        for i, aid in enumerate(account_ids):
            accounts.append({
                "Account_ID": aid, "Account_Name": f"Customer {i+1}",
                "Industry": pick(["Food_Beverage", "Retail", "HORECA", "Distribution", "Wholesale"]),
                "Region": pick(REGIONS), "Country": pick(COUNTRIES),
                "Channel_Type": pick(CHANNEL_TYPES), "Tier": pick(TIERS),
                "Annual_Revenue": money(100000, 50000000),
                "Account_Status": pick(ACCOUNT_STATUSES),
                "Credit_Limit": money(10000, 5000000),
            })
        data_map["Account"] = accounts

        contacts = []
        for i, cid in enumerate(contact_ids):
            contacts.append({
                "Contact_ID": cid, "Account_ID": pick(account_ids),
                "First_Name": f"First{i+1}", "Last_Name": f"Last{i+1}",
                "Email": f"contact{i+1}@example.com", "Role": pick(CONTACT_ROLES),
                "Phone": f"+65{_r.randint(80000000, 99999999)}",
            })
        data_map["Contact"] = contacts

        campaigns = []
        for _i, cid in enumerate(campaign_ids):
            campaigns.append({
                "Campaign_ID": cid, "Campaign_Name": f"{pick(BEVERAGE_BRANDS)} {pick(CAMPAIGN_TYPES)} Q{_r.randint(1,4)}",
                "Type": pick(CAMPAIGN_TYPES),
                "Start_Date": date_str(180, 30), "End_Date": date_str(30, 0),
                "Budget": money(5000, 500000), "Status": pick(["Active", "Completed", "Planned"]),
                "Target_Region": pick(REGIONS), "Target_Segment": pick(CHANNEL_TYPES),
            })
        data_map["Campaign"] = campaigns

        opps = []
        for i, oid in enumerate(opportunity_ids):
            opps.append({
                "Opportunity_ID": oid, "Account_ID": pick(account_ids),
                "Opportunity_Name": f"Order-{i+1:04d}",
                "Amount": money(1000, 500000), "Stage": pick(OPP_STAGES),
                "Close_Date": date_str(730, 0), "Region": pick(REGIONS),
                "Product_Category": pick(BEVERAGE_CATEGORIES),
                "Campaign_ID": pick(campaign_ids) if _r.random() > 0.6 else "",
            })
        data_map["Opportunity"] = opps

        line_items = []
        for i in range(1500):
            line_items.append({
                "Line_Item_ID": f"OLI-{i+1:05d}",
                "Opportunity_ID": pick(opportunity_ids), "Product_ID": pick(material_ids),
                "Product_Name": f"{pick(BEVERAGE_BRANDS)} {pick(BEVERAGE_CATEGORIES)} {pick(PACK_SIZES)}",
                "Quantity": _r.randint(10, 10000), "Unit_Price": money(0.5, 50),
                "Total_Price": money(100, 200000), "Discount_Pct": round(_r.uniform(0, 18), 1),
                "Delivery_Priority": pick(["Standard", "Express", "Critical"]),
            })
        data_map["Opportunity_Line_Item"] = line_items

        forecasts = []
        for i in range(500):
            year = _r.choice([2025, 2026])
            forecasts.append({
                "Forecast_ID": f"FC-{i+1:04d}", "Product_ID": pick(material_ids),
                "Region": pick(REGIONS), "Period": f"{year}-W{_r.randint(1,52):02d}",
                "Override_Quantity": _r.randint(100, 50000),
                "Reason": pick(["Promotion", "Seasonal", "Market_Intelligence", "Customer_Request", "Supply_Constraint"]),
                "Justification": pick(["Festive season expected uplift", "New retailer onboarding",
                    "Competitor stock-out in region", "Weather-driven demand spike",
                    "Trade promotion confirmed", "Historical pattern adjustment"]),
                "Submitted_By": f"Planner {_r.randint(1,10)}",
                "Status": pick(["Pending", "Approved", "Approved", "Approved", "Rejected"]),
            })
        data_map["Forecast_Override"] = forecasts

        leads = []
        for i in range(100):
            status = pick(["New", "Contacted", "Qualified", "Converted"])
            leads.append({
                "Lead_ID": f"LD-{i+1:05d}", "First_Name": f"Lead{i+1}", "Last_Name": f"Prospect{i+1}",
                "Company": f"Company {_r.randint(1,200)}", "Email": f"lead{i+1}@prospect.com",
                "Phone": f"+65{_r.randint(80000000, 99999999)}", "Status": status,
                "Lead_Source": pick(["Web", "Referral", "Trade_Show", "Cold_Call", "Partner"]),
                "Industry": pick(["Food_Beverage", "Retail", "HORECA", "Distribution"]),
                "Region": pick(REGIONS), "Annual_Revenue": money(50000, 10000000),
                "Converted_Account_ID": pick(account_ids) if status == "Converted" else "",
            })
        data_map["Lead"] = leads

        from nexus_simulator.plugins.diagnostic_seed import apply_sentinels
        apply_sentinels("sfdc", data_map)

        return await self._finalize_seed(SCHEMA, SERVER, data_map)

    # ─── Dump status (S3-backed for multi-pod consistency) ──────────────

    def _set_dump_status(self, running: bool, result: dict[str, Any] | None = None,
                         step: str | None = None, steps: list[dict] | None = None,
                         tables_done: int = 0, tables_total: int = 0, rows_dumped: int = 0):
        status: dict[str, Any] = {"running": running, "result": result}
        if steps is not None:
            status["steps"] = steps
        if tables_total > 0:
            status["tables_done"] = tables_done
            status["tables_total"] = tables_total
            status["rows_dumped"] = rows_dumped
        if step:
            status["step"] = step
        try:
            s3 = self._s3_client()
            s3.put_object(Bucket=self.bucket, Key=self._s3_key("_dump_status.json"),
                          Body=json.dumps(status, default=str), ContentType="application/json")
        except Exception as e:
            sim_logger.warning(f"Failed to write dump status: {e}")

    def get_dump_status(self) -> dict[str, Any]:
        if not self.bucket:
            return {"running": False, "result": None}
        data = self._s3_get_json("_dump_status.json")
        if data is None:
            return {"running": False, "result": None}
        return data

    async def dump_from_live_fdw(self, source_url: str, schema: str = "sfdc_itxp2dev",
                                  tables: list[str] | None = None, dump_all: bool = False,
                                  limit: int = 10000) -> dict[str, Any]:
        """Query a live FDW runtime and dump metadata + data to S3."""
        import httpx

        if not self.bucket:
            return {"success": False, "message": "SFDC_SIMULATOR_BUCKET not configured"}

        source_url = source_url.rstrip("/")
        sim_logger.info(f"Starting live FDW dump from {source_url}")
        dump_steps: list[dict] = []

        def _add_step(msg: str, status: str = "done"):
            dump_steps.append({"timestamp": datetime.now(timezone.utc).isoformat(), "message": msg, "status": status})

        _add_step(f"Starting dump from {source_url}...", "running")
        self._set_dump_status(True, {"message": "Starting dump..."}, steps=dump_steps)
        start = time.monotonic()
        s3 = self._s3_client()

        def _s3_put(key: str, data: Any):
            s3.put_object(Bucket=self.bucket, Key=self._s3_key(key),
                          Body=json.dumps(data, default=str, indent=2), ContentType="application/json")

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.get(f"{source_url}/api/fdw/servers")
            r.raise_for_status()
            servers = r.json()
            _s3_put("servers.json", servers)
            _add_step(f"Dumped {len(servers)} server(s)")

            _add_step("Fetching table list...", "running")
            r = await client.get(f"{source_url}/api/fdw/tables")
            r.raise_for_status()
            all_tables = r.json()
            _s3_put("tables.json", all_tables)
            _add_step(f"Dumped {len(all_tables)} table(s)")

            tables_in_schema = [t for t in all_tables if t.get("schemaName", t.get("schema_name", "")) == schema]

            _add_step(f"Dumping columns for {len(tables_in_schema)} tables...", "running")
            self._set_dump_status(True, step="Dumping columns", steps=dump_steps, tables_total=len(tables_in_schema))
            col_count = 0
            for t in tables_in_schema:
                tname = t.get("tableName", t.get("table_name", ""))
                try:
                    r = await client.get(f"{source_url}/api/fdw/tables/{schema}/{tname}/columns", timeout=30)
                    r.raise_for_status()
                    _s3_put(f"columns/{schema}.{tname}.json", r.json())
                    col_count += 1
                except Exception as e:
                    sim_logger.warning(f"Columns failed for {schema}.{tname}: {e}")
            _add_step(f"Dumped columns for {col_count} table(s)")

            if tables:
                available = {t.get("tableName", t.get("table_name", "")) for t in tables_in_schema}
                data_table_names = [t for t in tables if t in available]
            else:
                data_table_names = [t.get("tableName", t.get("table_name", "")) for t in tables_in_schema]

            data_manifest: dict[str, int] = {}
            total_data_tables = len(data_table_names)
            _add_step(f"Dumping data for {total_data_tables} tables...", "running")
            self._set_dump_status(True, step="Dumping data", steps=dump_steps, tables_total=total_data_tables)
            for idx, tname in enumerate(data_table_names):
                try:
                    body = {"table": tname, "schemaName": schema, "limit": limit}
                    r = await client.post(f"{source_url}/api/fdw/query", json=body, timeout=120)
                    r.raise_for_status()
                    rows = r.json().get("rows", [])
                    if rows:
                        _s3_put(f"data/{schema}.{tname}.json", rows)
                        data_manifest[tname] = len(rows)
                        _add_step(f"Dumped {tname} — {len(rows):,} rows")
                    else:
                        _add_step(f"Skipped {tname} — 0 rows")
                except Exception as e:
                    _add_step(f"Failed {tname}: {e}", "error")
                self._set_dump_status(True, step=f"Dumping {tname}", steps=dump_steps,
                                      tables_done=idx + 1, tables_total=total_data_tables,
                                      rows_dumped=sum(data_manifest.values()))

            elapsed = time.monotonic() - start
            manifest = {
                "dump_timestamp": datetime.now(timezone.utc).isoformat(), "source_url": source_url,
                "schema": schema, "total_tables": len(tables_in_schema), "tables_with_columns": col_count,
                "tables_with_data": len(data_manifest), "total_rows_dumped": sum(data_manifest.values()),
                "data_tables": data_manifest, "elapsed_seconds": round(elapsed, 1),
            }
            _s3_put("manifest.json", manifest)

        msg = (f"Dump complete — {len(tables_in_schema)} tables, {col_count} columns, "
               f"{len(data_manifest)} with data, {sum(data_manifest.values()):,} rows in {elapsed:.1f}s")
        _add_step(msg)
        result = {"success": True, "message": msg, "tables": len(tables_in_schema),
                  "tables_with_data": len(data_manifest), "total_rows": sum(data_manifest.values()),
                  "elapsed_seconds": round(elapsed, 1)}
        self._set_dump_status(False, result, steps=dump_steps)
        return result
