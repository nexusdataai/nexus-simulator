"""In-memory adapters for tests and local prototyping.

Satisfies ``StorageBackend``, ``CacheBackend`` and ``RecordingsBackend`` from
``nexus_simulator.contracts``. No network, no boto3, no Redis dependency.

The cache implementation also doubles as the Redis adapter's fallback store
when Redis is unreachable, mirroring the behavior of the legacy
``redis_client._fallback_store``.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import Iterable
from typing import Any, BinaryIO


class InMemoryStorageBackend:
    """In-memory ``StorageBackend`` implementation.

    Storage layout: ``{(bucket, prefix): {key: bytes}}``. JSON helpers
    serialize via ``json.dumps(default=str)`` to mirror the production S3
    adapter's wire format.
    """

    def __init__(self, bucket: str = "memory", prefix: str = "") -> None:
        self.bucket = bucket
        self.prefix = prefix
        self._store: dict[str, bytes] = {}

    def _full_key(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    async def get_json(self, key: str) -> Any | None:
        raw = self._store.get(self._full_key(key))
        if raw is None:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    async def put_json(self, key: str, value: Any) -> None:
        self._store[self._full_key(key)] = json.dumps(value, default=str).encode("utf-8")

    async def list_keys(self, sub_prefix: str = "") -> Iterable[str]:
        scan = self._full_key(sub_prefix) if sub_prefix else (self.prefix or "")
        # Return relative-to-prefix keys to match S3 paginator semantics.
        relative_prefix = f"{self.prefix}/" if self.prefix else ""
        out: list[str] = []
        for full in self._store:
            if not full.startswith(scan):
                continue
            if relative_prefix and full.startswith(relative_prefix):
                out.append(full[len(relative_prefix):])
            else:
                out.append(full)
        return out

    async def get_bytes(self, key: str) -> bytes | None:
        return self._store.get(self._full_key(key))

    async def put_bytes(self, key: str, data: bytes) -> None:
        self._store[self._full_key(key)] = data

    async def delete(self, key: str) -> None:
        self._store.pop(self._full_key(key), None)

    async def stream_to(self, key: str, sink: BinaryIO) -> None:
        data = self._store.get(self._full_key(key))
        if data is not None:
            sink.write(data)


class InMemoryCacheBackend:
    """In-memory ``CacheBackend`` implementation.

    String-only values; JSON helpers convert via ``json.dumps``/``loads``
    using the same ``default=str`` policy as the legacy redis_client.
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        # TTL is intentionally ignored for the in-memory adapter; tests that
        # need expiry semantics use freezegun + a real Redis or fakeredis.
        self._store[key] = value

    async def get_json(self, key: str) -> Any | None:
        raw = self._store.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        self._store[key] = json.dumps(value, default=str)

    async def mget(self, keys: list[str]) -> list[str | None]:
        return [self._store.get(k) for k in keys]

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def flush_prefix(self, prefix: str) -> int:
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            self._store.pop(k, None)
        return len(keys)

    async def ping(self) -> bool:
        return True


class InMemoryRecordingsBackend:
    """In-memory ``RecordingsBackend`` with LRU eviction.

    Mirrors the size + count limits applied by ``WXCCSimulatorService``'s
    ``LRUBytesCache`` so the harness exhibits the same eviction surface.
    """

    def __init__(self, max_items: int = 20, max_size_bytes: int = 50 * 1024 * 1024) -> None:
        self._cache: OrderedDict[str, tuple[str, bytes]] = OrderedDict()
        self._max_items = max_items
        self._max_size_bytes = max_size_bytes
        self._size = 0

    async def list_local_recordings(self) -> list[str]:
        return [filename for _, (filename, _) in self._cache.items()]

    async def get_recording(self, recording_id: str) -> tuple[str, bytes] | None:
        if recording_id not in self._cache:
            return None
        self._cache.move_to_end(recording_id)
        return self._cache[recording_id]

    async def put_recording(self, recording_id: str, filename: str, data: bytes) -> None:
        size = len(data)
        if size > self._max_size_bytes // 2:
            return  # too large to cache; mirrors WXCC behavior
        if recording_id in self._cache:
            _, old = self._cache.pop(recording_id)
            self._size -= len(old)
        while (self._size + size > self._max_size_bytes) or len(self._cache) >= self._max_items:
            if not self._cache:
                break
            _evicted_id, (_evicted_name, evicted) = self._cache.popitem(last=False)
            self._size -= len(evicted)
        self._cache[recording_id] = (filename, data)
        self._size += size

    async def delete_recording(self, recording_id: str) -> None:
        entry = self._cache.pop(recording_id, None)
        if entry is not None:
            _, data = entry
            self._size -= len(data)

    async def count(self) -> int:
        return len(self._cache)
