"""Redis-backed ``CacheBackend`` adapter with graceful in-memory fallback.

Verbatim semantic port of
[`nexus-backend/src/services/redis_client.py`](../../../../nexus-backend/src/services/redis_client.py)
into the contracts shape. Behavior preserved:

- Lazy connection pool creation; first ``ping`` failure flips a sticky
  ``_unavailable`` flag and the adapter never re-tries Redis after that for
  the lifetime of the instance (mirrors the legacy module-level state).
- Every operation falls back to the in-memory ``InMemoryCacheBackend`` when
  Redis is down, so the simulator keeps serving even with no Redis.
- JSON helpers serialize via ``json.dumps(default=str)``.
- ``flush_prefix`` walks ``scan_iter(match="<prefix>*", count=1000)`` for
  Redis, glob-prefix match for the fallback.
- ``mget`` does a single round-trip when Redis is up; falls back to a
  per-key dict lookup otherwise.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from ..errors import CacheError
from .memory import InMemoryCacheBackend

DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 days, matches nexus-backend's REDIS_SIMULATOR_TTL

redis_logger = logger.bind(component="redis-adapter")


class RedisCacheBackend:
    """``CacheBackend`` backed by Redis with in-memory fallback.

    The adapter uses ``redis.asyncio`` lazily; if the ``redis`` package is not
    installed, every operation routes to the in-memory fallback after logging
    a single warning at construction.
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        default_ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_connections: int = 20,
        socket_connect_timeout_seconds: int = 3,
        socket_timeout_seconds: int = 5,
    ) -> None:
        self._url = url
        self._default_ttl = default_ttl_seconds
        self._max_connections = max_connections
        self._socket_connect_timeout = socket_connect_timeout_seconds
        self._socket_timeout = socket_timeout_seconds
        self._pool: Any = None
        self._unavailable: bool = False if url else True
        self._fallback = InMemoryCacheBackend()
        if not url:
            redis_logger.info("RedisCacheBackend: no URL configured; using in-memory fallback")

    async def _get_pool(self) -> Any:
        """Get-or-create the redis-py async connection pool, sticky on failure."""
        if self._unavailable:
            return None
        if self._pool is not None:
            return self._pool
        try:
            import redis.asyncio as aioredis
        except ImportError:
            redis_logger.warning(
                "redis package not installed; install nexus-simulator[redis]. "
                "Falling back to in-memory cache."
            )
            self._unavailable = True
            return None
        try:
            self._pool = aioredis.from_url(
                self._url,
                decode_responses=True,
                max_connections=self._max_connections,
                socket_connect_timeout=self._socket_connect_timeout,
                socket_timeout=self._socket_timeout,
            )
            await self._pool.ping()
            redis_logger.info(f"Redis connected at {self._url}")
            return self._pool
        except Exception as e:  # noqa: BLE001
            redis_logger.warning(f"Redis unavailable ({e}), falling back to in-memory store")
            self._unavailable = True
            self._pool = None
            return None

    async def get(self, key: str) -> str | None:
        r = await self._get_pool()
        if r:
            try:
                return await r.get(key)
            except Exception as e:  # noqa: BLE001
                redis_logger.warning(f"Redis GET failed for {key}: {e}")
        return await self._fallback.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        r = await self._get_pool()
        if r:
            try:
                await r.set(key, value, ex=ttl)
                return
            except Exception as e:  # noqa: BLE001
                redis_logger.warning(f"Redis SET failed for {key}: {e}")
        await self._fallback.set(key, value, ttl_seconds=ttl)

    async def get_json(self, key: str) -> Any | None:
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        await self.set(key, json.dumps(value, default=str), ttl_seconds=ttl_seconds)

    async def scan_keys(self, pattern: str) -> list[str]:
        r = await self._get_pool()
        if r:
            try:
                found: list[str] = []
                async for key in r.scan_iter(match=pattern, count=1000):
                    found.append(key)
                return found
            except Exception as e:  # noqa: BLE001
                redis_logger.warning(f"Redis SCAN failed for {pattern}: {e}")
        return await self._fallback.scan_keys(pattern)

    async def mget(self, keys: list[str]) -> list[str | None]:
        if not keys:
            return []
        r = await self._get_pool()
        if r:
            try:
                return await r.mget(keys)
            except Exception as e:  # noqa: BLE001
                redis_logger.warning(f"Redis MGET failed: {e}")
        return await self._fallback.mget(keys)

    async def delete(self, key: str) -> None:
        r = await self._get_pool()
        if r:
            try:
                await r.delete(key)
                return
            except Exception as e:  # noqa: BLE001
                redis_logger.warning(f"Redis DELETE failed for {key}: {e}")
        await self._fallback.delete(key)

    async def flush_prefix(self, prefix: str) -> int:
        r = await self._get_pool()
        if r:
            try:
                count = 0
                async for key in r.scan_iter(match=f"{prefix}*", count=1000):
                    await r.delete(key)
                    count += 1
                return count
            except Exception as e:  # noqa: BLE001
                redis_logger.warning(f"Redis SCAN/DELETE failed for prefix {prefix}: {e}")
        return await self._fallback.flush_prefix(prefix)

    async def ping(self) -> bool:
        r = await self._get_pool()
        if r is None:
            return False
        try:
            return bool(await r.ping())
        except Exception:  # noqa: BLE001
            return False

    async def close(self) -> None:
        """Close the underlying connection pool; safe to call multiple times."""
        if self._pool is not None:
            try:
                await self._pool.aclose()
            except AttributeError:
                # redis-py <5 uses .close()
                try:
                    await self._pool.close()
                except Exception as e:  # noqa: BLE001
                    raise CacheError(f"Failed to close redis pool: {e}") from e
            finally:
                self._pool = None
