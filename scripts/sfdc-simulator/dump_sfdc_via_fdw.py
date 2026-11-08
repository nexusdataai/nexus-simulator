#!/usr/bin/env python3
"""
SFDC Data Dump via FDW Runtime

Calls the deployed FDW REST API (via ALB) to dump all foreign table metadata
and record data, then uploads to S3 for the SFDC simulator.

Usage:
    # Auto-detect ALB from kubectl ingress
    python dump_sfdc_via_fdw.py --auto-detect --s3-bucket my-bucket

    # Explicit ALB URL, priority tables only
    python dump_sfdc_via_fdw.py --url http://k8s-xxx.elb.amazonaws.com --s3-bucket my-bucket

    # Dump specific tables
    python dump_sfdc_via_fdw.py --url http://... --tables Account,Lead,RecordType --s3-bucket my-bucket

    # Dump ALL tables (slow)
    python dump_sfdc_via_fdw.py --url http://... --all --s3-bucket my-bucket

    # Local-only dump (no S3 upload)
    python dump_sfdc_via_fdw.py --url http://... --local-dir ./sfdc-dump
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

PRIORITY_TABLES = [
    "Account", "Lead", "Opportunity", "Contact",
    "RecordType",
    "cspmb__Price_Item__c",
    "ContentVersion", "ContentDocumentLink",
    "Note",
]

DEFAULT_SCHEMA = "sfdc_schema"
DEFAULT_PREFIX = "sfdc-simulator"
DEFAULT_LIMIT = 10000


def detect_alb_url(namespace: Optional[str] = None) -> str:
    """Auto-detect ALB hostname from kubectl get ingress."""
    cmd = ["kubectl", "get", "ingress"]
    if namespace:
        cmd.extend(["-n", namespace])
    else:
        cmd.extend(["--all-namespaces"])
    cmd.extend(["-o", "jsonpath={.items[0].status.loadBalancer.ingress[0].hostname}"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        hostname = result.stdout.strip()
        if not hostname:
            print("ERROR: Could not detect ALB hostname from kubectl ingress")
            sys.exit(1)
        url = f"http://{hostname}"
        print(f"  Auto-detected ALB URL: {url}")
        return url
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"ERROR: kubectl not available or timed out: {e}")
        sys.exit(1)


def fdw_get(base_url: str, path: str, timeout: int = 60) -> dict:
    """GET request to FDW API."""
    url = f"{base_url}{path}"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fdw_post(base_url: str, path: str, body: dict, timeout: int = 120) -> dict:
    """POST request to FDW API."""
    url = f"{base_url}{path}"
    resp = requests.post(url, json=body, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def dump_servers(base_url: str) -> list:
    """Dump foreign servers."""
    print("  Fetching foreign servers...")
    data = fdw_get(base_url, "/api/fdw/servers")
    print(f"    Found {len(data)} server(s)")
    return data


def dump_tables(base_url: str, server_name: Optional[str] = None) -> list:
    """Dump foreign tables list."""
    path = "/api/fdw/tables"
    if server_name:
        path += f"?server={server_name}"
    print(f"  Fetching foreign tables{f' for server {server_name}' if server_name else ''}...")
    data = fdw_get(base_url, path)
    print(f"    Found {len(data)} table(s)")
    return data


def dump_columns(base_url: str, schema: str, table: str) -> list:
    """Dump column metadata for a single table."""
    path = f"/api/fdw/tables/{schema}/{table}/columns"
    try:
        return fdw_get(base_url, path, timeout=30)
    except Exception as e:
        print(f"    WARNING: Failed to get columns for {schema}.{table}: {e}")
        return []


def dump_table_data(base_url: str, schema: str, table: str, limit: int = DEFAULT_LIMIT) -> dict:
    """Dump record data for a single table via FDW query."""
    body = {
        "table": table,
        "schemaName": schema,
        "limit": limit,
    }
    try:
        result = fdw_post(base_url, "/api/fdw/query", body, timeout=120)
        row_count = result.get("metadata", {}).get("rowCount", len(result.get("rows", [])))
        return {"rows": result.get("rows", []), "row_count": row_count}
    except Exception as e:
        print(f"    WARNING: Failed to query {schema}.{table}: {e}")
        return {"rows": [], "row_count": 0, "error": str(e)}


def upload_to_s3(bucket: str, prefix: str, key: str, data: dict, profile: Optional[str] = None):
    """Upload JSON data to S3."""
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    s3 = session.client("s3")
    full_key = f"{prefix}/{key}" if prefix else key
    s3.put_object(
        Bucket=bucket,
        Key=full_key,
        Body=json.dumps(data, default=str, indent=2),
        ContentType="application/json",
    )


def save_local(local_dir: str, key: str, data):
    """Save JSON data to local file."""
    path = Path(local_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, default=str, indent=2)


def run_dump(args):
    if not REQUESTS_AVAILABLE:
        print("ERROR: 'requests' library required. pip install requests")
        sys.exit(1)

    base_url = args.url
    if args.auto_detect:
        base_url = detect_alb_url(args.namespace)

    if not base_url:
        print("ERROR: Must provide --url or --auto-detect")
        sys.exit(1)

    base_url = base_url.rstrip("/")
    schema = args.schema
    use_s3 = bool(args.s3_bucket)
    use_local = bool(args.local_dir)

    if use_s3 and not BOTO3_AVAILABLE:
        print("ERROR: 'boto3' library required for S3 upload. pip install boto3")
        sys.exit(1)

    if not use_s3 and not use_local:
        print("ERROR: Must provide --s3-bucket or --local-dir")
        sys.exit(1)

    def save(key: str, data):
        if use_s3:
            upload_to_s3(args.s3_bucket, args.s3_prefix, key, data, args.aws_profile)
        if use_local:
            save_local(args.local_dir, key, data)

    start_time = time.time()
    print(f"\n{'='*60}")
    print(f"  SFDC Data Dump via FDW Runtime")
    print(f"  Target: {base_url}")
    print(f"  Schema: {schema}")
    if use_s3:
        print(f"  S3: s3://{args.s3_bucket}/{args.s3_prefix}/")
    if use_local:
        print(f"  Local: {args.local_dir}")
    print(f"{'='*60}\n")

    # 1. Dump servers
    servers = dump_servers(base_url)
    save("servers.json", servers)

    # 2. Dump tables list
    tables = dump_tables(base_url)
    save("tables.json", tables)

    table_names_in_schema = [
        t for t in tables
        if t.get("schemaName", t.get("schema_name", "")) == schema
    ]
    print(f"  Tables in schema '{schema}': {len(table_names_in_schema)}")

    # 3. Dump column metadata for all tables in schema
    print(f"\n  Dumping column metadata for {len(table_names_in_schema)} tables...")
    columns_manifest = {}
    for i, tbl in enumerate(table_names_in_schema):
        tname = tbl.get("tableName", tbl.get("table_name", ""))
        cols = dump_columns(base_url, schema, tname)
        key = f"columns/{schema}.{tname}.json"
        save(key, cols)
        columns_manifest[tname] = len(cols)
        if (i + 1) % 100 == 0:
            print(f"    ... {i+1}/{len(table_names_in_schema)} tables done")

    print(f"    Column metadata dumped for {len(columns_manifest)} tables")

    # 4. Dump record data for selected tables
    if args.all:
        data_tables = [
            t.get("tableName", t.get("table_name", ""))
            for t in table_names_in_schema
        ]
        print(f"\n  Dumping ALL table data ({len(data_tables)} tables)...")
    elif args.tables:
        data_tables = [t.strip() for t in args.tables.split(",")]
        print(f"\n  Dumping data for {len(data_tables)} specified tables...")
    else:
        available = {
            t.get("tableName", t.get("table_name", ""))
            for t in table_names_in_schema
        }
        data_tables = [t for t in PRIORITY_TABLES if t in available]
        missing = [t for t in PRIORITY_TABLES if t not in available]
        if missing:
            print(f"  Note: Priority tables not found in schema: {missing}")
        print(f"\n  Dumping data for {len(data_tables)} priority tables...")

    data_manifest = {}
    for i, tname in enumerate(data_tables):
        print(f"    [{i+1}/{len(data_tables)}] {schema}.{tname} ...", end=" ", flush=True)
        result = dump_table_data(base_url, schema, tname, args.limit)
        row_count = result["row_count"]
        print(f"{row_count} rows")
        key = f"data/{schema}.{tname}.json"
        save(key, result["rows"])
        data_manifest[tname] = row_count

    # 5. Write manifest
    elapsed = time.time() - start_time
    manifest = {
        "dump_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_url": base_url,
        "schema": schema,
        "total_tables": len(table_names_in_schema),
        "tables_with_columns": len(columns_manifest),
        "tables_with_data": len(data_manifest),
        "total_rows_dumped": sum(data_manifest.values()),
        "data_tables": data_manifest,
        "elapsed_seconds": round(elapsed, 1),
    }
    save("manifest.json", manifest)

    print(f"\n{'='*60}")
    print(f"  Dump complete!")
    print(f"  Tables: {len(table_names_in_schema)} schemas, {len(data_manifest)} data")
    print(f"  Rows: {sum(data_manifest.values()):,}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Dump SFDC data via FDW Runtime API")
    parser.add_argument("--url", help="ALB URL of deployed FDW runtime")
    parser.add_argument("--auto-detect", action="store_true", help="Auto-detect ALB URL from kubectl ingress")
    parser.add_argument("--namespace", help="Kubernetes namespace for auto-detect")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, help=f"Schema to dump (default: {DEFAULT_SCHEMA})")
    parser.add_argument("--tables", help="Comma-separated table names to dump data for")
    parser.add_argument("--all", action="store_true", help="Dump data for ALL tables")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Max rows per table (default: {DEFAULT_LIMIT})")
    parser.add_argument("--s3-bucket", help="S3 bucket for upload")
    parser.add_argument("--s3-prefix", default=DEFAULT_PREFIX, help=f"S3 prefix (default: {DEFAULT_PREFIX})")
    parser.add_argument("--aws-profile", default=os.getenv("AWS_PROFILE", "external-access"), help="AWS profile")
    parser.add_argument("--local-dir", help="Local directory to save dump (alternative to S3)")

    args = parser.parse_args()
    run_dump(args)


if __name__ == "__main__":
    main()
