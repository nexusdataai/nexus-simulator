"""Unit tests for ``BaseSimulator``.

Uses the in-memory storage + cache adapters end-to-end. Validates the
verbatim semantics ported from
``nexus-backend/src/services/base_simulator_service.py``:

- ``load_from_s3`` → ``manifest`` / ``servers`` / ``tables`` / ``columns``
  / ``data`` discovery and per-file routing.
- ``_store_table`` writes both the rows JSON and the count companion key.
- ``_get_all_row_counts`` MGET-batches.
- ``execute_query`` filters/projects/orders/paginates.
- ``reset`` flushes ``sim:<name>:`` and either reloads from S3 or seeds.
- ``ensure_loaded`` triggers a reload when the cache row count drops to zero.
"""

from __future__ import annotations

from typing import Any

import pytest

from nexus_simulator.adapters.memory import (
    InMemoryCacheBackend,
    InMemoryStorageBackend,
)
from nexus_simulator.base import BaseSimulator
from nexus_simulator.models.fdw import (
    FilterOperator,
    OrderByItem,
    QueryFilter,
    QueryRequest,
)


class _DummySimulator(BaseSimulator):
    """Minimal BaseSimulator subclass used for tests."""

    SERVICE_NAME = "dummy"
    PRIORITY_TABLES = ["accounts"]

    async def seed_data(self) -> dict[str, Any]:
        return await self._finalize_seed(
            schema="public",
            server="dummy_simulator",
            data_map={
                "accounts": [
                    {"id": 1, "name": "alice", "active": True, "score": 9.5},
                    {"id": 2, "name": "bob", "active": False, "score": 4.2},
                    {"id": 3, "name": "carol", "active": True, "score": 7.0},
                ],
                "empty": [],
            },
        )


@pytest.fixture
def in_memory_pair() -> tuple[InMemoryStorageBackend, InMemoryCacheBackend]:
    return InMemoryStorageBackend(prefix="dump"), InMemoryCacheBackend()


# ─── Construction + state ─────────────────────────────────────────────────


def test_subclass_must_define_seed_data() -> None:
    with pytest.raises(TypeError):
        BaseSimulator(bucket="b", prefix="p")  # type: ignore[abstract]


def test_initial_state_is_empty() -> None:
    s, c = InMemoryStorageBackend(), InMemoryCacheBackend()
    sim = _DummySimulator(bucket="b", prefix="dump", storage=s, cache=c)
    assert sim.loaded is False
    assert sim.bucket == "b"
    assert sim.prefix == "dump"
    assert sim._tables == []
    status = sim.get_status()
    assert status["enabled"] is True
    assert status["loaded"] is False
    assert status["table_count"] == 0


def test_cache_property_raises_when_unwired() -> None:
    sim = _DummySimulator(bucket="b", prefix="p")  # no cache wired
    with pytest.raises(RuntimeError, match="no CacheBackend"):
        _ = sim.cache


# ─── Cache-key layout ─────────────────────────────────────────────────────


def test_cache_key_layout_is_namespaced_per_service() -> None:
    sim = _DummySimulator(cache=InMemoryCacheBackend())
    assert sim._redis_key("public", "accounts") == "sim:dummy:public.accounts"
    assert sim._redis_count_key("public", "accounts") == "sim:dummy:count:public.accounts"
    assert sim._redis_meta_key("manifest") == "sim:dummy:meta:manifest"


# ─── Seed → query path (no S3 needed) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_seed_then_query_filters_project_and_paginates(
    in_memory_pair: tuple[InMemoryStorageBackend, InMemoryCacheBackend],
) -> None:
    storage, cache = in_memory_pair
    sim = _DummySimulator(bucket="", prefix="", storage=storage, cache=cache)
    result = await sim.seed_data()

    assert result["success"] is True
    assert result["tables"] == 2
    assert result["total_rows"] == 3
    assert sim.loaded is True

    # Filter active=True, project name+score, order by score desc, limit 1
    resp = await sim.execute_query(
        QueryRequest(
            table="accounts",
            schema_name="public",
            filters=[QueryFilter(column="active", operator=FilterOperator.eq, value=True)],
            columns=["name", "score"],
            order_by=[OrderByItem(column="score", direction="desc")],
            limit=1,
        )
    )
    assert resp.rows == [{"name": "alice", "score": 9.5}]
    assert resp.metadata.row_count == 1
    assert resp.metadata.table_queried == "public.accounts"


@pytest.mark.asyncio
async def test_seed_writes_count_companion_keys(
    in_memory_pair: tuple[InMemoryStorageBackend, InMemoryCacheBackend],
) -> None:
    storage, cache = in_memory_pair
    sim = _DummySimulator(bucket="", prefix="", storage=storage, cache=cache)
    await sim.seed_data()

    count_keys = await sim._get_all_row_counts()
    assert count_keys["public.accounts"] == 3
    assert count_keys["public.empty"] == 0


@pytest.mark.asyncio
async def test_get_object_list_uses_mget(
    in_memory_pair: tuple[InMemoryStorageBackend, InMemoryCacheBackend],
) -> None:
    storage, cache = in_memory_pair
    sim = _DummySimulator(bucket="", prefix="", storage=storage, cache=cache)
    await sim.seed_data()

    listing = await sim.get_object_list()
    by_name = {row["tableName"]: row for row in listing}
    assert by_name["accounts"]["rowCount"] == 3
    assert by_name["empty"]["rowCount"] == 0


@pytest.mark.asyncio
async def test_get_object_records_paginates(
    in_memory_pair: tuple[InMemoryStorageBackend, InMemoryCacheBackend],
) -> None:
    storage, cache = in_memory_pair
    sim = _DummySimulator(bucket="", prefix="", storage=storage, cache=cache)
    await sim.seed_data()

    page = await sim.get_object_records("public", "accounts", limit=1, offset=1)
    assert page["total"] == 3
    assert page["limit"] == 1
    assert page["offset"] == 1
    assert page["rows"] == [{"id": 2, "name": "bob", "active": False, "score": 4.2}]


# ─── Filter operators ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_query_filter_operators(
    in_memory_pair: tuple[InMemoryStorageBackend, InMemoryCacheBackend],
) -> None:
    storage, cache = in_memory_pair
    sim = _DummySimulator(storage=storage, cache=cache)
    await sim.seed_data()

    async def names_for(filt: QueryFilter) -> list[str]:
        resp = await sim.execute_query(
            QueryRequest(
                table="accounts",
                schema_name="public",
                filters=[filt],
                columns=["name"],
                order_by=[OrderByItem(column="name", direction="asc")],
            )
        )
        return [r["name"] for r in resp.rows]

    assert await names_for(
        QueryFilter(column="score", operator=FilterOperator.gt, value=5)
    ) == ["alice", "carol"]
    assert await names_for(
        QueryFilter(column="score", operator=FilterOperator.lte, value=5)
    ) == ["bob"]
    assert await names_for(
        QueryFilter(column="name", operator=FilterOperator.like, value="%ali%")
    ) == ["alice"]
    assert await names_for(
        QueryFilter(column="id", operator=FilterOperator.in_, value=[1, 3])
    ) == ["alice", "carol"]
    assert await names_for(
        QueryFilter(column="active", operator=FilterOperator.neq, value=True)
    ) == ["bob"]


# ─── load_from_s3 ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_from_s3_walks_manifest_servers_tables_columns_data() -> None:
    storage = InMemoryStorageBackend(prefix="dump")
    cache = InMemoryCacheBackend()

    await storage.put_json(
        "manifest.json",
        {
            "total_tables": 1,
            "dump_timestamp": "2026-01-01T00:00:00Z",
            "schema": "public",
            "server_name": "real_server",
        },
    )
    await storage.put_json(
        "servers.json",
        [{"serverName": "real_server", "wrapperType": "postgres_fdw", "serverOptions": {}}],
    )
    await storage.put_json(
        "tables.json",
        [
            {
                "schemaName": "public",
                "tableName": "users",
                "serverName": "real_server",
                "columnCount": 2,
            }
        ],
    )
    await storage.put_json(
        "columns/public.users.json",
        [
            {"columnName": "id", "dataType": "integer", "isNullable": False, "ordinalPosition": 1},
            {"columnName": "name", "dataType": "text", "isNullable": True, "ordinalPosition": 2},
        ],
    )
    await storage.put_json(
        "data/public.users.json",
        [{"id": 1, "name": "x"}, {"id": 2, "name": "y"}],
    )

    sim = _DummySimulator(bucket="b", prefix="dump", storage=storage, cache=cache)
    result = await sim.load_from_s3()

    assert result["success"] is True
    assert result["tables_with_data"] == 1
    assert result["total_rows"] == 2

    rows = await sim._get_table_data("public", "users")
    assert rows == [{"id": 1, "name": "x"}, {"id": 2, "name": "y"}]

    cols = await sim.get_table_columns("public", "users")
    assert [c.column_name for c in cols] == ["id", "name"]

    servers = await sim.list_foreign_servers()
    assert len(servers) == 1
    assert servers[0].server_name == "real_server"


@pytest.mark.asyncio
async def test_load_from_s3_returns_failure_when_manifest_missing() -> None:
    storage = InMemoryStorageBackend(prefix="dump")
    cache = InMemoryCacheBackend()
    sim = _DummySimulator(bucket="b", prefix="dump", storage=storage, cache=cache)
    result = await sim.load_from_s3()
    assert result["success"] is False
    assert "manifest.json" in result["message"]


# ─── reset ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_with_no_bucket_calls_seed_data(
    in_memory_pair: tuple[InMemoryStorageBackend, InMemoryCacheBackend],
) -> None:
    storage, cache = in_memory_pair
    sim = _DummySimulator(bucket="", prefix="", storage=storage, cache=cache)
    await sim.seed_data()
    # Manually pollute a side-channel sim:dummy:* key, confirm it gets flushed
    await cache.set("sim:dummy:custom", "stale")
    out = await sim.reset()
    assert out["success"] is True
    # The stale key should have been wiped by flush_prefix in reset()
    assert await cache.get("sim:dummy:custom") is None


# ─── ensure_loaded ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ensure_loaded_reloads_when_cache_row_count_dropped() -> None:
    storage = InMemoryStorageBackend(prefix="dump")
    cache = InMemoryCacheBackend()
    # Populate S3 dump
    await storage.put_json(
        "manifest.json", {"total_tables": 1, "schema": "public", "server_name": "srv"}
    )
    await storage.put_json("servers.json", [])
    await storage.put_json(
        "tables.json",
        [
            {
                "schemaName": "public",
                "tableName": "users",
                "serverName": "srv",
                "columnCount": 1,
            }
        ],
    )
    await storage.put_json("data/public.users.json", [{"id": 1}])

    sim = _DummySimulator(bucket="b", prefix="dump", storage=storage, cache=cache)
    await sim.load_from_s3()
    assert sim.loaded is True
    assert sim._total_rows == 1

    # Simulate cache eviction by deleting only the count key
    await cache.delete(sim._redis_count_key("public", "users"))
    await sim.ensure_loaded()
    # After the implicit reload the data is present again
    assert (await sim._get_table_row_count("public", "users")) == 1
