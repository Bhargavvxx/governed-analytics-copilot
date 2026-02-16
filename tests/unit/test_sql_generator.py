"""
Unit tests — SQL generator: builds governed SQL from QuerySpec.
"""
import re
import pytest
from src.copilot.spec import QuerySpec
from src.copilot.sql_generator import generate_sql, _resolve_time_range
from src.governance.semantic_loader import load_semantic_model


@pytest.fixture(scope="module")
def model():
    return load_semantic_model()


# ── Helper ───────────────────────────────────────────────

def _spec(**overrides) -> QuerySpec:
    defaults = dict(
        metric="revenue",
        dimensions=[],
        filters={},
        time_grain=None,
        time_range=None,
        limit=200,
    )
    defaults.update(overrides)
    return QuerySpec(**defaults)


# ── Basic structure ──────────────────────────────────────

def test_generates_select(model):
    sql = generate_sql(_spec(), model)
    assert sql.strip().upper().startswith("SELECT")


def test_has_limit(model):
    sql = generate_sql(_spec(limit=50), model)
    assert "LIMIT 50" in sql


def test_limit_clamped(model):
    sql = generate_sql(_spec(limit=999), model)
    assert "LIMIT 200" in sql


def test_has_from(model):
    sql = generate_sql(_spec(), model)
    assert "FROM marts_marts.fct_order_items" in sql


def test_has_order_by(model):
    sql = generate_sql(_spec(), model)
    assert "ORDER BY revenue DESC" in sql


# ── Metric expression ───────────────────────────────────

def test_revenue_expression(model):
    sql = generate_sql(_spec(), model)
    assert "SUM(oi.quantity * oi.unit_price) AS revenue" in sql


def test_orders_expression(model):
    sql = generate_sql(_spec(metric="orders"), model)
    assert "COUNT(DISTINCT o.order_id) AS orders" in sql


def test_aov_expression(model):
    sql = generate_sql(_spec(metric="aov"), model)
    assert "NULLIF" in sql


# ── Metric filters ───────────────────────────────────────

def test_revenue_has_completed_filter(model):
    sql = generate_sql(_spec(), model)
    assert "oi.status = 'completed'" in sql


def test_orders_has_completed_filter(model):
    sql = generate_sql(_spec(metric="orders"), model)
    assert "o.status = 'completed'" in sql


# ── Dimensions and GROUP BY ──────────────────────────────

def test_country_dimension(model):
    sql = generate_sql(_spec(dimensions=["country"]), model)
    assert "u.country AS country" in sql
    assert "GROUP BY u.country" in sql


def test_category_dimension(model):
    sql = generate_sql(_spec(dimensions=["category"]), model)
    assert "p.category AS category" in sql
    assert "GROUP BY p.category" in sql


def test_date_dimension_month(model):
    sql = generate_sql(_spec(dimensions=["date"], time_grain="month"), model)
    assert "d.month_start AS date_month" in sql
    assert "GROUP BY d.month_start" in sql


def test_date_dimension_week(model):
    sql = generate_sql(_spec(dimensions=["date"], time_grain="week"), model)
    assert "d.week_start AS date_week" in sql


def test_date_dimension_day(model):
    sql = generate_sql(_spec(dimensions=["date"], time_grain="day"), model)
    assert "d.date_day AS date_day" in sql


def test_multiple_dimensions(model):
    sql = generate_sql(_spec(dimensions=["country", "date"], time_grain="month"), model)
    assert "u.country AS country" in sql
    assert "d.month_start AS date_month" in sql
    assert "GROUP BY" in sql


# ── Joins ────────────────────────────────────────────────

def test_country_join(model):
    sql = generate_sql(_spec(dimensions=["country"]), model)
    # Must join dim_users
    assert "JOIN" in sql.upper()
    assert "dim_users" in sql


def test_category_join(model):
    sql = generate_sql(_spec(dimensions=["category"]), model)
    assert "dim_products" in sql


def test_date_join(model):
    sql = generate_sql(_spec(dimensions=["date"], time_grain="month"), model)
    assert "dim_date" in sql


def test_no_unnecessary_joins(model):
    """No dimensions → no joins needed beyond base table."""
    sql = generate_sql(_spec(), model)
    assert "JOIN" not in sql.upper()


# ── Spec-level filters ──────────────────────────────────

def test_country_filter_single(model):
    sql = generate_sql(_spec(filters={"country": ["US"]}), model)
    assert "u.country = 'US'" in sql


def test_country_filter_multi(model):
    sql = generate_sql(_spec(filters={"country": ["US", "IN"]}), model)
    assert "u.country IN" in sql
    assert "'US'" in sql
    assert "'IN'" in sql


# ── Time range ───────────────────────────────────────────

def test_time_range_adds_where(model):
    sql = generate_sql(
        _spec(dimensions=["date"], time_grain="month", time_range="last 6 months"),
        model,
    )
    assert "d.date_day >=" in sql
    assert "d.date_day <=" in sql


def test_resolve_time_range_last_30_days():
    result = _resolve_time_range("last 30 days")
    assert result is not None
    start, end = result
    assert (end - start).days == 30


def test_resolve_time_range_this_month():
    result = _resolve_time_range("this month")
    assert result is not None
    assert result[0].day == 1


def test_resolve_time_range_none():
    assert _resolve_time_range(None) is None
    assert _resolve_time_range("") is None


# ── Error handling ───────────────────────────────────────

def test_unknown_metric_raises(model):
    with pytest.raises(ValueError, match="Unknown metric"):
        generate_sql(_spec(metric="nonexistent"), model)


# ── Full end-to-end SQL shape ────────────────────────────

def test_full_sql_shape(model):
    sql = generate_sql(
        _spec(
            metric="revenue",
            dimensions=["country", "date"],
            filters={"country": ["US"]},
            time_grain="month",
            time_range="last 6 months",
            limit=100,
        ),
        model,
    )
    upper = sql.upper()
    # Must have all major clauses
    assert "SELECT" in upper
    assert "FROM" in upper
    assert "JOIN" in upper
    assert "WHERE" in upper
    assert "GROUP BY" in upper
    assert "ORDER BY" in upper
    assert "LIMIT 100" in sql
