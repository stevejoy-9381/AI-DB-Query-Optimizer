"""
analyzer.py
Query pattern detection and analysis engine.
Detects inefficient SQL patterns like SELECT *, missing WHERE clauses,
unindexed JOINs, nested subqueries, and oversized result sets.
"""

import re
import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Where
from sqlparse.tokens import Keyword, DML


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(query: str) -> str:
    """Return upper-cased, whitespace-collapsed version of query."""
    return re.sub(r"\s+", " ", query.strip().upper())


def _extract_tables(parsed) -> list[str]:
    """Extract table names referenced in the parsed SQL statement."""
    tables = []
    from_seen = False
    for token in parsed.flatten():
        if token.ttype is Keyword and token.value.upper() in ("FROM", "JOIN", "INNER JOIN",
                                                               "LEFT JOIN", "RIGHT JOIN",
                                                               "FULL JOIN", "CROSS JOIN"):
            from_seen = True
        elif from_seen:
            if token.ttype is not None and token.ttype not in (Keyword,):
                # skip keywords; grab identifiers
                pass
            if str(token.ttype) == "Token.Name":
                tables.append(token.value)
                from_seen = False
    return tables


def _count_joins(query_upper: str) -> int:
    """Count JOIN occurrences in the query."""
    pattern = r"\b(JOIN|INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+JOIN|CROSS\s+JOIN)\b"
    return len(re.findall(pattern, query_upper))


def _count_subqueries(query_upper: str) -> int:
    """Count nested SELECT statements (subqueries / CTEs)."""
    selects = re.findall(r"\bSELECT\b", query_upper)
    return max(0, len(selects) - 1)


def _has_select_star(query_upper: str) -> bool:
    return bool(re.search(r"\bSELECT\s+\*", query_upper))


def _has_where_clause(query_upper: str) -> bool:
    return bool(re.search(r"\bWHERE\b", query_upper))


def _has_limit(query_upper: str) -> bool:
    return bool(re.search(r"\b(LIMIT|ROWNUM|FETCH\s+FIRST|TOP\s+\d+)\b", query_upper))


def _has_aggregation(query_upper: str) -> bool:
    return bool(re.search(r"\b(COUNT|SUM|AVG|MAX|MIN)\s*\(", query_upper))


def _has_group_by(query_upper: str) -> bool:
    return bool(re.search(r"\bGROUP\s+BY\b", query_upper))


def _has_order_by(query_upper: str) -> bool:
    return bool(re.search(r"\bORDER\s+BY\b", query_upper))


def _has_distinct(query_upper: str) -> bool:
    return bool(re.search(r"\bSELECT\s+DISTINCT\b", query_upper))


def _has_wildcard_like(query_upper: str) -> bool:
    """Detect leading-wildcard LIKE patterns that prevent index use."""
    return bool(re.search(r"LIKE\s+['\"]%", query_upper))


def _has_function_on_column(query_upper: str) -> bool:
    """Detect functions applied to columns in WHERE (prevents index use)."""
    pattern = r"\bWHERE\b.*\b(UPPER|LOWER|YEAR|MONTH|DAY|DATE|TO_CHAR|CAST|CONVERT)\s*\("
    return bool(re.search(pattern, query_upper, re.DOTALL))


def _extract_filter_columns(query: str) -> list[str]:
    """Attempt to extract column names used in WHERE / ON conditions."""
    cols = []
    where_match = re.search(r"\bWHERE\b(.+?)(?:\bGROUP\b|\bORDER\b|\bHAVING\b|\bLIMIT\b|$)",
                             query, re.IGNORECASE | re.DOTALL)
    on_matches = re.finditer(r"\bON\b\s+([\w.]+)\s*=\s*([\w.]+)", query, re.IGNORECASE)

    if where_match:
        clause = where_match.group(1)
        col_matches = re.findall(r"([\w]+)\s*(?:=|>|<|>=|<=|!=|LIKE|IN|BETWEEN)", clause, re.IGNORECASE)
        cols.extend(col_matches)

    for m in on_matches:
        for grp in (m.group(1), m.group(2)):
            part = grp.split(".")[-1]
            cols.append(part)

    return list(set(c.lower() for c in cols if c.lower() not in
                    ("and", "or", "not", "null", "true", "false", "is")))


def _detect_query_type(query_upper: str) -> str:
    if query_upper.strip().startswith("SELECT"):
        return "SELECT"
    elif query_upper.strip().startswith("INSERT"):
        return "INSERT"
    elif query_upper.strip().startswith("UPDATE"):
        return "UPDATE"
    elif query_upper.strip().startswith("DELETE"):
        return "DELETE"
    elif query_upper.strip().startswith("WITH"):
        return "CTE/WITH"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_query(query: str) -> dict:
    """
    Analyze a SQL query and return a structured report.

    Returns
    -------
    dict with keys:
        query_type, issues, warnings, filter_columns,
        join_count, subquery_count, has_aggregation,
        has_group_by, has_order_by, has_limit, has_distinct,
        is_complex
    """
    q = _normalize(query)
    issues = []
    warnings = []

    query_type = _detect_query_type(q)
    join_count = _count_joins(q)
    subquery_count = _count_subqueries(q)
    agg = _has_aggregation(q)
    grp = _has_group_by(q)
    order = _has_order_by(q)
    limit = _has_limit(q)
    distinct = _has_distinct(q)
    filter_cols = _extract_filter_columns(query)

    # ---- Issue detection ----
    if _has_select_star(q):
        issues.append({
            "code": "SELECT_STAR",
            "severity": "HIGH",
            "message": "SELECT * fetches all columns — specify only the columns you need.",
        })

    if not _has_where_clause(q) and query_type == "SELECT":
        issues.append({
            "code": "MISSING_WHERE",
            "severity": "HIGH",
            "message": "No WHERE clause detected — query may perform a full table scan.",
        })

    if join_count > 0:
        issues.append({
            "code": "JOIN_DETECTED",
            "severity": "MEDIUM",
            "message": f"{join_count} JOIN(s) detected — ensure join columns are indexed.",
        })

    if join_count > 2:
        issues.append({
            "code": "EXCESSIVE_JOINS",
            "severity": "HIGH",
            "message": f"{join_count} JOINs may degrade performance significantly.",
        })

    if subquery_count > 0:
        issues.append({
            "code": "SUBQUERY_DETECTED",
            "severity": "MEDIUM",
            "message": (
                f"{subquery_count} nested subquery(ies) detected — "
                "consider rewriting with JOINs or CTEs."
            ),
        })

    if not limit and not _has_where_clause(q) and query_type == "SELECT":
        issues.append({
            "code": "MISSING_LIMIT",
            "severity": "MEDIUM",
            "message": "No LIMIT clause — large result sets may cause memory pressure.",
        })

    if _has_wildcard_like(q):
        warnings.append({
            "code": "LEADING_WILDCARD",
            "severity": "MEDIUM",
            "message": "Leading wildcard in LIKE (e.g. '%value') prevents index use.",
        })

    if _has_function_on_column(q):
        warnings.append({
            "code": "FUNCTION_ON_COLUMN",
            "severity": "MEDIUM",
            "message": "Function applied to a column in WHERE — index on that column cannot be used.",
        })

    if distinct and join_count > 0:
        warnings.append({
            "code": "DISTINCT_WITH_JOIN",
            "severity": "LOW",
            "message": "SELECT DISTINCT with JOINs may be masking duplicate-row bugs. Review the JOIN logic.",
        })

    if agg and not grp and not _has_where_clause(q):
        warnings.append({
            "code": "AGGREGATE_FULL_SCAN",
            "severity": "MEDIUM",
            "message": "Aggregate function with no GROUP BY or WHERE — full scan required."
        })

    # ---- Complexity ----
    if subquery_count > 0 or join_count > 2:
        complexity = "Complex"
    elif join_count > 0 or _has_where_clause(q) or agg:
        complexity = "Moderate"
    else:
        complexity = "Simple"

    return {
        "query_type": query_type,
        "complexity": complexity,
        "issues": issues,
        "warnings": warnings,
        "filter_columns": filter_cols,
        "join_count": join_count,
        "subquery_count": subquery_count,
        "has_aggregation": agg,
        "has_group_by": grp,
        "has_order_by": order,
        "has_limit": limit,
        "has_distinct": distinct,
        "select_star": _has_select_star(q),
        "has_where": _has_where_clause(q),
    }
