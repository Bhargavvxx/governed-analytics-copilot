"""
Unit tests — SQL safety checker: all 9 safety gates.
"""
import pytest
from src.governance.sql_safety import check_sql_safety
from src.governance.semantic_loader import load_semantic_model


@pytest.fixture(scope="module")
def model():
    return load_semantic_model()


# ── Helper: a known-safe SQL ─────────────────────────────

_SAFE_SQL = """\
SELECT
  u.country AS country,
  SUM(oi.quantity * oi.unit_price) AS revenue
FROM marts_marts.fct_order_items AS oi
LEFT JOIN marts_marts.dim_users AS u ON oi.user_id = u.user_id
WHERE oi.status = 'completed'
GROUP BY u.country
ORDER BY revenue DESC
LIMIT 50"""


def test_safe_sql_passes(model):
    errors = check_sql_safety(_SAFE_SQL, model)
    assert errors == [], f"Expected no errors but got: {errors}"


# ── 1. Must start with SELECT ───────────────────────────

def test_not_select(model):
    errors = check_sql_safety("INSERT INTO foo VALUES (1)", model)
    assert any("SELECT" in e for e in errors)


# ── 2. No multi-statement ───────────────────────────────

def test_multi_statement(model):
    sql = "SELECT 1 AS x LIMIT 10; DROP TABLE users"
    errors = check_sql_safety(sql, model)
    assert any("Multi-statement" in e or "Dangerous" in e for e in errors)


# ── 3. No SELECT * ──────────────────────────────────────

def test_select_star(model):
    sql = "SELECT * FROM marts_marts.fct_orders LIMIT 10"
    errors = check_sql_safety(sql, model)
    assert any("SELECT *" in e for e in errors)


# ── 4. No dangerous keywords ────────────────────────────

@pytest.mark.parametrize("keyword", [
    "DROP TABLE foo",
    "ALTER TABLE foo ADD col int",
    "TRUNCATE TABLE foo",
    "DELETE FROM foo",
    "UPDATE foo SET x=1",
    "INSERT INTO foo VALUES (1)",
    "GRANT ALL ON foo TO public",
    "CREATE TABLE foo (id int)",
])
def test_dangerous_keywords(model, keyword):
    errors = check_sql_safety(keyword, model)
    assert any("Dangerous" in e or "SELECT" in e for e in errors)


# ── 5. No SQL comments ──────────────────────────────────

def test_inline_comment(model):
    sql = "SELECT 1 AS x -- sneaky comment\nLIMIT 10"
    errors = check_sql_safety(sql, model)
    assert any("comment" in e.lower() for e in errors)


def test_block_comment(model):
    sql = "SELECT 1 AS x /* hidden */ LIMIT 10"
    errors = check_sql_safety(sql, model)
    assert any("comment" in e.lower() for e in errors)


# ── 6. Blocked schemas ──────────────────────────────────

def test_blocked_schema_pg_catalog(model):
    sql = "SELECT tablename FROM pg_catalog.pg_tables LIMIT 10"
    errors = check_sql_safety(sql, model)
    assert any("pg_catalog" in e for e in errors)


def test_blocked_schema_information_schema(model):
    sql = "SELECT table_name FROM information_schema.tables LIMIT 10"
    errors = check_sql_safety(sql, model)
    assert any("information_schema" in e for e in errors)


# ── 7. Blocked columns in SELECT ────────────────────────

def test_blocked_column_user_id_in_select(model):
    sql = "SELECT oi.user_id, SUM(oi.quantity) AS items\nFROM marts_marts.fct_order_items AS oi\nLIMIT 10"
    errors = check_sql_safety(sql, model)
    assert any("user_id" in e for e in errors)


def test_blocked_column_order_id_in_select(model):
    sql = "SELECT o.order_id, COUNT(*) AS cnt\nFROM marts_marts.fct_orders AS o\nLIMIT 10"
    errors = check_sql_safety(sql, model)
    assert any("order_id" in e for e in errors)


def test_blocked_column_in_join_on_is_ok(model):
    """Blocked columns in JOIN ON clauses are fine — only the SELECT projection is checked."""
    errors = check_sql_safety(_SAFE_SQL, model)
    # _SAFE_SQL has oi.user_id in the ON clause but not in SELECT
    assert errors == []


def test_blocked_column_inside_aggregate_is_ok(model):
    """Blocked columns inside COUNT/SUM/… are not exposed as raw values."""
    sql = (
        "SELECT COUNT(DISTINCT o.order_id) AS orders\n"
        "FROM marts_marts.fct_orders AS o\n"
        "LIMIT 10"
    )
    errors = check_sql_safety(sql, model)
    assert not any("order_id" in e for e in errors)


def test_blocked_column_inside_sum_is_ok(model):
    sql = (
        "SELECT SUM(o.user_id) AS uid_sum\n"
        "FROM marts_marts.fct_orders AS o\n"
        "LIMIT 10"
    )
    errors = check_sql_safety(sql, model)
    assert not any("user_id" in e for e in errors)


# ── 8. Allowed tables only ──────────────────────────────

def test_disallowed_table(model):
    sql = "SELECT COUNT(*) AS cnt FROM public.secret_table LIMIT 10"
    errors = check_sql_safety(sql, model)
    assert any("not in the allowed" in e for e in errors)


def test_allowed_table_passes(model):
    sql = "SELECT SUM(oi.quantity) AS items FROM marts_marts.fct_order_items AS oi LIMIT 10"
    errors = check_sql_safety(sql, model)
    # No table-related errors
    assert not any("allowed" in e.lower() for e in errors)


# ── 9. LIMIT clause ─────────────────────────────────────

def test_missing_limit(model):
    sql = "SELECT 1 AS x FROM marts_marts.fct_orders AS o"
    errors = check_sql_safety(sql, model)
    assert any("LIMIT" in e for e in errors)


def test_limit_too_high(model):
    sql = "SELECT 1 AS x FROM marts_marts.fct_orders AS o LIMIT 999"
    errors = check_sql_safety(sql, model)
    assert any("LIMIT" in e and "999" in e for e in errors)


def test_limit_at_max(model):
    sql = "SELECT 1 AS x FROM marts_marts.fct_orders AS o LIMIT 200"
    errors = check_sql_safety(sql, model)
    assert not any("LIMIT" in e for e in errors)


# ── Edge cases ───────────────────────────────────────────

def test_empty_sql(model):
    errors = check_sql_safety("", model)
    assert len(errors) >= 1


def test_auto_loads_model():
    """When model is None, auto-loads from disk."""
    errors = check_sql_safety(_SAFE_SQL)
    assert errors == []
