"""
tests/test_data_driven.py
Data-driven test suite verifying that all pre-built queries in data/sample_queries.csv
run cleanly through the entire analysis and optimization pipeline.
"""

from __future__ import annotations

import csv
import os

import pytest

from analyzer import analyze_query
from optimizer import generate_optimizations, generate_rule_insight
from recommendations import generate_index_recommendations
from rewrite_engine import rewrite_query
from scoring import compute_score, simulate_optimized_score


def load_all_sample_queries() -> list[dict[str, str]]:
    """Load all rows from sample_queries.csv."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "sample_queries.csv")
    rows = []
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


@pytest.mark.parametrize(
    "row",
    load_all_sample_queries(),
    ids=[f"{r['category']}_{i}" for i, r in enumerate(load_all_sample_queries())],
)
def test_sample_query_pipeline_never_crashes(row: dict[str, str], sample_schema):
    """Verify each sample query completes the entire pipeline without crashing and score is 0-100."""
    sql = row["query"]
    analysis = analyze_query(sql, schema=sample_schema)
    assert analysis["is_valid"] is True

    score_res = compute_score(analysis, schema=sample_schema)
    assert 0 <= score_res.total <= 100

    opt_score = simulate_optimized_score(analysis)
    assert 0 <= opt_score <= 100
    assert opt_score >= score_res.total

    opts = generate_optimizations(sql, analysis)
    assert isinstance(opts, list)

    recs = generate_index_recommendations(sql, analysis, schema=sample_schema)
    assert isinstance(recs, list)

    rw = rewrite_query(sql, analysis)
    assert "rewritten" in rw
    assert "is_changed" in rw

    insight = generate_rule_insight(sql, analysis, score_res.total)
    assert isinstance(insight, str)
    assert len(insight) > 0


def test_good_queries_score_higher_than_antipattern_queries(sample_schema):
    """Assert that 'Good' queries score significantly higher on average than 'Anti-pattern' queries."""
    rows = load_all_sample_queries()
    good_scores = []
    antipattern_scores = []

    for r in rows:
        analysis = analyze_query(r["query"], schema=sample_schema)
        score_res = compute_score(analysis, schema=sample_schema)
        if r["category"].lower() == "good":
            good_scores.append(score_res.total)
        elif r["category"].lower() == "anti-pattern":
            antipattern_scores.append(score_res.total)

    assert len(good_scores) > 0
    assert len(antipattern_scores) > 0

    avg_good = sum(good_scores) / len(good_scores)
    avg_anti = sum(antipattern_scores) / len(antipattern_scores)

    # Average Good score should exceed average Anti-pattern score
    assert avg_good > avg_anti
    assert avg_good - avg_anti >= 20, (
        f"Avg Good ({avg_good:.1f}) should be higher than Anti ({avg_anti:.1f})"
    )
