"""
Integration tests — SQL executor against live PostgreSQL.

These tests require a running Postgres instance with the analytics
database populated by dbt.  They are automatically skipped when the
database is unreachable.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

# ── Guard: skip all tests if DB is unreachable ───────────
try:
    from src.db.connection import get_engine

    engine = get_engine()
    with engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="Postgres not reachable")

from src.db.executor import execute_readonly


# ── Basic connectivity ───────────────────────────────────

def test_simple_select():
    rows = execute_readonly("SELECT 1 AS n")
    assert rows == [{"n": 1}]


def test_multiple_rows():
    rows = execute_readonly("SELECT generate_series(1,3) AS n")
    assert len(rows) == 3
    values = [r["n"] for r in rows]
    assert values == [1, 2, 3]


# ── Read-only enforcement ───────────────────────────────

def test_write_blocked():
    """READ ONLY transaction must reject INSERT/UPDATE/DELETE."""
    with pytest.raises(Exception):
        execute_readonly("CREATE TABLE _test_no_write (id INT)")


# ── Timeout enforcement ─────────────────────────────────

def test_timeout_fires():
    """Statement that exceeds timeout should be cancelled."""
    with pytest.raises(Exception):
        execute_readonly("SELECT pg_sleep(30)", timeout_ms=200)


# ── Decimal / date serialisation ─────────────────────────

def test_decimal_serialised_to_float():
    rows = execute_readonly("SELECT 3.14::numeric AS val")
    assert isinstance(rows[0]["val"], float)
    assert abs(rows[0]["val"] - 3.14) < 0.001


def test_date_serialised_to_iso():
    rows = execute_readonly("SELECT DATE '2024-01-15' AS d")
    assert rows[0]["d"] == "2024-01-15"


def test_timestamp_serialised_to_iso():
    rows = execute_readonly("SELECT TIMESTAMP '2024-01-15 10:30:00' AS ts")
    assert rows[0]["ts"].startswith("2024-01-15T10:30:00")


# ── Queries against mart tables ──────────────────────────

def test_query_fct_orders():
    rows = execute_readonly(
        "SELECT COUNT(*) AS cnt FROM marts_marts.fct_orders LIMIT 1"
    )
    assert len(rows) == 1
    assert rows[0]["cnt"] > 0


def test_query_revenue_aggregation():
    rows = execute_readonly("""
        SELECT u.country, SUM(o.revenue) AS total_revenue
        FROM marts_marts.fct_orders o
        JOIN marts_marts.dim_users u ON o.user_id = u.user_id
        GROUP BY u.country
        ORDER BY total_revenue DESC
        LIMIT 5
    """)
    assert len(rows) >= 1
    assert "country" in rows[0]
    assert "total_revenue" in rows[0]
    assert isinstance(rows[0]["total_revenue"], float)
