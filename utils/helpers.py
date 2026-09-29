"""
utils/helpers.py
Shared utility functions for the SQL Query Optimization Engine.
"""

from __future__ import annotations
import json
import csv
import io
import datetime
import sqlparse


def format_sql(query: str) -> str:
    """Return a pretty-printed version of the SQL query."""
    try:
        return sqlparse.format(
            query,
            reindent=True,
            keyword_case="upper",
            identifier_case="lower",
            strip_comments=False,
            indent_width=4,
        )
    except Exception:
        return query


def severity_badge(severity: str) -> str:
    """Return an emoji badge for a severity level."""
    return {
        "HIGH":   "🔴 HIGH",
        "MEDIUM": "🟡 MEDIUM",
        "LOW":    "🟢 LOW",
    }.get(severity.upper(), severity)


def priority_badge(priority: str) -> str:
    """Return an emoji badge for a priority level."""
    return {
        "HIGH":   "🔴 HIGH",
        "MEDIUM": "🟡 MEDIUM",
        "LOW":    "🟢 LOW",
    }.get(priority.upper(), priority)


def score_color(score: int) -> str:
    """Return a hex color string for a score value."""
    if score >= 80:
        return "#2ecc71"   # green
    elif score >= 50:
        return "#f39c12"   # orange
    return "#e74c3c"       # red


def cost_color(cost: str) -> str:
    """Return a hex color for a cost estimate string."""
    return {
        "LOW":    "#2ecc71",
        "MEDIUM": "#f39c12",
        "HIGH":   "#e74c3c",
    }.get(cost.upper(), "#95a5a6")


def complexity_color(complexity: str) -> str:
    return {
        "Simple":   "#2ecc71",
        "Moderate": "#f39c12",
        "Complex":  "#e74c3c",
    }.get(complexity, "#95a5a6")


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def build_json_report(
    query: str,
    analysis: dict,
    score_result,
    optimizations: list[dict],
    index_recs: list[dict],
    optimized_score: int,
) -> str:
    """Serialize a full analysis report to a JSON string."""
    report = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "query": query,
        "analysis": {
            "query_type": analysis["query_type"],
            "complexity": analysis["complexity"],
            "issues": analysis["issues"],
            "warnings": analysis["warnings"],
            "filter_columns": analysis["filter_columns"],
            "join_count": analysis["join_count"],
            "subquery_count": analysis["subquery_count"],
        },
        "score": {
            "original": score_result.total,
            "optimized_estimate": optimized_score,
            "improvement": optimized_score - score_result.total,
            "cost_estimate": score_result.cost_estimate,
            "rows_scanned_estimate": score_result.rows_scanned_estimate,
            "breakdown": score_result.breakdown,
        },
        "optimizations": optimizations,
        "index_recommendations": index_recs,
    }
    return json.dumps(report, indent=2)


def build_csv_report(
    query: str,
    analysis: dict,
    score_result,
    optimized_score: int,
) -> str:
    """Serialize a summary analysis report to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Field", "Value"])
    writer.writerow(["Query", query.replace("\n", " ")])
    writer.writerow(["Query Type", analysis["query_type"]])
    writer.writerow(["Complexity", analysis["complexity"]])
    writer.writerow(["Score (Original)", score_result.total])
    writer.writerow(["Score (Optimized Estimate)", optimized_score])
    writer.writerow(["Improvement", optimized_score - score_result.total])
    writer.writerow(["Cost Estimate", score_result.cost_estimate])
    writer.writerow(["Rows Scanned Estimate", score_result.rows_scanned_estimate])
    writer.writerow(["Issues Count", len(analysis["issues"])])
    writer.writerow(["Warnings Count", len(analysis["warnings"])])
    for i, issue in enumerate(analysis["issues"], 1):
        writer.writerow([f"Issue {i}", f"[{issue['severity']}] {issue['message']}"])
    for i, warn in enumerate(analysis["warnings"], 1):
        writer.writerow([f"Warning {i}", f"[{warn['severity']}] {warn['message']}"])
    return output.getvalue()


def build_text_report(
    query: str,
    analysis: dict,
    score_result,
    optimizations: list[dict],
    index_recs: list[dict],
    optimized_score: int,
    ai_insight: str,
) -> str:
    """Serialize a human-readable text report."""
    sep = "=" * 70
    thin = "-" * 70
    lines: list[str] = [
        sep,
        "  AI-POWERED SQL QUERY OPTIMIZATION REPORT",
        f"  Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        sep,
        "",
        "QUERY",
        thin,
        query.strip(),
        "",
        "SUMMARY",
        thin,
        f"  Query Type  : {analysis['query_type']}",
        f"  Complexity  : {analysis['complexity']}",
        f"  Score       : {score_result.total} / 100",
        f"  Cost        : {score_result.cost_estimate}",
        f"  Rows Scan   : {score_result.rows_scanned_estimate}",
        "",
        "AI INSIGHT",
        thin,
        # Strip markdown bold markers for plain text
        ai_insight.replace("**", ""),
        "",
    ]

    if analysis["issues"]:
        lines += ["ISSUES DETECTED", thin]
        for iss in analysis["issues"]:
            lines.append(f"  [{iss['severity']}] {iss['message']}")
        lines.append("")

    if analysis["warnings"]:
        lines += ["WARNINGS", thin]
        for w in analysis["warnings"]:
            lines.append(f"  [{w['severity']}] {w['message']}")
        lines.append("")

    if optimizations:
        lines += ["OPTIMIZATION RECOMMENDATIONS", thin]
        for i, opt in enumerate(optimizations, 1):
            lines.append(f"  {i}. [{opt['priority']}] {opt['title']}")
            lines.append(f"     {opt['description']}")
            lines.append(f"     Example:\n{opt['example']}")
            lines.append("")

    if index_recs:
        lines += ["INDEX RECOMMENDATIONS", thin]
        for rec in index_recs:
            lines.append(f"  {rec['index_name']}")
            lines.append(f"  {rec['ddl']}")
            lines.append(f"  Benefit: {rec['estimated_improvement']}")
            lines.append("")

    lines += [
        "OPTIMIZATION SIMULATION",
        thin,
        f"  Original Score  : {score_result.total} / 100",
        f"  Optimized Score : {optimized_score} / 100",
        f"  Improvement     : +{optimized_score - score_result.total}",
        "",
        sep,
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# History helper
# ---------------------------------------------------------------------------

def history_record(query: str, analysis: dict, score: int) -> dict:
    """Build a dict suitable for storing in the session history list."""
    return {
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
        "query_snippet": (query.strip().replace("\n", " ")[:80] + "…")
                         if len(query.strip()) > 80 else query.strip().replace("\n", " "),
        "score": score,
        "complexity": analysis.get("complexity", ""),
        "cost": "",   # filled in by caller
        "issues": len(analysis.get("issues", [])),
    }
