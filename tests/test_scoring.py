"""tests/test_scoring.py
Unit and regression tests for the query performance scoring engine.
Verifies score boundaries [0, 100], exact breakdown delta sums,
schema-aware table multipliers, indexed-filter bonuses, and
100% offline regression consistency across every sample query.
"""

import csv
import pytest
from pathlib import Path

from analyzer import analyze_query
from scoring import compute_score, simulate_optimized_score
from scoring_rules import get_table_size_multiplier
from db.schema import SchemaInfo, TableInfo, ColumnInfo, IndexInfo


@pytest.fixture
def tiered_schemas():
    """Returns schemas with small, medium, and large table sizes."""
    cols = [ColumnInfo("id", "int", False, "PRI", None), ColumnInfo("status", "varchar(20)", False, "", None)]
    idx_pk = [IndexInfo("PRIMARY", "orders", ["id"], True, True)]
    idx_status = [
        IndexInfo("PRIMARY", "orders", ["id"], True, True),
        IndexInfo("idx_status", "orders", ["status"], False, False),
    ]

    small_table = TableInfo(
        "orders",
        {c.name.lower(): c for c in cols},
        {i.name.lower(): i for i in idx_pk},
        estimated_rows=5_000,
    )
    med_table = TableInfo(
        "orders",
        {c.name.lower(): c for c in cols},
        {i.name.lower(): i for i in idx_pk},
        estimated_rows=250_000,
    )
    large_table = TableInfo(
        "orders",
        {c.name.lower(): c for c in cols},
        {i.name.lower(): i for i in idx_pk},
        estimated_rows=5_000_000,
    )
    indexed_table = TableInfo(
        "orders",
        {c.name.lower(): c for c in cols},
        {i.name.lower(): i for i in idx_status},
        estimated_rows=500_000,
    )

    return {
        "small": SchemaInfo("shop_db", {"orders": small_table}),
        "medium": SchemaInfo("shop_db", {"orders": med_table}),
        "large": SchemaInfo("shop_db", {"orders": large_table}),
        "indexed": SchemaInfo("shop_db", {"orders": indexed_table}),
    }


def test_table_size_multipliers():
    assert get_table_size_multiplier(None) == 1.0
    assert get_table_size_multiplier(500) == 1.0
    assert get_table_size_multiplier(9_999) == 1.0
    assert get_table_size_multiplier(10_000) == 1.5
    assert get_table_size_multiplier(500_000) == 1.5
    assert get_table_size_multiplier(1_000_000) == 1.5
    assert get_table_size_multiplier(1_000_001) == 2.0
    assert get_table_size_multiplier(10_000_000) == 2.0


def test_breakdown_adds_up_exactly():
    query = "SELECT * FROM orders WHERE status = 'pending';"
    analysis = analyze_query(query)
    score_res = compute_score(analysis)

    total_delta = sum(item["delta"] for item in score_res.breakdown)
    expected_unclipped = 100 + total_delta
    assert score_res.unclipped_score == expected_unclipped
    assert score_res.total == max(0, min(100, expected_unclipped))


def test_score_boundaries():
    # Massive anti-pattern query
    bad_query = "SELECT * FROM orders, customers;"
    bad_analysis = analyze_query(bad_query)
    bad_score = compute_score(bad_analysis)
    assert 0 <= bad_score.total <= 100

    # Highly-optimized query
    good_query = "SELECT id, name FROM customers WHERE id = 10 LIMIT 1;"
    good_analysis = analyze_query(good_query)
    good_score = compute_score(good_analysis)
    assert 0 <= good_score.total <= 100
    assert good_score.total >= 80


def test_schema_aware_penalties_scale_with_table_size(tiered_schemas):
    # Query with missing WHERE (base penalty -20)
    query = "SELECT id FROM orders;"
    analysis = analyze_query(query)

    score_small = compute_score(analysis, schema=tiered_schemas["small"])
    score_med = compute_score(analysis, schema=tiered_schemas["medium"])
    score_large = compute_score(analysis, schema=tiered_schemas["large"])

    delta_small = next(b["delta"] for b in score_small.breakdown if b["code"] == "MISSING_WHERE")
    delta_med = next(b["delta"] for b in score_med.breakdown if b["code"] == "MISSING_WHERE")
    delta_large = next(b["delta"] for b in score_large.breakdown if b["code"] == "MISSING_WHERE")

    # Base is -20
    # small (1.0x) -> -20
    # med (1.5x) -> -30
    # large (2.0x) -> -40
    assert delta_small == -20
    assert delta_med == -30
    assert delta_large == -40
    assert score_small.total > score_med.total > score_large.total


def test_schema_aware_indexed_filter_bonus(tiered_schemas):
    query = "SELECT id FROM orders WHERE status = 'shipped';"
    analysis = analyze_query(query)

    # In medium schema, status is not indexed
    score_unindexed = compute_score(analysis, schema=tiered_schemas["medium"])
    assert not any(b["code"] == "INDEXED_FILTER_COLUMN" for b in score_unindexed.breakdown)

    # In indexed schema, status is indexed -> bonus awarded
    score_indexed = compute_score(analysis, schema=tiered_schemas["indexed"])
    assert any(b["code"] == "INDEXED_FILTER_COLUMN" for b in score_indexed.breakdown)


def test_rows_scanned_estimate_labels(tiered_schemas):
    query = "SELECT * FROM orders;"
    analysis = analyze_query(query)

    # Offline mode: rough estimate
    offline_score = compute_score(analysis, schema=None)
    assert "rough estimate" in offline_score.rows_scanned_estimate

    # Schema mode: computed from stats
    schema_score = compute_score(analysis, schema=tiered_schemas["large"])
    assert "computed from table stats" in schema_score.rows_scanned_estimate


def test_offline_regression_across_all_sample_queries():
    """Verify that every query in data/sample_queries.csv scores consistently in [0, 100]

    and breakdown sums match unclipped score exactly.
    """
    csv_path = Path("data/sample_queries.csv")
    assert csv_path.exists(), "Sample queries file missing"

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            q = row.get("query", "").strip()
            if not q:
                continue
            count += 1
            analysis = analyze_query(q)
            score_res = compute_score(analysis, schema=None)

            # Assert score in bounds
            assert 0 <= score_res.total <= 100, f"Score out of bounds for query: {q}"

            # Assert breakdown delta consistency
            total_delta = sum(b["delta"] for b in score_res.breakdown)
            assert score_res.unclipped_score == 100 + total_delta
            assert score_res.total == max(0, min(100, score_res.unclipped_score))

            # Simulate optimized score
            sim = simulate_optimized_score(analysis)
            assert 0 <= sim <= 100

        assert count >= 100, f"Expected at least 100 sample queries, found {count}"
