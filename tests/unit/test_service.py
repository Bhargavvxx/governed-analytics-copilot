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
