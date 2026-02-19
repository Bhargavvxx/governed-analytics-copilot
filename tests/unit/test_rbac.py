"""
Unit tests -- RBAC (Role-Based Access Control).
"""
import pytest
from src.governance.rbac import Role, parse_roles, check_rbac


# ── parse_roles ─────────────────────────────────────────

def test_parse_roles_empty():
    assert parse_roles(None) == {}
    assert parse_roles({}) == {}


def test_parse_roles_basic():
    raw = {
        "finance": {
            "allowed_metrics": ["revenue", "aov"],
            "allowed_dimensions": ["date", "country"],
        },
        "analyst": {
            "allowed_metrics": "*",
            "allowed_dimensions": "*",
        },
    }
    roles = parse_roles(raw)
    assert "finance" in roles
    assert "analyst" in roles
    assert roles["finance"].allowed_metrics == ["revenue", "aov"]
    assert roles["analyst"].wildcard_metrics is True
    assert roles["analyst"].wildcard_dimensions is True


# ── check_rbac ──────────────────────────────────────────

@pytest.fixture
def sample_roles() -> dict[str, Role]:
    return parse_roles({
        "finance": {
            "allowed_metrics": ["revenue", "aov", "orders"],
            "allowed_dimensions": ["date", "country", "category"],
        },
        "marketing": {
            "allowed_metrics": ["active_users", "orders"],
            "allowed_dimensions": ["date", "country", "device"],
        },
        "analyst": {
            "allowed_metrics": "*",
            "allowed_dimensions": "*",
        },
    })


def test_no_role_bypasses_rbac(sample_roles):
    errors = check_rbac(None, "revenue", ["date"], sample_roles)
    assert errors == []


def test_empty_role_bypasses_rbac(sample_roles):
    errors = check_rbac("", "revenue", ["date"], sample_roles)
    assert errors == []


def test_unknown_role(sample_roles):
    errors = check_rbac("intern", "revenue", ["date"], sample_roles)
    assert len(errors) == 1
    assert "Unknown role" in errors[0]


def test_finance_can_access_revenue(sample_roles):
    errors = check_rbac("finance", "revenue", ["date", "country"], sample_roles)
    assert errors == []


def test_finance_blocked_from_active_users(sample_roles):
    errors = check_rbac("finance", "active_users", ["date"], sample_roles)
    assert len(errors) == 1
    assert "active_users" in errors[0]


def test_finance_blocked_from_device_dimension(sample_roles):
    errors = check_rbac("finance", "revenue", ["date", "device"], sample_roles)
    assert len(errors) == 1
    assert "device" in errors[0]


def test_marketing_can_access_active_users(sample_roles):
    errors = check_rbac("marketing", "active_users", ["date", "device"], sample_roles)
    assert errors == []


def test_marketing_blocked_from_revenue(sample_roles):
    errors = check_rbac("marketing", "revenue", ["date"], sample_roles)
    assert len(errors) == 1
    assert "revenue" in errors[0]


def test_analyst_wildcard_access(sample_roles):
    errors = check_rbac("analyst", "revenue", ["date", "device", "category"], sample_roles)
    assert errors == []


def test_analyst_can_access_any_metric(sample_roles):
    errors = check_rbac("analyst", "active_users", ["device"], sample_roles)
    assert errors == []


def test_no_roles_defined():
    """When no roles are defined, everything is allowed."""
    errors = check_rbac("finance", "revenue", ["date"], {})
    assert errors == []


def test_multiple_violations(sample_roles):
    """Marketing requesting revenue + category → metric + dimension errors."""
    errors = check_rbac("marketing", "revenue", ["category"], sample_roles)
    assert len(errors) == 2
    assert any("revenue" in e for e in errors)
    assert any("category" in e for e in errors)
