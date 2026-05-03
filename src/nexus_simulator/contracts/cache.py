"""CacheBackend port.

Abstracts the key/value store BaseSimulator uses to hold table data and row
counts (today: Redis, with an in-memory dict fallback). Designed to map 1:1
to the redis-py async API so the default adapter is a thin wrapper.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    """Async key/value cache used to hold simulator table data."""

    async def get(self, key: str) -> str | None:
        """Return the raw string value at ``key``, or ``None``."""
        ...

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Set the raw string value at ``key`` with an optional TTL."""
        ...

    async def get_json(self, key: str) -> Any | None:
        """Return the JSON-deserialized value at ``key``, or ``None``."""
        ...

    async def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Set ``value`` (JSON-serialized) at ``key`` with an optional TTL."""
        ...

    async def mget(self, keys: list[str]) -> list[str | None]:
        """Batch-read raw string values. Returns ``None`` per missing key."""
        ...

    async def delete(self, key: str) -> None:
        """Delete a single key. No-op if missing."""
        ...

    async def flush_prefix(self, prefix: str) -> int:
        """Delete every key beginning with ``prefix``. Returns the number deleted."""
        ...

    async def ping(self) -> bool:
        """Return ``True`` if the backend is reachable."""
        ...
