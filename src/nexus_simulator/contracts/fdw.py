"""FDWQueryPort.

Surface used by the ``fdw_api`` host integration in nexus-backend. A simulator
plugin satisfies this port to be a drop-in replacement for the real FDW
discovery + query stack. Mirrors the public methods of
``BaseSimulatorService`` in nexus-backend so the existing integration in
``nexus-backend/src/apis/fdw_api.py::configure_simulator`` works unchanged.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models.fdw import (
    ColumnInfo,
    ForeignServerInfo,
    ForeignTableInfo,
    QueryRequest,
    QueryResponse,
)


@runtime_checkable
class FDWQueryPort(Protocol):
    """Discovery + query surface for an FDW-style simulator."""

    @property
    def loaded(self) -> bool:
        """Whether the simulator has data ready to serve."""
        ...

    async def ensure_loaded(self) -> None:
        """Lazy-load data on first use; idempotent."""
        ...

    async def list_foreign_servers(self) -> list[ForeignServerInfo]:
        """Return the foreign servers this simulator advertises."""
        ...

    async def list_foreign_tables(
        self, server_name: str | None = None
    ) -> list[ForeignTableInfo]:
        """Return foreign tables, optionally filtered by server."""
        ...

    async def get_table_columns(self, schema: str, table: str) -> list[ColumnInfo]:
        """Return the column metadata for a single table."""
        ...

    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """Execute a filtered/projected/ordered/paginated query."""
        ...
