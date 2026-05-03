"""Shared pydantic models for the Nexus Simulator library.

The FDW request/response models in ``nexus_simulator.models.fdw`` are a
verbatim port of ``nexus-backend/src/models/fdw_models.py``. Keeping them
under the simulator namespace lets the library stand alone and lets backend
depend on it for the same models after the Phase 9 swap-in.
"""

from . import fdw

__all__ = ["fdw"]
