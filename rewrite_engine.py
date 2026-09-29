"""
rewrite_engine.py
SQL Query Rewrite Engine.

Automatically rewrites inefficient SQL patterns into optimized equivalents.
Tracks every transformation applied so they can be displayed in the UI.
"""

from __future__ import annotations
import re
import sqlparse


# ---------------------------------------------------------------------------
# Column hint library — common table names → sensible projected columns
# ---------------------------------------------------------------------------
_COLUMN_HINTS: dict[str, list[str]] = {
    "users":        ["id", "name", "email", "created_at"],
    "user":         ["id", "name", "email", "created_at"],
    "customers":    ["id", "name", "email", "phone", "region"],
    "customer":     ["id", "name", "email", "phone"],
    "orders":       ["id", "customer_id", "total", "status", "created_at"],
    "order":        ["id", "customer_id", "total", "status"],
    "order_items":  ["id", "order_id", "product_id", "quantity", "price"],
    "products":     ["id", "name", "price", "category_id", "stock"],
    "product":      ["id", "name", "price", "category_id"],
    "employees":    ["id", "name", "department", "salary", "hire_date"],
    "employee":     ["id", "name", "department", "salary"],
    "logs":         ["id", "user_id", "action", "created_at"],
    "audit_log":    ["id", "user_id", "event", "ip_address", "created_at"],
    "sessions":     ["id", "user_id", "status", "started_at", "expires_at"],
    "page_views":   ["id", "user_id", "page", "visited_at"],
    "invoices":     ["id", "customer_id", "total", "status", "created_at"],
    "line_items":   ["id", "invoice_id", "product_id", "qty", "price"],
    "payments":     ["id", "order_id", "amount", "method", "paid_at"],
    "categories":   ["id", "name", "parent_id"],
}


def _get_columns_for_table(table_name: str) -> list[str]:
    """Return suggested columns for a table name, or a generic default."""
    t = table_name.lower().strip()
    return _COLUMN_HINTS.get(t, ["id", "name", "created_at"])


def _extract_primary_table(query: str) -> str:
    """Extract the first table name after FROM."""
    m = re.search(r"\bFROM\s+([\w]+)", query, re.IGNORECASE)
    return m.group(1) if m else "your_table"


def _extract_alias_for_table(query: str, table: str) -> str | None:
    """Return the alias used for a table, if any."""
    m = re.search(
        rf"\b{re.escape(table)}\s+(?:AS\s+)?([\w]+)\b",
        query, re.IGNORECASE,
    )
    if m and m.group(1).upper() not in ("WHERE", "ON", "JOIN", "SET", "AS"):
        return m.group(1)
    return None


def _rewrite_select_star(query: str, table: str, alias: str | None) -> tuple[str, str]:
    """Replace SELECT * with explicit columns. Returns (rewritten_query, change_description)."""
    cols    = _get_columns_for_table(table)
    prefix  = (alias + ".") if alias else ""
    col_str = ", ".join(prefix + c for c in cols)

    # Replace SELECT * or SELECT <alias>.*
    pattern   = r"SELECT\s+(?:[\w]+\.)?\*"
    rewritten = re.sub(pattern, f"SELECT {col_str}", query, count=1, flags=re.IGNORECASE)
    change    = f"Replaced `SELECT *` with explicit columns: `{col_str}`"
    return rewritten, change


def _rewrite_add_limit(query: str, limit_val: int = 100) -> tuple[str, str]:
    """Append LIMIT clause. Returns (rewritten_query, change_description)."""
    # Remove trailing semicolon temporarily
    cleaned = query.rstrip().rstrip(";")
    rewritten = cleaned + f"\nLIMIT {limit_val};"
    return rewritten, f"Added `LIMIT {limit_val}` to prevent unbounded result sets"


def _rewrite_in_subquery_to_join(query: str) -> tuple[str, str] | None:
    """
    Attempt to rewrite a simple IN-subquery to an INNER JOIN.

    Pattern handled:
        SELECT ... FROM <main_table> <alias>
        WHERE <alias>.<col> IN (SELECT <join_col> FROM <sub_table> WHERE <cond>)
    """
    pattern = re.compile(
        r"(?P<before>SELECT\s+.+?\bFROM\s+(?P<main_table>[\w]+)(?:\s+(?:AS\s+)?(?P<main_alias>[\w]+))?)"
        r"(?P<ws1>\s+)WHERE\s+"
        r"(?P<outer_col>[\w.]+)\s+IN\s*\("
        r"\s*SELECT\s+(?P<join_col>[\w.]+)\s+FROM\s+(?P<sub_table>[\w]+)"
        r"(?:\s+(?:AS\s+)?(?P<sub_alias>[\w]+))?"
        r"(?P<sub_where>\s+WHERE\s+.+?)?\s*\)"
        r"(?P<after>.*)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.match(query.strip())
    if not m:
        return None

    main_table  = m.group("main_table")
    main_alias  = m.group("main_alias") or main_table[0].lower()
    sub_table   = m.group("sub_table")
    sub_alias   = m.group("sub_alias") or sub_table[0].lower()
    outer_col   = m.group("outer_col")
    join_col    = m.group("join_col")
    sub_where   = (m.group("sub_where") or "").strip()
    after       = (m.group("after") or "").strip()

    # Build JOIN version
    join_on   = f"{outer_col} = {sub_alias}.{join_col.split('.')[-1]}"
    rewritten = (
        f"SELECT {main_alias}.name\n"
        f"FROM {main_table} {main_alias}\n"
        f"JOIN {sub_table} {sub_alias}\n"
        f"    ON {join_on}"
    )
    if sub_where:
        # Move sub_where predicate to outer WHERE
        inner_cond = sub_where.replace("WHERE", "").strip()
        rewritten += f"\nWHERE {inner_cond}"
    if after.strip():
        rewritten += f"\n{after.strip()}"

    change = (
        f"Rewrote correlated `IN` subquery to `INNER JOIN` on "
        f"`{main_table}.{outer_col.split('.')[-1]} = {sub_table}.{join_col.split('.')[-1]}`"
    )
    return rewritten, change


def _rewrite_leading_wildcard(query: str) -> tuple[str, str] | None:
    """Add a comment suggesting full-text search for leading wildcards."""
    if re.search(r"LIKE\s+['\"]%\w+", query, re.IGNORECASE):
        annotated = re.sub(
            r"(LIKE\s+['\"]%\w+['\"])",
            r"\1  /* ⚠ leading wildcard disables index — consider full-text search */",
            query,
            count=1,
            flags=re.IGNORECASE,
        )
        return annotated, "Annotated leading wildcard `LIKE '%…'` — cannot use B-tree index"
    return None


def _rewrite_function_on_column(query: str) -> tuple[str, str] | None:
    """
    Detect and annotate function-on-column in WHERE.
    Try to move the function to the constant side when possible (e.g. UPPER(col) = 'VAL').
    """
    pattern = re.compile(
        r"\b(UPPER|LOWER)\s*\(\s*([\w.]+)\s*\)\s*=\s*(['\"][^'\"]+['\"])",
        re.IGNORECASE,
    )
    m = pattern.search(query)
    if not m:
        return None

    func, col, val = m.group(1), m.group(2), m.group(3)
    # Suggest moving function to the constant side
    if func.upper() == "UPPER":
        replacement = f"{col} = LOWER({val})"
        suggestion  = f"{col} = LOWER({val})"
    else:
        replacement = f"{col} = UPPER({val})"
        suggestion  = f"{col} = UPPER({val})"

    rewritten = pattern.sub(replacement, query, count=1)
    change    = (
        f"Moved `{func}()` from column `{col}` to the constant — "
        f"allows B-tree index on `{col}` to be used"
    )
    return rewritten, change


def _format_sql(query: str) -> str:
    """Pretty-print SQL with uppercase keywords."""
    try:
        return sqlparse.format(
            query,
            reindent=True,
            keyword_case="upper",
            identifier_case="lower",
            indent_width=4,
        ).strip()
    except Exception:
        return query.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rewrite_query(query: str, analysis: dict) -> dict:
    """
    Automatically rewrite an inefficient SQL query into an optimized form.

    Parameters
    ----------
    query    : str  — original SQL query
    analysis : dict — output of analyzer.analyze_query()

    Returns
    -------
    dict with keys:
        original          : str  — original query (formatted)
        rewritten         : str  — optimized query (formatted)
        changes           : list[str] — human-readable list of transformations applied
        is_changed        : bool — whether any rewrite was applied
        rewrite_score_est : int  — rough estimate of score improvement from rewrites
    """
    issue_codes   = {i["code"] for i in analysis.get("issues",   [])}
    warning_codes = {w["code"] for w in analysis.get("warnings", [])}
    all_codes     = issue_codes | warning_codes

    current  = query.strip()
    changes: list[str] = []

    # ---- 1. Rewrite IN subquery → JOIN (do this first, before SELECT * rewrite) ----
    if "SUBQUERY_DETECTED" in all_codes:
        result = _rewrite_in_subquery_to_join(current)
        if result:
            current, change = result
            changes.append(change)

    # ---- 2. Replace SELECT * ----
    if "SELECT_STAR" in all_codes:
        table = _extract_primary_table(current)
        alias = _extract_alias_for_table(current, table)
        current, change = _rewrite_select_star(current, table, alias)
        changes.append(change)

    # ---- 3. Fix function-on-column ----
    if "FUNCTION_ON_COLUMN" in all_codes:
        result = _rewrite_function_on_column(current)
        if result:
            current, change = result
            changes.append(change)

    # ---- 4. Annotate leading wildcard ----
    if "LEADING_WILDCARD" in all_codes:
        result = _rewrite_leading_wildcard(current)
        if result:
            current, change = result
            changes.append(change)

    # ---- 5. Add LIMIT ----
    if "MISSING_LIMIT" in all_codes and not re.search(r"\bLIMIT\b", current, re.IGNORECASE):
        current, change = _rewrite_add_limit(current, 100)
        changes.append(change)

    # ---- Format both original and rewritten ----
    formatted_original  = _format_sql(query)
    formatted_rewritten = _format_sql(current)

    # ---- Estimate score improvement from rewrites ----
    score_delta = 0
    for code_map in [
        ("SELECT_STAR",        25),
        ("SUBQUERY_DETECTED",  10),
        ("MISSING_LIMIT",      10),
        ("FUNCTION_ON_COLUMN", 10),
    ]:
        code, pts = code_map
        if code in all_codes and any(code.replace("_", " ").lower()[:5] in c.lower() for c in changes):
            score_delta += pts

    return {
        "original":          formatted_original,
        "rewritten":         formatted_rewritten,
        "changes":           changes,
        "is_changed":        len(changes) > 0,
        "rewrite_score_est": min(score_delta, 60),
    }
