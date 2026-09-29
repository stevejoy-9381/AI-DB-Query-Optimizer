"""
scoring.py
Query Performance Scoring Engine.

Assigns a 0–100 score to a SQL query based on its analysis report.
Higher is better.
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Score rules
# ---------------------------------------------------------------------------

SCORE_RULES: list[dict] = [
    # Penalties
    {"code": "SELECT_STAR",       "delta": -25, "label": "SELECT * usage"},
    {"code": "MISSING_WHERE",     "delta": -20, "label": "Missing WHERE clause"},
    {"code": "EXCESSIVE_JOINS",   "delta": -15, "label": "Excessive JOINs (>2)"},
    {"code": "JOIN_DETECTED",     "delta": -10, "label": "JOIN without verified index"},
    {"code": "SUBQUERY_DETECTED", "delta": -10, "label": "Nested subquery"},
    {"code": "MISSING_LIMIT",     "delta": -10, "label": "No LIMIT on large potential result"},
    {"code": "LEADING_WILDCARD",  "delta": -10, "label": "Leading wildcard LIKE"},
    {"code": "FUNCTION_ON_COLUMN","delta": -10, "label": "Function applied on WHERE column"},
    {"code": "DISTINCT_WITH_JOIN","delta": -5,  "label": "SELECT DISTINCT with JOINs"},
    {"code": "AGGREGATE_FULL_SCAN","delta": -10,"label": "Aggregate without filter"},
    # Bonuses
    {"code": "HAS_WHERE",         "delta": +10, "label": "WHERE clause present"},
    {"code": "HAS_LIMIT",         "delta": +10, "label": "LIMIT clause present"},
    {"code": "HAS_GROUP_BY",      "delta": +5,  "label": "GROUP BY used"},
    {"code": "HAS_ORDER_BY",      "delta": +5,  "label": "ORDER BY used"},
    {"code": "SPECIFIC_COLUMNS",  "delta": +10, "label": "Specific columns selected"},
    {"code": "HAS_FILTER_COLS",   "delta": +5,  "label": "Filterable columns identified"},
]

COST_THRESHOLDS = {
    "LOW":    (80, 100),
    "MEDIUM": (50, 79),
    "HIGH":   (0,  49),
}


@dataclass
class ScoreBreakdown:
    total: int
    breakdown: list[dict] = field(default_factory=list)
    cost_estimate: str = "MEDIUM"
    rows_scanned_estimate: str = "Unknown"


def compute_score(analysis: dict) -> ScoreBreakdown:
    """
    Compute a performance score from an analysis dict (produced by analyzer.analyze_query).

    Parameters
    ----------
    analysis : dict  — output of analyzer.analyze_query()

    Returns
    -------
    ScoreBreakdown
    """
    issue_codes  = {i["code"] for i in analysis.get("issues",  [])}
    warning_codes = {w["code"] for w in analysis.get("warnings", [])}
    all_codes = issue_codes | warning_codes

    # Positive signals derived from analysis flags
    positive_flags: set[str] = set()
    if analysis.get("has_where"):
        positive_flags.add("HAS_WHERE")
    if analysis.get("has_limit"):
        positive_flags.add("HAS_LIMIT")
    if analysis.get("has_group_by"):
        positive_flags.add("HAS_GROUP_BY")
    if analysis.get("has_order_by"):
        positive_flags.add("HAS_ORDER_BY")
    if not analysis.get("select_star"):
        positive_flags.add("SPECIFIC_COLUMNS")
    if analysis.get("filter_columns"):
        positive_flags.add("HAS_FILTER_COLS")

    score = 100
    applied: list[dict] = []

    for rule in SCORE_RULES:
        code  = rule["code"]
        delta = rule["delta"]
        label = rule["label"]

        triggered = False
        if delta < 0 and code in all_codes:
            triggered = True
        elif delta > 0 and code in positive_flags:
            triggered = True

        if triggered:
            score += delta
            applied.append({"label": label, "delta": delta, "code": code})

    score = max(0, min(100, score))

    # Cost estimation
    if score >= 80:
        cost = "LOW"
        rows = "~1K–10K rows"
    elif score >= 50:
        cost = "MEDIUM"
        rows = "~10K–500K rows"
    else:
        cost = "HIGH"
        rows = "~1M+ rows"

    return ScoreBreakdown(
        total=score,
        breakdown=applied,
        cost_estimate=cost,
        rows_scanned_estimate=rows,
    )


def simulate_optimized_score(analysis: dict) -> int:
    """
    Return an estimated score for the *optimized* version of the query
    by stripping the most impactful penalizing issues.
    """
    optimized_analysis = dict(analysis)

    # Assume optimization fixes SELECT *, adds WHERE, removes subqueries, adds LIMIT
    optimized_issues = [
        i for i in analysis.get("issues", [])
        if i["code"] not in ("SELECT_STAR", "MISSING_WHERE", "MISSING_LIMIT",
                              "SUBQUERY_DETECTED")
    ]
    optimized_warnings = [
        w for w in analysis.get("warnings", [])
        if w["code"] not in ("LEADING_WILDCARD", "FUNCTION_ON_COLUMN")
    ]
    optimized_analysis["issues"] = optimized_issues
    optimized_analysis["warnings"] = optimized_warnings
    optimized_analysis["select_star"] = False
    optimized_analysis["has_where"] = True
    optimized_analysis["has_limit"] = True

    return compute_score(optimized_analysis).total
