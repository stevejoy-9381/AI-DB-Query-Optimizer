"""Comprehensive unit tests for AST-based SQL query analyzer and QueryFeatures."""

from analyzer import analyze_query
from db.schema import SchemaInfo, TableInfo
from query_model import extract_query_features

# ---------------------------------------------------------------------------
# 1. SELECT * and Projection Tests
# ---------------------------------------------------------------------------


def test_select_star_detected():
    """Verify SELECT * triggers SELECT_STAR issue."""
    q = "SELECT * FROM orders WHERE id = 1"
    res = analyze_query(q)
    assert any(i["code"] == "SELECT_STAR" for i in res["issues"])
    assert res["select_star"] is True


def test_select_star_not_triggered_by_count_star():
    """Verify COUNT(*) does not falsely trigger SELECT_STAR."""
    q = "SELECT COUNT(*) FROM orders WHERE status = 'COMPLETED'"
    res = analyze_query(q)
    assert not any(i["code"] == "SELECT_STAR" for i in res["issues"])
    assert res["select_star"] is False


def test_select_specific_columns_not_flagged():
    """Verify explicit column list does not flag SELECT_STAR."""
    q = "SELECT id, total_amount, order_date FROM orders WHERE id = 1"
    res = analyze_query(q)
    assert not any(i["code"] == "SELECT_STAR" for i in res["issues"])
    assert res["select_star"] is False


def test_keyword_inside_string_literal_not_flagged():
    """Verify 'SELECT *' inside a string value does not trigger SELECT_STAR."""
    q = "SELECT id FROM query_logs WHERE query_text = 'SELECT * FROM orders'"
    res = analyze_query(q)
    assert not any(i["code"] == "SELECT_STAR" for i in res["issues"])
    assert res["select_star"] is False


def test_keyword_inside_comment_not_flagged():
    """Verify 'SELECT *' inside a comment does not trigger SELECT_STAR."""
    q = "SELECT id FROM orders WHERE id = 1 -- SELECT * FROM secret"
    res = analyze_query(q)
    assert not any(i["code"] == "SELECT_STAR" for i in res["issues"])
    assert res["select_star"] is False


# ---------------------------------------------------------------------------
# 2. WHERE and LIMIT Tests
# ---------------------------------------------------------------------------


def test_missing_where_detected():
    """Verify SELECT without WHERE triggers MISSING_WHERE and MISSING_LIMIT."""
    q = "SELECT id, name FROM customers"
    res = analyze_query(q)
    assert any(i["code"] == "MISSING_WHERE" for i in res["issues"])
    assert any(i["code"] == "MISSING_LIMIT" for i in res["issues"])
    assert res["has_where"] is False


def test_where_present_suppresses_missing_where():
    """Verify WHERE clause suppresses MISSING_WHERE."""
    q = "SELECT id, name FROM customers WHERE id = 10"
    res = analyze_query(q)
    assert not any(i["code"] == "MISSING_WHERE" for i in res["issues"])
    assert res["has_where"] is True


def test_limit_present_suppresses_missing_limit():
    """Verify LIMIT clause suppresses MISSING_LIMIT on unbounded queries."""
    q = "SELECT id, name FROM customers LIMIT 50"
    res = analyze_query(q)
    assert not any(i["code"] == "MISSING_LIMIT" for i in res["issues"])
    assert res["has_limit"] is True


# ---------------------------------------------------------------------------
# 3. JOIN Tests
# ---------------------------------------------------------------------------


def test_join_detected():
    """Verify query with 1-2 joins flags JOIN_DETECTED."""
    q = "SELECT * FROM orders JOIN customers ON orders.customer_id = customers.id"
    res = analyze_query(q)
    assert res["join_count"] == 1
    assert any(i["code"] == "JOIN_DETECTED" for i in res["issues"])
    assert not any(i["code"] == "EXCESSIVE_JOINS" for i in res["issues"])


def test_excessive_joins_detected():
    """Verify query with >2 joins flags EXCESSIVE_JOINS."""
    q = """
    SELECT * FROM orders o
    JOIN customers c ON o.customer_id = c.id
    JOIN order_items i ON o.id = i.order_id
    JOIN products p ON i.product_id = p.id
    """
    res = analyze_query(q)
    assert res["join_count"] == 3
    assert any(i["code"] == "EXCESSIVE_JOINS" for i in res["issues"])


# ---------------------------------------------------------------------------
# 4. Subquery Tests
# ---------------------------------------------------------------------------


def test_subquery_detected():
    """Verify nested subquery in WHERE flags SUBQUERY_DETECTED."""
    q = "SELECT * FROM orders WHERE customer_id IN (SELECT id FROM customers WHERE state = 'CA')"
    res = analyze_query(q)
    assert res["subquery_count"] >= 1
    assert any(i["code"] == "SUBQUERY_DETECTED" for i in res["issues"])


def test_scalar_subquery_in_projection():
    """Verify scalar subquery in SELECT projection is detected."""
    q = "SELECT id, (SELECT name FROM customers WHERE customers.id = orders.customer_id) AS cname FROM orders"
    res = analyze_query(q)
    assert res["subquery_count"] >= 1
    assert any(i["code"] == "SUBQUERY_DETECTED" for i in res["issues"])


# ---------------------------------------------------------------------------
# 5. Wildcard LIKE Tests
# ---------------------------------------------------------------------------


def test_leading_wildcard_like_flagged():
    """Verify LIKE '%val' triggers LEADING_WILDCARD warning."""
    q = "SELECT id FROM users WHERE email LIKE '%@gmail.com'"
    res = analyze_query(q)
    assert any(w["code"] == "LEADING_WILDCARD" for w in res["warnings"])


def test_trailing_wildcard_like_not_flagged():
    """Verify prefix search LIKE 'val%' does not trigger LEADING_WILDCARD."""
    q = "SELECT id FROM users WHERE email LIKE 'john%'"
    res = analyze_query(q)
    assert not any(w["code"] == "LEADING_WILDCARD" for w in res["warnings"])


def test_like_inside_literal_string_not_flagged():
    """Verify LIKE pattern inside string literal does not trigger warning."""
    q = "SELECT id FROM logs WHERE pattern_name = 'LIKE %test%'"
    res = analyze_query(q)
    assert not any(w["code"] == "LEADING_WILDCARD" for w in res["warnings"])


# ---------------------------------------------------------------------------
# 6. Function on Column in WHERE Tests
# ---------------------------------------------------------------------------


def test_function_on_column_upper():
    """Verify UPPER(col) in WHERE triggers FUNCTION_ON_COLUMN warning."""
    q = "SELECT id FROM users WHERE UPPER(username) = 'ADMIN'"
    res = analyze_query(q)
    assert any(w["code"] == "FUNCTION_ON_COLUMN" for w in res["warnings"])


def test_function_on_column_year():
    """Verify YEAR(col) in WHERE triggers FUNCTION_ON_COLUMN warning."""
    q = "SELECT * FROM orders WHERE YEAR(order_date) = 2024"
    res = analyze_query(q)
    assert any(w["code"] == "FUNCTION_ON_COLUMN" for w in res["warnings"])


def test_sargable_predicate_not_flagged_as_function():
    """Verify standard comparison col >= 'val' is recognized as sargable."""
    q = "SELECT * FROM orders WHERE order_date >= '2024-01-01' AND order_date < '2025-01-01'"
    res = analyze_query(q)
    assert not any(w["code"] == "FUNCTION_ON_COLUMN" for w in res["warnings"])


# ---------------------------------------------------------------------------
# 7. Aggregation & DISTINCT Tests
# ---------------------------------------------------------------------------


def test_aggregate_full_scan_flagged():
    """Verify aggregate without WHERE or GROUP BY flags AGGREGATE_FULL_SCAN."""
    q = "SELECT COUNT(*) FROM orders"
    res = analyze_query(q)
    assert any(w["code"] == "AGGREGATE_FULL_SCAN" for w in res["warnings"])


def test_aggregate_with_group_by_not_flagged():
    """Verify aggregate with GROUP BY does not trigger AGGREGATE_FULL_SCAN."""
    q = "SELECT status, COUNT(*) FROM orders GROUP BY status"
    res = analyze_query(q)
    assert not any(w["code"] == "AGGREGATE_FULL_SCAN" for w in res["warnings"])


def test_distinct_with_join_flagged():
    """Verify SELECT DISTINCT combined with JOIN flags DISTINCT_WITH_JOIN."""
    q = "SELECT DISTINCT c.city FROM customers c JOIN orders o ON c.id = o.customer_id"
    res = analyze_query(q)
    assert any(w["code"] == "DISTINCT_WITH_JOIN" for w in res["warnings"])


def test_distinct_without_join_not_flagged():
    """Verify SELECT DISTINCT on single table does not flag DISTINCT_WITH_JOIN."""
    q = "SELECT DISTINCT city FROM customers"
    res = analyze_query(q)
    assert not any(w["code"] == "DISTINCT_WITH_JOIN" for w in res["warnings"])


# ---------------------------------------------------------------------------
# 8. Complexity & AST Features
# ---------------------------------------------------------------------------


def test_complexity_classification():
    """Verify Simple, Moderate, and Complex classification logic."""
    simple_q = "SELECT id, name FROM customers"
    assert analyze_query(simple_q)["complexity"] == "Simple"

    mod_q = "SELECT id, name FROM customers WHERE id = 10"
    assert analyze_query(mod_q)["complexity"] == "Moderate"

    complex_q = "SELECT * FROM orders WHERE customer_id IN (SELECT id FROM customers)"
    assert analyze_query(complex_q)["complexity"] == "Complex"


def test_query_features_extraction():
    """Verify detailed AST feature extraction in query_model.py."""
    q = "SELECT id, name FROM customers WHERE id = 42 ORDER BY name DESC LIMIT 10 OFFSET 20"
    f = extract_query_features(q)
    assert f.statement_type == "SELECT"
    assert "customers" in f.tables
    assert f.has_where is True
    assert f.limit == 10
    assert f.offset == 20
    assert len(f.order_by_cols) == 1
    assert "id" in f.filter_columns


def test_schema_aware_unknown_table():
    """Verify analyzer identifies unknown table using SchemaInfo."""
    schema = SchemaInfo(database="test_db")
    schema.tables["users"] = TableInfo(name="users")

    q = "SELECT * FROM orders WHERE id = 1"
    res = analyze_query(q, schema=schema)
    assert "orders" in res["unknown_tables"]
    assert any(i["code"] == "UNKNOWN_TABLE" for i in res["issues"])


def test_fallback_on_unparseable_sql():
    """Verify invalid or incomplete SQL triggers regex fallback rather than crashing."""
    broken_sql = "SELECT FROM WHERE"
    res = analyze_query(broken_sql)
    assert res["analysis_engine"] == "regex_fallback"
    assert res["limited_analysis_notice"] is not None


def test_empty_query():
    """Verify empty query returns clean default analysis."""
    res = analyze_query("")
    assert res["query_type"] == "UNKNOWN"
    assert res["issues"] == []
