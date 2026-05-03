"""
SAP Simulator Models

Pydantic models for the SAP S/4HANA simulator admin API.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SimulatorStatus(BaseModel):
    """Status of the SAP simulator."""
    enabled: bool
    loaded: bool
    bucket: str = ""
    prefix: str = ""
    schema: str = ""
    table_count: int = 0
    tables_with_data: int = 0
    total_rows: int = 0
    dump_timestamp: str | None = None
    last_loaded: datetime | None = None


class ObjectSummary(BaseModel):
    """Summary of a loaded table."""
    schema_name: str = Field(..., alias="schemaName")
    table_name: str = Field(..., alias="tableName")
    column_count: int = Field(0, alias="columnCount")
    row_count: int = Field(0, alias="rowCount")

    class Config:
        populate_by_name = True


class ObjectRecordsResponse(BaseModel):
    """Paginated records for a table."""
    schema_name: str = Field(..., alias="schemaName")
    table_name: str = Field(..., alias="tableName")
    rows: list[dict]
    total: int
    limit: int
    offset: int

    class Config:
        populate_by_name = True


class AdminResponse(BaseModel):
    """Generic admin response."""
    success: bool = True
    message: str
    data: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
