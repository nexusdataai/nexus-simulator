"""RecordingsBackend port (WXCC-specific).

Abstracts the WXCC simulator's audio-recording store. Today the default
adapter is S3-backed (LRU bytes cache + size limits — see
``WXCCSimulatorService`` in nexus-backend). The harness ships an in-memory
adapter with synthetic WAV bytes so tests don't need network or boto3.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RecordingsBackend(Protocol):
    """WXCC recording store: list, fetch, write, prune."""

    async def list_local_recordings(self) -> list[str]:
        """Return the filenames of locally available recording samples."""
        ...

    async def get_recording(self, recording_id: str) -> tuple[str, bytes] | None:
        """Return ``(filename, audio_bytes)`` for a recording, or ``None``."""
        ...

    async def put_recording(self, recording_id: str, filename: str, data: bytes) -> None:
        """Persist a recording. Implementations may apply size/LRU limits."""
        ...

    async def delete_recording(self, recording_id: str) -> None:
        """Remove a recording. No-op if missing."""
        ...

    async def count(self) -> int:
        """Return the total number of stored recordings."""
        ...
