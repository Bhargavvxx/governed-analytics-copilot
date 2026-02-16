"""
Integration tests -- query audit log.

Requires live Postgres with the analytics database.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

try:
    from src.db.connection import get_engine

    engine = get_engine()
    with engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="Postgres not reachable")

from src.db.query_log import ensure_log_table, log_query



def test_ensure_log_table_idempotent():
    """Calling ensure_log_table() multiple times must not raise."""
    ensure_log_table()
    ensure_log_table()  # second call should be a no-op


def test_log_table_exists():
    ensure_log_table()
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'copilot_query_logs' "
            "AND table_schema = 'public'"
        )).fetchall()
    assert len(rows) == 1



def test_log_query_inserts_row():
    ensure_log_table()

    # Get count before
    engine = get_engine()
    with engine.connect() as conn:
        before = conn.execute(text(
            "SELECT COUNT(*) FROM copilot_query_logs"
        )).scalar()

    log_query(
        question="test query from pytest",
        mode="mock",
        spec={"metric": "revenue", "dimensions": ["country"], "filters": {}, "time_grain": "month", "time_range": "last 6 months"},
        sql="SELECT 1",
        row_count=1,
        validation_errors=[],
        safety_errors=[],
        latency_ms=42,
    )

    with engine.connect() as conn:
        after = conn.execute(text(
            "SELECT COUNT(*) FROM copilot_query_logs"
        )).scalar()

    assert after == before + 1


def test_log_query_stores_metric():
    ensure_log_table()
    log_query(
        question="revenue by country",
        mode="mock",
        spec={"metric": "revenue", "dimensions": ["country"], "filters": {}, "time_grain": None, "time_range": None},
        sql="SELECT country, SUM(total_amount) ...",
        row_count=5,
        validation_errors=[],
        safety_errors=[],
        latency_ms=100,
    )

    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT metric, row_count, validation_ok, safety_ok "
            "FROM copilot_query_logs ORDER BY id DESC LIMIT 1"
        )).fetchone()

    assert row[0] == "revenue"
    assert row[1] == 5
    assert row[2] is True
    assert row[3] is True


def test_log_query_records_errors():
    ensure_log_table()
    log_query(
        question="bad question",
        mode="mock",
        spec={"metric": "nonexistent", "dimensions": [], "filters": {}, "time_grain": None, "time_range": None},
        sql="",
        row_count=0,
        validation_errors=["Unknown metric 'nonexistent'"],
        safety_errors=[],
        latency_ms=5,
    )

    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT validation_ok, validation_errors "
            "FROM copilot_query_logs ORDER BY id DESC LIMIT 1"
        )).fetchone()

    assert row[0] is False
    assert "nonexistent" in row[1]
