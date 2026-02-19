"""
Unit tests -- LLM explanation layer.
"""
from src.copilot.explainer import explain_errors, explain_errors_mock


def test_success_explanation():
    result = explain_errors_mock("Revenue by country", [], [])
    assert "successfully" in result.lower()


def test_validation_error_explanation():
    v_errors = ["Unknown metric 'foo'. Allowed: revenue, orders"]
    result = explain_errors_mock("foo by date", v_errors, [])
    assert "blocked" in result.lower() or "why" in result.lower()
    assert "catalog" in result.lower()


def test_safety_error_explanation():
    s_errors = ["Dangerous keyword detected: 'DROP'."]
    result = explain_errors_mock("DROP TABLE users", [], s_errors)
    assert "dangerous" in result.lower()


def test_rbac_error_explanation():
    rbac_errors = ["Role 'viewer' does not have access to metric 'active_users'."]
    result = explain_errors_mock("active users", [], [], rbac_errors=rbac_errors)
    assert "role" in result.lower() or "access" in result.lower()


def test_cost_warning_explanation():
    cost_warnings = ["Query estimated cost score is 90/100 (threshold: 85). Query blocked."]
    result = explain_errors_mock("revenue by everything", [], [], cost_warnings=cost_warnings)
    assert "cost" in result.lower() or "reduce" in result.lower()


def test_pii_explanation():
    v_errors = ["Question requests personally identifiable information -- blocked."]
    result = explain_errors_mock("show me emails", v_errors, [])
    assert "personal" in result.lower() or "pii" in result.lower()


def test_derived_metric_explanation():
    v_errors = ["Metric 'conversion_proxy' is a derived/composite metric."]
    result = explain_errors_mock("conversion proxy", v_errors, [])
    assert "derived" in result.lower()


def test_explain_errors_dispatches_mock():
    result = explain_errors("revenue by country", [], [], mode="mock")
    assert "successfully" in result.lower()


def test_multiple_errors_all_explained():
    v_errors = ["Unknown metric 'foo'."]
    s_errors = ["Blocked column 'user_id' appears in SELECT."]
    result = explain_errors_mock("foo", v_errors, s_errors)
    assert "Unknown metric" in result
    assert "Blocked column" in result
    assert "How to fix" in result
