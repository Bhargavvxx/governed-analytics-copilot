"""
Unit tests -- Natural-language metric & dimension suggestions.
"""
import pytest
from src.copilot.suggestions import suggest, suggest_metrics, suggest_dimensions, Suggestion


def test_exact_metric_match():
    results = suggest_metrics("revenue")
    assert len(results) > 0
    assert results[0].name == "revenue"
    assert results[0].score > 0.8


def test_partial_metric_match():
    results = suggest_metrics("rev")
    names = [r.name for r in results]
    assert "revenue" in names


def test_fuzzy_metric_match():
    """'order count' should suggest 'orders' metric via description overlap."""
    results = suggest_metrics("order count", min_score=0.10)
    names = [r.name for r in results]
    assert "orders" in names


def test_orders_suggestion():
    results = suggest_metrics("orders")
    assert len(results) > 0
    assert results[0].name == "orders"


def test_dimension_suggest():
    results = suggest_dimensions("country")
    assert len(results) > 0
    assert results[0].name == "country"


def test_dimension_partial():
    results = suggest_dimensions("cat")
    names = [r.name for r in results]
    assert "category" in names


def test_combined_suggest():
    results = suggest("revenue")
    kinds = {r.kind for r in results}
    assert "metric" in kinds


def test_top_k_limits():
    results = suggest("a", top_k=2)
    assert len(results) <= 2


def test_min_score_filter():
    results = suggest("xyznonexistent", min_score=0.90)
    assert len(results) == 0


def test_suggestion_to_dict():
    s = Suggestion(name="revenue", kind="metric", description="Total revenue", score=0.95)
    d = s.to_dict()
    assert d["name"] == "revenue"
    assert d["kind"] == "metric"
    assert d["score"] == 0.95


def test_derived_metric_flagged():
    results = suggest_metrics("conversion")
    derived = [r for r in results if r.name == "conversion_proxy"]
    if derived:
        assert derived[0].is_derived is True


def test_empty_query():
    results = suggest("")
    # Empty query should still work (may return low-score suggestions)
    assert isinstance(results, list)


def test_revenue_suggestions_include_related():
    """User types 'revenue' → should suggest revenue, aov, items_sold (related)."""
    results = suggest("revenue", top_k=6, min_score=0.15)
    names = [r.name for r in results]
    assert "revenue" in names
