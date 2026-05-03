"""WXCC simulator plugin (Phase 5).

Public re-exports::

    WXCCSimulatorService    — the core simulator (port of nexus-backend's WXCC service).
    SimulatorProcessor      — journey-stage helper that consumes the service.
    SimulatorConfig         — dataclass passed to ``SimulatorProcessor``
                              (NOT the library-level ``SimulatorConfig``;
                              this is the per-plugin config used by the journey
                              stage in nexus-ai-engine).

The journey stage class (``WXCCSimulatorStage``) intentionally stays in
nexus-ai-engine and imports ``SimulatorProcessor`` from this module after
Phase 9.
"""

from .processor import SimulatorConfig, SimulatorProcessor
from .service import WXCCSimulatorService

__all__ = [
    "SimulatorConfig",
    "SimulatorProcessor",
    "WXCCSimulatorService",
]
