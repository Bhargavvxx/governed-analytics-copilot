"""
Unit tests -- Chart auto-generation.
"""
import pytest
from src.copilot.chart_generator import suggest_chart, CHART_BAR, CHART_LINE, CHART_PIE, CHART_METRIC, CHART_TABLE


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


# ── Single KPI (no dimensions) ──────────────────────────

def test_single_kpi():
    spec = _make_spec()
    rows = [{"revenue": 123456.78}]
    chart = suggest_chart(spec, rows, "revenue")
    assert chart.chart_type == CHART_METRIC
    assert chart.kpi_value == 123456.78
    assert chart.kpi_label == "revenue"


# ── Line chart (time-series) ────────────────────────────

def test_time_series_line_chart():
    spec = _make_spec(dimensions=["date"], time_grain="month")
    rows = [
        {"date_month": "2025-01", "revenue": 100},
        {"date_month": "2025-02", "revenue": 200},
        {"date_month": "2025-03", "revenue": 300},
    ]
    chart = suggest_chart(spec, rows, "revenue")
    assert chart.chart_type == CHART_LINE
    assert chart.x_column == "date_month"
    assert chart.y_column == "revenue"


# ── Pie chart (few categories) ──────────────────────────

def test_pie_for_few_categories():
    spec = _make_spec(dimensions=["country"])
    rows = [
        {"country": "US", "revenue": 500},
        {"country": "UK", "revenue": 300},
        {"country": "IN", "revenue": 200},
    ]
    chart = suggest_chart(spec, rows, "revenue")
    assert chart.chart_type == CHART_PIE


# ── Bar chart (many categories) ─────────────────────────

def test_bar_for_many_categories():
    spec = _make_spec(dimensions=["brand"])
    rows = [{"brand": f"brand_{i}", "revenue": i * 100} for i in range(10)]
    chart = suggest_chart(spec, rows, "revenue")
    assert chart.chart_type == CHART_BAR
    assert chart.x_column == "brand"
    assert chart.y_column == "revenue"


# ── Multi-dimension chart ───────────────────────────────

def test_multi_dimension_line_with_color():
    spec = _make_spec(dimensions=["date", "country"], time_grain="month")
    rows = [
        {"date_month": "2025-01", "country": "US", "revenue": 100},
        {"date_month": "2025-01", "country": "UK", "revenue": 80},
        {"date_month": "2025-02", "country": "US", "revenue": 120},
        {"date_month": "2025-02", "country": "UK", "revenue": 90},
    ]
    chart = suggest_chart(spec, rows, "revenue")
    assert chart.chart_type == CHART_LINE
    assert chart.color_column == "country"


# ── Empty rows → table ──────────────────────────────────

def test_empty_rows():
    spec = _make_spec(dimensions=["country"])
    chart = suggest_chart(spec, [], "revenue")
    assert chart.chart_type == CHART_TABLE
    assert len(chart.rows) == 0


# ── Title generation ────────────────────────────────────

def test_title_includes_metric():
    spec = _make_spec(dimensions=["country"], time_range="last 6 months")
    rows = [{"country": "US", "revenue": 100}]
    chart = suggest_chart(spec, rows, "revenue")
    assert "Revenue" in chart.title
    assert "Country" in chart.title
    assert "last 6 months" in chart.title


# ── to_dict ─────────────────────────────────────────────

def test_to_dict():
    spec = _make_spec()
    rows = [{"revenue": 42}]
    chart = suggest_chart(spec, rows, "revenue")
    d = chart.to_dict()
    assert d["chart_type"] == CHART_METRIC
    assert d["row_count"] == 1
