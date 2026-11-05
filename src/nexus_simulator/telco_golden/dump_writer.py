"""Write filesystem dumps for telco golden (and optional BSS/NSS/OSS)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def write_table_dump(
    dumps_root: Path,
    *,
    prefix: str,
    schema: str,
    server: str,
    tables: Dict[str, List[dict]],
) -> Path:
    root = Path(dumps_root) / prefix
    root.mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(exist_ok=True)
    (root / "columns").mkdir(exist_ok=True)

    table_meta = []
    total_rows = 0
    for table, rows in tables.items():
        total_rows += len(rows)
        data_path = root / "data" / f"{schema}.{table}.json"
        data_path.write_text(json.dumps(rows, default=str), encoding="utf-8")
        cols = []
        if rows:
            for i, key in enumerate(rows[0].keys()):
                cols.append(
                    {
                        "columnName": key,
                        "dataType": "text",
                        "isNullable": True,
                        "ordinalPosition": i + 1,
                    }
                )
        (root / "columns" / f"{schema}.{table}.json").write_text(
            json.dumps(cols), encoding="utf-8"
        )
        table_meta.append(
            {
                "schemaName": schema,
                "tableName": table,
                "serverName": server,
                "rowCount": len(rows),
            }
        )

    servers = [{"serverName": server, "schemaName": schema}]
    (root / "servers.json").write_text(json.dumps(servers), encoding="utf-8")
    (root / "tables.json").write_text(json.dumps(table_meta), encoding="utf-8")
    manifest: Dict[str, Any] = {
        "prefix": prefix,
        "schema": schema,
        "server": server,
        "dump_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_tables": len(tables),
        "total_rows_dumped": total_rows,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return root
