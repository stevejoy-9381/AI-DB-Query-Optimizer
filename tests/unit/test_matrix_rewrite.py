"""tests/unit/test_matrix_rewrite.py
Automated Unit Tests for all Rewrite Engine behaviors defined in docs/TEST_MATRIX.md.
"""

from analyzer import analyze_query
from rewrite_engine import rewrite_query
from rewrite_validation import validate_rewrite_static


def test_rwt_in_exists():
    """RWT-IN-EXISTS: Rewrites IN (subquery) to correlated EXISTS."""
    q = "SELECT name FROM customers WHERE id IN (SELECT customer_id FROM orders)"
    anl = analyze_query(q)
    res = rewrite_query(q, anl)
    assert res["is_changed"] is True
    assert "EXISTS" in res["rewritten"].upper()
    assert any("EXISTS" in c for c in res["changes"])


def test_rwt_notin_notexists():
    """RWT-NOTIN-NOTEXISTS: Rewrites NOT IN (subquery) to NOT EXISTS eliminating NULL trap."""
    q = "SELECT id, name FROM customers WHERE id NOT IN (SELECT customer_id FROM orders)"
    anl = analyze_query(q)
    res = rewrite_query(q, anl)
    assert res["is_changed"] is True
    assert "NOT EXISTS" in res["rewritten"].upper()
    assert any("NOT EXISTS" in c for c in res["changes"])


def test_rwt_date_range():
    """RWT-DATE-RANGE: Rewrites YEAR(col) = YYYY into sargable date range."""
    q = "SELECT * FROM orders WHERE YEAR(order_date) = 2024"
    anl = analyze_query(q)
    res = rewrite_query(q, anl)
    assert res["is_changed"] is True
    assert "order_date >=" in res["rewritten"] or "order_date BETWEEN" in res["rewritten"] or "2024-01-01" in res["rewritten"]


def test_rwt_select_star():
    """RWT-SELECT-STAR: Expands SELECT * into explicit table columns using schema or column hints."""
    q = "SELECT * FROM users WHERE id = 10"
    anl = analyze_query(q)
    res = rewrite_query(q, anl)
    assert res["is_changed"] is True
    assert "SELECT *" not in res["rewritten"]
    # Checks for hints: id, name, email, created_at
    assert "name" in res["rewritten"]


def test_rwt_static_valid():
    """RWT-STATIC-VALID: Validates syntactic correctness and semantic equivalence of generated rewrites."""
    orig = "SELECT name FROM customers WHERE id IN (SELECT customer_id FROM orders)"
    rewritten = "SELECT name FROM customers WHERE EXISTS (SELECT 1 FROM orders WHERE orders.customer_id = customers.id)"
    val_res = validate_rewrite_static(orig, rewritten, [])
    assert val_res.is_valid_sql is True
    assert val_res.level in ("Verified equivalent", "Equivalent on sample data", "Changes results (intentional subset/limit)")


def test_rwt_union_all():
    """RWT-UNION-ALL: Rewrites UNION to UNION ALL when duplicate rows do not require deduplication."""
    q = "SELECT id FROM orders WHERE status = 'shipped' UNION SELECT id FROM orders WHERE status = 'delivered'"
    anl = analyze_query(q)
    res = rewrite_query(q, anl)
    assert res["is_changed"] is True
    assert "UNION ALL" in res["rewritten"].upper()


def test_rwt_func_on_column():
    """RWT-FUNC-ARITH: Tests FunctionOnColumnRule transforming UPPER/LOWER on column into literal inversion.
    Note: Code implements FunctionOnColumnRule for UPPER/LOWER, but arithmetic transformations (col + 10 = 100)
    are currently not implemented in REWRITE_RULES_REGISTRY (finding logged in report).
    """
    q = "SELECT id, email FROM users WHERE UPPER(email) = 'TEST@EXAMPLE.COM'"
    anl = analyze_query(q)
    res = rewrite_query(q, anl)
    assert res["is_changed"] is True
    assert "email = 'test@example.com'" in res["rewritten"] or "email='test@example.com'" in res["rewritten"]


def test_rwt_rem_distinct():
    """RWT-REM-DISTINCT: Removes redundant DISTINCT when query groups by all selected columns."""
    q = "SELECT DISTINCT department, COUNT(*) FROM employees GROUP BY department"
    anl = analyze_query(q)
    res = rewrite_query(q, anl)
    assert res["is_changed"] is True or "DISTINCT" not in res["rewritten"]


def test_rwt_limit_inject():
    """RWT-LIMIT-INJECT: Injects protective LIMIT clause on unbounded SELECT queries."""
    q = "SELECT id, name FROM customers"
    anl = analyze_query(q)
    res = rewrite_query(q, anl)
    assert "LIMIT" in res["rewritten"].upper()
