"""
Unit tests -- Query cost & performance guardrails.
"""
import pytest
from src.governance.cost_guard import estimate_query_cost, block_if_too_expensive, CostEstimate


def _make_spec(**overrides):
    base = {
        "metric": "revenue",
        "dimensions": [],
        "filters": {},
        "time_grain": None,
        "time_range": None,
        "limit": 200,
    }
    base.update(overrides)
    return base


# ── estimate_query_cost ─────────────────────────────────

def test_simple_query_low_cost():
    spec = _make_spec(dimensions=["country"], time_range="last 6 months")
    sql = "SELECT u.country AS country, SUM(oi.quantity * oi.unit_price) AS revenue\nFROM marts_marts.fct_order_items AS oi\nLEFT JOIN marts_marts.dim_users AS u ON oi.user_id = u.user_id\nWHERE oi.status = 'completed'\nGROUP BY u.country\nORDER BY revenue DESC\nLIMIT 200"
    est = estimate_query_cost(spec, sql)
    assert est.estimated_score < 50
    assert est.dimension_count == 1
    assert est.has_time_range is True


def test_many_dimensions_high_cost():
    spec = _make_spec(dimensions=["date", "country", "device", "category", "brand", "order_status"])
    sql = "SELECT d.date_day, u.country, u.device, p.category, p.brand, o.status, SUM(x) AS revenue\nFROM t AS oi\nJOIN t2 AS o ON 1=1\nJOIN t3 AS u ON 1=1\nJOIN t4 AS p ON 1=1\nJOIN t5 AS d ON 1=1\nGROUP BY 1,2,3,4,5,6\nLIMIT 200"
    est = estimate_query_cost(spec, sql)
    assert est.estimated_score > 50
    assert est.dimension_count == 6
    assert len(est.warnings) > 0


def test_no_time_range_with_date_warns():
    spec = _make_spec(dimensions=["date"])
    sql = "SELECT d.date_day, SUM(x) AS revenue\nFROM t AS oi\nJOIN t2 AS d ON 1=1\nGROUP BY 1\nLIMIT 200"
    est = estimate_query_cost(spec, sql)
    assert any("time_range" in w.lower() for w in est.warnings)


def test_cte_adds_cost():
    spec = _make_spec()
    sql_with_cte = "WITH cte AS (SELECT 1) SELECT SUM(x) AS revenue FROM t LIMIT 200"
    sql_without_cte = "SELECT SUM(x) AS revenue FROM t LIMIT 200"
    est_with = estimate_query_cost(spec, sql_with_cte)
    est_without = estimate_query_cost(spec, sql_without_cte)
    assert est_with.has_cte is True
    assert est_without.has_cte is False
    assert est_with.estimated_score > est_without.estimated_score


def test_many_joins_warns():
    spec = _make_spec(dimensions=["date", "country", "category"])
    sql = "SELECT x FROM t JOIN a ON 1=1 JOIN b ON 1=1 JOIN c ON 1=1 JOIN d ON 1=1 JOIN e ON 1=1 LIMIT 200"
    est = estimate_query_cost(spec, sql)
    assert est.join_count == 5
    assert any("join" in w.lower() for w in est.warnings)


# ── block_if_too_expensive ──────────────────────────────

def test_block_high_cost():
    est = CostEstimate(estimated_score=90, warnings=["too many joins"])
    errors = block_if_too_expensive(est, threshold=85)
    assert len(errors) == 1
    assert "blocked" in errors[0].lower()


def test_no_block_low_cost():
    est = CostEstimate(estimated_score=30, warnings=[])
    errors = block_if_too_expensive(est, threshold=85)
    assert errors == []


def test_block_at_exact_threshold():
    est = CostEstimate(estimated_score=85, warnings=[])
    errors = block_if_too_expensive(est, threshold=85)
    assert len(errors) == 1
