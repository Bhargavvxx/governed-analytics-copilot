"""
Unit tests -- semantic loader: parsing, lookups, join graph.
"""
from src.governance.semantic_loader import (
    load_semantic_model,
    get_metric_names,
    get_dimension_names,
    SemanticModel,
    Metric,
    Dimension,
    JoinEdge,
)



def test_loads_without_error():
    model = load_semantic_model()
    assert isinstance(model, SemanticModel)
    assert model.version == 1


def test_metric_names_loaded():
    """get_metric_names() returns only queryable (non-derived) metrics."""
    names = get_metric_names()
    assert "revenue" in names
    assert "aov" in names
    assert "orders" in names
    assert "items_sold" in names
    assert "active_users" in names
    assert "returning_customers" in names
    assert "conversion_proxy" not in names  # derived -- excluded
    assert len(names) == 6


def test_dimension_names_loaded():
    names = get_dimension_names()
    assert "country" in names
    assert "device" in names
    assert "category" in names
    assert "brand" in names
    assert "date" in names
    assert "order_status" in names
    assert len(names) == 6



def test_metric_revenue_definition():
    model = load_semantic_model()
    m = model.metric("revenue")
    assert m is not None
    assert isinstance(m, Metric)
    assert m.base_table == "marts_marts.fct_order_items"
    assert m.alias == "oi"
    assert "SUM" in m.expression
    assert len(m.filters) >= 1
    assert "completed" in m.filters[0]


def test_metric_derived_flag():
    model = load_semantic_model()
    cp = model.metric("conversion_proxy")
    assert cp is not None
    assert cp.is_derived is True
    assert "orders" in cp.components
    assert "active_users" in cp.components


def test_metric_not_found_returns_none():
    model = load_semantic_model()
    assert model.metric("nonexistent_metric") is None



def test_dimension_date_has_grains():
    model = load_semantic_model()
    d = model.dimension("date")
    assert d is not None
    assert isinstance(d, Dimension)
    assert set(d.grains) == {"day", "week", "month"}
    assert "day" in d.grain_expressions
    assert "week" in d.grain_expressions
    assert "month" in d.grain_expressions


def test_dimension_country():
    model = load_semantic_model()
    d = model.dimension("country")
    assert d is not None
    assert d.column == "u.country"
    assert d.table == "marts_marts.dim_users"
    assert d.alias == "u"



def test_joins_loaded():
    model = load_semantic_model()
    assert len(model.joins) >= 5
    for j in model.joins:
        assert isinstance(j, JoinEdge)
        assert j.on  # non-empty ON clause


def test_find_join_direct():
    model = load_semantic_model()
    j = model.find_join("marts_marts.fct_orders", "marts_marts.dim_users")
    assert j is not None
    assert "user_id" in j.on


def test_find_join_reverse():
    model = load_semantic_model()
    # Should find the same join regardless of argument order
    j = model.find_join("marts_marts.dim_users", "marts_marts.fct_orders")
    assert j is not None


def test_find_join_not_exists():
    model = load_semantic_model()
    j = model.find_join("marts_marts.dim_users", "raw.raw_sessions")
    # dim_users is not directly connected to raw_sessions (sessions->dim_users, not reverse-keyed)
    # Actually it IS -- raw_sessions -> dim_users exists
    # So let's test a truly impossible join
    j2 = model.find_join("marts_marts.dim_products", "raw.raw_sessions")
    assert j2 is None


def test_tables_reachable_from_fct_orders():
    model = load_semantic_model()
    reachable = model.tables_reachable_from("marts_marts.fct_orders")
    assert "marts_marts.dim_users" in reachable
    assert "marts_marts.dim_date" in reachable
    assert "marts_marts.fct_order_items" in reachable


def test_tables_reachable_from_fct_order_items():
    model = load_semantic_model()
    reachable = model.tables_reachable_from("marts_marts.fct_order_items")
    assert "marts_marts.dim_products" in reachable
    assert "marts_marts.fct_orders" in reachable
    assert "marts_marts.dim_users" in reachable
    assert "marts_marts.dim_date" in reachable


def test_find_join_path():
    model = load_semantic_model()
    path = model.find_join_path(
        "marts_marts.fct_order_items", "marts_marts.dim_users"
    )
    assert path is not None
    assert len(path) >= 1  # at least one hop


def test_find_join_path_same_table():
    model = load_semantic_model()
    path = model.find_join_path("marts_marts.fct_orders", "marts_marts.fct_orders")
    assert path == []



def test_security_blocked_columns():
    model = load_semantic_model()
    assert "user_id" in model.security.blocked_columns
    assert "order_id" in model.security.blocked_columns


def test_security_max_rows():
    model = load_semantic_model()
    assert model.security.max_rows == 200


def test_security_read_only():
    model = load_semantic_model()
    assert model.security.read_only is True



def test_allowed_tables():
    model = load_semantic_model()
    assert "marts_marts.fct_orders" in model.allowed_tables
    assert "marts_marts.fct_order_items" in model.allowed_tables
    assert "raw.raw_sessions" in model.allowed_tables
    assert "pg_catalog.pg_tables" not in model.allowed_tables



def test_alias_to_table():
    model = load_semantic_model()
    mapping = model.alias_to_table()
    assert mapping["o"] == "marts_marts.fct_orders"
    assert mapping["oi"] == "marts_marts.fct_order_items"
    assert mapping["u"] == "marts_marts.dim_users"
    assert mapping["d"] == "marts_marts.dim_date"
    assert mapping["p"] == "marts_marts.dim_products"
    assert mapping["s"] == "raw.raw_sessions"
