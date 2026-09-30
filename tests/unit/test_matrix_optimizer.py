"""tests/unit/test_matrix_optimizer.py
Automated Unit Tests for all Optimizer behaviors defined in docs/TEST_MATRIX.md.
"""

from analyzer import analyze_query
from optimizer import generate_optimizations, generate_rule_insight
from scoring import compute_score


def test_opt_rec_star():
    """OPT-REC-STAR: Generates recommendation to replace SELECT * with specific columns."""
    q = "SELECT * FROM users WHERE id = 10"
    anl = analyze_query(q)
    recs = generate_optimizations(q, anl)
    star_recs = [r for r in recs if "SELECT *" in r["title"]]
    assert len(star_recs) == 1
    assert star_recs[0]["priority"] == "HIGH"


def test_opt_rec_where():
    """OPT-REC-WHERE: Generates recommendation to add WHERE clause on full table scan."""
    q = "SELECT name FROM customers"
    anl = analyze_query(q)
    recs = generate_optimizations(q, anl)
    where_recs = [r for r in recs if "WHERE" in r["title"]]
    assert len(where_recs) == 1
    assert where_recs[0]["priority"] == "HIGH"


def test_opt_rec_sort():
    """OPT-REC-SORT: Sorts optimization recommendations by priority order (CRITICAL -> HIGH -> MEDIUM -> LOW)."""
    q = "UPDATE users SET status = 'inactive'"
    anl = analyze_query(q)
    recs = generate_optimizations(q, anl)
    priorities = [r["priority"] for r in recs]
    # Priority order: CRITICAL (-1) < HIGH (0) < MEDIUM (1) < LOW (2)
    priority_ranks = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    ranks = [priority_ranks.get(p, 99) for p in priorities]
    assert ranks == sorted(ranks)


def test_opt_rec_join():
    """OPT-REC-JOIN: Generates recommendation to index JOIN/ON columns."""
    q = "SELECT o.id, c.name FROM orders o JOIN customers c ON o.customer_id = c.id"
    anl = analyze_query(q)
    recs = generate_optimizations(q, anl)
    join_recs = [r for r in recs if "JOIN" in r["title"].upper()]
    assert len(join_recs) >= 1


def test_opt_rec_limit():
    """OPT-REC-LIMIT: Generates recommendation to add LIMIT to cap result set size."""
    q = "SELECT id, name FROM orders"
    anl = analyze_query(q)
    recs = generate_optimizations(q, anl)
    limit_recs = [r for r in recs if "LIMIT" in r["title"].upper()]
    assert len(limit_recs) >= 1


def test_opt_rec_wildcard():
    """OPT-REC-WILDCARD: Generates recommendation to avoid leading wildcards in LIKE."""
    q = "SELECT id FROM users WHERE email LIKE '%@gmail.com'"
    anl = analyze_query(q)
    recs = generate_optimizations(q, anl)
    wild_recs = [r for r in recs if "wildcard" in r["title"].lower() or "like" in r["title"].lower()]
    assert len(wild_recs) >= 1


def test_opt_rec_func():
    """OPT-REC-FUNC: Generates recommendation to remove function from WHERE column reference."""
    q = "SELECT id FROM users WHERE UPPER(email) = 'A@B.COM'"
    anl = analyze_query(q)
    recs = generate_optimizations(q, anl)
    func_recs = [r for r in recs if "function" in r["title"].lower()]
    assert len(func_recs) >= 1


def test_opt_insight_gen():
    """OPT-INSIGHT-GEN: Generates deterministic natural-language rule insight paragraph."""
    q = "SELECT * FROM orders WHERE customer_id = 10"
    anl = analyze_query(q)
    score_res = compute_score(anl)
    insight = generate_rule_insight(q, anl, score_res.total)
    assert isinstance(insight, str)
    assert "score" in insight.lower() or "performance" in insight.lower()
    assert "query" in insight.lower()
