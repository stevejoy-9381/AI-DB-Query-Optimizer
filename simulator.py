"""
simulator.py
MySQL Index Impact Simulator.

Compares query execution metrics before and after applying index recommendations,
producing estimated performance projections based on heuristic scoring analysis
and typical MySQL InnoDB B-tree traversal characteristics.

All metrics produced by this module are mathematical approximations (labeled as estimated).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Estimated row counts from cost tier
# ---------------------------------------------------------------------------
_ROWS_BY_COST = {
    "HIGH": 1_000_000,
    "MEDIUM": 100_000,
    "LOW": 5_000,
}

# Estimated execution time approximations for MySQL InnoDB:
# Sequential full table scan (ALL): ~2.0 ms per 1K rows (buffer pool / disk read + filter)
# Index-backed seek (ref / range): ~0.05 ms per 1K rows (B-tree lookup + clustered row seek)
_MS_PER_1K_ROWS_SEQ = 2.0  # estimated ms per 1K rows for ALL scan
_MS_PER_1K_ROWS_IDX = 0.05  # estimated ms per 1K rows for index lookup


def _rows_from_estimate(estimate_str: str) -> int:
    """Parse the rows_scanned_estimate string back to an integer."""
    if "1M" in estimate_str or "1,000,000" in estimate_str:
        return 1_000_000
    elif "500K" in estimate_str:
        return 500_000
    elif "100K" in estimate_str:
        return 100_000
    elif "10K" in estimate_str:
        return 10_000
    elif "5K" in estimate_str or "1K" in estimate_str:
        return 5_000
    return 100_000  # default fallback


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def simulate_index_impact(query: str, analysis: dict, score_result) -> dict:
    """
    Simulate query performance before and after applying MySQL index recommendations.

    Parameters
    ----------
    query        : str  — original SQL query
    analysis     : dict — output of analyzer.analyze_query()
    score_result : ScoreBreakdown — output of scoring.compute_score()

    Returns
    -------
    dict with keys:
        before_score, after_score, score_improvement,
        before_cost, after_cost,
        before_rows, after_rows, rows_reduction_pct,
        before_time_ms, after_time_ms,
        speedup_factor, speedup_label,
        indexed_columns, impact_level
    """
    issue_codes = {i["code"] for i in analysis.get("issues", [])}
    warning_codes = {w["code"] for w in analysis.get("warnings", [])}
    all_codes = issue_codes | warning_codes
    filter_cols = analysis.get("filter_columns", [])

    before_score = score_result.total
    before_cost = score_result.cost_estimate
    before_rows = _rows_from_estimate(score_result.rows_scanned_estimate)

    # ---- Score after indexing ----
    score_boost = 0
    if "SELECT_STAR" not in all_codes:
        score_boost += 5
    if filter_cols:
        # Indexing resolves JOIN_DETECTED and adds filtered efficiency
        score_boost += min(len(filter_cols) * 10, 30)
    if "JOIN_DETECTED" in all_codes:
        score_boost += 10
    if "EXCESSIVE_JOINS" in all_codes:
        score_boost += 5  # partial relief from indexing alone

    after_score = min(100, before_score + score_boost)

    # ---- Rows after indexing (estimated selectivity) ----
    if "MISSING_WHERE" in all_codes:
        # Index alone cannot fix a missing WHERE clause
        selectivity = 0.8
    elif filter_cols:
        # Selective equality or range predicate on indexed column: ~1% selectivity
        selectivity = 0.01
    else:
        selectivity = 0.1

    after_rows = max(1, int(before_rows * selectivity))

    # ---- Estimated execution time (approximations) ----
    before_time_ms = (before_rows / 1000) * _MS_PER_1K_ROWS_SEQ
    after_time_ms = (after_rows / 1000) * _MS_PER_1K_ROWS_IDX

    # ---- Speedup factor ----
    speedup_factor = before_time_ms / max(after_time_ms, 0.001)
    speedup_factor = round(speedup_factor, 1)

    before_time_ms = round(before_time_ms, 1)
    after_time_ms = round(max(after_time_ms, 0.1), 1)

    # ---- Cost tier after indexing ----
    if after_score >= 80:
        after_cost = "LOW"
    elif after_score >= 50:
        after_cost = "MEDIUM"
    else:
        after_cost = "HIGH"

    # ---- Rows reduction % ----
    rows_reduction_pct = round((1 - after_rows / before_rows) * 100, 1)

    # ---- Impact classification ----
    if speedup_factor >= 50:
        impact_level = "Transformative"
        speedup_label = f"~{speedup_factor}× faster (est.)"
    elif speedup_factor >= 10:
        impact_level = "Major"
        speedup_label = f"~{speedup_factor}× faster (est.)"
    elif speedup_factor >= 2:
        impact_level = "Moderate"
        speedup_label = f"~{speedup_factor}× faster (est.)"
    else:
        impact_level = "Minor"
        speedup_label = "Marginal improvement (est.)"

    indexed_columns = filter_cols[:4]

    return {
        "before_score": before_score,
        "after_score": after_score,
        "score_improvement": after_score - before_score,
        "before_cost": before_cost,
        "after_cost": after_cost,
        "before_rows": before_rows,
        "after_rows": after_rows,
        "rows_reduction_pct": rows_reduction_pct,
        "before_time_ms": before_time_ms,
        "after_time_ms": after_time_ms,
        "speedup_factor": speedup_factor,
        "speedup_label": speedup_label,
        "indexed_columns": indexed_columns,
        "impact_level": impact_level,
    }


def impact_color(impact_level: str) -> str:
    """Color code mapping for UI cards."""
    return {
        "Transformative": "#2ecc71",
        "Major": "#27ae60",
        "Moderate": "#f39c12",
        "Minor": "#95a5a6",
    }.get(impact_level, "#95a5a6")
