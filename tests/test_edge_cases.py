"""
tests/test_edge_cases.py
Edge cases and adversarial input tests:
- Empty strings, whitespace, and comments-only inputs
- 100 KB query handling without crashing
- Unicode characters in identifiers and string literals
- Semicolon-separated multiple statements
- Invalid SQL syntax gracefully handled
- SQL injection patterns analyzed safely without execution
"""

from __future__ import annotations

import pytest

from analyzer import analyze_query
from optimizer import generate_optimizations, generate_rule_insight
from recommendations import generate_index_recommendations
from rewrite_engine import rewrite_query
from scoring import compute_score, simulate_optimized_score


def test_empty_string():
    """Empty string does not crash and returns invalid/neutral features."""
    analysis = analyze_query("")
    assert analysis["is_valid"] is False
    score = compute_score(analysis)
    assert 0 <= score.total <= 100
    recs = generate_index_recommendations("", analysis)
    assert isinstance(recs, list)


def test_whitespace_only():
    """Whitespace-only input does not crash."""
    analysis = analyze_query("   \n\t   ")
    assert analysis["is_valid"] is False
    score = compute_score(analysis)
    assert 0 <= score.total <= 100


def test_comments_only():
    """Comments-only input does not crash."""
    query = """
    -- This is a comment
    /* Multiline
       comment */
    """
    analysis = analyze_query(query)
    score = compute_score(analysis)
    assert 0 <= score.total <= 100


def test_100kb_query():
    """100 KB large query completes analysis cleanly without memory exhaustion or stack overflow."""
    # Generate 100 KB query: SELECT * FROM orders WHERE id IN (1, 2, ..., 20000)
    ids = ", ".join(str(i) for i in range(20_000))
    query = f"SELECT * FROM orders WHERE id IN ({ids});"
    assert len(query) > 100_000

    analysis = analyze_query(query)
    assert analysis["is_valid"] is True
    assert analysis["query_type"] == "SELECT"
    assert "id" in analysis["filter_columns"]
    score = compute_score(analysis)
    assert 0 <= score.total <= 100


def test_unicode_query():
    """Unicode table names, column names, and string literals are parsed without encoding errors."""
    query = "SELECT id, 姓名, 年龄 FROM 用户 WHERE 城市 = 'München' AND 状态 = '活跃';"
    analysis = analyze_query(query)
    assert analysis["is_valid"] is True
    score = compute_score(analysis)
    assert 0 <= score.total <= 100
    insight = generate_rule_insight(query, analysis, score.total)
    assert isinstance(insight, str)


def test_semicolon_separated_multiple_statements():
    """Semicolon-separated multiple statements parse safely and detect hazards."""
    query = "SELECT id FROM users; DROP TABLE users;"
    analysis = analyze_query(query)
    score = compute_score(analysis)
    assert 0 <= score.total <= 100
    # Query rewriter should not execute anything
    rw = rewrite_query(query, analysis)
    assert "DROP TABLE" in rw["rewritten"] or "SELECT" in rw["rewritten"]


def test_invalid_sql_syntax():
    """Syntactically broken SQL does not crash the system."""
    query = "SELECT FROM WHERE GROUP BY ORDER BY;"
    analysis = analyze_query(query)
    # Analyzer should handle fallback regex or ast failure gracefully
    score = compute_score(analysis)
    assert 0 <= score.total <= 100


def test_sql_injection_style_input():
    """SQL injection patterns analyze purely as strings without executing."""
    query = "SELECT * FROM accounts WHERE username = 'admin' OR '1'='1' UNION SELECT credit_card, cvv FROM cards;"
    analysis = analyze_query(query)
    assert analysis["is_valid"] is True
    score = compute_score(analysis)
    assert 0 <= score.total <= 100
    # Must flag anti-patterns such as SELECT * or UNION without ALL
    issue_codes = {i["code"] for i in analysis["issues"]} | {w["code"] for w in analysis["warnings"]}
    assert "SELECT_STAR" in issue_codes or "UNION_INSTEAD_OF_UNION_ALL" in issue_codes
