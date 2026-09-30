"""
tests/test_plan_and_simulator.py
Unit tests for execution plan tree generator, plan flattening,
and index impact simulation.
"""

from __future__ import annotations

from analyzer import analyze_query
from execution_plan import (
    PlanNode,
    flatten_plan,
    generate_execution_plan,
    get_all_nodes,
    plan_summary,
)
from scoring import compute_score
from simulator import impact_color, simulate_index_impact


def test_execution_plan_generation_and_traversal():
    """Verify execution plan tree is constructed with proper nodes and summary."""
    query = "SELECT id, name FROM users WHERE email = 'test@example.com' ORDER BY id LIMIT 10;"
    analysis = analyze_query(query)
    plan = generate_execution_plan(query, analysis)

    assert isinstance(plan, PlanNode)
    assert plan.node_type != ""

    all_nodes = get_all_nodes(plan)
    assert len(all_nodes) >= 1

    flat = flatten_plan(plan)
    assert len(flat) == len(all_nodes)
    assert "Access Type" in flat[0]
    assert "Est. Cost" in flat[0]

    summary = plan_summary(plan)
    assert "cost_category" in summary
    assert "total_nodes" in summary
    assert summary["total_nodes"] == len(all_nodes)


def test_index_impact_simulator():
    """Verify index impact simulation calculates speedup, before/after score, and rows reduced."""
    query = "SELECT * FROM orders WHERE customer_id = 42;"
    analysis = analyze_query(query)
    score_res = compute_score(analysis)

    impact = simulate_index_impact(query, analysis, score_res)

    assert "before_score" in impact
    assert "after_score" in impact
    assert impact["after_score"] >= impact["before_score"]
    assert "score_improvement" in impact
    assert "speedup_label" in impact
    assert "rows_reduction_pct" in impact
    assert "impact_level" in impact

    col = impact_color(impact["impact_level"])
    assert col.startswith("#")
