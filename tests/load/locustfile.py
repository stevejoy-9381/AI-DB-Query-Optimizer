"""
tests/load/locustfile.py
Locust load & concurrency test suite for AI DB Query Optimizer API.
Simulates realistic developer personas and stress workloads across all API endpoints.
"""

import random
from locust import HttpUser, task, between, events

SAMPLE_QUERIES = [
    # Simple query
    "SELECT * FROM orders WHERE customer_id = 42;",
    # Complex join query
    """
    SELECT o.id, o.order_date, c.name, SUM(oi.price * oi.quantity) AS total_spent
    FROM orders o
    JOIN customers c ON o.customer_id = c.id
    JOIN order_items oi ON o.id = oi.order_id
    WHERE o.status = 'COMPLETED'
      AND o.order_date >= '2023-01-01'
    GROUP BY o.id, o.order_date, c.name
    ORDER BY total_spent DESC
    LIMIT 20;
    """,
    # Non-sargable query for rewrite
    "SELECT id, order_date, total_amount FROM orders WHERE YEAR(order_date) = 2023 AND customer_id = 100;",
    # Leading wildcard and anti-patterns
    "SELECT * FROM products WHERE name LIKE '%wireless%' OR description LIKE '%bluetooth%';",
    # Aggregate with subquery
    """
    SELECT department_id, AVG(salary) AS avg_sal
    FROM employees
    WHERE department_id IN (SELECT id FROM departments WHERE active = 1)
    GROUP BY department_id
    HAVING AVG(salary) > 75000;
    """,
]

CANDIDATE_INDEXES = [
    "idx_customer_status (customer_id, status)",
    "idx_order_date (order_date)",
    "idx_products_name (name)",
    "idx_emp_dept_salary (department_id, salary)",
]


class QueryOptimizerUser(HttpUser):
    """
    Simulates developer interacting with the Query Optimizer API.
    Uses realistic think-time between 100ms and 500ms.
    """
    wait_time = between(0.1, 0.5)

    @task(5)
    def test_analyze_endpoint(self):
        """Exercises POST /api/analyze with various SQL workloads."""
        sql = random.choice(SAMPLE_QUERIES)
        with self.client.post(
            "/api/analyze",
            json={"query": sql},
            name="POST /api/analyze",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "score" in data and "statement_type" in data:
                    response.success()
                else:
                    response.failure("Missing required keys in /api/analyze response")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def test_score_endpoint(self):
        """Exercises POST /api/score for performance penalty waterfalls."""
        sql = random.choice(SAMPLE_QUERIES)
        with self.client.post(
            "/api/score",
            json={"query": sql},
            name="POST /api/score",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "score" in data and "breakdown" in data:
                    response.success()
                else:
                    response.failure("Missing score/breakdown in /api/score response")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def test_recommendations_endpoint(self):
        """Exercises POST /api/recommendations for index DDL generation."""
        sql = random.choice(SAMPLE_QUERIES)
        with self.client.post(
            "/api/recommendations",
            json={"query": sql},
            name="POST /api/recommendations",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "recommendations" in data:
                    response.success()
                else:
                    response.failure("Missing recommendations key in /api/recommendations response")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def test_rewrite_endpoint(self):
        """Exercises POST /api/rewrite for AST transformation."""
        sql = random.choice(SAMPLE_QUERIES)
        with self.client.post(
            "/api/rewrite",
            json={"query": sql},
            name="POST /api/rewrite",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "rewritten" in data and "is_changed" in data:
                    response.success()
                else:
                    response.failure("Missing rewritten/is_changed in /api/rewrite response")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def test_execution_plan_endpoint(self):
        """Exercises POST /api/execution-plan for InnoDB node tree simulation."""
        sql = random.choice(SAMPLE_QUERIES)
        with self.client.post(
            "/api/execution-plan",
            json={"query": sql},
            name="POST /api/execution-plan",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "plan_root" in data and "summary" in data:
                    response.success()
                else:
                    response.failure("Missing plan_root/summary in /api/execution-plan response")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def test_simulate_index_endpoint(self):
        """Exercises POST /api/simulate-index for what-if index modeling."""
        sql = random.choice(SAMPLE_QUERIES)
        idx = random.choice(CANDIDATE_INDEXES)
        with self.client.post(
            "/api/simulate-index",
            json={"query": sql, "index": idx},
            name="POST /api/simulate-index",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "simulation" in data and "speedup_factor" in data["simulation"]:
                    response.success()
                else:
                    response.failure("Missing simulation/speedup_factor in /api/simulate-index response")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def test_sample_queries_endpoint(self):
        """Exercises GET /api/sample-queries benchmark dataset."""
        with self.client.get(
            "/api/sample-queries",
            name="GET /api/sample-queries",
            catch_response=True,
        ) as response:
            if response.status_code == 200 and isinstance(response.json(), list):
                response.success()
            else:
                response.failure(f"Invalid sample-queries response: {response.status_code}")

    @task(1)
    def test_health_endpoint(self):
        """Exercises GET /api/health for system telemetry."""
        with self.client.get(
            "/api/health",
            name="GET /api/health",
            catch_response=True,
        ) as response:
            if response.status_code == 200 and response.json().get("status") == "ok":
                response.success()
            else:
                response.failure(f"Health probe check failed: {response.status_code}")

    @task(1)
    def test_validation_rejection_under_load(self):
        """Ensures invalid/empty inputs return HTTP 422 cleanly without crashing the event loop."""
        with self.client.post(
            "/api/analyze",
            json={"query": ""},
            name="POST /api/analyze [Invalid 422]",
            catch_response=True,
        ) as response:
            if response.status_code == 422:
                response.success()
            else:
                response.failure(f"Expected 422 for empty query, got {response.status_code}")
