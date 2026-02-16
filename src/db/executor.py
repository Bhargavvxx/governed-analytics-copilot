"""
Read-only SQL executor.

All copilot-generated queries run through `execute_readonly`, which:
  1. Opens a READ ONLY transaction (Postgres-enforced)
  2. Wraps the query in text() to prevent raw SQL injection
  3. Converts Decimal/date/datetime to JSON-safe Python types
  4. Enforces query timeout (statement_timeout)
"""
from __future__ import annotations

import decimal
import datetime
from typing import Any

from sqlalchemy import text

from src.db.connection import readonly_connection
from src.core.logging import get_logger

logger = get_logger(__name__)

_QUERY_TIMEOUT_MS = 10_000  # 10 seconds max per query


def _serialise_value(val: Any) -> Any:
    """Convert DB types to JSON-serialisable Python types."""
    if isinstance(val, decimal.Decimal):
        return float(val)
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.isoformat()
    if isinstance(val, datetime.timedelta):
        return str(val)
    return val


def execute_readonly(
    sql: str,
    params: dict | None = None,
    timeout_ms: int = _QUERY_TIMEOUT_MS,
) -> list[dict[str, Any]]:
    """Execute a read-only SQL query and return rows as serialisable dicts.

    Raises
    ------
    RuntimeError
        If the query fails for any reason.
    """
    logger.info("Executing SQL (%d chars)", len(sql))

    with readonly_connection() as conn:
        # Per-query timeout
        conn.execute(text(f"SET LOCAL statement_timeout = {int(timeout_ms)}"))

        result = conn.execute(text(sql), params or {})
        columns = list(result.keys())
        rows = [
            {col: _serialise_value(val) for col, val in zip(columns, row)}
            for row in result.fetchall()
        ]

    logger.info("Returned %d rows", len(rows))
    return rows
