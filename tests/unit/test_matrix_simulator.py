"""tests/unit/test_matrix_simulator.py
Automated Unit Tests for all Simulator behaviors defined in docs/TEST_MATRIX.md.
"""

from analyzer import analyze_query
from scoring import compute_score
from simulator import simulate_index_impact


def test_sim_metrics_calc():
    """SIM-METRICS-CALC: Calculates projected improvements in score, cost, rows, and time."""
    q = "SELECT * FROM orders WHERE customer_id = 10"
    anl = analyze_query(q)
    score_res = compute_score(anl)
    sim = simulate_index_impact(q, anl, score_res)
    assert sim["after_score"] >= sim["before_score"]
    assert sim["after_rows"] <= sim["before_rows"]
    assert sim["before_time_ms"] > 0
    assert sim["after_time_ms"] > 0


def test_sim_speedup_factor():
    """SIM-SPEEDUP-FACTOR: Calculates speedup factor as ratio of sequential scan time to indexed seek."""
    q = "SELECT * FROM orders WHERE customer_id = 10"
    anl = analyze_query(q)
    score_res = compute_score(anl)
    sim = simulate_index_impact(q, anl, score_res)
    assert isinstance(sim["speedup_factor"], (int, float))
    assert sim["speedup_factor"] >= 1.0
    assert "faster" in sim["speedup_label"] or "Marginal" in sim["speedup_label"]


def test_sim_where_selectivity():
    """SIM-WHERE-SELECTIVITY: Recognizes missing WHERE clause limits index impact (selectivity 0.8)."""
    q = "SELECT * FROM orders"
    anl = analyze_query(q)
    score_res = compute_score(anl)
    sim = simulate_index_impact(q, anl, score_res)
    # When missing WHERE, rows reduction is modest (e.g. 20%) compared to 99% with WHERE
    assert sim["rows_reduction_pct"] <= 50.0


def test_sim_impact_level():
    """SIM-IMPACT-LEVEL: Classifies impact into Transformative, Major, Moderate, or Minor."""
    q = "SELECT * FROM orders WHERE customer_id = 10"
    anl = analyze_query(q)
    score_res = compute_score(anl)
    sim = simulate_index_impact(q, anl, score_res)
    assert sim["impact_level"] in ("Transformative", "Major", "Moderate", "Minor")
