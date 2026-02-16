"""
Unit tests — validator: all 8 validation checks.
"""
import pytest
from src.governance.semantic_loader import load_semantic_model, SemanticModel
from src.governance.validator import validate_spec


@pytest.fixture(scope="module")
def model() -> SemanticModel:
    return load_semantic_model()


# ── Helper: build a valid spec ───────────────────────────

def _valid_spec(**overrides) -> dict:
    base = {
        "metric": "revenue",
        "dimensions": ["country"],
        "filters": {},
        "time_grain": "month",
        "limit": 50,
    }
    base.update(overrides)
    return base


# ── 0. Valid spec → no errors ────────────────────────────

def test_valid_spec_no_errors(model):
    errors = validate_spec(_valid_spec(), model)
    assert errors == []


def test_valid_spec_no_dimensions(model):
    errors = validate_spec(_valid_spec(dimensions=[]), model)
    assert errors == []


def test_valid_spec_multiple_dimensions(model):
    errors = validate_spec(
        _valid_spec(dimensions=["country", "category", "date"]),
        model,
    )
    assert errors == []


# ── 1. Unknown metric ───────────────────────────────────

def test_unknown_metric(model):
    errors = validate_spec(_valid_spec(metric="nonexistent"), model)
    assert any("metric" in e.lower() and "nonexistent" in e for e in errors)


# ── 2. Derived metric blocked ───────────────────────────

def test_derived_metric_blocked(model):
    errors = validate_spec(_valid_spec(metric="conversion_proxy"), model)
    assert any("derived" in e.lower() or "cannot be queried" in e.lower() for e in errors)


# ── 3. Unknown dimension ────────────────────────────────

def test_unknown_dimension(model):
    errors = validate_spec(
        _valid_spec(dimensions=["country", "weather"]),
        model,
    )
    assert any("weather" in e for e in errors)


# ── 4. Filter key not a valid dimension ──────────────────

def test_filter_key_invalid(model):
    errors = validate_spec(
        _valid_spec(filters={"nonsense": "US"}),
        model,
    )
    assert any("nonsense" in e for e in errors)


def test_filter_key_valid(model):
    errors = validate_spec(
        _valid_spec(filters={"country": ["US"]}),
        model,
    )
    assert errors == []


# ── 5. Time grain validation ────────────────────────────

def test_invalid_time_grain(model):
    errors = validate_spec(_valid_spec(time_grain="quarter"), model)
    assert any("grain" in e.lower() or "quarter" in e.lower() for e in errors)


def test_valid_time_grains(model):
    for grain in ("day", "week", "month"):
        errors = validate_spec(_valid_spec(time_grain=grain), model)
        assert errors == [], f"grain={grain} should be valid but got: {errors}"


def test_no_time_grain(model):
    spec = _valid_spec()
    del spec["time_grain"]
    errors = validate_spec(spec, model)
    # time_grain is optional; missing is OK
    assert not any("grain" in e.lower() for e in errors)


# ── 6. Join-path reachability ────────────────────────────

def test_reachable_dimensions(model):
    """revenue is on fct_order_items; country is on dim_users; path exists via fct_orders"""
    errors = validate_spec(
        _valid_spec(metric="revenue", dimensions=["country"]),
        model,
    )
    assert errors == []


def test_reachable_category_from_revenue(model):
    """revenue on fct_order_items; category on dim_products; direct join exists"""
    errors = validate_spec(
        _valid_spec(metric="revenue", dimensions=["category"]),
        model,
    )
    assert errors == []


# ── 7. Filter value sanity ──────────────────────────────

def test_empty_string_filter_value(model):
    errors = validate_spec(
        _valid_spec(filters={"country": [""]}),
        model,
    )
    assert any("empty" in e.lower() or "invalid" in e.lower() for e in errors)


def test_none_filter_value(model):
    errors = validate_spec(
        _valid_spec(filters={"country": None}),
        model,
    )
    # None is not a list, so validator rejects it
    assert any("list" in e.lower() for e in errors)


def test_list_filter_with_empty_element(model):
    errors = validate_spec(
        _valid_spec(filters={"country": ["US", ""]}),
        model,
    )
    assert any("empty" in e.lower() or "blank" in e.lower() for e in errors)


# ── 8. Limit exceeds max_rows ───────────────────────────

def test_limit_exceeds_max_rows(model):
    errors = validate_spec(_valid_spec(limit=500), model)
    assert any("limit" in e.lower() or "200" in e or "max" in e.lower() for e in errors)


def test_limit_at_max(model):
    errors = validate_spec(_valid_spec(limit=200), model)
    assert errors == []


def test_limit_zero(model):
    errors = validate_spec(_valid_spec(limit=0), model)
    # 0 is acceptable — means "no limit"
    assert not any("limit" in e.lower() for e in errors)


# ── Edge cases ───────────────────────────────────────────

def test_multiple_errors_at_once(model):
    """Valid metric + bad dimension + bad filter key + bad grain + over-limit.
    Validator short-circuits on unknown metric, so use a valid one."""
    spec = {
        "metric": "revenue",
        "dimensions": ["bad_dim"],
        "filters": {"bad_filter_key": ["x"]},
        "time_grain": "century",
        "limit": 9999,
    }
    errors = validate_spec(spec, model)
    assert len(errors) >= 3  # dimension + filter key + grain


def test_validate_spec_auto_loads_model():
    """When model is not passed, loader should auto-load."""
    errors = validate_spec(_valid_spec())
    assert errors == []
