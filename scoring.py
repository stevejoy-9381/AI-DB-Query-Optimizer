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
    {"code": "CORRELATED_SUBQUERY", "delta": -15, "label": "Correlated subquery in SELECT/WHERE"},
    {"code": "OR_DIFFERENT_COLUMNS", "delta": -10, "label": "OR across different columns"},
    {"code": "IMPLICIT_TYPE_CONVERSION", "delta": -15, "label": "Implicit type conversion on column"},
    {"code": "NOT_IN_SUBQUERY", "delta": -15, "label": "NOT IN with subquery (NULL trap)"},
    {"code": "ORDER_BY_RAND", "delta": -20, "label": "ORDER BY RAND() full filesort"},
    {"code": "UNINDEXED_ORDER_BY", "delta": -10, "label": "ORDER BY on unindexed column"},
    {"code": "LARGE_OFFSET", "delta": -10, "label": "Deep OFFSET pagination scan"},
    {"code": "MISSING_JOIN_CONDITION", "delta": -25, "label": "Missing JOIN condition (Cartesian product)"},
    {"code": "NON_SARGABLE_ARITHMETIC", "delta": -10, "label": "Non-sargable arithmetic on column"},
    {"code": "HAVING_AS_WHERE", "delta": -5, "label": "HAVING filtering non-aggregate column"},
    {"code": "COUNT_DISTINCT", "delta": -5,  "label": "COUNT(DISTINCT) / column mismatch"},
    {"code": "UNION_INSTEAD_OF_UNION_ALL", "delta": -10, "label": "UNION instead of UNION ALL"},
    {"code": "UPDATE_WITHOUT_WHERE", "delta": -50, "label": "UPDATE without WHERE clause (Critical)"},
    {"code": "DELETE_WITHOUT_WHERE", "delta": -50, "label": "DELETE without WHERE clause (Critical)"},
    {"code": "UPDATE_DELETE_UNINDEXED_WHERE", "delta": -20, "label": "Unindexed WHERE filter (Lock escalation)"},
    {"code": "INSERT_SINGLE_ROW", "delta": -5, "label": "Single-row INSERT (Prefer bulk)"},
    {"code": "INSERT_SELECT_UNBOUNDED", "delta": -20, "label": "Unbounded INSERT...SELECT (Massive write)"},
    {"code": "CTE_MULTIPLY_REFERENCED", "delta": -10, "label": "CTE evaluated multiple times"},
    {"code": "WINDOW_WITHOUT_PARTITION", "delta": -10, "label": "Window function without PARTITION BY"},
    # Bonuses
    {"code": "HAS_WHERE",         "delta": +10, "label": "WHERE clause present"},
    {"code": "HAS_LIMIT",         "delta": +10, "label": "LIMIT clause present"},
    {"code": "HAS_GROUP_BY",      "delta": +5,  "label": "GROUP BY used"},
    {"code": "HAS_ORDER_BY",      "delta": +5,  "label": "ORDER BY used"},
    {"code": "SPECIFIC_COLUMNS",  "delta": +10, "label": "Specific columns selected"},
    {"code": "HAS_FILTER_COLS",   "delta": +5,  "label": "Filterable columns identified"},
    {"code": "BULK_INSERT",       "delta": +15, "label": "Bulk multi-row INSERT"},
]

# Statement-specific rule overrides for focused scoring
STATEMENT_RULES: dict[str, list[dict]] = {
    "UPDATE": [
        {"code": "UPDATE_WITHOUT_WHERE", "delta": -50, "label": "UPDATE without WHERE (Critical)"},
        {"code": "UPDATE_DELETE_UNINDEXED_WHERE", "delta": -20, "label": "Unindexed WHERE (Lock contention risk)"},
        {"code": "NON_SARGABLE_ARITHMETIC", "delta": -10, "label": "Non-sargable arithmetic in WHERE"},
        {"code": "FUNCTION_ON_COLUMN", "delta": -10, "label": "Function on WHERE column"},
        {"code": "HAS_WHERE", "delta": +15, "label": "Specific row filter present"},
        {"code": "HAS_LIMIT", "delta": +5, "label": "LIMIT clause caps row updates"},
    ],
    "DELETE": [
        {"code": "DELETE_WITHOUT_WHERE", "delta": -50, "label": "DELETE without WHERE (Critical)"},
        {"code": "UPDATE_DELETE_UNINDEXED_WHERE", "delta": -20, "label": "Unindexed WHERE (Lock contention risk)"},
        {"code": "NON_SARGABLE_ARITHMETIC", "delta": -10, "label": "Non-sargable arithmetic in WHERE"},
        {"code": "FUNCTION_ON_COLUMN", "delta": -10, "label": "Function on WHERE column"},
        {"code": "HAS_WHERE", "delta": +15, "label": "Specific row filter present"},
        {"code": "HAS_LIMIT", "delta": +5, "label": "LIMIT clause caps deletions"},
    ],
    "INSERT": [
        {"code": "INSERT_SELECT_UNBOUNDED", "delta": -25, "label": "Unbounded INSERT...SELECT transaction"},
        {"code": "INSERT_SINGLE_ROW", "delta": -10, "label": "Single-row INSERT loop overhead"},
        {"code": "BULK_INSERT", "delta": +15, "label": "Multi-row batch INSERT"},
        {"code": "HAS_WHERE", "delta": +10, "label": "Bounded source query filter"},
    ],
    "INSERT...SELECT": [
        {"code": "INSERT_SELECT_UNBOUNDED", "delta": -25, "label": "Unbounded INSERT...SELECT transaction"},
        {"code": "SELECT_STAR", "delta": -15, "label": "SELECT * in INSERT source"},
        {"code": "HAS_WHERE", "delta": +15, "label": "Source table filtered with WHERE"},
        {"code": "HAS_LIMIT", "delta": +10, "label": "LIMIT caps transaction batch size"},
    ],
}

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
    table_row_counts: dict[str, int] = field(default_factory=dict)


def compute_score(analysis: dict, schema: Any | None = None) -> ScoreBreakdown:
    """
    Compute a performance score from an analysis dict (produced by analyzer.analyze_query).

    Parameters
    ----------
    analysis : dict  — output of analyzer.analyze_query()
    schema   : SchemaInfo | None — optional schema metadata for row-count and cardinality adjustments

    Returns
    -------
    ScoreBreakdown
    """
    issue_codes   = {i["code"] for i in analysis.get("issues",   [])}
    warning_codes = {w["code"] for w in analysis.get("warnings", [])}
    all_codes = issue_codes | warning_codes
    stmt_type = analysis.get("statement_type", "SELECT").upper()

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
    if not analysis.get("select_star") and stmt_type in ("SELECT", "CTE", "UNION"):
        positive_flags.add("SPECIFIC_COLUMNS")
    if analysis.get("filter_columns"):
        positive_flags.add("HAS_FILTER_COLS")
    if analysis.get("insert_row_count", 0) and analysis.get("insert_row_count", 0) > 1:
        positive_flags.add("BULK_INSERT")

    score = 100
    applied: list[dict] = []

    # Choose statement-specific rules or fallback to full rules
    rules_to_use = STATEMENT_RULES.get(stmt_type, SCORE_RULES)

    for rule in rules_to_use:
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

    row_counts = {}
    if schema is not None and hasattr(schema, "tables"):
        row_counts = {t.name: t.estimated_rows for t in schema.tables.values()}

    return ScoreBreakdown(
        total=score,
        breakdown=applied,
        cost_estimate=cost,
        rows_scanned_estimate=rows,
        table_row_counts=row_counts,
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
