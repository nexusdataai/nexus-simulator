"""Protocol ports for adapter substitution.

Each port is a small ``Protocol`` defining what a plugin needs from its
storage / cache / query / recordings backend. Default adapter implementations
live in ``nexus_simulator.adapters`` and are wired by ``build_simulator``.
Custom adapters can be supplied by host applications via direct injection.
"""

from .cache import CacheBackend
from .fdw import FDWQueryPort
from .recordings import RecordingsBackend
from .storage import StorageBackend

__all__ = [
    "CacheBackend",
    "FDWQueryPort",
    "RecordingsBackend",
    "StorageBackend",
]
