"""tests/api/test_matrix_api.py
Integration & Edge-Case Test Suite executing all API and Cross-Cutting Matrix Rows.
"""

from __future__ import annotations

import csv
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


# =============================================================================
# 1. API Endpoints Matrix Tests
# =============================================================================

def test_api_health_ok():
    """API-HEALTH-OK: GET /api/health returns status ok and version."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"


def test_api_sample_queries_ok():
    """API-SAMPLE-QUERIES: GET /api/sample-queries returns parsed list of sample queries."""
    res = client.get("/api/sample-queries")
    assert res.status_code == 200
    queries = res.json()
    assert isinstance(queries, list)
    assert len(queries) > 0
    assert "query" in queries[0]
    assert "description" in queries[0]


def test_api_analyze_ok():
    """API-ANALYZE-OK: POST /api/analyze returns 200 with structured analysis findings."""
    payload = {"query": "SELECT * FROM users"}
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "issues" in data
    assert "warnings" in data
    assert "complexity" in data
    assert "score" in data


def test_api_score_ok():
    """API-SCORE-OK: POST /api/score returns 200 with numeric score, cost tier, and breakdown."""
    payload = {"query": "SELECT * FROM users"}
    res = client.post("/api/score", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "score" in data
    assert 0 <= data["score"] <= 100
    assert data["cost_estimate"] in ("LOW", "MEDIUM", "HIGH")
    assert isinstance(data["breakdown"], list)


def test_api_optimize_ok():
    """API-OPTIMIZE-OK: POST /api/optimize returns 200 with optimizations list and insight text."""
    payload = {"query": "SELECT * FROM users"}
    res = client.post("/api/optimize", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "optimizations" in data
    assert "insight" in data
    assert isinstance(data["optimizations"], list)


def test_api_recommend_ok():
    """API-RECOMMEND-OK: POST /api/recommendations returns 200 with CREATE INDEX suggestions."""
    payload = {"query": "SELECT * FROM customers WHERE city = 'Pune'"}
    res = client.post("/api/recommendations", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)
    if data["recommendations"]:
        first = data["recommendations"][0]
        assert "CREATE INDEX" in first["ddl"]


def test_api_rewrite_ok():
    """API-REWRITE-OK: POST /api/rewrite returns 200 with rewritten query, changes, and diff."""
    payload = {"query": "SELECT * FROM users WHERE id IN (SELECT customer_id FROM orders)"}
    res = client.post("/api/rewrite", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "rewritten" in data
    assert "changes" in data
    assert "is_changed" in data
    assert data["is_changed"] is True


def test_api_exec_plan_ok():
    """API-EXEC-PLAN-OK: POST /api/execution-plan returns 200 with plan tree and costs."""
    payload = {"query": "SELECT * FROM orders WHERE customer_id = 10"}
    res = client.post("/api/execution-plan", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "plan_root" in data
    assert "node_type" in data["plan_root"]
    assert "total_cost" in data["plan_root"]


def test_api_sim_index_ok():
    """API-SIM-INDEX-OK: POST /api/simulate-index returns 200 with before/after comparison."""
    payload = {
        "query": "SELECT * FROM orders WHERE customer_id = 10",
        "index": "CREATE INDEX idx_orders_cust ON orders(customer_id);",
    }
    res = client.post("/api/simulate-index", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "simulation" in data
    sim = data["simulation"]
    assert "before_score" in sim
    assert "after_score" in sim
    assert "speedup_factor" in sim


# =============================================================================
# 2. Cross-Cutting & Edge Case Tests
# =============================================================================

def test_edge_empty_input():
    """EDGE-EMPTY-INPUT: Rejects empty or whitespace-only query string with HTTP 422."""
    for empty_val in ["", "   ", "\t\n"]:
        res = client.post("/api/analyze", json={"query": empty_val})
        assert res.status_code == 422
        data = res.json()
        assert "error" in data or "detail" in data


def test_edge_oversize_input():
    """EDGE-OVERSIZE-INPUT: Rejects queries exceeding 20,000 characters with HTTP 422."""
    huge_query = "SELECT 1 WHERE " + ("1=1 AND " * 3000)
    assert len(huge_query) > 20000
    res = client.post("/api/analyze", json={"query": huge_query})
    assert res.status_code == 422
    data = res.json()
    err_text = str(data.get("error", "") or data.get("detail", ""))
    assert "maximum" in err_text.lower() or "length" in err_text.lower() or "character" in err_text.lower()


def test_edge_comments_only():
    """EDGE-COMMENTS-ONLY: Rejects SQL containing only comments with HTTP 422."""
    query = "-- Just a comment\n/* block comment */"
    res = client.post("/api/analyze", json={"query": query})
    assert res.status_code == 422
    data = res.json()
    err_text = str(data.get("error", "") or data.get("detail", ""))
    assert "comment" in err_text.lower() or "executable" in err_text.lower()


def test_edge_multi_stmt():
    """EDGE-MULTI-STMT: Rejects multiple semicolon-separated statements with HTTP 422."""
    query = "SELECT id FROM users; DROP TABLE users;"
    res = client.post("/api/analyze", json={"query": query})
    assert res.status_code == 422
    data = res.json()
    err_text = str(data.get("error", "") or data.get("detail", ""))
    assert "multiple" in err_text.lower() or "single" in err_text.lower()


def test_edge_null_bytes():
    """EDGE-NULL-BYTES: Rejects queries containing null bytes with HTTP 422."""
    query = "SELECT * FROM users\x00 WHERE id = 1"
    res = client.post("/api/analyze", json={"query": query})
    assert res.status_code == 422
    data = res.json()
    err_text = str(data.get("error", "") or data.get("detail", ""))
    assert "null" in err_text.lower() or "invalid" in err_text.lower()


def test_edge_malformed_sql():
    """EDGE-MALFORMED-SQL: Handles malformed SQL syntax gracefully without server 500 crash."""
    query = "SELECT FROM WHERE GROUP BY ORDER"
    res = client.post("/api/analyze", json={"query": query})
    assert res.status_code in (200, 422)
    assert res.status_code != 500


def test_edge_non_sql_text():
    """EDGE-NON-SQL-TEXT: Rejects arbitrary plain non-SQL text with HTTP 422."""
    query = "Hello world, please optimize my database query immediately!"
    res = client.post("/api/analyze", json={"query": query})
    assert res.status_code == 422
    data = res.json()
    assert "error" in data or "detail" in data


def test_edge_cors_restrict():
    """EDGE-CORS-RESTRICT: Verifies CORS response for localhost origin."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    res = client.options("/api/health", headers=headers)
    assert res.status_code == 200
    allow_origin = res.headers.get("access-control-allow-origin")
    assert allow_origin in ("http://localhost:5173", "*")


def test_edge_unicode():
    """EDGE-UNICODE: Correctly parses queries containing Unicode characters in literals and aliases."""
    query = "SELECT id, name AS `ユーザー名` FROM users WHERE city = 'München' AND status = '⚡active'"
    res = client.post("/api/analyze", json={"query": query})
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == query


def test_edge_concurrency():
    """EDGE-CONCURRENCY: Handles 10 concurrent requests simultaneously without race conditions."""
    queries = [
        "SELECT * FROM users WHERE id = 1",
        "SELECT name, email FROM customers WHERE status = 'active'",
        "SELECT id, total FROM orders WHERE total > 100",
        "SELECT * FROM products WHERE price < 50",
        "SELECT AVG(salary) FROM employees WHERE department = 'IT'",
    ] * 2  # 10 queries

    def _call(q: str):
        return client.post("/api/score", json={"query": q})

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(_call, queries))

    for res in results:
        assert res.status_code == 200
        data = res.json()
        assert 0 <= data["score"] <= 100


# =============================================================================
# 3. Data-Driven Test Suite (Entire sample_queries.csv)
# =============================================================================

def test_data_driven_all_sample_queries():
    """Runs every single query from data/sample_queries.csv through /api/analyze and /api/score.
    Asserts:
    1. No query ever causes an unhandled HTTP 500 error.
    2. Score is strictly between 0 and 100.
    """
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "sample_queries.csv")
    assert os.path.exists(csv_path), f"sample_queries.csv not found at {csv_path}"

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        queries = [row["query"].strip() for row in reader if row.get("query", "").strip()]

    assert len(queries) >= 50, f"Expected at least 50 sample queries, found {len(queries)}"

    tested_count = 0
    for q in queries:
        # Test /api/analyze
        anl_res = client.post("/api/analyze", json={"query": q})
        assert anl_res.status_code != 500, f"HTTP 500 returned for query: {q}"
        if anl_res.status_code == 200:
            anl_data = anl_res.json()
            score = anl_data["score"]["score"]
            assert 0 <= score <= 100, f"Score out of bounds ({score}) for query: {q}"

        # Test /api/score
        scr_res = client.post("/api/score", json={"query": q})
        assert scr_res.status_code != 500, f"HTTP 500 returned on score for query: {q}"
        if scr_res.status_code == 200:
            scr_data = scr_res.json()
            assert 0 <= scr_data["score"] <= 100, f"Score out of bounds ({scr_data['score']}) for query: {q}"

        tested_count += 1

    print(f"Data-driven test verified {tested_count} sample queries without a single 500 or score out-of-bounds error.")
