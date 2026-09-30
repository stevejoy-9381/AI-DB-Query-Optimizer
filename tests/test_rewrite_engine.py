"""tests/test_rewrite_engine.py
Unit tests for AST-driven RewriteRule registry and rewrite transformations.
Verifies each rule before/after transformation individually and in combination.
"""

import pytest

from analyzer import analyze_query
from db.schema import ColumnInfo, IndexInfo, SchemaInfo, TableInfo
from rewrite_engine import (
    rewrite_query,
)


@pytest.fixture
def test_schema():
    """Schema with primary key on customers and orders."""
    cust_cols = [
        ColumnInfo("id", "int", False, "PRI", None),
        ColumnInfo("name", "varchar(100)", False, "", None),
        ColumnInfo("email", "varchar(100)", False, "", None),
    ]
    cust_idx = [
        IndexInfo("PRIMARY", "customers", ["id"], True, True),
    ]
    customers_table = TableInfo(
        "customers",
        {c.name.lower(): c for c in cust_cols},
        {i.name.lower(): i for i in cust_idx},
    )
    return SchemaInfo("shop_db", {"customers": customers_table})


# ---------------------------------------------------------------------------
# 1. IN Subquery to EXISTS
# ---------------------------------------------------------------------------


def test_rule_in_subquery_to_exists():
    q = "SELECT id FROM customers WHERE id IN (SELECT customer_id FROM orders);"
    analysis = analyze_query(q)
    res = rewrite_query(q, analysis, allow_limit_injection=False)

    assert "EXISTS" in res["rewritten"]
    assert "IN (" not in res["rewritten"]
    assert any("IN (subquery) to EXISTS" in c for c in res["changes"])


# ---------------------------------------------------------------------------
# 2. NOT IN Subquery to NOT EXISTS
# ---------------------------------------------------------------------------


def test_rule_not_in_subquery_to_not_exists():
    q = "SELECT id FROM customers WHERE id NOT IN (SELECT customer_id FROM orders);"
    analysis = analyze_query(q)
    res = rewrite_query(q, analysis, allow_limit_injection=False)

    assert "NOT EXISTS" in res["rewritten"]
    assert "NOT IN" not in res["rewritten"]
    assert any("NOT IN (subquery) to NOT EXISTS" in c for c in res["changes"])


# ---------------------------------------------------------------------------
# 3. YEAR(col) to Sargable Date Range
# ---------------------------------------------------------------------------


def test_rule_year_function_to_range():
    q = "SELECT id FROM orders WHERE YEAR(created_at) = 2024;"
    analysis = analyze_query(q)
    res = rewrite_query(q, analysis, allow_limit_injection=False)

    assert "created_at >= '2024-01-01'" in res["rewritten"]
    assert "created_at < '2025-01-01'" in res["rewritten"]
    assert "YEAR(" not in res["rewritten"]


# ---------------------------------------------------------------------------
# 4. Remove Redundant DISTINCT (with Schema)
# ---------------------------------------------------------------------------


def test_rule_remove_redundant_distinct(test_schema):
    q = "SELECT DISTINCT id, name FROM customers;"
    analysis = analyze_query(q, schema=test_schema)
    res = rewrite_query(q, analysis, schema=test_schema, allow_limit_injection=False)

    assert "DISTINCT" not in res["rewritten"]
    assert any("redundant DISTINCT" in c for c in res["changes"])


def test_rule_distinct_preserved_when_no_unique_key(test_schema):
    q = "SELECT DISTINCT name FROM customers;"
    analysis = analyze_query(q, schema=test_schema)
    res = rewrite_query(q, analysis, schema=test_schema, allow_limit_injection=False)

    # DISTINCT should NOT be removed because name is not unique
    assert "DISTINCT" in res["rewritten"]


# ---------------------------------------------------------------------------
# 5. UNION to UNION ALL
# ---------------------------------------------------------------------------


def test_rule_union_to_union_all():
    q = "SELECT id FROM current_orders UNION SELECT id FROM past_orders;"
    analysis = analyze_query(q)
    res = rewrite_query(q, analysis, allow_limit_injection=False)

    assert "UNION ALL" in res["rewritten"]
    assert any("UNION ALL" in c for c in res["changes"])


# ---------------------------------------------------------------------------
# 6. Function on Column Inversion
# ---------------------------------------------------------------------------


def test_rule_function_on_column():
    q = "SELECT id FROM users WHERE UPPER(status) = 'ACTIVE';"
    analysis = analyze_query(q)
    res = rewrite_query(q, analysis, allow_limit_injection=False)

    assert "status = 'active'" in res["rewritten"]
    assert "UPPER(" not in res["rewritten"]


# ---------------------------------------------------------------------------
# 7. SELECT * Expansion (Schema vs Hints)
# ---------------------------------------------------------------------------


def test_rule_select_star_with_schema(test_schema):
    q = "SELECT * FROM customers WHERE id = 1;"
    analysis = analyze_query(q, schema=test_schema)
    res = rewrite_query(q, analysis, schema=test_schema, allow_limit_injection=False)

    assert "SELECT *" not in res["rewritten"]
    assert "id" in res["rewritten"]
    assert "name" in res["rewritten"]
    assert "email" in res["rewritten"]


def test_rule_select_star_fallback_hints():
    q = "SELECT * FROM orders WHERE id = 1;"
    analysis = analyze_query(q)
    res = rewrite_query(q, analysis, allow_limit_injection=False)

    assert "SELECT *" not in res["rewritten"]
    assert "customer_id" in res["rewritten"]


# ---------------------------------------------------------------------------
# 8. LIMIT Injection & Opt-in Toggle
# ---------------------------------------------------------------------------


def test_rule_limit_injection_enabled():
    q = "SELECT id, name FROM customers;"
    analysis = analyze_query(q)
    res = rewrite_query(q, analysis, allow_limit_injection=True)

    assert "LIMIT 100" in res["rewritten"]


def test_rule_limit_injection_disabled():
    q = "SELECT id, name FROM customers;"
    analysis = analyze_query(q)
    res = rewrite_query(q, analysis, allow_limit_injection=False)

    assert "LIMIT" not in res["rewritten"]
    assert res["is_changed"] is False


# ---------------------------------------------------------------------------
# 9. Deep OFFSET Keyset Pagination Advice
# ---------------------------------------------------------------------------


def test_offset_pagination_advice():
    q = "SELECT id, total FROM orders ORDER BY id LIMIT 20 OFFSET 5000;"
    analysis = analyze_query(q)
    res = rewrite_query(q, analysis, allow_limit_injection=False)

    assert any("keyset pagination" in c.lower() for c in res["changes"])
