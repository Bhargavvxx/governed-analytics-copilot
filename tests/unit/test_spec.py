"""
Unit tests — smoke test for imports & QuerySpec.
"""
from src.copilot.spec import QuerySpec


def test_query_spec_defaults():
    spec = QuerySpec(metric="revenue")
    assert spec.metric == "revenue"
    assert spec.limit == 200
    assert spec.dimensions == []
    assert spec.filters == {}


def test_query_spec_full():
    spec = QuerySpec(
        metric="aov",
        dimensions=["date", "country"],
        filters={"country": ["India", "US"]},
        time_grain="month",
        time_range="last 6 months",
        limit=50,
    )
    assert spec.metric == "aov"
    assert "country" in spec.dimensions
    assert spec.limit == 50
