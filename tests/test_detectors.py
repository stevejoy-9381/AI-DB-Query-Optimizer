"""tests/test_detectors.py
Comprehensive unit tests for the 12 query anti-pattern detectors.
Contains at least 2 positive (bad query -> detector fires) and 2 negative (good query -> detector silent)
tests for each detector.
"""

import pytest
from analyzer import analyze_query
from db.schema import SchemaInfo, TableInfo, ColumnInfo, IndexInfo


@pytest.fixture
def mock_schema():
    """Provides a sample schema for schema-dependent detectors."""
    cust_cols = [
        ColumnInfo("id", "int", False, "PRI", None),
        ColumnInfo("phone", "varchar(20)", False, "", None),
        ColumnInfo("name", "varchar(100)", False, "", None),
        ColumnInfo("age", "int", False, "", None),
    ]
    cust_idx = [
        IndexInfo(name="PRIMARY", table_name="customers", columns=["id"], is_primary=True, is_unique=True),
        IndexInfo(name="idx_phone", table_name="customers", columns=["phone"], is_primary=False, is_unique=False),
    ]
    customers_table = TableInfo(
        "customers",
        {c.name.lower(): c for c in cust_cols},
        {i.name.lower(): i for i in cust_idx},
    )

    order_cols = [
        ColumnInfo("id", "bigint", False, "PRI", None),
        ColumnInfo("customer_id", "int", False, "MUL", None),
        ColumnInfo("total", "decimal(10,2)", False, "", None),
        ColumnInfo("status", "varchar(20)", False, "", None),
    ]
    order_idx = [
        IndexInfo(name="PRIMARY", table_name="orders", columns=["id"], is_primary=True, is_unique=True),
        IndexInfo(name="idx_orders_cust", table_name="orders", columns=["customer_id"], is_primary=False, is_unique=False),
    ]
    orders_table = TableInfo(
        "orders",
        {c.name.lower(): c for c in order_cols},
        {i.name.lower(): i for i in order_idx},
    )

    return SchemaInfo(
        database="shop_db",
        tables={"customers": customers_table, "orders": orders_table},
    )


# ---------------------------------------------------------------------------
# 1. Correlated Subquery Detector
# ---------------------------------------------------------------------------

def test_correlated_subquery_positive_select():
    q = "SELECT c.name, (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.id) FROM customers c;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "CORRELATED_SUBQUERY" in codes


def test_correlated_subquery_positive_where():
    q = "SELECT c.name FROM customers c WHERE (SELECT MAX(o.total) FROM orders o WHERE o.customer_id = c.id) > 100;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "CORRELATED_SUBQUERY" in codes


def test_correlated_subquery_negative_join():
    q = "SELECT c.name, o.total FROM customers c JOIN orders o ON c.id = o.customer_id;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "CORRELATED_SUBQUERY" not in codes


def test_correlated_subquery_negative_independent_subquery():
    q = "SELECT c.name FROM customers c WHERE c.id IN (SELECT o.customer_id FROM orders o WHERE o.total > 500);"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "CORRELATED_SUBQUERY" not in codes


# ---------------------------------------------------------------------------
# 2. OR Across Different Columns Detector
# ---------------------------------------------------------------------------

def test_or_different_columns_positive_1():
    q = "SELECT id FROM orders WHERE customer_id = 42 OR status = 'pending';"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "OR_DIFFERENT_COLUMNS" in codes


def test_or_different_columns_positive_2():
    q = "SELECT id, name FROM customers WHERE name = 'John' OR phone = '12345';"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "OR_DIFFERENT_COLUMNS" in codes


def test_or_different_columns_negative_same_column():
    q = "SELECT id FROM orders WHERE status = 'pending' OR status = 'processing';"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "OR_DIFFERENT_COLUMNS" not in codes


def test_or_different_columns_negative_and_only():
    q = "SELECT id FROM orders WHERE customer_id = 42 AND status = 'pending';"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "OR_DIFFERENT_COLUMNS" not in codes


# ---------------------------------------------------------------------------
# 3. Implicit Type Conversion Detector
# ---------------------------------------------------------------------------

def test_implicit_type_conversion_positive_string_compared_to_number(mock_schema):
    q = "SELECT id FROM customers WHERE phone = 1234567890;"
    res = analyze_query(q, schema=mock_schema)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "IMPLICIT_TYPE_CONVERSION" in codes


def test_implicit_type_conversion_positive_reversed(mock_schema):
    q = "SELECT id FROM customers WHERE 98765 = phone;"
    res = analyze_query(q, schema=mock_schema)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "IMPLICIT_TYPE_CONVERSION" in codes


def test_implicit_type_conversion_negative_quoted_string(mock_schema):
    q = "SELECT id FROM customers WHERE phone = '1234567890';"
    res = analyze_query(q, schema=mock_schema)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "IMPLICIT_TYPE_CONVERSION" not in codes


def test_implicit_type_conversion_negative_number_compared_to_number(mock_schema):
    q = "SELECT id FROM customers WHERE age = 30;"
    res = analyze_query(q, schema=mock_schema)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "IMPLICIT_TYPE_CONVERSION" not in codes


# ---------------------------------------------------------------------------
# 4. NOT IN with Subquery Detector
# ---------------------------------------------------------------------------

def test_not_in_subquery_positive_1():
    q = "SELECT id, name FROM customers WHERE id NOT IN (SELECT customer_id FROM orders);"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "NOT_IN_SUBQUERY" in codes


def test_not_in_subquery_positive_2():
    q = "SELECT id FROM orders WHERE customer_id NOT IN (SELECT id FROM customers WHERE status = 'banned');"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "NOT_IN_SUBQUERY" in codes


def test_not_in_subquery_negative_not_exists():
    q = "SELECT c.id, c.name FROM customers c WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "NOT_IN_SUBQUERY" not in codes


def test_not_in_subquery_negative_literal_list():
    q = "SELECT id, name FROM customers WHERE id NOT IN (1, 2, 3, 4);"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "NOT_IN_SUBQUERY" not in codes


# ---------------------------------------------------------------------------
# 5. ORDER BY RAND() & Unindexed ORDER BY Detectors
# ---------------------------------------------------------------------------

def test_order_by_rand_positive_1():
    q = "SELECT id, name FROM customers ORDER BY RAND() LIMIT 5;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "ORDER_BY_RAND" in codes


def test_order_by_rand_positive_2():
    q = "SELECT id FROM orders ORDER BY RANDOM() LIMIT 1;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "ORDER_BY_RAND" in codes


def test_order_by_negative_indexed_column(mock_schema):
    q = "SELECT id, name FROM customers ORDER BY id LIMIT 10;"
    res = analyze_query(q, schema=mock_schema)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "ORDER_BY_RAND" not in codes
    assert "UNINDEXED_ORDER_BY" not in codes


def test_unindexed_order_by_positive(mock_schema):
    q = "SELECT id, name FROM customers ORDER BY name LIMIT 10;"
    res = analyze_query(q, schema=mock_schema)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "UNINDEXED_ORDER_BY" in codes


# ---------------------------------------------------------------------------
# 6. Large OFFSET Pagination Detector
# ---------------------------------------------------------------------------

def test_large_offset_positive_explicit_offset():
    q = "SELECT id, name FROM customers ORDER BY id LIMIT 20 OFFSET 5000;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "LARGE_OFFSET" in codes


def test_large_offset_positive_comma_offset():
    q = "SELECT id, name FROM customers ORDER BY id LIMIT 1000, 20;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "LARGE_OFFSET" in codes


def test_large_offset_negative_small_offset():
    q = "SELECT id, name FROM customers ORDER BY id LIMIT 20 OFFSET 10;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "LARGE_OFFSET" not in codes


def test_large_offset_negative_no_offset():
    q = "SELECT id, name FROM customers ORDER BY id LIMIT 50;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "LARGE_OFFSET" not in codes


# ---------------------------------------------------------------------------
# 7. Missing JOIN Condition Detector
# ---------------------------------------------------------------------------

def test_missing_join_condition_positive_cross_join():
    q = "SELECT c.name, o.id FROM customers c CROSS JOIN orders o;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "MISSING_JOIN_CONDITION" in codes


def test_missing_join_condition_positive_comma_join():
    q = "SELECT customers.name, orders.id FROM customers, orders;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "MISSING_JOIN_CONDITION" in codes


def test_missing_join_condition_negative_explicit_on():
    q = "SELECT c.name, o.id FROM customers c JOIN orders o ON c.id = o.customer_id;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "MISSING_JOIN_CONDITION" not in codes


def test_missing_join_condition_negative_comma_with_where_eq():
    q = "SELECT c.name, o.id FROM customers c, orders o WHERE c.id = o.customer_id;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "MISSING_JOIN_CONDITION" not in codes


# ---------------------------------------------------------------------------
# 8. Non-Sargable Arithmetic Detector
# ---------------------------------------------------------------------------

def test_non_sargable_arithmetic_positive_add():
    q = "SELECT id, total FROM orders WHERE total + 10 > 100;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "NON_SARGABLE_ARITHMETIC" in codes


def test_non_sargable_arithmetic_positive_multiply():
    q = "SELECT id, total FROM orders WHERE total * 1.15 >= 500;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "NON_SARGABLE_ARITHMETIC" in codes


def test_non_sargable_arithmetic_negative_isolated_column():
    q = "SELECT id, total FROM orders WHERE total > 100 - 10;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "NON_SARGABLE_ARITHMETIC" not in codes


def test_non_sargable_arithmetic_negative_plain_compare():
    q = "SELECT id, total FROM orders WHERE total > 90;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "NON_SARGABLE_ARITHMETIC" not in codes


# ---------------------------------------------------------------------------
# 9. HAVING as WHERE Detector
# ---------------------------------------------------------------------------

def test_having_as_where_positive_1():
    q = "SELECT customer_id, COUNT(*) FROM orders GROUP BY customer_id HAVING customer_id > 100;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "HAVING_AS_WHERE" in codes


def test_having_as_where_positive_2():
    q = "SELECT status, SUM(total) FROM orders GROUP BY status HAVING status = 'completed';"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "HAVING_AS_WHERE" in codes


def test_having_as_where_negative_aggregate_filter():
    q = "SELECT customer_id, COUNT(*) FROM orders GROUP BY customer_id HAVING COUNT(*) > 5;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "HAVING_AS_WHERE" not in codes


def test_having_as_where_negative_where_used():
    q = "SELECT customer_id, COUNT(*) FROM orders WHERE customer_id > 100 GROUP BY customer_id;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "HAVING_AS_WHERE" not in codes


# ---------------------------------------------------------------------------
# 10. COUNT(DISTINCT) Detector
# ---------------------------------------------------------------------------

def test_count_distinct_positive_1():
    q = "SELECT COUNT(DISTINCT customer_id) FROM orders;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "COUNT_DISTINCT" in codes


def test_count_distinct_positive_2():
    q = "SELECT status, COUNT(DISTINCT total) FROM orders GROUP BY status;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "COUNT_DISTINCT" in codes


def test_count_distinct_negative_standard_count():
    q = "SELECT COUNT(*) FROM orders WHERE status = 'completed';"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "COUNT_DISTINCT" not in codes


def test_count_distinct_negative_column_count():
    q = "SELECT COUNT(id) FROM customers;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "COUNT_DISTINCT" not in codes


# ---------------------------------------------------------------------------
# 11. Leading Wildcard Detector
# ---------------------------------------------------------------------------

def test_leading_wildcard_positive_percent():
    q = "SELECT id, name FROM customers WHERE name LIKE '%son';"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "LEADING_WILDCARD" in codes


def test_leading_wildcard_positive_underscore():
    q = "SELECT id, name FROM customers WHERE name LIKE '_alice';"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "LEADING_WILDCARD" in codes


def test_leading_wildcard_negative_trailing_percent():
    q = "SELECT id, name FROM customers WHERE name LIKE 'son%';"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "LEADING_WILDCARD" not in codes


def test_leading_wildcard_negative_equality():
    q = "SELECT id, name FROM customers WHERE name = 'John Doe';"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "LEADING_WILDCARD" not in codes


# ---------------------------------------------------------------------------
# 12. UNION Instead of UNION ALL Detector
# ---------------------------------------------------------------------------

def test_union_all_positive_1():
    q = "SELECT id, total FROM orders WHERE status = 'shipped' UNION SELECT id, total FROM orders WHERE status = 'delivered';"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "UNION_INSTEAD_OF_UNION_ALL" in codes


def test_union_all_positive_2():
    q = "SELECT name FROM customers UNION SELECT name FROM suppliers;"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "UNION_INSTEAD_OF_UNION_ALL" in codes


def test_union_all_negative_union_all():
    q = "SELECT id, total FROM orders WHERE status = 'shipped' UNION ALL SELECT id, total FROM orders WHERE status = 'delivered';"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "UNION_INSTEAD_OF_UNION_ALL" not in codes


def test_union_all_negative_single_select():
    q = "SELECT id, total FROM orders WHERE status IN ('shipped', 'delivered');"
    res = analyze_query(q)
    codes = {item["code"] for item in res["issues"] + res["warnings"]}
    assert "UNION_INSTEAD_OF_UNION_ALL" not in codes
