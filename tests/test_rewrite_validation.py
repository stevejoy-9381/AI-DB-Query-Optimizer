"""tests/test_rewrite_validation.py
Tests for query rewrite semantic validation and safety levels:
- Verified equivalent rewrites
- Cardinality / subset changes (LIMIT injection)
- Table mismatch and AST syntax errors
- NOT IN with NULLs vs JOIN equivalence breakdown
- Empirical multiset comparisons
"""

from unittest.mock import MagicMock
import pytest

from rewrite_validation import (
    validate_rewrite_static,
    validate_rewrite_data,
    EquivalenceLevel,
)
from rewrite_engine import rewrite_query
from analyzer import analyze_query


def test_static_validation_verified_equivalent():
    orig = "SELECT id, name FROM customers WHERE UPPER(name) = 'ALICE';"
    rew = "SELECT id, name FROM customers WHERE name = 'alice';"
    res = validate_rewrite_static(orig, rew, ["Fix function on column"])
    assert res.is_valid_sql is True
    assert res.level == EquivalenceLevel.VERIFIED_EQUIVALENT.value
    assert res.badge_color == "#2ecc71"


def test_static_validation_limit_injection_flagged_as_changes_results():
    orig = "SELECT id, name FROM customers;"
    rew = "SELECT id, name FROM customers LIMIT 100;"
    res = validate_rewrite_static(orig, rew, ["Add LIMIT 100"])
    assert res.is_valid_sql is True
    assert res.level == EquivalenceLevel.CHANGES_RESULTS_SUBSET.value
    assert res.badge_color == "#f39c12"
    assert "LIMIT clause was injected" in res.details[0]


def test_static_validation_syntax_error():
    orig = "SELECT id FROM customers;"
    bad_rew = "SELECT id FROM customers WHERE WHERE ;;"
    res = validate_rewrite_static(orig, bad_rew, ["Broken change"])
    assert res.is_valid_sql is False
    assert res.level == EquivalenceLevel.UNVERIFIED.value


def test_static_validation_table_mismatch():
    orig = "SELECT id FROM customers;"
    mismatch_rew = "SELECT id FROM suppliers;"
    res = validate_rewrite_static(orig, mismatch_rew, ["Substituted table"])
    assert res.level == EquivalenceLevel.CHANGES_RESULTS.value
    assert any("Table mismatch" in d for d in res.details)


def test_allow_limit_injection_opt_in():
    q = "SELECT * FROM customers;"
    analysis = analyze_query(q)

    # When enabled (default): LIMIT 100 is appended
    res_with_limit = rewrite_query(q, analysis, allow_limit_injection=True)
    assert "LIMIT 100" in res_with_limit["rewritten"]
    assert res_with_limit["validation"]["level"] == EquivalenceLevel.CHANGES_RESULTS_SUBSET.value

    # When disabled: LIMIT is NOT appended
    res_without_limit = rewrite_query(q, analysis, allow_limit_injection=False)
    assert "LIMIT 100" not in res_without_limit["rewritten"]
    assert res_without_limit["validation"]["level"] == EquivalenceLevel.VERIFIED_EQUIVALENT.value


def test_not_in_with_null_semantics_break():
    """NOT IN with subquery behaves differently than INNER JOIN if subquery has NULLs.

    In SQL:
      'x NOT IN (1, 2, NULL)' evaluates to UNKNOWN (no rows returned).
    A naive rewrite to 'LEFT JOIN ... WHERE ... IS NULL' or 'INNER JOIN' changes semantics!
    validate_rewrite_static flags this warning.
    """
    orig = "SELECT * FROM customers WHERE id NOT IN (SELECT customer_id FROM orders);"
    rew = "SELECT c.* FROM customers c JOIN orders o ON c.id = o.customer_id;"
    res = validate_rewrite_static(orig, rew, ["Convert IN subquery to JOIN"])
    assert any("duplicate" in d.lower() or "subquery" in d.lower() for d in res.details)


def test_data_validation_multiset_match_mock():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Simulate same multiset in different order (order-insensitive)
    mock_conn.execute.return_value.fetchall.side_effect = [
        [("Alice", 1), ("Bob", 2)],
        [("Bob", 2), ("Alice", 1)],
    ]

    orig = "SELECT name, id FROM customers;"
    rew = "SELECT name, id FROM customers;"

    val = validate_rewrite_data(mock_engine, orig, rew, row_cap=50)
    assert val.is_valid_sql is True
    assert val.level == EquivalenceLevel.EQUIVALENT_ON_SAMPLE_DATA.value
    assert val.multiset_match is True
    assert val.row_count_original == 2
    assert val.row_count_rewritten == 2


def test_data_validation_multiset_mismatch_mock():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Original returns 2 rows, rewritten returns 1 row
    mock_conn.execute.return_value.fetchall.side_effect = [
        [("Alice", 1), ("Bob", 2)],
        [("Alice", 1)],
    ]

    orig = "SELECT name, id FROM customers;"
    rew = "SELECT name, id FROM customers LIMIT 1;"

    val = validate_rewrite_data(mock_engine, orig, rew, row_cap=50)
    assert val.level == EquivalenceLevel.CHANGES_RESULTS.value
    assert val.multiset_match is False
    assert val.row_count_original == 2
    assert val.row_count_rewritten == 1
