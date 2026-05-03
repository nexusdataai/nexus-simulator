"""Default adapter implementations.

- ``s3.S3StorageBackend``               — boto3-backed StorageBackend.
- ``redis.RedisCacheBackend``           — redis-py-backed CacheBackend with in-memory fallback.
- ``memory.InMemoryStorageBackend``     — in-memory StorageBackend.
- ``memory.InMemoryCacheBackend``       — in-memory CacheBackend.
- ``memory.InMemoryRecordingsBackend``  — in-memory RecordingsBackend (LRU eviction).

Plugins do not import from this package directly; ``build_simulator`` wires
the right adapter into each plugin based on the active ``SimulatorConfig``.
"""

from .memory import (
    InMemoryCacheBackend,
    InMemoryRecordingsBackend,
    InMemoryStorageBackend,
)
from .redis import RedisCacheBackend
from .s3 import S3StorageBackend

__all__ = [
    "InMemoryCacheBackend",
    "InMemoryRecordingsBackend",
    "InMemoryStorageBackend",
    "RedisCacheBackend",
    "S3StorageBackend",
]
