"""Tests for db/explain.py module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from db.explain import (
    parse_mysql_explain_json,
    run_explain,
    validate_explainable_query,
)
from execution_plan import PlanNode

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_validate_valid_selects():
    """Verify normal SELECT queries pass validation."""
    valid_queries = [
        "SELECT * FROM orders WHERE customer_id = 10",
        "SELECT id, name FROM customers JOIN orders ON customers.id = orders.customer_id",
        "SELECT COUNT(*), status FROM orders GROUP BY status HAVING COUNT(*) > 5",
        "SELECT * FROM (SELECT id FROM products) AS p",
    ]
    for q in valid_queries:
        ok, reason = validate_explainable_query(q)
        assert ok is True, f"Failed on valid query: {q}, reason: {reason}"


def test_validate_reject_non_select():
    """Verify non-SELECT statements are rejected."""
    bad_queries = [
        ("DELETE FROM orders WHERE id = 1", "SELECT queries"),
        ("UPDATE customers SET name = 'test'", "SELECT queries"),
        ("INSERT INTO products (name) VALUES ('item')", "SELECT queries"),
        ("DROP TABLE customers", "SELECT queries"),
        ("TRUNCATE TABLE logs", "SELECT queries"),
        ("CREATE TABLE test (id int)", "SELECT queries"),
    ]
    for q, expected in bad_queries:
        ok, reason = validate_explainable_query(q)
        assert not ok
        assert expected in reason


def test_validate_reject_multi_statement():
    """Verify multiple statements separated by semicolon are rejected."""
    multi_queries = [
        "SELECT * FROM orders; DROP TABLE customers;",
        "SELECT * FROM orders;\nSELECT * FROM customers;",
        "SELECT 1; DELETE FROM orders WHERE 1=1;",
    ]
    for q in multi_queries:
        ok, reason = validate_explainable_query(q)
        assert not ok, f"Did not reject multi-statement query: {q}"


def test_validate_reject_empty_or_comments_only():
    """Verify empty queries or comment-only strings are rejected."""
    assert not validate_explainable_query("")[0]
    assert not validate_explainable_query("   ")[0]
    assert not validate_explainable_query("-- Just a comment")[0]
    assert not validate_explainable_query("/* Multi-line comment */")[0]


def test_validate_reject_into_outfile():
    """Verify file write statements like INTO OUTFILE are blocked."""
    q = "SELECT * FROM orders INTO OUTFILE '/tmp/orders.csv'"
    ok, reason = validate_explainable_query(q)
    assert not ok
    assert "prohibited" in reason.lower()


def test_parse_fixture_all_scan():
    """Verify parsing of full table scan JSON fixture."""
    path = FIXTURES_DIR / "explain_all_scan.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    node, warnings = parse_mysql_explain_json(data)
    assert isinstance(node, PlanNode)
    assert node.access_type == "ALL"
    assert node.icon == "🔴"
    assert node.table == "orders"
    assert node.total_cost == 1045.20
    assert any("Full table scan" in w for w in warnings)


def test_parse_fixture_index_ref():
    """Verify parsing of index ref lookup JSON fixture."""
    path = FIXTURES_DIR / "explain_index_ref.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    node, warnings = parse_mysql_explain_json(data)
    assert isinstance(node, PlanNode)
    assert node.access_type == "REF"
    assert node.icon == "🟢"
    assert node.key_used == "idx_orders_customer_id"
    assert node.total_cost == 3.50
    assert len(warnings) == 0


def test_parse_fixture_join_nested_loop():
    """Verify parsing of nested loop join JSON fixture."""
    path = FIXTURES_DIR / "explain_join_nested_loop.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    node, warnings = parse_mysql_explain_json(data)
    assert isinstance(node, PlanNode)
    assert node.node_type == "Nested Loop"
    assert len(node.children) == 2
    # First child is ALL on orders, second is eq_ref on customers
    assert node.children[0].access_type == "ALL"
    assert node.children[1].access_type == "EQ_REF"
    assert any("Full table scan" in w for w in warnings)


def test_parse_fixture_filesort_and_temporary():
    """Verify parsing of ordering and grouping operations with filesort and temp tables."""
    path = FIXTURES_DIR / "explain_filesort_temp.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    node, warnings = parse_mysql_explain_json(data)
    assert isinstance(node, PlanNode)
    assert any("Filesort" in w for w in warnings)
    assert any("Temporary table" in w for w in warnings)


def test_run_explain_safety_guard_rejects():
    """Verify run_explain halts before executing unsafe queries."""
    mock_engine = MagicMock()
    result = run_explain(mock_engine, "DROP TABLE orders")
    assert not result["success"]
    assert result["mode"] == "rejected"
    mock_engine.connect.assert_not_called()


def test_run_explain_success_mock():
    """Verify run_explain executes and parses valid EXPLAIN query."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # 1. VERSION query returns 8.0.32
    # 2. EXPLAIN query returns JSON string
    fixture_path = FIXTURES_DIR / "explain_index_ref.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        raw_json_str = f.read()

    ver_res = MagicMock()
    ver_res.scalar.return_value = "8.0.32"

    explain_res = MagicMock()
    explain_res.fetchone.return_value = (raw_json_str,)

    mock_conn.execute.side_effect = [ver_res, explain_res]

    result = run_explain(mock_engine, "SELECT * FROM orders WHERE customer_id = 42")
    assert result["success"] is True
    assert result["mode"] == "real_explain"
    assert isinstance(result["plan_tree"], PlanNode)
    assert result["mysql_version"] == "8.0.32"


def test_run_explain_handles_mysql_error():
    """Verify run_explain catches execution exceptions gracefully without crashing."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.side_effect = Exception("Table 'shop_db.missing' doesn't exist")

    result = run_explain(mock_engine, "SELECT * FROM missing")
    assert result["success"] is False
    assert result["mode"] == "failed"
    assert "Table 'shop_db.missing' doesn't exist" in result["error"]
