"""
Integration tests — full service pipeline with live SQL execution.

Tests the complete ask() flow end-to-end: NL → Spec → SQL → Execute → Rows.
Requires live Postgres with dbt mart tables populated.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

# ── Guard: skip if DB is unreachable ─────────────────────
try:
    from src.db.connection import get_engine

    engine = get_engine()
    with engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="Postgres not reachable")

from src.copilot.service import ask, CopilotResult


# ── End-to-end with execute=True ─────────────────────────

def test_ask_returns_real_rows():
    result = ask("Revenue by country last 6 months", execute=True)
    assert isinstance(result, CopilotResult)
    assert result.success is True
    assert len(result.rows) > 0


def test_rows_contain_metric_and_dimension():
    result = ask("Revenue by country last 6 months", execute=True)
    first = result.rows[0]
    # Should have country and a revenue aggregate
    assert "country" in first
    assert any(k in first for k in ("revenue", "total_revenue"))


def test_ask_row_count_within_limit():
    result = ask("Revenue by country last 6 months", execute=True)
    assert len(result.rows) <= result.spec.limit


def test_execute_false_returns_no_rows():
    result = ask("Revenue by country last 6 months", execute=False)
    assert result.rows == []
    assert result.success is True
    assert len(result.sql) > 0


def test_orders_by_month():
    result = ask("Orders by month last 30 days", execute=True)
    assert result.success is True
    # Seed data may not have orders in recent 30 days either —
    # just verify the pipeline completes without error
    assert isinstance(result.rows, list)


def test_latency_is_positive_when_executing():
    result = ask("Revenue last 30 days", execute=True)
    assert result.latency_ms > 0


def test_audit_log_written():
    """After an ask(), the query log table should have a new row."""
    from src.db.query_log import ensure_log_table

    ensure_log_table()
    engine = get_engine()

    with engine.connect() as conn:
        before = conn.execute(text(
            "SELECT COUNT(*) FROM copilot_query_logs"
        )).scalar()

    ask("Revenue by country last 6 months", execute=True)

    with engine.connect() as conn:
        after = conn.execute(text(
            "SELECT COUNT(*) FROM copilot_query_logs"
        )).scalar()

    assert after >= before + 1
