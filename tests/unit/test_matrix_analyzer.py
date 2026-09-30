"""tests/unit/test_matrix_analyzer.py
Automated Unit Tests for all Analyzer behaviors defined in docs/TEST_MATRIX.md.
"""

import pytest

from analyzer import analyze_query
from db.schema import ColumnInfo, IndexInfo, SchemaInfo, TableInfo


@pytest.fixture
def mock_schema() -> SchemaInfo:
    schema = SchemaInfo(database="test_db")
    users = TableInfo(name="users", estimated_rows=10_000, data_length_bytes=1_000_000)
    users.columns = {
        "id": ColumnInfo("id", "int", is_nullable=False, ordinal_position=1),
        "name": ColumnInfo("name", "varchar(100)", is_nullable=False, ordinal_position=2),
        "email": ColumnInfo("email", "varchar(150)", is_nullable=False, ordinal_position=3),
        "phone": ColumnInfo("phone", "varchar(20)", is_nullable=True, ordinal_position=4),
        "created_at": ColumnInfo("created_at", "datetime", is_nullable=False, ordinal_position=5),
    }
    users.indexes = {
        "primary": IndexInfo("PRIMARY", "users", ["id"], is_unique=True, is_primary=True),
    }
    schema.tables["users"] = users

    audit_log = TableInfo(name="audit_log", estimated_rows=50_000, data_length_bytes=5_000_000)
    audit_log.columns = {
        "id": ColumnInfo("id", "int", is_nullable=False, ordinal_position=1),
        "event": ColumnInfo("event", "varchar(50)", is_nullable=False, ordinal_position=2),
    }
    audit_log.indexes = {
        "primary": IndexInfo("PRIMARY", "audit_log", ["id"], is_unique=True, is_primary=True),
    }
    schema.tables["audit_log"] = audit_log
    return schema


def _all_codes(res: dict) -> set[str]:
    return {i["code"] for i in res.get("issues", [])} | {w["code"] for w in res.get("warnings", [])}


# --- HIGH PRIORITY ---

def test_anl_sel_star():
    """ANL-SEL-STAR: Detects SELECT * projection retrieving all columns."""
    trig = analyze_query("SELECT * FROM users WHERE id = 10")
    assert "SELECT_STAR" in _all_codes(trig)
    assert trig["select_star"] is True

    non_trig = analyze_query("SELECT id, name FROM users WHERE id = 10")
    assert "SELECT_STAR" not in _all_codes(non_trig)
    assert non_trig["select_star"] is False


def test_anl_miss_where():
    """ANL-MISS-WHERE: Detects SELECT statement missing a WHERE clause."""
    trig = analyze_query("SELECT id, name FROM customers")
    assert "MISSING_WHERE" in _all_codes(trig)
    assert trig["has_where"] is False

    non_trig = analyze_query("SELECT id, name FROM customers WHERE active = 1")
    assert "MISSING_WHERE" not in _all_codes(non_trig)
    assert non_trig["has_where"] is True


def test_anl_excess_join():
    """ANL-EXCESS-JOIN: Detects excessive JOIN count (> 2 JOINs)."""
    trig = analyze_query("SELECT o.id FROM orders o JOIN customers c ON o.customer_id = c.id JOIN items i ON o.id = i.order_id JOIN products p ON i.product_id = p.id")
    assert "EXCESSIVE_JOINS" in _all_codes(trig)
    assert trig["join_count"] > 2

    non_trig = analyze_query("SELECT o.id FROM orders o JOIN customers c ON o.customer_id = c.id")
    assert "EXCESSIVE_JOINS" not in _all_codes(non_trig)
    assert trig["join_count"] > 0


def test_anl_corr_subq():
    """ANL-CORR-SUBQ: Detects correlated subqueries referencing outer table columns."""
    trig = analyze_query("SELECT c.name FROM customers c WHERE c.id IN (SELECT o.customer_id FROM orders o WHERE o.total > 500 AND o.customer_id = c.id)")
    assert "CORRELATED_SUBQUERY" in _all_codes(trig)

    non_trig = analyze_query("SELECT c.name FROM customers c JOIN orders o ON c.id = o.customer_id WHERE o.total > 500")
    assert "CORRELATED_SUBQUERY" not in _all_codes(non_trig)


def test_anl_type_conv(mock_schema):
    """ANL-TYPE-CONV: Detects implicit type conversion comparing string/varchar column to numeric literal."""
    trig = analyze_query("SELECT id, name FROM users WHERE phone = 1234567890", schema=mock_schema)
    assert "IMPLICIT_TYPE_CONVERSION" in _all_codes(trig)

    non_trig = analyze_query("SELECT id, name FROM users WHERE phone = '1234567890'", schema=mock_schema)
    assert "IMPLICIT_TYPE_CONVERSION" not in _all_codes(non_trig)


def test_anl_not_in():
    """ANL-NOT-IN: Detects NOT IN with subquery risking NULL trap and unnesting failures."""
    trig = analyze_query("SELECT id, name FROM customers WHERE id NOT IN (SELECT customer_id FROM orders)")
    assert "NOT_IN_SUBQUERY" in _all_codes(trig)

    non_trig = analyze_query("SELECT id, name FROM customers c WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)")
    assert "NOT_IN_SUBQUERY" not in _all_codes(non_trig)


def test_anl_ord_rand():
    """ANL-ORD-RAND: Detects ORDER BY RAND() forcing full table scan and filesort."""
    trig = analyze_query("SELECT id, name FROM products ORDER BY RAND() LIMIT 5")
    assert "ORDER_BY_RAND" in _all_codes(trig)

    non_trig = analyze_query("SELECT id, name FROM products ORDER BY id ASC LIMIT 5")
    assert "ORDER_BY_RAND" not in _all_codes(non_trig)


def test_anl_miss_join_cond():
    """ANL-MISS-JOIN-COND: Detects accidental Cartesian product via CROSS JOIN or missing ON condition."""
    trig = analyze_query("SELECT c.name, o.id FROM customers c CROSS JOIN orders o")
    assert "MISSING_JOIN_CONDITION" in _all_codes(trig)

    non_trig = analyze_query("SELECT c.name, o.id FROM customers c JOIN orders o ON c.id = o.customer_id")
    assert "MISSING_JOIN_CONDITION" not in _all_codes(non_trig)


def test_anl_ins_unbound():
    """ANL-INS-UNBOUND: Detects unbounded INSERT...SELECT causing massive atomic locks."""
    trig = analyze_query("INSERT INTO archived_orders SELECT * FROM orders")
    assert "INSERT_SELECT_UNBOUNDED" in _all_codes(trig)

    non_trig = analyze_query("INSERT INTO archived_orders SELECT id, total FROM orders WHERE status = 'delivered' LIMIT 1000")
    assert "INSERT_SELECT_UNBOUNDED" not in _all_codes(non_trig)


def test_anl_upd_no_where():
    """ANL-UPD-NO-WHERE: Detects catastrophic UPDATE statement without WHERE clause."""
    trig = analyze_query("UPDATE users SET status = 'inactive'")
    assert "UPDATE_WITHOUT_WHERE" in _all_codes(trig)

    non_trig = analyze_query("UPDATE users SET status = 'inactive' WHERE id = 42")
    assert "UPDATE_WITHOUT_WHERE" not in _all_codes(non_trig)


def test_anl_del_no_where():
    """ANL-DEL-NO-WHERE: Detects catastrophic DELETE statement without WHERE clause."""
    trig = analyze_query("DELETE FROM logs")
    assert "DELETE_WITHOUT_WHERE" in _all_codes(trig)

    non_trig = analyze_query("DELETE FROM logs WHERE created_at < '2023-01-01'")
    assert "DELETE_WITHOUT_WHERE" not in _all_codes(non_trig)


def test_anl_dml_unidx_where(mock_schema):
    """ANL-DML-UNIDX-WHERE: Detects UPDATE or DELETE filtering on unindexed column."""
    trig = analyze_query("DELETE FROM audit_log WHERE event = 'login_failed'", schema=mock_schema)
    assert "UPDATE_DELETE_UNINDEXED_WHERE" in _all_codes(trig)

    non_trig = analyze_query("DELETE FROM audit_log WHERE id = 105", schema=mock_schema)
    assert "UPDATE_DELETE_UNINDEXED_WHERE" not in _all_codes(non_trig)


def test_anl_schema_tbl(mock_schema):
    """ANL-SCHEMA-TBL: Detects unknown table when schema metadata is provided."""
    trig = analyze_query("SELECT id FROM nonexistent_table_xyz WHERE id = 1", schema=mock_schema)
    assert "UNKNOWN_TABLE" in _all_codes(trig)

    non_trig = analyze_query("SELECT id FROM users WHERE id = 1", schema=mock_schema)
    assert "UNKNOWN_TABLE" not in _all_codes(non_trig)


def test_anl_schema_col(mock_schema):
    """ANL-SCHEMA-COL: Detects unknown column when schema metadata is provided."""
    trig = analyze_query("SELECT users.nonexistent_column_xyz FROM users WHERE users.id = 1", schema=mock_schema)
    assert "UNKNOWN_COLUMN" in _all_codes(trig)

    non_trig = analyze_query("SELECT users.name FROM users WHERE users.id = 1", schema=mock_schema)
    assert "UNKNOWN_COLUMN" not in _all_codes(non_trig)


# --- MEDIUM PRIORITY ---

def test_anl_join_det():
    """ANL-JOIN-DET: Detects standard JOIN requiring indexed join condition."""
    trig = analyze_query("SELECT o.id, c.name FROM orders o JOIN customers c ON o.customer_id = c.id WHERE o.status = 'shipped'")
    assert "JOIN_DETECTED" in _all_codes(trig)
    assert trig["join_count"] == 1

    non_trig = analyze_query("SELECT id, name FROM customers WHERE id = 10")
    assert "JOIN_DETECTED" not in _all_codes(non_trig)


def test_anl_subq_det():
    """ANL-SUBQ-DET: Detects subquery present in query."""
    trig = analyze_query("SELECT name FROM employees WHERE salary > (SELECT AVG(salary) FROM employees)")
    assert "SUBQUERY_DETECTED" in _all_codes(trig)
    assert trig["subquery_count"] >= 1

    non_trig = analyze_query("SELECT name, salary FROM employees WHERE salary > 50000")
    assert "SUBQUERY_DETECTED" not in _all_codes(non_trig)


def test_anl_miss_limit():
    """ANL-MISS-LIMIT: Detects missing LIMIT on unbounded SELECT lacking WHERE."""
    trig = analyze_query("SELECT name FROM customers")
    assert "MISSING_LIMIT" in _all_codes(trig)

    non_trig = analyze_query("SELECT name FROM customers LIMIT 50")
    assert "MISSING_LIMIT" not in _all_codes(non_trig)


def test_anl_lead_wild():
    """ANL-LEAD-WILD: Detects leading wildcard in LIKE pattern."""
    trig = analyze_query("SELECT id, name FROM users WHERE email LIKE '%@gmail.com'")
    assert "LEADING_WILDCARD" in _all_codes(trig)

    non_trig = analyze_query("SELECT id, name FROM users WHERE email LIKE 'john%'")
    assert "LEADING_WILDCARD" not in _all_codes(non_trig)


def test_anl_func_col():
    """ANL-FUNC-COL: Detects function wrapped around column in WHERE."""
    trig = analyze_query("SELECT id FROM users WHERE UPPER(email) = 'TEST@EXAMPLE.COM'")
    assert "FUNCTION_ON_COLUMN" in _all_codes(trig)

    non_trig = analyze_query("SELECT id FROM users WHERE email = 'test@example.com'")
    assert "FUNCTION_ON_COLUMN" not in _all_codes(non_trig)


def test_anl_agg_scan():
    """ANL-AGG-SCAN: Detects aggregate function with no WHERE or GROUP BY."""
    trig = analyze_query("SELECT AVG(salary) FROM employees")
    assert "AGGREGATE_FULL_SCAN" in _all_codes(trig)

    non_trig = analyze_query("SELECT AVG(salary) FROM employees WHERE department = 'IT'")
    assert "AGGREGATE_FULL_SCAN" not in _all_codes(non_trig)


def test_anl_or_diff_col():
    """ANL-OR-DIFF-COL: Detects OR condition across different columns."""
    trig = analyze_query("SELECT id, total FROM orders WHERE customer_id = 42 OR status = 'pending'")
    assert "OR_DIFFERENT_COLUMNS" in _all_codes(trig)

    non_trig = analyze_query("SELECT id, total FROM orders WHERE customer_id = 42 OR customer_id = 99")
    assert "OR_DIFFERENT_COLUMNS" not in _all_codes(non_trig)


def test_anl_unidx_ord(mock_schema):
    """ANL-UNIDX-ORD: Detects ORDER BY on unindexed column requiring temporary filesort."""
    trig = analyze_query("SELECT id, name FROM users ORDER BY name LIMIT 10", schema=mock_schema)
    assert "UNINDEXED_ORDER_BY" in _all_codes(trig)

    non_trig = analyze_query("SELECT id, name FROM users ORDER BY id LIMIT 10", schema=mock_schema)
    assert "UNINDEXED_ORDER_BY" not in _all_codes(non_trig)


def test_anl_lrg_offset():
    """ANL-LRG-OFFSET: Detects deep pagination OFFSET (> 1000) scanning and discarding rows."""
    trig = analyze_query("SELECT id, total FROM orders ORDER BY id ASC LIMIT 20 OFFSET 5000")
    assert "LARGE_OFFSET" in _all_codes(trig)

    non_trig = analyze_query("SELECT id, total FROM orders WHERE id > 5000 ORDER BY id ASC LIMIT 20")
    assert "LARGE_OFFSET" not in _all_codes(non_trig)


def test_anl_non_sarg_arith():
    """ANL-NON-SARG-ARITH: Detects non-sargable arithmetic expression on column in WHERE."""
    trig = analyze_query("SELECT id, price FROM products WHERE price + 15.00 > 100.00")
    assert "NON_SARGABLE_ARITHMETIC" in _all_codes(trig)

    non_trig = analyze_query("SELECT id, price FROM products WHERE price > 85.00")
    assert "NON_SARGABLE_ARITHMETIC" not in _all_codes(non_trig)


def test_anl_union_all():
    """ANL-UNION-ALL: Detects UNION instead of UNION ALL incurring temp table deduplication."""
    trig = analyze_query("SELECT id FROM orders WHERE status = 'shipped' UNION SELECT id FROM orders WHERE status = 'delivered'")
    assert "UNION_INSTEAD_OF_UNION_ALL" in _all_codes(trig)

    non_trig = analyze_query("SELECT id FROM orders WHERE status = 'shipped' UNION ALL SELECT id FROM orders WHERE status = 'delivered'")
    assert "UNION_INSTEAD_OF_UNION_ALL" not in _all_codes(non_trig)


def test_anl_cte_mult():
    """ANL-CTE-MULT: Detects CTE referenced multiple times risking duplicated evaluation in MySQL 8."""
    trig = analyze_query("WITH user_orders AS (SELECT customer_id, COUNT(*) AS cnt FROM orders GROUP BY customer_id) SELECT c.name, u1.cnt, u2.cnt FROM customers c JOIN user_orders u1 ON c.id = u1.customer_id JOIN user_orders u2 ON c.id = u2.customer_id")
    assert "CTE_MULTIPLY_REFERENCED" in _all_codes(trig)

    non_trig = analyze_query("WITH recent_orders AS (SELECT * FROM orders WHERE created_at > '2024-01-01') SELECT * FROM recent_orders LIMIT 10")
    assert "CTE_MULTIPLY_REFERENCED" not in _all_codes(non_trig)


def test_anl_win_no_part():
    """ANL-WIN-NO-PART: Detects window function without PARTITION BY forcing global filesort frame."""
    trig = analyze_query("SELECT id, total, ROW_NUMBER() OVER (ORDER BY total DESC) FROM orders")
    assert "WINDOW_WITHOUT_PARTITION" in _all_codes(trig)

    non_trig = analyze_query("SELECT id, customer_id, total, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY total DESC) FROM orders")
    assert "WINDOW_WITHOUT_PARTITION" not in _all_codes(non_trig)


# --- LOW PRIORITY ---

def test_anl_dist_join():
    """ANL-DIST-JOIN: Detects SELECT DISTINCT with JOIN."""
    trig = analyze_query("SELECT DISTINCT product_id FROM order_items JOIN orders ON order_items.order_id = orders.id")
    assert "DISTINCT_WITH_JOIN" in _all_codes(trig)

    non_trig = analyze_query("SELECT DISTINCT category FROM products")
    assert "DISTINCT_WITH_JOIN" not in _all_codes(non_trig)


def test_anl_hav_as_where():
    """ANL-HAV-AS-WHERE: Detects non-aggregated column filtered in HAVING instead of WHERE."""
    trig = analyze_query("SELECT status, COUNT(*) FROM orders GROUP BY status HAVING status = 'completed'")
    assert "HAVING_AS_WHERE" in _all_codes(trig)

    non_trig = analyze_query("SELECT status, COUNT(*) FROM orders WHERE status = 'completed' GROUP BY status")
    assert "HAVING_AS_WHERE" not in _all_codes(non_trig)


def test_anl_cnt_dist():
    """ANL-CNT-DIST: Detects COUNT(DISTINCT) requiring temporary hash table deduplication."""
    trig = analyze_query("SELECT COUNT(DISTINCT customer_id) FROM orders")
    assert "COUNT_DISTINCT" in _all_codes(trig)

    non_trig = analyze_query("SELECT COUNT(customer_id) FROM orders")
    assert "COUNT_DISTINCT" not in _all_codes(non_trig)


def test_anl_ins_single():
    """ANL-INS-SINGLE: Detects single-row INSERT when bulk insertion is preferred."""
    trig = analyze_query("INSERT INTO customers (id, name, email) VALUES (1, 'Alice', 'alice@example.com')")
    assert "INSERT_SINGLE_ROW" in _all_codes(trig)

    non_trig = analyze_query("INSERT INTO customers (id, name, email) VALUES (1, 'Alice', 'alice@example.com'), (2, 'Bob', 'bob@example.com')")
    assert "INSERT_SINGLE_ROW" not in _all_codes(non_trig)
