"""
QuerySpec -- the structured intermediate representation between
natural language and SQL.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class QuerySpec(BaseModel):
    """Parsed representation of a business question."""

    metric: str = Field(..., description="Primary metric name (e.g. 'revenue')")
    dimensions: list[str] = Field(default_factory=list, description="Group-by dimensions")
    filters: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Dimension -> list of allowed values, e.g. {'country': ['India', 'US']}",
    )
    time_grain: str | None = Field(None, description="day | week | month")
    time_range: str | None = Field(None, description="Natural-language time range, e.g. 'last 6 months'")
    limit: int = Field(200, description="Maximum rows to return")
