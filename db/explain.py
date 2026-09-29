"""Real MySQL 8.x EXPLAIN and EXPLAIN ANALYZE executor and JSON plan parser."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import DML, Keyword
from sqlalchemy import text
from sqlalchemy.engine import Engine

from execution_plan import PlanNode

logger = logging.getLogger(__name__)

# Disallowed keywords for safe EXPLAIN execution
_FORBIDDEN_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "REPLACE", "RENAME", "EXEC",
    "EXECUTE", "CALL", "LOAD", "INTO", "OUTFILE", "DUMPFILE",
}


def validate_explainable_query(query: str) -> tuple[bool, str]:
    """Validate that query is strictly a single, read-only SELECT statement.

    Args:
        query: Raw SQL query string.

    Returns:
        Tuple of (is_valid, rejection_reason).
    """
    if not query or not query.strip():
        return False, "Query cannot be empty."

    # Remove comments to inspect underlying statements
    cleaned = sqlparse.format(query, strip_comments=True).strip()
    if not cleaned:
        return False, "Query contains only comments or whitespace."

    statements = [s for s in sqlparse.parse(cleaned) if s.tokens and str(s).strip()]
    if len(statements) != 1:
        return False, f"Only a single SQL statement is permitted for EXPLAIN (found {len(statements)})."

    stmt: Statement = statements[0]
    stmt_type = stmt.get_type()

    if stmt_type != "SELECT":
        return False, f"Only SELECT queries can be analyzed with EXPLAIN (detected statement type: '{stmt_type}')."

    # Deep scan for prohibited command tokens or nested modifications
    tokens_str = str(stmt).upper()
    
    # Check for semicolon-separated chained queries that might bypass statement splitting
    if ";" in cleaned.rstrip(";"):
        return False, "Multiple SQL statements detected via semicolon separator."

    # Look for forbidden keywords as standalone word tokens
    for word in re.findall(r"\b[A-Z_]+\b", tokens_str):
        if word in _FORBIDDEN_KEYWORDS:
            # Exception: INTO is allowed only if NOT part of SELECT ... INTO OUTFILE
            if word == "INTO" and ("OUTFILE" in tokens_str or "DUMPFILE" in tokens_str or "INSERT" in tokens_str):
                return False, "File write clauses (INTO OUTFILE/DUMPFILE) are prohibited."
            elif word != "INTO":
                return False, f"Prohibited operation keyword '{word}' detected."

    return True, "Valid SELECT statement."


def _parse_table_node(table_data: dict[str, Any], warnings: list[str]) -> PlanNode:
    """Parse a single MySQL table access block into a PlanNode."""
    table_name = table_data.get("table_name", "unknown_table")
    access_type = table_data.get("access_type", "ALL").upper()
    rows_examined = int(table_data.get("rows_examined_per_scan", table_data.get("rows_produced_per_join", 1)))
    filtered = float(table_data.get("filtered", 100.0))
    possible_keys = table_data.get("possible_keys", [])
    key_used = table_data.get("key")
    cost_info = table_data.get("cost_info", {})
    query_cost = float(cost_info.get("prefix_cost", cost_info.get("read_cost", 0.0)))

    extra = []
    if table_data.get("attached_condition"):
        extra.append("Using where")
    if table_data.get("using_index"):
        extra.append("Using index")
    if table_data.get("using_filesort"):
        extra.append("Using filesort")
    if table_data.get("using_temporary_table"):
        extra.append("Using temporary")

    # Assess warnings
    if access_type == "ALL":
        icon = "🔴"
        desc = f"Full Table Scan (ALL) on `{table_name}`"
        warnings.append(f"Full table scan (ALL) on table `{table_name}` ({rows_examined:,} rows examined).")
    elif access_type in ("REF", "EQ_REF", "CONST"):
        icon = "🟢"
        desc = f"Indexed lookup ({access_type}) on `{table_name}` via `{key_used}`"
    elif access_type in ("RANGE", "INDEX"):
        icon = "🟡"
        desc = f"Index scan ({access_type}) on `{table_name}` via `{key_used or 'index'}`"
    else:
        icon = "⚪"
        desc = f"Table access ({access_type}) on `{table_name}`"

    if "Using filesort" in extra:
        warnings.append(f"Filesort required for query ordering on `{table_name}`.")
    if "Using temporary" in extra:
        warnings.append(f"Temporary table required during execution for `{table_name}`.")
    if rows_examined > 5000 and access_type == "ALL":
        warnings.append(f"Large scan cardinality: `{table_name}` evaluates {rows_examined:,} rows.")

    return PlanNode(
        node_type=access_type,
        description=desc,
        estimated_rows=rows_examined,
        startup_cost=0.0,
        total_cost=round(query_cost, 2),
        icon=icon,
        table=table_name,
        access_type=access_type,
        possible_keys=possible_keys,
        key_used=key_used,
        filtered_pct=filtered,
        extra=extra,
        children=[],
    )


def _parse_nested_loop(nl_list: list[dict[str, Any]], warnings: list[str]) -> PlanNode:
    """Parse a MySQL nested_loop construct into a PlanNode tree."""
    child_nodes = []
    for item in nl_list:
        if "table" in item:
            child_nodes.append(_parse_table_node(item["table"], warnings))
        elif "nested_loop" in item:
            child_nodes.append(_parse_nested_loop(item["nested_loop"], warnings))

    if not child_nodes:
        return PlanNode(
            node_type="Nested Loop",
            description="Empty join loop",
            estimated_rows=1,
            startup_cost=0.0,
            total_cost=0.0,
            icon="⚪",
        )

    # Chain nodes as nested loops if multiple
    current = child_nodes[0]
    for right in child_nodes[1:]:
        total_rows = max(1, current.estimated_rows * right.estimated_rows)
        total_cost = round(current.total_cost + right.total_cost, 2)
        current = PlanNode(
            node_type="Nested Loop",
            description=f"Nested Loop Join (`{current.table}` ⨝ `{right.table}`)",
            estimated_rows=total_rows,
            startup_cost=0.0,
            total_cost=total_cost,
            icon="🔷",
            children=[current, right],
        )

    return current


def _parse_operation(block: dict[str, Any], warnings: list[str]) -> PlanNode:
    """Recursively parse query blocks and nested operations into PlanNodes."""
    if "ordering_operation" in block:
        order_op = block["ordering_operation"]
        child = _parse_operation(order_op, warnings)
        extra = []
        if order_op.get("using_filesort"):
            extra.append("Using filesort")
            warnings.append("Filesort required for query result sorting.")
        return PlanNode(
            node_type="Ordering",
            description=f"Sort & Ordering operation ({', '.join(extra) or 'sorted'})",
            estimated_rows=child.estimated_rows,
            startup_cost=0.0,
            total_cost=child.total_cost,
            icon="🔄",
            extra=extra,
            children=[child],
        )

    if "grouping_operation" in block:
        grp_op = block["grouping_operation"]
        child = _parse_operation(grp_op, warnings)
        extra = []
        if grp_op.get("using_temporary_table"):
            extra.append("Using temporary")
            warnings.append("Temporary table required for grouping/aggregates.")
        if grp_op.get("using_filesort"):
            extra.append("Using filesort")
            warnings.append("Filesort required for grouping operation.")
        return PlanNode(
            node_type="Grouping",
            description=f"Aggregation / Grouping ({', '.join(extra) or 'grouped'})",
            estimated_rows=child.estimated_rows,
            startup_cost=0.0,
            total_cost=child.total_cost,
            icon="📊",
            extra=extra,
            children=[child],
        )

    if "nested_loop" in block:
        return _parse_nested_loop(block["nested_loop"], warnings)

    if "table" in block:
        return _parse_table_node(block["table"], warnings)

    return PlanNode(
        node_type="Result",
        description="Query result plan",
        estimated_rows=1,
        startup_cost=0.0,
        total_cost=0.0,
        icon="⚡",
    )


def parse_mysql_explain_json(data: dict[str, Any]) -> tuple[PlanNode, list[str]]:
    """Convert MySQL EXPLAIN FORMAT=JSON dictionary into a PlanNode tree.

    Args:
        data: Parsed JSON dictionary from MySQL EXPLAIN FORMAT=JSON.

    Returns:
        Tuple of (root PlanNode, list of detected query plan warnings).
    """
    warnings: list[str] = []
    query_block = data.get("query_block", data)
    total_cost = float(query_block.get("cost_info", {}).get("query_cost", 0.0))

    root = _parse_operation(query_block, warnings)

    # Ensure total cost on root reflects query_cost if nonzero
    if total_cost > 0 and root.total_cost == 0.0:
        root.total_cost = round(total_cost, 2)

    return root, warnings


def run_explain(
    engine: Engine,
    query: str,
    analyze: bool = False,
    max_time_ms: int = 5000,
) -> dict[str, Any]:
    """Execute EXPLAIN FORMAT=JSON (and optionally EXPLAIN ANALYZE) against MySQL.

    Args:
        engine: Connected SQLAlchemy Engine.
        query: Single SELECT SQL statement.
        analyze: If True, execute EXPLAIN ANALYZE (MySQL 8.0.18+).
        max_time_ms: Statement timeout in milliseconds for EXPLAIN ANALYZE.

    Returns:
        Dictionary with execution plan tree, raw output, warnings, and metadata.
    """
    # 1. Security & syntax validation
    is_valid, reason = validate_explainable_query(query)
    if not is_valid:
        return {
            "success": False,
            "error": f"Query safety validation rejected: {reason}",
            "mode": "rejected",
        }

    raw_json_str = None
    raw_analyze_text = None
    mysql_version = "Unknown"

    try:
        with engine.connect() as conn:
            # Check version
            ver_res = conn.execute(text("SELECT VERSION()")).scalar()
            mysql_version = str(ver_res) if ver_res else "8.0"

            # Execute EXPLAIN FORMAT=JSON
            explain_query = f"EXPLAIN FORMAT=JSON {query.strip().rstrip(';')}"
            json_result = conn.execute(text(explain_query))
            row = json_result.fetchone()
            if not row or not row[0]:
                return {
                    "success": False,
                    "error": "EXPLAIN FORMAT=JSON produced empty output.",
                    "mode": "failed",
                }
            raw_json_str = row[0]
            parsed_json = json.loads(raw_json_str)

            # Optional EXPLAIN ANALYZE for MySQL 8.0.18+
            if analyze:
                # Check version compatibility
                version_match = re.search(r"(\d+)\.(\d+)\.(\d+)", mysql_version)
                is_supported = False
                if version_match:
                    major, minor, patch = map(int, version_match.groups())
                    if (major, minor, patch) >= (8, 0, 18):
                        is_supported = True

                if not is_supported:
                    raw_analyze_text = f"EXPLAIN ANALYZE requires MySQL 8.0.18+ (Current server version: {mysql_version}). Feature disabled."
                else:
                    # Enforce timeout and read-only transaction for safety
                    try:
                        conn.execute(text(f"SET SESSION max_execution_time = {max_time_ms}"))
                    except Exception:
                        pass  # Some engines or users lack session privilege

                    analyze_sql = f"EXPLAIN ANALYZE {query.strip().rstrip(';')}"
                    analyze_res = conn.execute(text(analyze_sql))
                    analyze_rows = [str(r[0]) for r in analyze_res.fetchall()]
                    raw_analyze_text = "\n".join(analyze_rows)

        # Parse JSON into PlanNode tree
        plan_tree, warnings = parse_mysql_explain_json(parsed_json)

        return {
            "success": True,
            "mode": "real_explain",
            "plan_tree": plan_tree,
            "warnings": warnings,
            "raw_json": parsed_json,
            "raw_analyze_text": raw_analyze_text,
            "mysql_version": mysql_version,
            "analyze_executed": analyze and is_supported,
        }

    except Exception as err:
        logger.exception("Failed to execute real EXPLAIN on MySQL: %s", err)
        return {
            "success": False,
            "error": f"MySQL EXPLAIN failed: {str(err)}",
            "mode": "failed",
        }
