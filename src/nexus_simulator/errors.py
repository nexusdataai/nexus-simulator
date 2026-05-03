"""Exception hierarchy for the Nexus Simulator library.

All library-raised exceptions inherit from ``SimulatorError`` so consumers can
catch a single type and inspect ``.code`` if they need to branch on subclass.
"""

from __future__ import annotations


class SimulatorError(Exception):
    """Base class for all errors raised by ``nexus_simulator``."""

    code: str = "simulator_error"


class SimulatorNotConfigured(SimulatorError):
    """``build_simulator`` was called without enough config to instantiate any plugin."""

    code = "simulator_not_configured"


class PluginNotEnabled(SimulatorError):
    """A caller asked for a plugin that was not enabled in ``SimulatorConfig``."""

    code = "plugin_not_enabled"


class StorageError(SimulatorError):
    """A backing store (S3, DynamoDB, Redis) failed."""

    code = "storage_error"


class CacheError(SimulatorError):
    """The cache port (Redis or in-memory fallback) failed."""

    code = "cache_error"


class QueryError(SimulatorError):
    """An FDW query against a simulator failed."""

    code = "query_error"
