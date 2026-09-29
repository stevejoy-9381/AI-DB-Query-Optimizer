"""tests/test_statement_types.py
Tests for multi-statement type detection, statement-specific rules,
safety guards against executing non-SELECT queries, and graceful rewrite handling.
"""

import pytest
from analyzer import analyze_query
from scoring import compute_score
from rewrite_engine import rewrite_query
from db.explain import validate_explainable_query
from db.schema import SchemaInfo, TableInfo, ColumnInfo, IndexInfo


@pytest.fixture
def statement_test_schema():
    """Sample schema with indexed id and unindexed notes column."""
    cust_cols = [
        ColumnInfo("id", "int", False, "PRI", None),
        ColumnInfo("name", "varchar(100)", False, "", None),
        ColumnInfo("notes", "text", False, "", None),
    ]
    cust_idx = [
        IndexInfo(name="PRIMARY", table_name="customers", columns=["id"], is_primary=True, is_unique=True),
    ]
    return SchemaInfo(
        database="shop_db",
        tables={
            "customers": TableInfo(
                "customers",
                {c.name.lower(): c for c in cust_cols},
                {i.name.lower(): i for i in cust_idx},
            )
        },
    )


# ---------------------------------------------------------------------------
# 1. Statement Type Detection
# ---------------------------------------------------------------------------

def test_detect_select():
    res = analyze_query("SELECT id FROM customers WHERE id = 1;")
    assert res["statement_type"] == "SELECT"


def test_detect_update():
    res = analyze_query("UPDATE customers SET name = 'Bob' WHERE id = 1;")
    assert res["statement_type"] == "UPDATE"


def test_detect_delete():
    res = analyze_query("DELETE FROM customers WHERE id = 1;")
    assert res["statement_type"] == "DELETE"


def test_detect_insert_values():
    res = analyze_query("INSERT INTO customers (id, name) VALUES (1, 'Alice');")
    assert res["statement_type"] == "INSERT"
    assert res["is_insert_select"] is False


def test_detect_insert_select():
    res = analyze_query("INSERT INTO customers_archive SELECT * FROM customers;")
    assert res["statement_type"] == "INSERT...SELECT"
    assert res["is_insert_select"] is True


def test_detect_cte():
    q = "WITH c AS (SELECT id FROM customers) SELECT id FROM c;"
    res = analyze_query(q)
    assert res["statement_type"] == "CTE"
    assert res["is_cte"] is True


def test_detect_union():
    q = "SELECT id FROM a UNION SELECT id FROM b;"
    res = analyze_query(q)
    assert res["statement_type"] == "UNION"


def test_detect_window_function():
    q = "SELECT id, ROW_NUMBER() OVER (ORDER BY id) FROM customers;"
    res = analyze_query(q)
    assert res["has_window_functions"] is True


# ---------------------------------------------------------------------------
# 2. Critical Safety Rules (UPDATE/DELETE without WHERE)
# ---------------------------------------------------------------------------

def test_update_without_where_critical():
    res = analyze_query("UPDATE customers SET name = 'AllHacked';")
    critical_issues = [i for i in res["issues"] if i["code"] == "UPDATE_WITHOUT_WHERE"]
    assert len(critical_issues) == 1
    assert critical_issues[0]["severity"] == "CRITICAL"

    # Verify score is drastically penalized
    score = compute_score(res)
    assert score.total <= 50


def test_delete_without_where_critical():
    res = analyze_query("DELETE FROM customers;")
    critical_issues = [i for i in res["issues"] if i["code"] == "DELETE_WITHOUT_WHERE"]
    assert len(critical_issues) == 1
    assert critical_issues[0]["severity"] == "CRITICAL"

    score = compute_score(res)
    assert score.total <= 50


def test_update_with_where_is_not_critical():
    res = analyze_query("UPDATE customers SET name = 'Alice' WHERE id = 5;")
    critical_issues = [i for i in res["issues"] if i["code"] == "UPDATE_WITHOUT_WHERE"]
    assert len(critical_issues) == 0


def test_delete_with_where_is_not_critical():
    res = analyze_query("DELETE FROM customers WHERE id = 5;")
    critical_issues = [i for i in res["issues"] if i["code"] == "DELETE_WITHOUT_WHERE"]
    assert len(critical_issues) == 0


# ---------------------------------------------------------------------------
# 3. Unindexed UPDATE/DELETE Locking Hazard
# ---------------------------------------------------------------------------

def test_update_unindexed_where_column(statement_test_schema):
    # notes is not indexed
    res = analyze_query("UPDATE customers SET name = 'Alice' WHERE notes = 'VIP';", schema=statement_test_schema)
    codes = {i["code"] for i in res["issues"] + res["warnings"]}
    assert "UPDATE_DELETE_UNINDEXED_WHERE" in codes


def test_update_indexed_where_column(statement_test_schema):
    # id is indexed (PRIMARY KEY)
    res = analyze_query("UPDATE customers SET name = 'Alice' WHERE id = 10;", schema=statement_test_schema)
    codes = {i["code"] for i in res["issues"] + res["warnings"]}
    assert "UPDATE_DELETE_UNINDEXED_WHERE" not in codes


# ---------------------------------------------------------------------------
# 4. INSERT Patterns
# ---------------------------------------------------------------------------

def test_insert_single_row_flag():
    res = analyze_query("INSERT INTO customers (id, name) VALUES (1, 'Alice');")
    codes = {i["code"] for i in res["issues"] + res["warnings"]}
    assert "INSERT_SINGLE_ROW" in codes


def test_insert_bulk_rows():
    res = analyze_query("INSERT INTO customers (id, name) VALUES (1, 'Alice'), (2, 'Bob'), (3, 'Charlie');")
    codes = {i["code"] for i in res["issues"] + res["warnings"]}
    assert "INSERT_SINGLE_ROW" not in codes
    score = compute_score(res)
    # Bulk insert bonus awarded
    applied_codes = {b["code"] for b in score.breakdown}
    assert "BULK_INSERT" in applied_codes


def test_insert_select_unbounded():
    res = analyze_query("INSERT INTO archive_orders SELECT * FROM orders;")
    codes = {i["code"] for i in res["issues"] + res["warnings"]}
    assert "INSERT_SELECT_UNBOUNDED" in codes


def test_insert_select_bounded():
    res = analyze_query("INSERT INTO archive_orders SELECT * FROM orders WHERE status = 'delivered' LIMIT 1000;")
    codes = {i["code"] for i in res["issues"] + res["warnings"]}
    assert "INSERT_SELECT_UNBOUNDED" not in codes


# ---------------------------------------------------------------------------
# 5. CTE Multiple References & Window Framing
# ---------------------------------------------------------------------------

def test_cte_multiply_referenced():
    q = """
    WITH summary AS (SELECT customer_id, count(*) as cnt FROM orders GROUP BY customer_id)
    SELECT c.name, s1.cnt, s2.cnt
    FROM customers c
    JOIN summary s1 ON c.id = s1.customer_id
    JOIN summary s2 ON c.id = s2.customer_id;
    """
    res = analyze_query(q)
    codes = {i["code"] for i in res["issues"] + res["warnings"]}
    assert "CTE_MULTIPLY_REFERENCED" in codes


def test_window_without_partition():
    q = "SELECT id, ROW_NUMBER() OVER (ORDER BY id DESC) FROM orders;"
    res = analyze_query(q)
    codes = {i["code"] for i in res["issues"] + res["warnings"]}
    assert "WINDOW_WITHOUT_PARTITION" in codes


def test_window_with_partition():
    q = "SELECT id, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY id DESC) FROM orders;"
    res = analyze_query(q)
    codes = {i["code"] for i in res["issues"] + res["warnings"]}
    assert "WINDOW_WITHOUT_PARTITION" not in codes


# ---------------------------------------------------------------------------
# 6. Database Safety: Non-SELECT queries blocked from EXPLAIN
# ---------------------------------------------------------------------------

def test_validate_explainable_query_blocks_update():
    valid, reason = validate_explainable_query("UPDATE customers SET name = 'Bob' WHERE id = 1;")
    assert valid is False
    assert "Only SELECT queries" in reason or "UPDATE" in reason


def test_validate_explainable_query_blocks_delete():
    valid, reason = validate_explainable_query("DELETE FROM customers WHERE id = 1;")
    assert valid is False
    assert "Only SELECT queries" in reason or "DELETE" in reason


def test_validate_explainable_query_blocks_insert():
    valid, reason = validate_explainable_query("INSERT INTO customers (id) VALUES (1);")
    assert valid is False
    assert "Only SELECT queries" in reason or "INSERT" in reason


def test_validate_explainable_query_allows_select():
    valid, reason = validate_explainable_query("SELECT id, name FROM customers WHERE id = 1;")
    assert valid is True
    assert "Valid" in reason or reason == ""


# ---------------------------------------------------------------------------
# 7. Rewrite Engine Safety: Unsupported statement type handling
# ---------------------------------------------------------------------------

def test_rewrite_engine_unsupported_statement_type():
    update_sql = "UPDATE customers SET name = 'Bob' WHERE id = 1;"
    analysis = analyze_query(update_sql)
    res = rewrite_query(update_sql, analysis)
    assert res["is_changed"] is False
    assert res.get("supported") is False
    assert "No automatic rewrite available for UPDATE" in res["changes"][0]
