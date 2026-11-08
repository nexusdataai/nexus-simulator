"""``BaseSimulator`` — Redis-backed FDW simulator with S3 load + in-memory fallback.

Verbatim semantic port of
[`nexus-backend/src/services/base_simulator_service.py`](../../../../nexus-backend/src/services/base_simulator_service.py).
The port substitutes the module-level ``redis_client`` and ad-hoc boto3
calls for the ``StorageBackend`` and ``CacheBackend`` ports defined in
``nexus_simulator.contracts``. Every branch, guard, log message, and
early-return is preserved.

Data flow::

    S3 JSON dumps  -->  load_from_s3()  -->  CacheBackend (or fallback dict)
    seed_data()    -->  _store_table()  -->  CacheBackend (or fallback dict)
    execute_query() <--  _get_table_data() <-- CacheBackend (or fallback dict)
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from loguru import logger

from ..models.fdw import (
    ColumnInfo,
    ForeignServerInfo,
    ForeignTableInfo,
    QueryMetadata,
    QueryRequest,
    QueryResponse,
)

if TYPE_CHECKING:
    from ..contracts import CacheBackend, StorageBackend


class BaseSimulator(ABC):
    """Redis-backed FDW simulator with S3 load and in-memory fallback.

    Subclasses set ``SERVICE_NAME`` and ``PRIORITY_TABLES`` and override
    ``seed_data`` to generate synthetic data via ``self._store_table``.
    """

    SERVICE_NAME: str = "base"
    PRIORITY_TABLES: list[str] = []

    def __init__(
        self,
        bucket: str = "",
        prefix: str = "",
        *,
        storage: StorageBackend | None = None,
        cache: CacheBackend | None = None,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix
        self.enabled = True

        self._storage = storage
        self._cache = cache

        self._servers: list[ForeignServerInfo] = []
        self._tables: list[ForeignTableInfo] = []
        self._columns: dict[tuple[str, str], list[ColumnInfo]] = {}
        self._manifest: dict[str, Any] = {}
        self._loaded = False
        self._loaded_at: datetime | None = None
        self._load_status: dict[str, Any] = {"running": False, "steps": [], "result": None}
        self._tables_with_data: int = 0
        self._total_rows: int = 0
        self._sim_logger = logger.bind(component=f"{self.SERVICE_NAME}-simulator")

    # ─── Cache / storage access guards ────────────────────────────────────

    @property
    def cache(self) -> CacheBackend:
        if self._cache is None:
            raise RuntimeError(
                f"{type(self).__name__}: no CacheBackend wired. "
                "Construct via build_simulator(SimulatorConfig(...))."
            )
        return self._cache

    @property
    def storage(self) -> StorageBackend | None:
        return self._storage

    # ─── Direct-boto3 escape hatches ─────────────────────────────────────
    # FDW-style plugins ported verbatim from nexus-backend (SFDC, Oracle ERP,
    # SAP, External) sometimes call ``self._s3_client()`` / ``self._s3_get_json()``
    # synchronously, especially in code paths that pre-existed before the
    # async StorageBackend port. These helpers preserve that surface so the
    # ports stay verbatim.

    def _s3_client(self) -> Any:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError(
                "boto3 is not installed. Install nexus-simulator[aws] for direct-boto3 access."
            ) from exc
        return boto3.client("s3", region_name=getattr(self, "region", None))

    def _s3_key(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    def _s3_get_json(self, key: str) -> Any:
        import json

        s3 = self._s3_client()
        full_key = self._s3_key(key)
        try:
            resp = s3.get_object(Bucket=self.bucket, Key=full_key)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - mirrors backend's broad except
            self._sim_logger.warning(f"Failed to load s3://{self.bucket}/{full_key}: {e}")
            return None

    # ─── Status ──────────────────────────────────────────────────────────

    @property
    def loaded(self) -> bool:
        return self._loaded

    async def ensure_loaded(self) -> None:
        rebuilt = await self.rebuild_catalog_from_cache()
        if rebuilt:
            return
        if not self._loaded and self.bucket:
            await self.load_from_s3()
            await self.rebuild_catalog_from_cache()
        elif self._loaded and self._tables:
            sample = self._tables[0]
            count = await self._get_table_row_count(sample.schema_name, sample.table_name)
            if count == 0 and self._total_rows > 0:
                self._sim_logger.warning("Cache data expired, reloading from S3")
                await self.load_from_s3()
                await self.rebuild_catalog_from_cache()

    # ─── Cache key layout ────────────────────────────────────────────────

    def _redis_key(self, schema: str, table: str) -> str:
        return f"sim:{self.SERVICE_NAME}:{schema}.{table}"

    def _redis_count_key(self, schema: str, table: str) -> str:
        return f"sim:{self.SERVICE_NAME}:count:{schema}.{table}"

    def _redis_meta_key(self, kind: str) -> str:
        return f"sim:{self.SERVICE_NAME}:meta:{kind}"

    async def _store_table(self, schema: str, table: str, rows: list[dict]) -> None:
        """Store table data + row count in cache (or fallback)."""
        key = self._redis_key(schema, table)
        count_key = self._redis_count_key(schema, table)
        await self.cache.set_json(key, rows)
        await self.cache.set(count_key, str(len(rows)))

    async def _get_table_data(self, schema: str, table: str) -> list[dict]:
        """Retrieve table data from cache (or fallback)."""
        key = self._redis_key(schema, table)
        data = await self.cache.get_json(key)
        return data if isinstance(data, list) else []

    async def _get_table_row_count(self, schema: str, table: str) -> int:
        """Get row count from lightweight count key (no JSON deserialization)."""
        count_key = self._redis_count_key(schema, table)
        raw = await self.cache.get(count_key)
        if raw is not None:
            try:
                return int(raw)
            except (ValueError, TypeError):
                pass
        return 0

    async def _get_all_row_counts(self) -> dict[str, int]:
        """Batch-read all row counts in a single MGET (O(1) round-trip)."""
        if not self._tables:
            return {}
        count_keys = [self._redis_count_key(t.schema_name, t.table_name) for t in self._tables]
        values = await self.cache.mget(count_keys)
        counts: dict[str, int] = {}
        for i, t in enumerate(self._tables):
            key = f"{t.schema_name}.{t.table_name}"
            try:
                counts[key] = int(values[i]) if values[i] is not None else 0
            except (ValueError, TypeError):
                counts[key] = 0
        return counts

    async def rebuild_catalog_from_cache(self) -> bool:
        """Rebuild the FDW catalogue from Redis keys already populated.

        Journey processors and prior ontology seeds write extra tables into
        the shared Redis. The in-memory ``_tables`` list must pick those up
        or the UI/FDW APIs only show the last seed subset.
        """
        scan = getattr(self._cache, "scan_keys", None) if self._cache is not None else None
        if scan is None:
            return bool(self._tables)
        prefix = f"sim:{self.SERVICE_NAME}:"
        try:
            keys = await scan(f"{prefix}*")
        except Exception as exc:
            self._sim_logger.warning(f"catalog scan failed: {exc}")
            return bool(self._tables)

        count_prefix = f"{prefix}count:"
        meta_prefix = f"{prefix}meta:"
        discovered: list[tuple[str, str]] = []
        for key in keys:
            if key.startswith(count_prefix) or key.startswith(meta_prefix):
                continue
            rest = key[len(prefix) :]
            if "." not in rest:
                continue
            schema, table = rest.split(".", 1)
            if schema and table:
                discovered.append((schema, table))
        if not discovered:
            return bool(self._tables)

        server = (
            self._servers[0].server_name
            if self._servers
            else self._manifest.get("server_name", f"{self.SERVICE_NAME}_simulator")
        )
        if not self._servers:
            self._servers = [
                ForeignServerInfo(server_name=server, wrapper_type="simulator", server_options={})
            ]

        known = {(t.schema_name, t.table_name) for t in self._tables}
        for schema, table in discovered:
            if (schema, table) in known:
                continue
            rows = await self._get_table_data(schema, table)
            self._tables.append(
                ForeignTableInfo(
                    schema_name=schema,
                    table_name=table,
                    server_name=server,
                    column_count=len(rows[0]) if rows else 0,
                )
            )
            if rows:
                self._auto_register_columns(schema, table, rows[0])
            known.add((schema, table))

        counts = await self._get_all_row_counts()
        self._tables_with_data = sum(1 for n in counts.values() if n > 0)
        self._total_rows = sum(counts.values())
        self._loaded = True
        if self._loaded_at is None:
            self._loaded_at = datetime.now(timezone.utc)
        schema = discovered[0][0] if discovered else self._manifest.get("schema", "")
        self._manifest = {
            **self._manifest,
            "schema": schema or self._manifest.get("schema", ""),
            "total_tables": len(self._tables),
            "total_rows_dumped": self._total_rows,
            "dump_timestamp": self._manifest.get("dump_timestamp")
            or (self._loaded_at.isoformat() if self._loaded_at else None),
        }
        self._sim_logger.info(
            f"{self.SERVICE_NAME} catalog rebuilt from cache — "
            f"{len(self._tables)} tables, {self._tables_with_data} with data, "
            f"{self._total_rows:,} rows"
        )
        return True

    # ─── Load status tracking ────────────────────────────────────────────

    def _log_load_step(self, message: str, status: str = "done") -> None:
        step = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "status": status,
        }
        self._load_status["steps"].append(step)

    def get_load_status(self) -> dict[str, Any]:
        return dict(self._load_status)

    # ─── S3 bulk load ────────────────────────────────────────────────────

    async def load_from_s3(self) -> dict[str, Any]:
        """Download S3 dump and store in cache."""
        self._load_status = {"running": True, "steps": [], "result": None}
        self._log_load_step("Starting load from S3...", "running")
        self._sim_logger.info(
            f"Loading {self.SERVICE_NAME} simulator data from S3",
            bucket=self.bucket,
            prefix=self.prefix,
        )
        start = time.monotonic()

        if self._storage is None:
            result = {"success": False, "message": "No StorageBackend wired"}
            self._load_status["result"] = result
            self._load_status["running"] = False
            return result

        try:
            self._servers = []
            self._tables = []
            self._columns = {}

            self._log_load_step("Loading manifest.json...", "running")
            manifest = await self._storage.get_json("manifest.json")
            if manifest is None:
                self._log_load_step("manifest.json not found in S3", "error")
                result = {"success": False, "message": "manifest.json not found in S3"}
                self._load_status["result"] = result
                return result
            self._manifest = manifest
            self._log_load_step(
                f"Found manifest — {manifest.get('total_tables', '?')} tables, "
                f"dumped {manifest.get('dump_timestamp', 'unknown')}"
            )

            self._log_load_step("Loading servers.json...", "running")
            servers_raw = await self._storage.get_json("servers.json")
            if servers_raw:
                for s in servers_raw:
                    self._servers.append(
                        ForeignServerInfo(
                            server_name=s.get("serverName", s.get("server_name", "")),
                            wrapper_type=s.get("wrapperType", s.get("wrapper_type", "")),
                            server_options=s.get("serverOptions", s.get("server_options", {})),
                        )
                    )
            self._log_load_step(f"Loaded {len(self._servers)} server(s)")

            self._log_load_step("Loading tables.json...", "running")
            tables_raw = await self._storage.get_json("tables.json")
            if tables_raw:
                for t in tables_raw:
                    schema = t.get("schemaName", t.get("schema_name", ""))
                    tname = t.get("tableName", t.get("table_name", ""))
                    self._tables.append(
                        ForeignTableInfo(
                            schema_name=schema,
                            table_name=tname,
                            server_name=t.get("serverName", t.get("server_name", "")),
                            column_count=t.get("columnCount", t.get("column_count", 0)),
                        )
                    )
            self._log_load_step(f"Loaded {len(self._tables)} table(s)")

            self._log_load_step("Loading column metadata...", "running")
            try:
                col_keys = await self._storage.list_keys("columns/")
                for key in col_keys:
                    filename = key.split("/")[-1]
                    if not filename.endswith(".json"):
                        continue
                    parts = filename.replace(".json", "").split(".", 1)
                    if len(parts) != 2:
                        continue
                    schema, tname = parts
                    raw = await self._storage.get_json(key)
                    if raw is None:
                        continue
                    cols = [
                        ColumnInfo(
                            column_name=c.get("columnName", c.get("column_name", "")),
                            data_type=c.get("dataType", c.get("data_type", "")),
                            is_nullable=c.get("isNullable", c.get("is_nullable", True)),
                            ordinal_position=c.get("ordinalPosition", c.get("ordinal_position", 0)),
                        )
                        for c in raw
                    ]
                    self._columns[(schema, tname)] = cols
            except Exception as e:  # noqa: BLE001
                self._sim_logger.warning(f"Error loading column metadata: {e}")
            self._log_load_step(f"Loaded columns for {len(self._columns)} table(s)")

            self._log_load_step("Loading data files into cache...", "running")
            total_rows = 0
            tables_loaded = 0
            try:
                data_keys = await self._storage.list_keys("data/")
                for key in data_keys:
                    filename = key.split("/")[-1]
                    if not filename.endswith(".json"):
                        continue
                    parts = filename.replace(".json", "").split(".", 1)
                    if len(parts) != 2:
                        continue
                    schema, tname = parts
                    raw = await self._storage.get_json(key)
                    if isinstance(raw, list):
                        rows = raw
                    elif isinstance(raw, dict) and "rows" in raw:
                        rows = raw["rows"]
                    else:
                        rows = []
                    await self._store_table(schema, tname, rows)
                    total_rows += len(rows)
                    tables_loaded += 1

                    known_tables = {(t.schema_name, t.table_name) for t in self._tables}
                    if (schema, tname) not in known_tables:
                        self._tables.append(
                            ForeignTableInfo(
                                schema_name=schema,
                                table_name=tname,
                                server_name=self._manifest.get(
                                    "server_name", f"{self.SERVICE_NAME}_simulator"
                                ),
                                column_count=len(rows[0]) if rows else 0,
                            )
                        )
                        if rows and (schema, tname) not in self._columns:
                            self._auto_register_columns(schema, tname, rows[0])
            except Exception as e:  # noqa: BLE001
                self._sim_logger.warning(f"Error loading data files: {e}")

            self._log_load_step(
                f"Stored data for {tables_loaded} table(s), {total_rows:,} total rows in cache"
            )

            elapsed = time.monotonic() - start
            self._loaded = True
            self._loaded_at = datetime.now(timezone.utc)
            self._tables_with_data = tables_loaded
            self._total_rows = total_rows
            await self.rebuild_catalog_from_cache()

            tables_with_data = self._tables_with_data
            total_rows = self._total_rows
            msg = (
                f"Load complete — {len(self._tables)} tables, {tables_with_data} with data, "
                f"{total_rows:,} rows in {elapsed:.1f}s"
            )
            self._log_load_step(msg)
            result = {
                "success": True,
                "message": msg,
                "tables": len(self._tables),
                "tables_with_data": tables_with_data,
                "total_rows": total_rows,
            }
            self._load_status["result"] = result
            return result
        except Exception as e:  # noqa: BLE001
            self._sim_logger.error(f"{self.SERVICE_NAME} load_from_s3 failed: {e}")
            self._log_load_step(f"Load failed: {e}", "error")
            result = {"success": False, "message": str(e)}
            self._load_status["result"] = result
            return result
        finally:
            self._load_status["running"] = False

    def _auto_register_columns(self, schema: str, tname: str, sample_row: dict) -> None:
        cols = []
        for idx, (k, v) in enumerate(sample_row.items()):
            dt = "text"
            if isinstance(v, bool):
                dt = "boolean"
            elif isinstance(v, int):
                dt = "integer"
            elif isinstance(v, float):
                dt = "numeric"
            cols.append(
                ColumnInfo(column_name=k, data_type=dt, is_nullable=True, ordinal_position=idx + 1)
            )
        self._columns[(schema, tname)] = cols

    async def reset(self) -> dict[str, Any]:
        await self.cache.flush_prefix(f"sim:{self.SERVICE_NAME}:")
        if self.bucket:
            return await self.load_from_s3()
        return await self.seed_data()

    @abstractmethod
    async def seed_data(self) -> dict[str, Any]:
        """Generate synthetic data. Subclasses must call ``self._store_table()`` for each table."""
        ...

    # ─── Status ──────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        prefix = self.prefix or ""
        files_prefix = f"{prefix}/files".rstrip("/") if prefix else ""
        return {
            "enabled": self.enabled,
            "loaded": self._loaded,
            "bucket": self.bucket,
            "prefix": prefix,
            "table_data_prefix": prefix,
            "files_data_prefix": files_prefix,
            "schema": self._manifest.get("schema", ""),
            "table_count": len(self._tables),
            "tables_with_data": self._tables_with_data,
            "total_rows": self._total_rows,
            "file_count": 0,
            "api_count": 0,
            "stream_count": 0,
            "dump_timestamp": self._manifest.get("dump_timestamp"),
            "last_loaded": self._loaded_at.isoformat() if self._loaded_at else None,
        }

    # ─── FDWDiscoveryService-compatible interface ────────────────────────

    async def list_foreign_servers(self) -> list[ForeignServerInfo]:
        return self._servers

    async def list_foreign_tables(
        self, server_name: str | None = None
    ) -> list[ForeignTableInfo]:
        if server_name:
            return [t for t in self._tables if t.server_name == server_name]
        return self._tables

    async def get_table_columns(self, schema: str, table: str) -> list[ColumnInfo]:
        return self._columns.get((schema, table), [])

    async def refresh_cache(self) -> None:  # noqa: B027 - intentional no-op default; subclasses override
        pass

    # ─── FDWQueryService-compatible interface ────────────────────────────

    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """Execute a query against cache-backed data."""
        start = time.monotonic()
        schema = request.schema_name
        table = request.table

        rows = await self._get_table_data(schema, table)

        if request.filters:
            for filt in request.filters:
                col = filt.column
                op = filt.operator.value if hasattr(filt.operator, "value") else str(filt.operator)
                val = filt.value
                rows = [r for r in rows if self._match_filter(r, col, op, val)]

        if request.columns:
            rows = [{c: r.get(c) for c in request.columns} for r in rows]

        if request.order_by:
            for ob in reversed(request.order_by):
                reverse = ob.direction.lower() == "desc"
                rows = sorted(
                    rows,
                    key=lambda r, c=ob.column: (r.get(c) is None, r.get(c)),
                    reverse=reverse,
                )

        if request.offset:
            rows = rows[request.offset:]
        if request.limit:
            rows = rows[: request.limit]

        elapsed_ms = (time.monotonic() - start) * 1000
        metadata = QueryMetadata(
            duration_ms=round(elapsed_ms, 2),
            table_queried=f"{schema}.{table}",
            row_count=len(rows),
        )
        return QueryResponse(rows=rows, metadata=metadata)

    async def write_table(self, schema: str, table: str, rows: list[dict]) -> int:
        """Replace table contents and register the table in the FDW catalogue."""
        rows = list(rows or [])
        await self._store_table(schema, table, rows)
        if rows:
            known = {(t.schema_name, t.table_name) for t in self._tables}
            if (schema, table) not in known:
                self._tables.append(
                    ForeignTableInfo(
                        schema_name=schema,
                        table_name=table,
                        server_name=self._manifest.get("server_name", f"{self.SERVICE_NAME}_simulator"),
                        column_count=len(rows[0]),
                    )
                )
            if (schema, table) not in self._columns:
                self._columns[(schema, table)] = [
                    ColumnInfo(
                        column_name=k,
                        data_type="string",
                        is_nullable=True,
                        ordinal_position=i + 1,
                    )
                    for i, k in enumerate(rows[0].keys())
                ]
        counts = await self._get_all_row_counts()
        if counts:
            self._tables_with_data = sum(1 for n in counts.values() if n > 0)
            self._total_rows = sum(counts.values())
        await self._persist_table_to_s3(schema, table, rows)
        return len(rows)

    async def _persist_table_to_s3(self, schema: str, table: str, rows: list[dict]) -> None:
        """Write the mutated table back to MinIO/S3 so dumps survive Redis TTL."""
        if not self.bucket or self._storage is None:
            return
        try:
            ensure = getattr(self._storage, "ensure_bucket", None)
            if callable(ensure):
                await ensure()
            await self._storage.put_json(f"data/{schema}.{table}.json", rows)
            tables_json = await self._storage.get_json("tables.json")
            if isinstance(tables_json, list):
                found = False
                for entry in tables_json:
                    name = entry.get("tableName") or entry.get("table_name")
                    sch = entry.get("schemaName") or entry.get("schema_name")
                    if name == table and sch == schema:
                        entry["columnCount"] = len(rows[0]) if rows else entry.get("columnCount", 0)
                        found = True
                        break
                if not found:
                    tables_json.append({
                        "schemaName": schema,
                        "tableName": table,
                        "serverName": self._manifest.get("server_name", f"{self.SERVICE_NAME}_simulator"),
                        "columnCount": len(rows[0]) if rows else 0,
                    })
                await self._storage.put_json("tables.json", tables_json)
            manifest = await self._storage.get_json("manifest.json") or dict(self._manifest)
            if isinstance(manifest, dict):
                data_tables = dict(manifest.get("data_tables") or {})
                data_tables[table] = len(rows)
                manifest["data_tables"] = data_tables
                manifest["tables_with_data"] = sum(1 for n in data_tables.values() if n)
                manifest["total_rows_dumped"] = sum(data_tables.values())
                await self._storage.put_json("manifest.json", manifest)
        except Exception as exc:  # noqa: BLE001
            self._sim_logger.warning(f"S3 persist failed for {schema}.{table}: {exc}")

    async def append_rows(self, schema: str, table: str, rows: list[dict]) -> int:
        if not rows:
            existing = await self._get_table_data(schema, table)
            return len(existing)
        existing = await self._get_table_data(schema, table)
        combined = list(existing) + list(rows)
        await self.write_table(schema, table, combined)
        return len(combined)

    @staticmethod
    def _match_filter(row: dict, column: str, operator: str, value: Any) -> bool:
        rv = row.get(column)
        if rv is None:
            return operator == "neq"
        try:
            if operator == "eq":
                return rv == value
            elif operator == "neq":
                return rv != value
            elif operator == "gt":
                return rv > value
            elif operator == "gte":
                return rv >= value
            elif operator == "lt":
                return rv < value
            elif operator == "lte":
                return rv <= value
            elif operator == "like":
                pattern = str(value).replace("%", "")
                return pattern.lower() in str(rv).lower()
            elif operator == "in":
                return rv in (value if isinstance(value, list) else [value])
        except (TypeError, ValueError):
            return False
        return False

    # ─── Admin methods ───────────────────────────────────────────────────

    async def get_object_list(self) -> list[dict[str, Any]]:
        """List all tables with row counts (single MGET for all counts)."""
        counts = await self._get_all_row_counts()
        result = []
        for t in self._tables:
            key = f"{t.schema_name}.{t.table_name}"
            result.append(
                {
                    "schemaName": t.schema_name,
                    "tableName": t.table_name,
                    "columnCount": t.column_count,
                    "rowCount": counts.get(key, 0),
                }
            )
        return result

    async def get_object_records(
        self, schema: str, table: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        rows = await self._get_table_data(schema, table)
        total = len(rows)
        page = rows[offset: offset + limit]
        return {
            "schemaName": schema,
            "tableName": table,
            "rows": page,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    # ─── Seed helper ─────────────────────────────────────────────────────

    async def _finalize_seed(
        self, schema: str, server: str, data_map: dict[str, list[dict]]
    ) -> dict[str, Any]:
        """Common seed finalization: store tables in cache, register metadata, return result."""
        start = time.monotonic()
        self._servers = [
            ForeignServerInfo(server_name=server, wrapper_type="simulator", server_options={})
        ]
        self._tables = []
        self._columns = {}

        for table_name, rows in data_map.items():
            await self._store_table(schema, table_name, rows)
            self._tables.append(
                ForeignTableInfo(
                    schema_name=schema,
                    table_name=table_name,
                    server_name=server,
                    column_count=len(rows[0]) if rows else 0,
                )
            )
            if rows:
                self._auto_register_columns(schema, table_name, rows[0])

        total_rows = sum(len(r) for r in data_map.values())
        self._loaded = True
        self._loaded_at = datetime.now(timezone.utc)
        self._tables_with_data = sum(1 for r in data_map.values() if r)
        self._total_rows = total_rows
        self._manifest = {
            "dump_timestamp": self._loaded_at.isoformat(),
            "source_url": "seeded",
            "schema": schema,
            "total_tables": len(self._tables),
            "total_rows_dumped": total_rows,
        }
        await self.rebuild_catalog_from_cache()
        elapsed = time.monotonic() - start
        msg = (
            f"{self.SERVICE_NAME} seed complete — {len(self._tables)} tables, "
            f"{self._total_rows:,} rows in {elapsed:.1f}s"
        )
        self._sim_logger.info(msg)
        return {
            "success": True,
            "message": msg,
            "tables": len(self._tables),
            "total_rows": total_rows,
        }

    async def _finalize_seed_multi(
        self,
        server: str,
        schemas_data: dict[str, dict[str, list[dict]]],
        *,
        merge_manifest: bool = True,
    ) -> dict[str, Any]:
        """Seed multiple schemas in one pass (e.g. legacy + telco_atlas_*)."""
        start = time.monotonic()
        self._servers = [
            ForeignServerInfo(server_name=server, wrapper_type="simulator", server_options={})
        ]
        self._tables = []
        self._columns = {}

        total_rows = 0
        manifest_schemas: dict[str, int] = {}
        primary_schema = ""

        for schema, data_map in schemas_data.items():
            if not primary_schema:
                primary_schema = schema
            table_count = 0
            for table_name, rows in data_map.items():
                await self._store_table(schema, table_name, rows)
                self._tables.append(
                    ForeignTableInfo(
                        schema_name=schema,
                        table_name=table_name,
                        server_name=server,
                        column_count=len(rows[0]) if rows else 0,
                    )
                )
                if rows:
                    self._auto_register_columns(schema, table_name, rows[0])
                table_count += 1
                total_rows += len(rows)
            manifest_schemas[schema] = table_count

        self._loaded = True
        self._loaded_at = datetime.now(timezone.utc)
        self._tables_with_data = sum(1 for t in self._tables if t.column_count > 0)
        self._total_rows = total_rows

        if merge_manifest:
            self._manifest = {
                "dump_timestamp": self._loaded_at.isoformat(),
                "source_url": "seeded",
                "schema": primary_schema,
                "schemas": manifest_schemas,
                "total_tables": len(self._tables),
                "total_rows_dumped": total_rows,
            }
        await self.rebuild_catalog_from_cache()
        elapsed = time.monotonic() - start
        msg = (
            f"{self.SERVICE_NAME} multi-schema seed — {len(self._tables)} tables, "
            f"{self._total_rows:,} rows across {len(schemas_data)} schema(s) in {elapsed:.1f}s"
        )
        self._sim_logger.info(msg)
        return {
            "success": True,
            "message": msg,
            "tables": len(self._tables),
            "total_rows": total_rows,
            "schemas": manifest_schemas,
        }
