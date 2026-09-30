"""
tests/test_integration_db.py
Live database integration tests against real MySQL.
Marked with @pytest.mark.db and executed ONLY when TEST_DB_URL environment variable is set.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from db.benchmark import benchmark_query
from db.explain import run_explain
from db.schema import load_schema_from_db

TEST_DB_URL = os.getenv("TEST_DB_URL")


@pytest.mark.skipif(
    not TEST_DB_URL, reason="TEST_DB_URL environment variable not set (real MySQL required)"
)
@pytest.mark.db
class TestLiveMySQLIntegration:
    """Live database integration tests against MySQL 8.x."""

    @pytest.fixture(scope="class")
    def live_engine(self):
        engine = create_engine(TEST_DB_URL)
        yield engine
        engine.dispose()

    def test_live_connection(self, live_engine):
        """Verify real connection ping works."""
        with live_engine.connect() as conn:
            res = conn.execute(text("SELECT 1 AS live_test")).scalar()
            assert res == 1

    def test_live_schema_introspection(self, live_engine):
        """Introspect real database tables and indexes."""
        # Extract db name from engine URL
        db_name = live_engine.url.database or "mysql"
        schema = load_schema_from_db(live_engine, db_name)
        assert schema.database == db_name
        assert isinstance(schema.tables, dict)

    def test_live_explain_json(self, live_engine):
        """Execute real EXPLAIN FORMAT=JSON against live database."""
        query = "SELECT 1 AS col WHERE 1 = 1;"
        res = run_explain(live_engine, query)
        assert res["success"] is True
        assert res["raw_json"] is not None

    def test_live_benchmark_execution(self, live_engine):
        """Benchmark live query execution."""
        query = "SELECT 1 AS num;"
        bm_res = benchmark_query(live_engine, query, runs=3, warmup=1)
        assert bm_res.success is True
        assert bm_res.median_ms >= 0.0
        assert len(bm_res.raw_timings_ms) == 3
