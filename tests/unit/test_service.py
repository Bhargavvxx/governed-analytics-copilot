"""
Unit tests -- copilot service: end-to-end mock pipeline.
Uses execute=False so no DB connection is needed.
"""
from src.copilot.service import ask, CopilotResult


def test_ask_returns_copilot_result():
    result = ask("Revenue by country last 6 months", execute=False)
    assert isinstance(result, CopilotResult)


def test_ask_success_on_valid_question():
    result = ask("Revenue by country last 6 months", execute=False)
    assert result.success is True
    assert result.validation_errors == []
    assert result.safety_errors == []


def test_ask_produces_sql():
    result = ask("Revenue by country last 6 months", execute=False)
    assert len(result.sql) > 0
    assert "SELECT" in result.sql.upper()


def test_ask_spec_populated():
    result = ask("Orders by month this year", execute=False)
    assert result.spec.metric == "orders"


def test_ask_latency_tracked():
    result = ask("Revenue last 30 days", execute=False)
    assert result.latency_ms >= 0


def test_ask_no_rows_when_execute_false():
    """Dry-run mode should never return rows."""
    result = ask("Revenue by country last 6 months", execute=False)
    assert result.rows == []


def test_derived_metric_blocked_end_to_end():
    """conversion_proxy is derived -- must be rejected at validation."""
    result = ask("Conversion proxy by month last 6 months", execute=False)
    assert result.success is False
    assert any("derived" in e.lower() for e in result.validation_errors)
    assert result.spec.metric == "conversion_proxy"
    assert result.sql == ""  # no SQL generated for blocked queries


def test_disallowed_dimension_blocked_end_to_end():
    """active_users by category must be rejected -- category not in allowed_dimensions."""
    result = ask("Active users by category last 30 days", execute=False)
    assert result.success is False
    assert any("not allowed" in e.lower() and "category" in e for e in result.validation_errors)
    assert result.spec.metric == "active_users"
    assert result.sql == ""  # no SQL generated for blocked queries
