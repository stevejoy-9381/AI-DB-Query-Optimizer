"""
execution_plan.py
Simulated Query Execution Plan Generator for MySQL 8.x.

Produces a tree of plan nodes modeled after MySQL 8.x EXPLAIN execution plans,
displaying MySQL access types (ALL, index, range, ref, eq_ref, const), possible_keys,
key, rows, filtered, and Extra attributes (Using where, Using index, Using filesort,
Using temporary).

All cost constants and cardinality metrics are heuristic approximations and are explicitly
labeled as estimated.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plan node definition (MySQL EXPLAIN representation)
# ---------------------------------------------------------------------------


@dataclass
class PlanNode:
    """Represents a node in a simulated MySQL 8.x query execution plan."""

    node_type: str
    description: str
    estimated_rows: int
    startup_cost: float
    total_cost: float
    icon: str
    children: list["PlanNode"] = field(default_factory=list)

    # MySQL-specific EXPLAIN attributes
    table: str = ""
    access_type: str = ""
    possible_keys: list[str] = field(default_factory=list)
    key_used: str | None = None
    filtered_pct: float = 100.0
    extra: list[str] = field(default_factory=list)

    @property
    def cost_label(self) -> str:
        """Human-readable estimated cost label."""
        return f"est. cost: {self.total_cost:.2f}"


# ---------------------------------------------------------------------------
# MySQL 8.x Cost Model Constants (Estimated Heuristics)
# Based on default values in mysql.server_cost and mysql.engine_cost
# ---------------------------------------------------------------------------
_ROWS_BASE = 100_000  # Baseline table cardinality assumption
_PAGE_SIZE = 16_384  # Default InnoDB page size (16 KB)
_AVG_ROW_WIDTH = 100  # Estimated average row width in bytes
_ROWS_PER_PAGE = max(1, _PAGE_SIZE // _AVG_ROW_WIDTH)  # ~163 rows per page

# Engine and server cost factors (MySQL 8.0 defaults)
_ROW_EVALUATE_COST = 0.10  # CPU cost to evaluate a record
_MEMORY_BLOCK_READ_COST = 0.25  # Cost to read a 16KB page from buffer pool
_IO_BLOCK_READ_COST = 1.00  # Cost to read a 16KB page from disk
_KEY_COMPARE_COST = 0.05  # Cost to compare index keys during B-tree traversal


# ---------------------------------------------------------------------------
# Node constructors (MySQL EXPLAIN vocabulary)
# ---------------------------------------------------------------------------


def _table_scan_node(table: str, selectivity: float = 1.0, has_where: bool = False) -> PlanNode:
    """
    Construct an 'ALL' access type node (Full Table Scan in MySQL).
    Reads all table pages sequentially and evaluates row filters in memory.
    """
    rows_out = max(1, int(_ROWS_BASE * selectivity))
    pages = math.ceil(_ROWS_BASE / _ROWS_PER_PAGE)
    # Disk I/O to scan pages + CPU cost to evaluate each row
    total_cost = (pages * _IO_BLOCK_READ_COST) + (_ROWS_BASE * _ROW_EVALUATE_COST)
    filtered = 10.0 if has_where else 100.0
    extra = ["Using where"] if has_where else []

    return PlanNode(
        node_type="ALL",
        description=f"Full table scan (ALL) on `{table}` (est. rows: {_ROWS_BASE:,}, filtered: {filtered:.1f}%)",
        estimated_rows=rows_out,
        startup_cost=0.00,
        total_cost=round(total_cost, 2),
        icon="🔴",
        table=table,
        access_type="ALL",
        possible_keys=[],
        key_used=None,
        filtered_pct=filtered,
        extra=extra,
    )


def _index_lookup_node(table: str, column: str, selectivity: float = 0.01) -> PlanNode:
    """
    Construct a 'ref' access type node (Non-unique Index Lookup in MySQL).
    Performs B-tree seek followed by matching row lookups.
    """
    rows_out = max(1, int(_ROWS_BASE * selectivity))
    key_name = f"idx_{table}_{column}"
    pages = max(1, math.ceil(rows_out / _ROWS_PER_PAGE))
    # 3 key comparisons (root, intermediate, leaf) + buffer pool page reads + row evaluations
    total_cost = (
        (3 * _KEY_COMPARE_COST)
        + (pages * _MEMORY_BLOCK_READ_COST)
        + (rows_out * _ROW_EVALUATE_COST)
    )

    return PlanNode(
        node_type="ref",
        description=f"Index lookup (ref) on `{table}` using key `{key_name}` (est. rows: {rows_out:,})",
        estimated_rows=rows_out,
        startup_cost=round(3 * _KEY_COMPARE_COST, 2),
        total_cost=round(total_cost, 2),
        icon="🟢",
        table=table,
        access_type="ref",
        possible_keys=[key_name],
        key_used=key_name,
        filtered_pct=100.0,
        extra=[],
    )


def _index_range_node(table: str, column: str, selectivity: float = 0.05) -> PlanNode:
    """
    Construct a 'range' access type node (Index Range Scan in MySQL).
    Used for BETWEEN, >, <, or IN conditions on indexed columns.
    """
    rows_out = max(1, int(_ROWS_BASE * selectivity))
    key_name = f"idx_{table}_{column}"
    pages = max(1, math.ceil(rows_out / _ROWS_PER_PAGE))
    total_cost = (pages * _MEMORY_BLOCK_READ_COST) + (rows_out * _ROW_EVALUATE_COST)

    return PlanNode(
        node_type="range",
        description=f"Index range scan (range) on `{table}` using key `{key_name}`",
        estimated_rows=rows_out,
        startup_cost=round(3 * _KEY_COMPARE_COST, 2),
        total_cost=round(total_cost, 2),
        icon="🟢",
        table=table,
        access_type="range",
        possible_keys=[key_name],
        key_used=key_name,
        filtered_pct=100.0,
        extra=["Using index condition"],
    )


def _covering_index_node(table: str, column: str) -> PlanNode:
    """
    Construct an 'index' access type node with 'Using index' Extra attribute.
    Represents an index-only scan (covering index) in MySQL InnoDB.
    """
    rows_out = max(1, int(_ROWS_BASE * 0.1))
    key_name = f"idx_{table}_{column}_covering"
    pages = max(1, math.ceil(rows_out / (_ROWS_PER_PAGE * 2)))  # index leaf pages are denser
    total_cost = (pages * _MEMORY_BLOCK_READ_COST) + (rows_out * (_ROW_EVALUATE_COST * 0.5))

    return PlanNode(
        node_type="index",
        description=f"Covering index scan (index) on `{table}` using `{key_name}` — no clustered row lookups",
        estimated_rows=rows_out,
        startup_cost=0.00,
        total_cost=round(total_cost, 2),
        icon="🟡",
        table=table,
        access_type="index",
        possible_keys=[key_name],
        key_used=key_name,
        filtered_pct=100.0,
        extra=["Using index"],
    )


def _filter_node(child: PlanNode, condition: str) -> PlanNode:
    """Filter node representing MySQL 'Using where' post-filter."""
    rows_out = max(1, int(child.estimated_rows * 0.1))
    added_cost = rows_out * _ROW_EVALUATE_COST
    node = PlanNode(
        node_type="Filter",
        description=f"Filter (Using where): {condition}",
        estimated_rows=rows_out,
        startup_cost=child.startup_cost,
        total_cost=round(child.total_cost + added_cost, 2),
        icon="🔵",
        table=child.table,
        access_type=child.access_type,
        possible_keys=child.possible_keys,
        key_used=child.key_used,
        filtered_pct=10.0,
        extra=list(set(child.extra + ["Using where"])),
    )
    node.children.append(child)
    return node


def _hash_join_node(left: PlanNode, right: PlanNode, condition: str) -> PlanNode:
    """
    MySQL 8.0.18+ Hash Join node.
    Used by MySQL for equi-joins when join columns lack indexes.
    """
    rows_out = max(1, int(math.sqrt(left.estimated_rows * right.estimated_rows)))
    hash_build_cost = right.estimated_rows * _ROW_EVALUATE_COST
    probe_cost = left.estimated_rows * _ROW_EVALUATE_COST
    total_cost = left.total_cost + right.total_cost + hash_build_cost + probe_cost

    node = PlanNode(
        node_type="Hash Join",
        description=f"Inner hash join (join cond: {condition})",
        estimated_rows=rows_out,
        startup_cost=round(right.total_cost, 2),
        total_cost=round(total_cost, 2),
        icon="🟠",
        table=f"{left.table}+{right.table}",
        access_type="hash_join",
        extra=["Hash join (MySQL 8.0.18+)"],
    )
    node.children = [left, right]
    return node


def _nested_loop_node(outer: PlanNode, inner: PlanNode, condition: str) -> PlanNode:
    """
    MySQL Index Nested Loop join node.
    Iterates over outer rows and probes index on inner table for each row.
    """
    rows_out = max(1, outer.estimated_rows)
    total_cost = outer.total_cost + (outer.estimated_rows * inner.total_cost)

    node = PlanNode(
        node_type="Nested Loop",
        description=f"Index nested loop join ({condition})",
        estimated_rows=rows_out,
        startup_cost=outer.startup_cost,
        total_cost=round(min(total_cost, 9_999_999), 2),
        icon="🔶",
        table=f"{outer.table}+{inner.table}",
        access_type="nested_loop",
        extra=[],
    )
    node.children = [outer, inner]
    return node


def _filesort_node(child: PlanNode, keys: str) -> PlanNode:
    """
    MySQL filesort node ('Using filesort' in Extra).
    Represents an in-memory sort buffer pass when rows cannot be read in index order.
    """
    rows_out = child.estimated_rows
    # Sorting cost: N * log2(N) comparisons
    sort_cost = rows_out * math.log2(max(rows_out, 2)) * _KEY_COMPARE_COST
    node = PlanNode(
        node_type="filesort",
        description=f"Sort rows (Using filesort) on key: {keys}",
        estimated_rows=rows_out,
        startup_cost=round(child.total_cost, 2),
        total_cost=round(child.total_cost + sort_cost, 2),
        icon="🔷",
        table=child.table,
        access_type=child.access_type,
        key_used=child.key_used,
        extra=list(set(child.extra + ["Using filesort"])),
    )
    node.children.append(child)
    return node


def _temporary_aggregate_node(child: PlanNode, group_keys: str) -> PlanNode:
    """
    MySQL temporary table aggregation node ('Using temporary' in Extra).
    Used for GROUP BY or DISTINCT operations without index support.
    """
    rows_out = max(1, child.estimated_rows // 20)
    temp_table_cost = child.estimated_rows * _ROW_EVALUATE_COST
    node = PlanNode(
        node_type="temporary",
        description=f"Aggregate using internal temp table (Using temporary) grouped by: {group_keys}",
        estimated_rows=rows_out,
        startup_cost=round(child.total_cost, 2),
        total_cost=round(child.total_cost + temp_table_cost, 2),
        icon="🟤",
        table=child.table,
        access_type=child.access_type,
        extra=list(set(child.extra + ["Using temporary"])),
    )
    node.children.append(child)
    return node


def _limit_node(child: PlanNode, limit_val: int) -> PlanNode:
    """MySQL Limit node to cap output rows."""
    rows_out = min(child.estimated_rows, limit_val)
    reduction = rows_out / max(child.estimated_rows, 1)
    total_cost = child.startup_cost + (child.total_cost - child.startup_cost) * reduction
    node = PlanNode(
        node_type="Limit",
        description=f"Limit (est. output: {rows_out:,} rows)",
        estimated_rows=rows_out,
        startup_cost=round(child.startup_cost, 2),
        total_cost=round(total_cost, 2),
        icon="⬛",
        table=child.table,
        access_type=child.access_type,
        extra=child.extra,
    )
    node.children.append(child)
    return node


def _subquery_node(child: PlanNode, alias: str) -> PlanNode:
    """MySQL Materialized Subquery node."""
    node = PlanNode(
        node_type="Subquery",
        description=f"Materialized derived table / subquery: `{alias}`",
        estimated_rows=child.estimated_rows,
        startup_cost=child.startup_cost,
        total_cost=child.total_cost,
        icon="🔻",
        table=alias,
        access_type="DERIVED",
        extra=["Using temporary"],
    )
    node.children.append(child)
    return node


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _extract_tables(query: str) -> list[str]:
    hits = re.findall(
        r"\b(?:FROM|JOIN)\s+([\w]+)(?:\s+(?:AS\s+)?[\w]+)?",
        query,
        re.IGNORECASE,
    )
    return [h.lower() for h in hits]


def _extract_on_conditions(query: str) -> list[str]:
    return re.findall(r"\bON\b\s+([\w.]+\s*=\s*[\w.]+)", query, re.IGNORECASE)


def _extract_order_keys(query: str) -> str:
    m = re.search(r"\bORDER\s+BY\b\s+(.+?)(?:\bLIMIT\b|$)", query, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else "key"


def _extract_group_keys(query: str) -> str:
    m = re.search(
        r"\bGROUP\s+BY\b\s+(.+?)(?:\bHAVING\b|\bORDER\b|\bLIMIT\b|$)",
        query,
        re.IGNORECASE | re.DOTALL,
    )
    return m.group(1).strip() if m else ""


def _extract_limit_val(query: str) -> int:
    m = re.search(r"\bLIMIT\s+(\d+)", query, re.IGNORECASE)
    return int(m.group(1)) if m else 100


def _where_preview(query: str) -> str:
    m = re.search(
        r"\bWHERE\b\s+(.{1,50}?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|$)",
        query,
        re.IGNORECASE | re.DOTALL,
    )
    return m.group(1).strip().replace("\n", " ") if m else "condition"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_execution_plan(query: str, analysis: dict) -> PlanNode:
    """
    Build a simulated MySQL 8.x execution plan tree.
    Returns the root PlanNode (top of the plan = final stage of query processing).
    """
    tables = _extract_tables(query)
    join_cnt = analysis.get("join_count", 0)
    has_where = analysis.get("has_where", False)
    has_idx = bool(analysis.get("filter_columns"))
    filter_cols = analysis.get("filter_columns", [])
    has_agg = analysis.get("has_aggregation", False)
    has_grp = analysis.get("has_group_by", False)
    has_ord = analysis.get("has_order_by", False)
    has_lim = analysis.get("has_limit", False)
    sub_cnt = analysis.get("subquery_count", 0)

    primary = tables[0] if tables else "table"

    # ---- 1. Base access node (MySQL table/index scan) ----
    if has_where and has_idx and filter_cols:
        scan = _index_lookup_node(primary, filter_cols[0], selectivity=0.01)
    elif has_where:
        # WHERE present but no index: ALL scan with 'Using where'
        scan = _table_scan_node(primary, selectivity=1.0, has_where=True)
        scan = _filter_node(scan, _where_preview(query))
    else:
        # No WHERE: ALL scan
        scan = _table_scan_node(primary, selectivity=1.0, has_where=False)

    # ---- 2. Subquery ----
    if sub_cnt > 0:
        sub_table = tables[-1] if len(tables) > 1 else "subquery_table"
        sub_inner = _table_scan_node(sub_table, selectivity=0.1, has_where=True)
        sub_inner = _filter_node(sub_inner, "subquery predicate")
        scan = _subquery_node(sub_inner, "derived_subquery")

    # ---- 3. JOINs ----
    on_conds = _extract_on_conditions(query)
    join_tables = tables[1:] if len(tables) > 1 else []
    for i in range(join_cnt):
        jt = join_tables[i] if i < len(join_tables) else f"t{i + 2}"
        cond = on_conds[i] if i < len(on_conds) else f"{primary}.id = {jt}.{primary}_id"
        if has_idx and i == 0:
            # Indexed join: MySQL uses Index Nested Loop
            right = _index_lookup_node(jt, "id", selectivity=0.001)
            scan = _nested_loop_node(scan, right, cond)
        else:
            # Unindexed join: MySQL 8.0.18+ uses Hash Join
            right = _table_scan_node(jt, selectivity=1.0, has_where=False)
            scan = _hash_join_node(scan, right, cond)

    # ---- 4. Aggregate / GROUP BY ----
    if has_grp:
        group_keys = _extract_group_keys(query)
        scan = _temporary_aggregate_node(scan, group_keys)
    elif has_agg:
        scan = _temporary_aggregate_node(scan, "aggregate_fn")

    # ---- 5. Sort / ORDER BY (Using filesort) ----
    if has_ord:
        scan = _filesort_node(scan, _extract_order_keys(query))

    # ---- 6. Limit ----
    if has_lim:
        scan = _limit_node(scan, _extract_limit_val(query))

    return scan


def flatten_plan(root: PlanNode) -> list[dict]:
    """
    Flatten the plan tree depth-first into a list of dicts for tabular display.
    Formatted using standard MySQL EXPLAIN column headers.
    """
    result: list[dict] = []

    def _walk(node: PlanNode, depth: int) -> None:
        indent = "\u00a0\u00a0\u00a0\u00a0" * depth
        result.append(
            {
                "Plan Node": indent + node.icon + " " + node.node_type,
                "Table": node.table or "—",
                "Access Type": node.access_type or node.node_type,
                "Key": node.key_used or "—",
                "Est. Rows": f"{node.estimated_rows:,}",
                "Filtered %": f"{node.filtered_pct:.1f}%",
                "Extra": ", ".join(node.extra) if node.extra else "—",
                "Est. Cost": f"{node.total_cost:.2f}",
            }
        )
        for child in node.children:
            _walk(child, depth + 1)

    _walk(root, 0)
    return result


def get_all_nodes(root: PlanNode) -> list[PlanNode]:
    """Return all nodes in pre-order (root first) for chart building."""
    result: list[PlanNode] = []

    def _walk(node: PlanNode) -> None:
        result.append(node)
        for child in node.children:
            _walk(child)

    _walk(root)
    return result


def plan_cost_category(root: PlanNode) -> str:
    """Classify the root total cost as LOW / MEDIUM / HIGH (estimated)."""
    cost = root.total_cost
    if cost > 20_000:
        return "HIGH"
    elif cost > 2_000:
        return "MEDIUM"
    return "LOW"


def plan_summary(root: PlanNode) -> dict:
    """
    Return a summary dict of the execution plan.
    Preserves backward compatibility while exposing MySQL EXPLAIN indicators.
    """
    nodes = get_all_nodes(root)
    node_types = [n.node_type for n in nodes]
    access_types = [n.access_type for n in nodes if n.access_type]

    has_index = any(
        t in ("ref", "range", "eq_ref", "const", "index", "Index Scan")
        for t in (node_types + access_types)
    )
    has_all = any(t in ("ALL", "Seq Scan") for t in (node_types + access_types))

    return {
        "total_nodes": len(nodes),
        "plan_root": root.node_type,
        "access_type": root.access_type or root.node_type,
        "has_seq_scan": has_all,  # preserved for backward compatibility
        "has_all_scan": has_all,  # MySQL terminology
        "has_index_scan": has_index,
        "has_hash_join": "Hash Join" in node_types,
        "has_nested_loop": "Nested Loop" in node_types,
        "has_sort": any(t in ("filesort", "Sort") for t in node_types),
        "has_aggregate": any(t in ("temporary", "Aggregate", "HashAggregate") for t in node_types),
        "plan_cost": root.total_cost,
        "cost_category": plan_cost_category(root),
        "estimated_rows": root.estimated_rows,
        "key_used": root.key_used,
    }
