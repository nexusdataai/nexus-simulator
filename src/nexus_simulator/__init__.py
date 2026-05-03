"""Nexus Simulator — pluggable simulator library.

Public API is intentionally small during the 0.1.0a* pre-release phase and will
stabilize at 0.1.0. The names re-exported below are part of the stable surface
even during the alpha series.
"""

from .config import (
    ExternalSourcePluginConfig,
    OracleERPPluginConfig,
    SAPPluginConfig,
    SFDCPluginConfig,
    SimulatorConfig,
    WXCCPluginConfig,
)
from .errors import (
    CacheError,
    PluginNotEnabled,
    QueryError,
    SimulatorError,
    SimulatorNotConfigured,
    StorageError,
)
from .factory import Simulator, build_simulator
from .registry import SimulatorRegistry, register_simulator

__version__ = "0.1.0a1"

__all__ = [
    "__version__",
    # Config
    "SimulatorConfig",
    "WXCCPluginConfig",
    "SFDCPluginConfig",
    "OracleERPPluginConfig",
    "SAPPluginConfig",
    "ExternalSourcePluginConfig",
    # Factory
    "Simulator",
    "build_simulator",
    # Registry
    "SimulatorRegistry",
    "register_simulator",
    # Errors
    "SimulatorError",
    "SimulatorNotConfigured",
    "PluginNotEnabled",
    "StorageError",
    "CacheError",
    "QueryError",
]
