"""Unit tests for the in-memory adapters."""

from __future__ import annotations

import pytest

from nexus_simulator.adapters.memory import (
    InMemoryCacheBackend,
    InMemoryRecordingsBackend,
    InMemoryStorageBackend,
)

# ─── Storage ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_storage_json_roundtrip() -> None:
    s = InMemoryStorageBackend(prefix="dump")
    assert await s.get_json("missing.json") is None
    await s.put_json("a.json", {"k": 1, "v": "x"})
    assert await s.get_json("a.json") == {"k": 1, "v": "x"}


@pytest.mark.asyncio
async def test_storage_bytes_roundtrip() -> None:
    s = InMemoryStorageBackend(prefix="dump")
    await s.put_bytes("blob.bin", b"\x00\x01\x02")
    assert await s.get_bytes("blob.bin") == b"\x00\x01\x02"
    assert await s.get_bytes("missing.bin") is None


@pytest.mark.asyncio
async def test_storage_list_keys_returns_relative_paths() -> None:
    s = InMemoryStorageBackend(prefix="dump")
    await s.put_json("data/a.json", [{"x": 1}])
    await s.put_json("data/b.json", [{"x": 2}])
    await s.put_json("columns/a.json", [])
    out = list(await s.list_keys("data/"))
    assert sorted(out) == ["data/a.json", "data/b.json"]


@pytest.mark.asyncio
async def test_storage_delete() -> None:
    s = InMemoryStorageBackend()
    await s.put_json("foo.json", {"k": 1})
    await s.delete("foo.json")
    assert await s.get_json("foo.json") is None
    # Delete-missing is a no-op
    await s.delete("never.json")


# ─── Cache ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_get_set_delete() -> None:
    c = InMemoryCacheBackend()
    assert await c.get("k") is None
    await c.set("k", "v")
    assert await c.get("k") == "v"
    await c.delete("k")
    assert await c.get("k") is None


@pytest.mark.asyncio
async def test_cache_json_helpers() -> None:
    c = InMemoryCacheBackend()
    await c.set_json("rows", [{"id": 1}, {"id": 2}])
    assert await c.get_json("rows") == [{"id": 1}, {"id": 2}]


@pytest.mark.asyncio
async def test_cache_mget_preserves_order_and_misses() -> None:
    c = InMemoryCacheBackend()
    await c.set("a", "1")
    await c.set("c", "3")
    assert await c.mget(["a", "b", "c"]) == ["1", None, "3"]


@pytest.mark.asyncio
async def test_cache_flush_prefix_only_matches_prefix() -> None:
    c = InMemoryCacheBackend()
    await c.set("sim:wxcc:foo", "1")
    await c.set("sim:wxcc:bar", "2")
    await c.set("sim:sfdc:foo", "3")
    deleted = await c.flush_prefix("sim:wxcc:")
    assert deleted == 2
    assert await c.get("sim:wxcc:foo") is None
    assert await c.get("sim:sfdc:foo") == "3"


@pytest.mark.asyncio
async def test_cache_ping() -> None:
    c = InMemoryCacheBackend()
    assert await c.ping() is True


# ─── Recordings (LRU eviction) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_recordings_evicts_lru_on_count() -> None:
    rb = InMemoryRecordingsBackend(max_items=2, max_size_bytes=10_000)
    await rb.put_recording("r1", "a.wav", b"a" * 100)
    await rb.put_recording("r2", "b.wav", b"b" * 100)
    await rb.put_recording("r3", "c.wav", b"c" * 100)
    # r1 evicted (oldest); r2, r3 remain
    assert await rb.get_recording("r1") is None
    assert (await rb.get_recording("r2"))[0] == "b.wav"
    assert (await rb.get_recording("r3"))[0] == "c.wav"
    assert await rb.count() == 2


@pytest.mark.asyncio
async def test_recordings_skips_oversized_payloads() -> None:
    rb = InMemoryRecordingsBackend(max_items=10, max_size_bytes=100)
    too_big = b"x" * 80  # > max_size_bytes // 2 (50)
    await rb.put_recording("r1", "huge.wav", too_big)
    assert await rb.get_recording("r1") is None
    assert await rb.count() == 0


@pytest.mark.asyncio
async def test_recordings_promotes_on_get() -> None:
    rb = InMemoryRecordingsBackend(max_items=2, max_size_bytes=10_000)
    await rb.put_recording("r1", "a.wav", b"a" * 10)
    await rb.put_recording("r2", "b.wav", b"b" * 10)
    # Access r1 to promote it; next put should evict r2 instead of r1
    await rb.get_recording("r1")
    await rb.put_recording("r3", "c.wav", b"c" * 10)
    assert await rb.get_recording("r1") is not None
    assert await rb.get_recording("r2") is None
    assert await rb.get_recording("r3") is not None
