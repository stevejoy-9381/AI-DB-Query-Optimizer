"""scoring.py
Query Performance Scoring Engine for MySQL 8.x.

Assigns an explainable 0–100 score to a SQL query based on its analysis report.
Data-driven configuration loaded from scoring_rules.py.
Supports table-size multipliers and indexed-column bonuses when schema is available,
while maintaining 100% regression compatibility in offline mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from scoring_rules import (
    SCORE_RULES_CATALOG,
    SCORE_RULES_DICT,
    STATEMENT_SCORE_RULES,
    ScoreRuleConfig,
    get_table_size_multiplier,
)

# Export legacy SCORE_RULES list of dicts for backward compatibility
SCORE_RULES: list[dict] = [
    {
        "code": r.code,
        "delta": r.delta,
        "label": r.label,
        "severity": r.severity,
        "explanation": r.explanation,
    }
    for r in SCORE_RULES_CATALOG
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
    table_row_counts: dict[str, int] = field(default_factory=dict)
    unclipped_score: int = 100
    table_multiplier: float = 1.0


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
    stmt_type = analysis.get("statement_type") or analysis.get("query_type", "SELECT")
    stmt_type = stmt_type.upper()

    # Determine table multiplier and row stats when schema is known
    table_multiplier = 1.0
    max_table_rows: Optional[int] = None
    row_counts: dict[str, int] = {}
    has_indexed_filter = False

    if schema is not None and hasattr(schema, "tables"):
        query_tables = analysis.get("tables", [])
        if not query_tables and hasattr(analysis, "get"):
            # Try to get from filter columns or schema tables
            query_tables = list(schema.tables.keys())

        matched_tables = []
        for tbl_name in query_tables:
            clean_name = tbl_name.split(".")[-1].strip("`\"' ").lower()
            t_info = schema.get_table(clean_name)
            if t_info:
                matched_tables.append(t_info)
                row_counts[t_info.name] = t_info.estimated_rows

        if matched_tables:
            max_table_rows = max(t.estimated_rows for t in matched_tables)
            table_multiplier = get_table_size_multiplier(max_table_rows)

            # Check if any filter column has a covering/prefix index
            filter_cols = [c.lower() for c in analysis.get("filter_columns", [])]
            for t_info in matched_tables:
                indexes_iterable = t_info.indexes.values() if isinstance(t_info.indexes, dict) else t_info.indexes
                for idx in indexes_iterable:
                    if idx.columns and idx.columns[0].lower() in filter_cols:
                        has_indexed_filter = True
                        break

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
    if has_indexed_filter:
        positive_flags.add("INDEXED_FILTER_COLUMN")

    # Select rules catalog based on statement type
    rule_configs = STATEMENT_SCORE_RULES.get(stmt_type, SCORE_RULES_CATALOG)

    unclipped_score = 100
    applied: list[dict] = []

    for rule in rule_configs:
        code  = rule.code
        base_delta = rule.delta
        label = rule.label
        explanation = rule.explanation

        triggered = False
        if base_delta < 0 and code in all_codes:
            triggered = True
        elif base_delta > 0 and code in positive_flags:
            triggered = True

        if triggered:
            # Apply multiplier ONLY when schema is present and on negative penalties
            if schema is not None and base_delta < 0:
                final_delta = round(base_delta * table_multiplier)
            else:
                final_delta = base_delta

            unclipped_score += final_delta
            applied.append({
                "code": code,
                "label": label,
                "delta": final_delta,
                "severity": rule.severity,
                "reason": explanation,
            })

    score = max(0, min(100, unclipped_score))

    # Cost category
    if score >= 80:
        cost = "LOW"
    elif score >= 50:
        cost = "MEDIUM"
    else:
        cost = "HIGH"

    # Rows scanned estimate
    if schema is not None and max_table_rows is not None and max_table_rows > 0:
        if score >= 80:
            est_rows = max(1, round(max_table_rows * 0.05))
        elif score >= 50:
            est_rows = max(1, round(max_table_rows * 0.35))
        else:
            est_rows = max_table_rows
        rows_str = f"~{est_rows:,} rows (computed from table stats)"
    else:
        if score >= 80:
            rows_str = "~1K–10K rows (rough estimate)"
        elif score >= 50:
            rows_str = "~10K–500K rows (rough estimate)"
        else:
            rows_str = "~1M+ rows (rough estimate)"

    return ScoreBreakdown(
        total=score,
        breakdown=applied,
        cost_estimate=cost,
        rows_scanned_estimate=rows_str,
        table_row_counts=row_counts,
        unclipped_score=unclipped_score,
        table_multiplier=table_multiplier,
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
                             "SUBQUERY_DETECTED", "UPDATE_WITHOUT_WHERE",
                             "DELETE_WITHOUT_WHERE", "ORDER_BY_RAND")
    ]
    optimized_warnings = [
        w for w in analysis.get("warnings", [])
        if w["code"] not in ("LEADING_WILDCARD", "FUNCTION_ON_COLUMN", "UNION_INSTEAD_OF_UNION_ALL")
    ]
    optimized_analysis["issues"] = optimized_issues
    optimized_analysis["warnings"] = optimized_warnings
    optimized_analysis["select_star"] = False
    optimized_analysis["has_where"] = True
    optimized_analysis["has_limit"] = True

    sim_breakdown = compute_score(optimized_analysis)
    return sim_breakdown.total
