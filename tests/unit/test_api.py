"""
API tests -- FastAPI endpoints via TestClient (no live server needed).
"""
import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)



def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"



def test_metrics_list():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics" in data
    assert "revenue" in data["metrics"]
    assert "conversion_proxy" not in data["metrics"]  # derived -- excluded
    assert len(data["metrics"]) == 6


def test_dimensions_list():
    resp = client.get("/dimensions")
    assert resp.status_code == 200
    data = resp.json()
    assert "dimensions" in data
    assert "country" in data["dimensions"]
    assert len(data["dimensions"]) == 6



def test_metrics_detail():
    resp = client.get("/metrics/detail")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    names = [m["name"] for m in items]
    assert "revenue" in names
    # Check structure
    revenue = next(m for m in items if m["name"] == "revenue")
    assert "description" in revenue
    assert revenue["is_derived"] is False


def test_dimensions_detail():
    resp = client.get("/dimensions/detail")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    names = [d["name"] for d in items]
    assert "date" in names
    date_dim = next(d for d in items if d["name"] == "date")
    assert "day" in date_dim["grains"]


def test_full_catalog():
    resp = client.get("/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics" in data
    assert "dimensions" in data
    assert "allowed_tables" in data
    assert "max_rows" in data
    assert data["max_rows"] == 200
    assert len(data["allowed_tables"]) == 6



def test_ask_basic():
    resp = client.post("/ask", json={"question": "Revenue by country last 6 months", "execute": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["question"] == "Revenue by country last 6 months"
    assert data["spec"]["metric"] == "revenue"
    assert len(data["sql"]) > 0
    assert "SELECT" in data["sql"]


def test_ask_with_mode():
    resp = client.post("/ask", json={"question": "Monthly orders this year", "mode": "mock", "execute": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["spec"]["metric"] == "orders"


def test_ask_returns_spec_structure():
    resp = client.post("/ask", json={"question": "Revenue last 30 days", "execute": False})
    data = resp.json()
    spec = data["spec"]
    assert "metric" in spec
    assert "dimensions" in spec
    assert "filters" in spec
    assert "time_grain" in spec
    assert "time_range" in spec
    assert "limit" in spec


def test_ask_has_latency():
    resp = client.post("/ask", json={"question": "Revenue last month", "execute": False})
    data = resp.json()
    assert "latency_ms" in data
    assert isinstance(data["latency_ms"], int)
    assert data["latency_ms"] >= 0


def test_ask_validation_and_safety_empty_on_success():
    resp = client.post("/ask", json={"question": "Revenue by country last 6 months", "execute": False})
    data = resp.json()
    assert data["validation_errors"] == []
    assert data["safety_errors"] == []


def test_ask_question_too_short():
    resp = client.post("/ask", json={"question": "Hi"})
    assert resp.status_code == 422  # Pydantic validation


def test_ask_empty_body():
    resp = client.post("/ask", json={})
    assert resp.status_code == 422



def test_explain_basic():
    resp = client.post("/ask/explain", json={"question": "Revenue by country last 6 months"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert data["validation_errors"] == []
    assert data["spec"]["metric"] == "revenue"


def test_explain_no_sql_returned():
    """Explain endpoint should NOT return SQL."""
    resp = client.post("/ask/explain", json={"question": "Revenue last 6 months"})
    data = resp.json()
    assert "sql" not in data  # explain doesn't generate SQL



def test_generated_sql_has_proper_clauses():
    resp = client.post("/ask", json={"question": "Revenue by category by month last 6 months", "execute": False})
    data = resp.json()
    sql = data["sql"].upper()
    assert "SELECT" in sql
    assert "FROM" in sql
    assert "JOIN" in sql
    assert "WHERE" in sql
    assert "GROUP BY" in sql
    assert "ORDER BY" in sql
    assert "LIMIT" in sql


def test_generated_sql_uses_governed_tables():
    resp = client.post("/ask", json={"question": "Revenue by country last 6 months", "execute": False})
    sql = resp.json()["sql"]
    assert "marts_marts." in sql



def test_multiple_asks():
    """Verify the API is stateless -- each call independent."""
    r1 = client.post("/ask", json={"question": "Revenue last 6 months", "execute": False})
    r2 = client.post("/ask", json={"question": "Orders this year", "execute": False})
    assert r1.json()["spec"]["metric"] == "revenue"
    assert r2.json()["spec"]["metric"] == "orders"
