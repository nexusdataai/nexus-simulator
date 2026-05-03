"""Unit tests for the Redis adapter (covers the in-memory fallback path).

Real-Redis behavior is exercised under tests/integration/ once Phase 4 lands
the ``redis_client`` fixture (fakeredis). Here we cover the
"redis-not-configured" branch and confirm the fallback semantics match the
in-memory adapter.
"""

from __future__ import annotations

import pytest

from nexus_simulator.adapters.redis import RedisCacheBackend


@pytest.mark.asyncio
async def test_falls_back_to_memory_when_no_url() -> None:
    c = RedisCacheBackend(url=None)
    await c.set("k", "v")
    assert await c.get("k") == "v"
    assert await c.ping() is False  # cannot ping when no url


@pytest.mark.asyncio
async def test_json_helpers_roundtrip_through_fallback() -> None:
    c = RedisCacheBackend(url=None)
    await c.set_json("rows", [1, 2, 3])
    assert await c.get_json("rows") == [1, 2, 3]


@pytest.mark.asyncio
async def test_mget_through_fallback() -> None:
    c = RedisCacheBackend(url=None)
    await c.set("a", "1")
    await c.set("b", "2")
    assert await c.mget(["a", "missing", "b"]) == ["1", None, "2"]


@pytest.mark.asyncio
async def test_flush_prefix_through_fallback() -> None:
    c = RedisCacheBackend(url=None)
    await c.set("sim:wxcc:1", "x")
    await c.set("sim:wxcc:2", "y")
    await c.set("sim:sfdc:1", "z")
    assert await c.flush_prefix("sim:wxcc:") == 2
    assert await c.get("sim:wxcc:1") is None
    assert await c.get("sim:sfdc:1") == "z"


@pytest.mark.asyncio
async def test_unreachable_url_marks_unavailable_and_falls_back() -> None:
    """A bogus URL flips the sticky `_unavailable` flag and routes to fallback."""
    c = RedisCacheBackend(url="redis://127.0.0.1:1/0")  # nothing should be listening
    await c.set("k", "v")
    assert await c.get("k") == "v"
    # After the first failure it should be marked unavailable
    assert c._unavailable is True
