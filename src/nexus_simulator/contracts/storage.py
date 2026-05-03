"""StorageBackend port.

Abstracts the persistence layer that BaseSimulator pulls table dumps from
(today: S3) and writes recording artifacts to. Plugins read JSON manifests,
column metadata, and per-table data files from this port; the in-memory
adapter satisfies the same contract for tests and local prototyping.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Object-store access for plugin data dumps and binary artifacts."""

    bucket: str
    prefix: str

    async def get_json(self, key: str) -> Any | None:
        """Read a JSON object at ``<prefix>/<key>``. Returns ``None`` if missing."""
        ...

    async def put_json(self, key: str, value: Any) -> None:
        """Write ``value`` as JSON at ``<prefix>/<key>``."""
        ...

    async def list_keys(self, sub_prefix: str = "") -> Iterable[str]:
        """List keys (relative to ``prefix``) under an optional sub-prefix."""
        ...

    async def get_bytes(self, key: str) -> bytes | None:
        """Read raw bytes at ``<prefix>/<key>``. Returns ``None`` if missing."""
        ...

    async def put_bytes(self, key: str, data: bytes) -> None:
        """Write raw bytes at ``<prefix>/<key>``."""
        ...

    async def delete(self, key: str) -> None:
        """Delete an object at ``<prefix>/<key>``. No-op if missing."""
        ...

    async def stream_to(self, key: str, sink: BinaryIO) -> None:
        """Stream the object at ``<prefix>/<key>`` into a file-like sink."""
        ...
