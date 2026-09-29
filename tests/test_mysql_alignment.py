"""
tests/test_mysql_alignment.py
Unit tests verifying MySQL 8.x alignment and dialect abstraction.
"""

import pytest
from analyzer import analyze_query
from config import Dialect, get_current_dialect, get_dialect_config, is_mysql, set_dialect
from execution_plan import flatten_plan, generate_execution_plan, get_all_nodes, plan_summary
from recommendations import BEST_PRACTICES, generate_index_recommendations
from scoring import compute_score
from simulator import simulate_index_impact


@pytest.fixture(autouse=True)
def ensure_mysql_dialect():
    """Ensure active dialect is reset to MySQL for each test."""
    set_dialect(Dialect.MYSQL)
    yield
    set_dialect(Dialect.MYSQL)


# ---------------------------------------------------------------------------
# Config & Dialect Tests
# ---------------------------------------------------------------------------

def test_config_default_dialect_is_mysql():
    assert get_current_dialect() == Dialect.MYSQL
    assert is_mysql() is True
    cfg = get_dialect_config()
    assert cfg.display_name == "MySQL"
    assert cfg.default_port == 3306
    assert cfg.supports_include_indexes is False
    assert "ALL" in cfg.access_types
    assert "ref" in cfg.access_types


def test_config_covering_index_format_mysql():
    cfg = get_dialect_config(Dialect.MYSQL)
    ddl = cfg.format_covering_index("orders", "idx_orders_covering", "customer_id", ["total", "status"])
    assert "INCLUDE" not in ddl
    assert "ON orders(customer_id, total, status);" in ddl


def test_config_fulltext_index_format_mysql():
    cfg = get_dialect_config(Dialect.MYSQL)
    ddl = cfg.format_fulltext_index("articles", "idx_fts", "body")
    assert "FULLTEXT INDEX" in ddl
    assert "USING gin" not in ddl


def test_config_dialect_switch():
    set_dialect(Dialect.POSTGRESQL)
    assert get_current_dialect() == Dialect.POSTGRESQL
    pg_cfg = get_dialect_config()
    assert pg_cfg.supports_include_indexes is True

    # Switch back to MySQL
    set_dialect("mysql")
    assert is_mysql() is True


def test_config_invalid_dialect_raises():
    with pytest.raises(ValueError):
        set_dialect("sqlite_unsupported")


# ---------------------------------------------------------------------------
# Index Recommendations Tests (MySQL 8.x)
# ---------------------------------------------------------------------------

def test_recommendations_no_postgres_terms():
    query = "SELECT * FROM orders WHERE customer_id = 10 AND status = 'pending';"
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    for rec in recs:
        # Must not contain PostgreSQL syntax or terms
        assert "INCLUDE (" not in rec["ddl"]
        assert "USING gin" not in rec["ddl"]
        assert "heap scan" not in rec["reason"].lower()

        # Improvement must be labeled as estimated
        assert "estimated" in rec["estimated_improvement"].lower()


def test_recommendations_fulltext_syntax():
    query = "SELECT * FROM articles WHERE title LIKE '%database%';"
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    fts_recs = [r for r in recs if "FULLTEXT" in r["index_type"]]
    assert len(fts_recs) == 1
    assert "ALTER TABLE" in fts_recs[0]["ddl"]
    assert "ADD FULLTEXT INDEX" in fts_recs[0]["ddl"]


def test_best_practices_no_postgres_terms():
    for practice in BEST_PRACTICES:
        assert "pgbouncer" not in practice.lower()
        assert "postgresql" not in practice.lower()
    # Confirm MySQL references
    assert any("mysql" in p.lower() for p in BEST_PRACTICES)


# ---------------------------------------------------------------------------
# Simulated Execution Plan Tests (MySQL 8.x EXPLAIN)
# ---------------------------------------------------------------------------

def test_execution_plan_unindexed_query_uses_all():
    query = "SELECT * FROM orders;"
    analysis = analyze_query(query)
    root = generate_execution_plan(query, analysis)

    assert root.node_type == "ALL"
    assert root.access_type == "ALL"
    assert root.table == "orders"
    assert "est. cost:" in root.cost_label


def test_execution_plan_indexed_query_uses_ref():
    query = "SELECT id, name FROM users WHERE id = 42;"
    analysis = analyze_query(query)
    root = generate_execution_plan(query, analysis)

    # In MySQL, indexed seek produces ref access type
    assert root.node_type in ("ref", "range")
    assert root.access_type in ("ref", "range")
    assert root.key_used is not None
    assert "idx_users_" in root.key_used


def test_execution_plan_order_by_uses_filesort():
    query = "SELECT id, name FROM users WHERE id = 42 ORDER BY name;"
    analysis = analyze_query(query)
    root = generate_execution_plan(query, analysis)

    all_nodes = get_all_nodes(root)
    node_types = [n.node_type for n in all_nodes]
    assert "filesort" in node_types
    filesort_node = next(n for n in all_nodes if n.node_type == "filesort")
    assert "Using filesort" in filesort_node.extra


def test_execution_plan_group_by_uses_temporary():
    query = "SELECT dept, count(*) FROM employees GROUP BY dept;"
    analysis = analyze_query(query)
    root = generate_execution_plan(query, analysis)

    all_nodes = get_all_nodes(root)
    node_types = [n.node_type for n in all_nodes]
    assert "temporary" in node_types


def test_flatten_plan_structure():
    query = "SELECT * FROM customers c JOIN orders o ON c.id = o.customer_id WHERE c.status = 'active';"
    analysis = analyze_query(query)
    root = generate_execution_plan(query, analysis)
    flattened = flatten_plan(root)

    assert len(flattened) >= 2
    for row in flattened:
        assert "Plan Node" in row
        assert "Table" in row
        assert "Access Type" in row
        assert "Key" in row
        assert "Est. Rows" in row
        assert "Filtered %" in row
        assert "Extra" in row
        assert "Est. Cost" in row


def test_plan_summary_keys_backward_compatible():
    query = "SELECT * FROM orders WHERE status = 'pending';"
    analysis = analyze_query(query)
    root = generate_execution_plan(query, analysis)
    summary = plan_summary(root)

    # Verify all expected keys are present
    assert "total_nodes" in summary
    assert "plan_root" in summary
    assert "access_type" in summary
    assert "has_index_scan" in summary
    assert "has_all_scan" in summary
    assert "has_seq_scan" in summary   # preserved backward-compatibility alias
    assert "cost_category" in summary
    assert "estimated_rows" in summary
    assert "plan_cost" in summary


# ---------------------------------------------------------------------------
# Simulator Tests
# ---------------------------------------------------------------------------

def test_simulator_labels_numbers_as_estimated():
    query = "SELECT * FROM orders WHERE customer_id = 10;"
    analysis = analyze_query(query)
    score_result = compute_score(analysis)
    impact = simulate_index_impact(query, analysis, score_result)

    assert "(est.)" in impact["speedup_label"]
    assert impact["before_rows"] > 0
    assert impact["after_rows"] > 0
    assert impact["speedup_factor"] >= 1.0
