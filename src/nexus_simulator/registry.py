"""SimulatorRegistry — plugin discovery + lookup for built simulator instances.

The registry is populated at startup by ``build_simulator``: each enabled
plugin in ``SimulatorConfig`` produces a ``BaseSimulator`` instance that gets
registered under its short name (``wxcc``, ``sfdc``, ``oracle_erp``, ``sap``,
``external_source``).

Third-party plugins outside the in-tree set can register a factory via the
module-level ``register_simulator`` helper before ``build_simulator`` runs.
The factory takes a ``SimulatorConfig`` and returns a ``BaseSimulator``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base.simulator import BaseSimulator
    from .config import SimulatorConfig


SimulatorFactory = Callable[["SimulatorConfig"], "BaseSimulator"]


class SimulatorRegistry:
    """Per-instance registry returned from ``build_simulator``.

    Holds the live ``BaseSimulator`` instances keyed by plugin name. Used by
    the FastAPI routers (``app.state.simulator.registry.get("wxcc")``) and by
    direct library consumers that want to enumerate enabled plugins.
    """

    def __init__(self) -> None:
        self._instances: dict[str, BaseSimulator] = {}

    def register(self, name: str, simulator: BaseSimulator) -> None:
        """Register a built simulator instance under ``name``."""
        self._instances[name] = simulator

    def get(self, name: str) -> BaseSimulator | None:
        """Return the registered simulator or ``None`` if the plugin is disabled."""
        return self._instances.get(name)

    def all(self) -> dict[str, BaseSimulator]:
        """Return a copy of all registered (name -> instance) pairs."""
        return dict(self._instances)

    def names(self) -> list[str]:
        """Return the sorted list of registered plugin names."""
        return sorted(self._instances.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._instances


# Module-level factory registry for out-of-tree plugins.
# ``build_simulator`` consults this after wiring the in-tree plugins.
_FACTORIES: dict[str, SimulatorFactory] = {}


def register_simulator(name: str, factory: SimulatorFactory) -> None:
    """Register a factory for an out-of-tree simulator plugin.

    Call before ``build_simulator(config)``. The factory receives the full
    ``SimulatorConfig`` and should return a ``BaseSimulator`` instance ready
    to be added to the registry.

    Args:
        name: Short, unique plugin name (e.g. ``"my_custom"``).
        factory: Callable ``(SimulatorConfig) -> BaseSimulator``.
    """
    if name in _FACTORIES:
        raise ValueError(f"Simulator plugin already registered: {name}")
    _FACTORIES[name] = factory


def get_registered_factories() -> dict[str, SimulatorFactory]:
    """Internal: return a copy of the out-of-tree factory registry."""
    return dict(_FACTORIES)


def _clear_registered_factories() -> None:
    """Test-only: reset the module-level factory registry."""
    _FACTORIES.clear()
