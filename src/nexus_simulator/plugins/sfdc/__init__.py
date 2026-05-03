"""SFDC simulator plugin (Phase 6).

Public re-exports::

    SFDCSimulatorService — Redis-backed FDW simulator for Salesforce CRM.
"""

from .service import SFDCSimulatorService

__all__ = ["SFDCSimulatorService"]
