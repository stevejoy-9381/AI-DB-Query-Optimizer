"""
optimizer.py
SQL Optimization Recommendation Engine.

Takes an analysis report (from analyzer.py) and produces a set of concrete,
ranked optimization strategies with example SQL where applicable.
"""

from __future__ import annotations
import re


# ---------------------------------------------------------------------------
# Recommendation library
# ---------------------------------------------------------------------------

def _select_star_fix(query: str) -> dict:
    """Suggest replacing SELECT * with explicit columns."""
    # Try to extract table name for a friendlier message
    match = re.search(r"\bFROM\s+([\w.]+)", query, re.IGNORECASE)
    table = match.group(1) if match else "your_table"
    return {
        "title": "Replace SELECT * with specific columns",
        "priority": "HIGH",
        "description": (
            "Fetching all columns wastes I/O and memory, especially on wide tables. "
            "Select only the columns your application actually needs."
        ),
        "example": f"-- Before\nSELECT * FROM {table};\n\n-- After\nSELECT id, name, created_at FROM {table};",
    }


def _missing_where_fix() -> dict:
    return {
        "title": "Add a WHERE clause to filter rows early",
        "priority": "HIGH",
        "description": (
            "Without a WHERE clause the database performs a full table scan, "
            "reading every row. Adding a filter condition dramatically reduces I/O."
        ),
        "example": (
            "-- Before\nSELECT name FROM customers;\n\n"
            "-- After\nSELECT name FROM customers WHERE status = 'active';"
        ),
    }


def _join_index_fix(filter_cols: list[str]) -> dict:
    cols_str = ", ".join(filter_cols) if filter_cols else "join_column"
    return {
        "title": "Index JOIN / ON columns",
        "priority": "HIGH",
        "description": (
            "JOIN operations become nested-loop or hash-join full scans when the "
            "join columns lack indexes. Add indexes on both sides of every ON condition."
        ),
        "example": (
            f"CREATE INDEX idx_{cols_str.replace(', ', '_')} "
            f"ON your_table({cols_str});"
        ),
    }


def _excessive_join_fix() -> dict:
    return {
        "title": "Reduce the number of JOINs",
        "priority": "HIGH",
        "description": (
            "More than 2 JOINs in a single query multiplies the cardinality the planner "
            "must handle. Consider breaking the query into CTEs (WITH clauses) or smaller "
            "queries that are assembled in application code."
        ),
        "example": (
            "-- Use CTEs to pre-filter before joining\n"
            "WITH active_orders AS (\n"
            "    SELECT * FROM orders WHERE status = 'active'\n"
            ")\nSELECT c.name, o.total\nFROM customers c\nJOIN active_orders o ON c.id = o.customer_id;"
        ),
    }


def _subquery_fix() -> dict:
    return {
        "title": "Replace subqueries with JOINs or CTEs",
        "priority": "MEDIUM",
        "description": (
            "Correlated subqueries execute once per row of the outer query (O(n²) "
            "behaviour). Rewriting as a JOIN or a WITH (CTE) lets the planner choose "
            "the most efficient execution strategy."
        ),
        "example": (
            "-- Before (correlated subquery)\n"
            "SELECT name FROM employees e\n"
            "WHERE salary > (SELECT AVG(salary) FROM employees WHERE dept_id = e.dept_id);\n\n"
            "-- After (CTE + JOIN)\n"
            "WITH dept_avg AS (\n"
            "    SELECT dept_id, AVG(salary) AS avg_sal FROM employees GROUP BY dept_id\n"
            ")\nSELECT e.name\nFROM employees e\nJOIN dept_avg d ON e.dept_id = d.dept_id\n"
            "WHERE e.salary > d.avg_sal;"
        ),
    }


def _limit_fix() -> dict:
    return {
        "title": "Add LIMIT to cap result-set size",
        "priority": "MEDIUM",
        "description": (
            "Unbounded SELECT queries can return millions of rows, saturating network "
            "buffers and application memory. Always add LIMIT (or equivalent) when the "
            "full result set is not needed."
        ),
        "example": "SELECT id, name FROM orders WHERE status = 'pending' LIMIT 100;",
    }


def _leading_wildcard_fix() -> dict:
    return {
        "title": "Avoid leading wildcards in LIKE patterns",
        "priority": "MEDIUM",
        "description": (
            "A pattern like LIKE '%value' forces a full index scan because the B-tree "
            "cannot seek on an unknown prefix. Use a trailing wildcard (LIKE 'value%') "
            "or full-text search for contains-style queries."
        ),
        "example": (
            "-- Prevents index use\nWHERE name LIKE '%smith'\n\n"
            "-- Index-friendly\nWHERE name LIKE 'smith%'"
        ),
    }


def _function_on_column_fix() -> dict:
    return {
        "title": "Remove functions from WHERE column references",
        "priority": "MEDIUM",
        "description": (
            "Wrapping a column in a function (e.g. UPPER(email) = '...') makes the index "
            "unusable. Instead, transform the constant or create a function-based index."
        ),
        "example": (
            "-- Prevents index use\nWHERE UPPER(email) = 'USER@EXAMPLE.COM'\n\n"
            "-- Index-friendly (transform the constant instead)\nWHERE email = lower('USER@EXAMPLE.COM')\n\n"
            "-- Or create a function-based index\nCREATE INDEX idx_email_lower ON users(LOWER(email));"
        ),
    }


def _aggregate_full_scan_fix() -> dict:
    return {
        "title": "Filter rows before aggregating",
        "priority": "MEDIUM",
        "description": (
            "Running aggregate functions (COUNT, SUM, AVG …) without a WHERE or a "
            "selective GROUP BY means every row is read and processed. Add a WHERE "
            "clause to reduce the working set first."
        ),
        "example": (
            "-- Before\nSELECT AVG(salary) FROM employees;\n\n"
            "-- After\nSELECT AVG(salary) FROM employees WHERE department = 'Engineering';"
        ),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_optimizations(query: str, analysis: dict) -> list[dict]:
    """
    Generate a prioritised list of optimization recommendations.

    Parameters
    ----------
    query    : str  — original SQL query
    analysis : dict — output of analyzer.analyze_query()

    Returns
    -------
    list of recommendation dicts with keys: title, priority, description, example
    """
    issue_codes   = {i["code"] for i in analysis.get("issues",   [])}
    warning_codes = {w["code"] for w in analysis.get("warnings", [])}
    all_codes = issue_codes | warning_codes

    recs: list[dict] = []

    if "SELECT_STAR" in all_codes:
        recs.append(_select_star_fix(query))

    if "MISSING_WHERE" in all_codes:
        recs.append(_missing_where_fix())

    if "EXCESSIVE_JOINS" in all_codes:
        recs.append(_excessive_join_fix())
    elif "JOIN_DETECTED" in all_codes:
        recs.append(_join_index_fix(analysis.get("filter_columns", [])))

    if "SUBQUERY_DETECTED" in all_codes:
        recs.append(_subquery_fix())

    if "MISSING_LIMIT" in all_codes:
        recs.append(_limit_fix())

    if "LEADING_WILDCARD" in all_codes:
        recs.append(_leading_wildcard_fix())

    if "FUNCTION_ON_COLUMN" in all_codes:
        recs.append(_function_on_column_fix())

    if "AGGREGATE_FULL_SCAN" in all_codes:
        recs.append(_aggregate_full_scan_fix())

    # Sort: HIGH first, then MEDIUM, then LOW
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    recs.sort(key=lambda r: priority_order.get(r["priority"], 99))

    return recs


def generate_ai_insight(query: str, analysis: dict, score: int) -> str:
    """
    Generate a natural-language AI insight paragraph about the query.
    (Rule-based; no external LLM required.)
    """
    parts: list[str] = []

    complexity = analysis.get("complexity", "Unknown")
    parts.append(
        f"This is a **{complexity}** query with a performance score of **{score}/100**."
    )

    issue_codes = {i["code"] for i in analysis.get("issues", [])}

    if "SELECT_STAR" in issue_codes:
        parts.append(
            "The use of `SELECT *` retrieves all columns from the table, which increases "
            "network overhead and can prevent the query planner from using covering indexes."
        )

    if "MISSING_WHERE" in issue_codes:
        parts.append(
            "The absence of a `WHERE` clause means the database must perform a full table scan, "
            "reading every row before returning results. This is the single most impactful "
            "anti-pattern for large tables."
        )

    if "JOIN_DETECTED" in issue_codes or "EXCESSIVE_JOINS" in issue_codes:
        n = analysis.get("join_count", 1)
        parts.append(
            f"The query contains {n} JOIN operation(s). Each JOIN multiplies the number of "
            "row combinations the planner must evaluate. Ensuring that the join columns are "
            "indexed is critical for acceptable performance."
        )

    if "SUBQUERY_DETECTED" in issue_codes:
        parts.append(
            "Nested subqueries can cause correlated execution, where the inner query runs once "
            "for every row of the outer query. Rewriting as a JOIN or CTE often yields an "
            "order-of-magnitude speedup."
        )

    if score >= 80:
        parts.append("Overall, this query is well-structured and should perform efficiently.")
    elif score >= 50:
        parts.append(
            "Applying the recommendations above could improve the estimated execution time "
            "by 2–5×."
        )
    else:
        parts.append(
            "This query has multiple critical anti-patterns. Addressing all recommendations "
            "could improve performance by 10× or more."
        )

    return " ".join(parts)
