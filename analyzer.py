"""analyzer.py
Query pattern detection and analysis engine using sqlglot AST parsing for MySQL 8.x.
Detects inefficient SQL patterns like SELECT *, missing WHERE clauses,
unindexed JOINs, nested subqueries, and oversized result sets.
Includes graceful regex fallback when AST parsing fails.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Where
from sqlparse.tokens import Keyword, DML

from query_model import QueryFeatures, extract_query_features

if TYPE_CHECKING:
    from db.schema import SchemaInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Legacy Regex Helpers (Preserved for Fallback)
# ---------------------------------------------------------------------------

def _normalize(query: str) -> str:
    """Return upper-cased, whitespace-collapsed version of query."""
    return re.sub(r"\s+", " ", query.strip().upper())


def _extract_tables_regex(parsed) -> list[str]:
    """Extract table names referenced in the parsed SQL statement using tokens."""
    tables = []
    from_seen = False
    for token in parsed.flatten():
        if token.ttype is Keyword and token.value.upper() in (
            "FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "CROSS JOIN"
        ):
            from_seen = True
        elif from_seen:
            if str(token.ttype) == "Token.Name":
                tables.append(token.value)
                from_seen = False
    return tables


def _count_joins_regex(query_upper: str) -> int:
    pattern = r"\b(JOIN|INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+JOIN|CROSS\s+JOIN)\b"
    return len(re.findall(pattern, query_upper))


def _count_subqueries_regex(query_upper: str) -> int:
    selects = re.findall(r"\bSELECT\b", query_upper)
    return max(0, len(selects) - 1)


def _has_select_star_regex(query_upper: str) -> bool:
    return bool(re.search(r"\bSELECT\s+\*", query_upper))


def _has_where_clause_regex(query_upper: str) -> bool:
    return bool(re.search(r"\bWHERE\b", query_upper))


def _has_limit_regex(query_upper: str) -> bool:
    return bool(re.search(r"\b(LIMIT|ROWNUM|FETCH\s+FIRST|TOP\s+\d+)\b", query_upper))


def _has_aggregation_regex(query_upper: str) -> bool:
    return bool(re.search(r"\b(COUNT|SUM|AVG|MAX|MIN)\s*\(", query_upper))


def _has_group_by_regex(query_upper: str) -> bool:
    return bool(re.search(r"\bGROUP\s+BY\b", query_upper))


def _has_order_by_regex(query_upper: str) -> bool:
    return bool(re.search(r"\bORDER\s+BY\b", query_upper))


def _has_distinct_regex(query_upper: str) -> bool:
    return bool(re.search(r"\bSELECT\s+DISTINCT\b", query_upper))


def _has_wildcard_like_regex(query_upper: str) -> bool:
    return bool(re.search(r"LIKE\s+['\"]%", query_upper))


def _has_function_on_column_regex(query_upper: str) -> bool:
    pattern = r"\bWHERE\b.*\b(UPPER|LOWER|YEAR|MONTH|DAY|DATE|TO_CHAR|CAST|CONVERT)\s*\("
    return bool(re.search(pattern, query_upper, re.DOTALL))


def _extract_filter_columns_regex(query: str) -> list[str]:
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


def _analyze_query_regex_fallback(query: str, schema: SchemaInfo | None = None) -> dict:
    """Fallback query analysis using regex and sqlparse tokens."""
    q = _normalize(query)
    issues = []
    warnings = []
    unknown_tables: list[str] = []
    unknown_columns: list[str] = []

    query_type = "SELECT" if q.startswith("SELECT") else ("INSERT" if q.startswith("INSERT") else ("UPDATE" if q.startswith("UPDATE") else ("DELETE" if q.startswith("DELETE") else "UNKNOWN")))
    join_count = _count_joins_regex(q)
    subquery_count = _count_subqueries_regex(q)
    agg = _has_aggregation_regex(q)
    grp = _has_group_by_regex(q)
    order = _has_order_by_regex(q)
    limit = _has_limit_regex(q)
    distinct = _has_distinct_regex(q)
    filter_cols = _extract_filter_columns_regex(query)

    if _has_select_star_regex(q):
        issues.append({
            "code": "SELECT_STAR",
            "severity": "HIGH",
            "message": "SELECT * fetches all columns — specify only the columns you need.",
        })

    if not _has_where_clause_regex(q) and query_type == "SELECT":
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

    if not limit and not _has_where_clause_regex(q) and query_type == "SELECT":
        issues.append({
            "code": "MISSING_LIMIT",
            "severity": "MEDIUM",
            "message": "No LIMIT clause — large result sets may cause memory pressure.",
        })

    if _has_wildcard_like_regex(q):
        warnings.append({
            "code": "LEADING_WILDCARD",
            "severity": "MEDIUM",
            "message": "Leading wildcard in LIKE (e.g. '%value') prevents index use.",
        })

    if _has_function_on_column_regex(q):
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

    if agg and not grp and not _has_where_clause_regex(q):
        warnings.append({
            "code": "AGGREGATE_FULL_SCAN",
            "severity": "MEDIUM",
            "message": "Aggregate function with no GROUP BY or WHERE — full scan required."
        })

    if subquery_count > 0 or join_count > 2:
        complexity = "Complex"
    elif join_count > 0 or _has_where_clause_regex(q) or agg:
        complexity = "Moderate"
    else:
        complexity = "Simple"

    if schema is not None:
        parsed_stmts = sqlparse.parse(query)
        parsed = parsed_stmts[0] if parsed_stmts else None
        extracted_tables = _extract_tables_regex(parsed) if parsed else []
        for tbl in extracted_tables:
            clean_tbl = tbl.split(".")[-1].strip("`\"' ")
            if clean_tbl and schema.get_table(clean_tbl) is None:
                if clean_tbl not in unknown_tables:
                    unknown_tables.append(clean_tbl)
                    issues.append({
                        "code": "UNKNOWN_TABLE",
                        "severity": "HIGH",
                        "message": f"Table `{clean_tbl}` does not exist in schema `{schema.database}`.",
                    })

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
        "select_star": _has_select_star_regex(q),
        "has_where": _has_where_clause_regex(q),
        "schema_validated": schema is not None,
        "unknown_tables": unknown_tables,
        "unknown_columns": unknown_columns,
    }


# ---------------------------------------------------------------------------
# AST-Driven Analysis (Primary Engine)
# ---------------------------------------------------------------------------

def _analyze_with_features(query: str, features: QueryFeatures, schema: SchemaInfo | None = None) -> dict:
    """Analyze query features extracted from sqlglot AST."""
    issues: list[dict] = []
    warnings: list[dict] = []
    unknown_tables: list[str] = []
    unknown_columns: list[str] = []

    # 1. SELECT *
    if features.select_star:
        issues.append({
            "code": "SELECT_STAR",
            "severity": "HIGH",
            "message": "SELECT * fetches all columns — specify only the columns you need.",
        })

    # 2. Missing WHERE
    if not features.has_where and features.statement_type == "SELECT":
        issues.append({
            "code": "MISSING_WHERE",
            "severity": "HIGH",
            "message": "No WHERE clause detected — query may perform a full table scan.",
        })

    # 3. Joins
    join_count = len(features.joins)
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

    # 4. Subqueries
    subquery_count = len(features.subqueries)
    if subquery_count > 0:
        issues.append({
            "code": "SUBQUERY_DETECTED",
            "severity": "MEDIUM",
            "message": (
                f"{subquery_count} nested subquery(ies) detected — "
                "consider rewriting with JOINs or CTEs."
            ),
        })

    # 5. Missing LIMIT
    has_limit = (features.limit is not None)
    if not has_limit and not features.has_where and features.statement_type == "SELECT":
        issues.append({
            "code": "MISSING_LIMIT",
            "severity": "MEDIUM",
            "message": "No LIMIT clause — large result sets may cause memory pressure.",
        })

    # 6. Wildcard LIKE ('%val')
    if features.wildcard_likes:
        warnings.append({
            "code": "LEADING_WILDCARD",
            "severity": "MEDIUM",
            "message": "Leading wildcard in LIKE (e.g. '%value') prevents index use.",
        })

    # 7. Function on column in WHERE
    has_func_on_col = any(p.is_function_wrapped for p in features.where_predicates)
    if has_func_on_col:
        warnings.append({
            "code": "FUNCTION_ON_COLUMN",
            "severity": "MEDIUM",
            "message": "Function applied to a column in WHERE — index on that column cannot be used.",
        })

    # 8. DISTINCT with JOINs
    if features.has_distinct and join_count > 0:
        warnings.append({
            "code": "DISTINCT_WITH_JOIN",
            "severity": "LOW",
            "message": "SELECT DISTINCT with JOINs may be masking duplicate-row bugs. Review the JOIN logic.",
        })

    # 9. Aggregate without GROUP BY or WHERE
    has_agg = len(features.aggregates) > 0
    has_grp = len(features.group_by_cols) > 0
    if has_agg and not has_grp and not features.has_where:
        warnings.append({
            "code": "AGGREGATE_FULL_SCAN",
            "severity": "MEDIUM",
            "message": "Aggregate function with no GROUP BY or WHERE — full scan required.",
        })

    # Complexity classification
    if subquery_count > 0 or join_count > 2:
        complexity = "Complex"
    elif join_count > 0 or features.has_where or has_agg:
        complexity = "Moderate"
    else:
        complexity = "Simple"

    # Schema Validation
    if schema is not None:
        for tbl in features.tables:
            clean_tbl = tbl.split(".")[-1].strip("`\"' ")
            if clean_tbl and schema.get_table(clean_tbl) is None:
                if clean_tbl not in unknown_tables:
                    unknown_tables.append(clean_tbl)
                    issues.append({
                        "code": "UNKNOWN_TABLE",
                        "severity": "HIGH",
                        "message": f"Table `{clean_tbl}` does not exist in schema `{schema.database}`.",
                    })

        if features.raw_ast:
            from sqlglot import exp as s_exp
            for col_node in features.raw_ast.find_all(s_exp.Column):
                if col_node.table and col_node.name != "*":
                    tbl_name = features.alias_map.get(col_node.table.lower(), col_node.table.lower())
                    tbl_info = schema.get_table(tbl_name)
                    if tbl_info and tbl_info.get_column(col_node.name) is None:
                        col_ref = f"{tbl_name}.{col_node.name}"
                        if col_ref not in unknown_columns:
                            unknown_columns.append(col_ref)
                            issues.append({
                                "code": "UNKNOWN_COLUMN",
                                "severity": "HIGH",
                                "message": f"Column `{col_node.name}` does not exist in table `{tbl_name}`.",
                            })

    # Combine filter columns from predicates and join ON clauses
    combined_filter_cols = set(features.filter_columns)
    for j in features.joins:
        if j.left_column:
            combined_filter_cols.add(j.left_column.lower())
        if j.right_column:
            combined_filter_cols.add(j.right_column.lower())

    return {
        "query_type": features.statement_type,
        "complexity": complexity,
        "issues": issues,
        "warnings": warnings,
        "filter_columns": sorted(list(combined_filter_cols)),
        "join_count": join_count,
        "subquery_count": subquery_count,
        "has_aggregation": has_agg,
        "has_group_by": has_grp,
        "has_order_by": len(features.order_by_cols) > 0,
        "has_limit": has_limit,
        "has_distinct": features.has_distinct,
        "select_star": features.select_star,
        "has_where": features.has_where,
        "schema_validated": schema is not None,
        "unknown_tables": unknown_tables,
        "unknown_columns": unknown_columns,
        "analysis_engine": "sqlglot_ast",
        "limited_analysis_notice": None,
    }


# ---------------------------------------------------------------------------
# Public Entrypoint
# ---------------------------------------------------------------------------

def analyze_query(query: str, schema: SchemaInfo | None = None) -> dict:
    """Analyze a SQL query using sqlglot AST parsing with regex fallback.

    Args:
        query: SQL statement string.
        schema: Optional SchemaInfo object.

    Returns:
        Structured analysis report dictionary.
    """
    if not query or not query.strip():
        return {
            "query_type": "UNKNOWN",
            "complexity": "Simple",
            "issues": [],
            "warnings": [],
            "filter_columns": [],
            "join_count": 0,
            "subquery_count": 0,
            "has_aggregation": False,
            "has_group_by": False,
            "has_order_by": False,
            "has_limit": False,
            "has_distinct": False,
            "select_star": False,
            "has_where": False,
            "schema_validated": schema is not None,
            "unknown_tables": [],
            "unknown_columns": [],
            "analysis_engine": "sqlglot_ast",
            "limited_analysis_notice": None,
        }

    try:
        features = extract_query_features(query, dialect="mysql")
        return _analyze_with_features(query, features, schema)
    except Exception as err:
        logger.warning("AST parse error, triggering regex fallback: %s", err)
        result = _analyze_query_regex_fallback(query, schema)
        result["analysis_engine"] = "regex_fallback"
        result["limited_analysis_notice"] = f"AST parse could not complete ({type(err).__name__}); analyzed with regex fallback."
        return result
