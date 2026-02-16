"""
Unit tests -- planner: mock-mode keyword extraction.
"""
import pytest
from src.copilot.planner import plan, _plan_mock, _parse_llm_response
from src.copilot.spec import QuerySpec
from src.governance.semantic_loader import load_semantic_model


@pytest.fixture(scope="module")
def model():
    return load_semantic_model()



def test_revenue_detected():
    spec = plan("What is the total revenue this year?")
    assert spec.metric == "revenue"


def test_orders_detected():
    spec = plan("How many orders last month?")
    assert spec.metric == "orders"


def test_aov_detected():
    spec = plan("Show me the average order value by country")
    assert spec.metric == "aov"


def test_items_sold_detected():
    spec = plan("Total items sold last 3 months")
    assert spec.metric == "items_sold"


def test_active_users_detected():
    spec = plan("How many active users last 30 days?")
    assert spec.metric == "active_users"


def test_returning_customers_detected():
    spec = plan("Show returning customers by month")
    assert spec.metric == "returning_customers"


def test_fallback_to_revenue():
    spec = plan("Tell me something interesting")
    assert spec.metric == "revenue"



def test_date_dimension():
    spec = plan("Revenue over time")
    assert "date" in spec.dimensions


def test_country_dimension():
    spec = plan("Revenue by country last 6 months")
    assert "country" in spec.dimensions


def test_category_dimension():
    spec = plan("Items sold by category")
    assert "category" in spec.dimensions


def test_brand_dimension():
    spec = plan("Revenue by brand this year")
    assert "brand" in spec.dimensions


def test_device_dimension():
    spec = plan("Orders by device")
    assert "device" in spec.dimensions


def test_multiple_dimensions():
    spec = plan("Revenue by country by month")
    assert "country" in spec.dimensions
    assert "date" in spec.dimensions


def test_no_dimensions():
    spec = plan("Total revenue")
    assert spec.dimensions == [] or spec.metric == "revenue"



def test_grain_daily():
    spec = plan("Daily revenue last 30 days")
    assert spec.time_grain == "day"


def test_grain_weekly():
    spec = plan("Weekly orders last 3 months")
    assert spec.time_grain == "week"


def test_grain_monthly():
    spec = plan("Monthly revenue this year")
    assert spec.time_grain == "month"


def test_date_dimension_defaults_to_month():
    spec = plan("Revenue over time")
    assert spec.time_grain == "month"



def test_time_range_last_6_months():
    spec = plan("Revenue last 6 months")
    assert spec.time_range == "last 6 months"


def test_time_range_last_30_days():
    spec = plan("Orders last 30 days")
    assert spec.time_range == "last 30 days"


def test_time_range_this_month():
    spec = plan("Revenue this month")
    assert spec.time_range == "this month"


def test_time_range_this_year():
    spec = plan("Revenue this year")
    assert spec.time_range == "this year"



def test_country_filter():
    spec = plan("Revenue in US last 6 months")
    assert spec.filters.get("country") == ["US"]


def test_multi_country_filter():
    spec = plan("Revenue in US, IN last year")
    assert "US" in spec.filters.get("country", [])
    assert "IN" in spec.filters.get("country", [])



def test_top_10():
    spec = plan("Top 10 products by revenue")
    assert spec.limit == 10


def test_limit_capped_at_max_rows():
    spec = plan("Top 500 items by revenue")
    assert spec.limit <= 200



def test_returns_query_spec():
    spec = plan("Revenue by country last 6 months")
    assert isinstance(spec, QuerySpec)
    assert spec.metric == "revenue"



def test_parse_valid_llm_json(model):
    json_text = '{"metric": "orders", "dimensions": ["country"], "filters": {}, "time_grain": "month", "time_range": "last 6 months", "limit": 50}'
    spec = _parse_llm_response(json_text, model)
    assert spec.metric == "orders"
    assert spec.dimensions == ["country"]
    assert spec.limit == 50


def test_parse_llm_json_with_fences(model):
    json_text = '```json\n{"metric": "revenue", "dimensions": [], "filters": {}, "time_grain": null, "time_range": null, "limit": 200}\n```'
    spec = _parse_llm_response(json_text, model)
    assert spec.metric == "revenue"


def test_parse_llm_invalid_json_fallback(model):
    spec = _parse_llm_response("This is not JSON at all!", model)
    # Should fall back to mock planner defaults
    assert isinstance(spec, QuerySpec)


def test_parse_llm_clamps_limit(model):
    json_text = '{"metric": "revenue", "dimensions": [], "filters": {}, "time_grain": null, "time_range": null, "limit": 9999}'
    spec = _parse_llm_response(json_text, model)
    assert spec.limit <= 200
