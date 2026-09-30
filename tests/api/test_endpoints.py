"""
tests/api/test_endpoints.py
Integration test suite for the FastAPI REST API endpoints using TestClient.
Tests both happy paths and boundary/error conditions for every single endpoint.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. System Endpoints (Health & Sample Queries)
# ---------------------------------------------------------------------------


def test_health_check_endpoint():
    """Verify GET /api/health returns status ok and valid version."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"


def test_sample_queries_endpoint():
    """Verify GET /api/sample-queries returns non-empty list of sample queries."""
    response = client.get("/api/sample-queries")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    assert "query" in first
    assert "description" in first
    assert "category" in first


# ---------------------------------------------------------------------------
# 2. Query Analysis Endpoint (/api/analyze)
# ---------------------------------------------------------------------------


def test_analyze_query_happy_path():
    """Verify POST /api/analyze parses SQL and returns findings and score."""
    payload = {"query": "SELECT * FROM orders WHERE customer_id = 42;"}
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == payload["query"]
    assert "issues" in data
    assert "complexity" in data
    assert "score" in data
    assert data["score"]["score"] <= 100


@pytest.mark.parametrize(
    "invalid_query,expected_detail",
    [
        ("", "at least 1 character"),
        ("   ", "whitespace"),
        ("SELECT 1; " * 2500, "at most 20000 characters"),
    ],
)
def test_analyze_query_invalid_input(invalid_query, expected_detail):
    """Verify POST /api/analyze rejects empty, whitespace, or oversized queries with 422."""
    response = client.post("/api/analyze", json={"query": invalid_query})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data


# ---------------------------------------------------------------------------
# 3. Performance Scoring Endpoint (/api/score)
# ---------------------------------------------------------------------------


def test_score_query_happy_path():
    """Verify POST /api/score returns calculated score and cost breakdown."""
    payload = {"query": "SELECT id, name FROM customers WHERE id = 1050;"}
    response = client.post("/api/score", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert 0 <= data["score"] <= 100
    assert data["cost_estimate"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert isinstance(data["breakdown"], list)


def test_score_query_invalid_input():
    """Verify POST /api/score rejects empty query with 422."""
    response = client.post("/api/score", json={"query": ""})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 4. Optimization Recommendations Endpoint (/api/optimize)
# ---------------------------------------------------------------------------


def test_optimize_query_happy_path():
    """Verify POST /api/optimize returns architectural advice and insight."""
    payload = {"query": "SELECT * FROM orders WHERE total_amount > 500;"}
    response = client.post("/api/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "optimizations" in data
    assert "insight" in data
    assert isinstance(data["optimizations"], list)


def test_optimize_query_invalid_input():
    """Verify POST /api/optimize rejects empty input with 422."""
    response = client.post("/api/optimize", json={"query": "   "})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 5. Index Recommendations Endpoint (/api/recommendations)
# ---------------------------------------------------------------------------


def test_recommendations_happy_path():
    """Verify POST /api/recommendations produces ranked DDL suggestions."""
    payload = {"query": "SELECT * FROM orders WHERE customer_id = 42;"}
    response = client.post("/api/recommendations", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "recommendations" in data
    assert data["count"] == len(data["recommendations"])
    if data["count"] > 0:
        first_rec = data["recommendations"][0]
        assert "ddl" in first_rec
        assert "CREATE INDEX" in first_rec["ddl"]


def test_recommendations_invalid_input():
    """Verify POST /api/recommendations rejects empty input with 422."""
    response = client.post("/api/recommendations", json={"query": ""})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 6. Query Rewrite Endpoint (/api/rewrite)
# ---------------------------------------------------------------------------


def test_rewrite_query_happy_path():
    """Verify POST /api/rewrite transforms non-sargable functions into date ranges."""
    payload = {"query": "SELECT * FROM orders WHERE YEAR(order_date) = 2024;"}
    response = client.post("/api/rewrite", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "rewritten" in data
    assert "is_changed" in data
    assert "validation" in data
    if data["is_changed"]:
        assert "2024-01-01" in data["rewritten"]


def test_rewrite_query_invalid_input():
    """Verify POST /api/rewrite rejects empty query with 422."""
    response = client.post("/api/rewrite", json={"query": ""})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 7. Execution Plan Endpoint (/api/execution-plan)
# ---------------------------------------------------------------------------


def test_execution_plan_happy_path():
    """Verify POST /api/execution-plan produces hierarchical plan tree."""
    payload = {"query": "SELECT c.name, o.id FROM customers c JOIN orders o ON c.id = o.customer_id;"}
    response = client.post("/api/execution-plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "plan_root" in data
    assert "flattened_nodes" in data
    assert "summary" in data
    assert data["plan_root"]["node_type"] != ""


def test_execution_plan_invalid_input():
    """Verify POST /api/execution-plan rejects empty query with 422."""
    response = client.post("/api/execution-plan", json={"query": ""})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 8. Simulate Index Endpoint (/api/simulate-index)
# ---------------------------------------------------------------------------


def test_simulate_index_happy_path():
    """Verify POST /api/simulate-index computes before/after latency and speedup."""
    payload = {
        "query": "SELECT * FROM orders WHERE customer_id = 42;",
        "index": "CREATE INDEX idx_orders_customer_id ON orders(customer_id);",
    }
    response = client.post("/api/simulate-index", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["index"] == payload["index"]
    assert "simulation" in data
    sim = data["simulation"]
    assert "before_score" in sim
    assert "after_score" in sim
    assert "speedup_factor" in sim


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "", "index": "CREATE INDEX idx ON orders(id);"},
        {"query": "SELECT * FROM orders;", "index": ""},
        {"query": "   ", "index": "   "},
    ],
)
def test_simulate_index_invalid_input(payload):
    """Verify POST /api/simulate-index rejects missing or empty fields with 422."""
    response = client.post("/api/simulate-index", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 9. CORS and OpenAPI Documentation Verification
# ---------------------------------------------------------------------------


def test_openapi_docs_endpoint():
    """Verify /docs and /openapi.json are accessible and properly documented."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/api/analyze" in schema["paths"]
    assert "/api/health" in schema["paths"]


def test_cors_headers_on_options():
    """Verify CORS preflight headers accept localhost:5173."""
    response = client.options(
        "/api/analyze",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
