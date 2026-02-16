"""
Copilot query audit log -- records every question -> SQL -> result cycle.

The table is created automatically on first use via `ensure_log_table()`.
"""
from __future__ import annotations

import json
import datetime
from typing import Any

from sqlalchemy import text

from src.db.connection import get_engine
from src.core.logging import get_logger

logger = get_logger(__name__)

_TABLE = "copilot_query_logs"

_CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {_TABLE} (
    id              SERIAL PRIMARY KEY,
    question        TEXT NOT NULL,
    mode            VARCHAR(20) NOT NULL DEFAULT 'mock',
    metric          VARCHAR(60),
    dimensions      TEXT,          -- JSON array
    filters         TEXT,          -- JSON object
    time_grain      VARCHAR(20),
    time_range      VARCHAR(60),
    generated_sql   TEXT,
    row_count       INTEGER,
    validation_ok   BOOLEAN NOT NULL DEFAULT TRUE,
    safety_ok       BOOLEAN NOT NULL DEFAULT TRUE,
    validation_errors TEXT,        -- JSON array
    safety_errors     TEXT,        -- JSON array
    latency_ms      INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def ensure_log_table() -> None:
    """Create the query log table if it doesn't exist."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text(_CREATE_SQL))
        conn.commit()
    logger.info("Query log table '%s' ensured", _TABLE)


def log_query(
    question: str,
    mode: str,
    spec: dict[str, Any] | None,
    sql: str,
    row_count: int,
    validation_errors: list[str],
    safety_errors: list[str],
    latency_ms: int,
) -> None:
    """Insert one row into the query log table."""
    engine = get_engine()
    insert_sql = text(f"""
        INSERT INTO {_TABLE}
            (question, mode, metric, dimensions, filters,
             time_grain, time_range, generated_sql, row_count,
             validation_ok, safety_ok, validation_errors, safety_errors,
             latency_ms)
        VALUES
            (:question, :mode, :metric, :dimensions, :filters,
             :time_grain, :time_range, :generated_sql, :row_count,
             :validation_ok, :safety_ok, :validation_errors, :safety_errors,
             :latency_ms)
    """)

    params = {
        "question": question,
        "mode": mode,
        "metric": spec.get("metric") if spec else None,
        "dimensions": json.dumps(spec.get("dimensions", [])) if spec else None,
        "filters": json.dumps(spec.get("filters", {})) if spec else None,
        "time_grain": spec.get("time_grain") if spec else None,
        "time_range": spec.get("time_range") if spec else None,
        "generated_sql": sql or None,
        "row_count": row_count,
        "validation_ok": len(validation_errors) == 0,
        "safety_ok": len(safety_errors) == 0,
        "validation_errors": json.dumps(validation_errors) if validation_errors else None,
        "safety_errors": json.dumps(safety_errors) if safety_errors else None,
        "latency_ms": latency_ms,
    }

    try:
        with engine.connect() as conn:
            conn.execute(insert_sql, params)
            conn.commit()
        logger.debug("Query logged: question=%s", question[:80])
    except Exception:
        logger.exception("Failed to log query -- continuing without logging")
