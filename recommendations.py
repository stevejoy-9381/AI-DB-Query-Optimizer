"""
recommendations.py
Index Recommendation Engine for MySQL 8.x.

Analyses a SQL query's filter, join, and projection columns to produce concrete,
valid MySQL 8.x CREATE INDEX statements along with clear explanations.

Features:
- Single-column indexes for isolated predicates.
- Composite indexes with optimal column ordering (equality columns first, then range columns).
- Covering indexes (composite B-trees with filter columns leading and selected columns trailing).
- FULLTEXT indexes for leading/middle wildcard LIKE patterns.
- Prefix indexes for long VARCHAR / TEXT columns (`col(191)`).
- Safe, deduplicated identifier generation (max 64 characters, `[a-z0-9_]`).
- Pre-execution verification comments (no invalid `IF NOT EXISTS`).
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import TYPE_CHECKING

from config import Dialect, get_dialect_config

if TYPE_CHECKING:
    from db.schema import SchemaInfo

logger = logging.getLogger(__name__)

# Known column names that typically store unstructured text or large VARCHAR/TEXT
LONG_TEXT_COLUMN_NAMES = {
    "body",
    "content",
    "description",
    "notes",
    "comment",
    "bio",
    "message",
    "payload",
    "article",
    "text",
    "query_text",
    "summary",
    "details",
    "raw_data",
}


# ---------------------------------------------------------------------------
# Identifier and Name Helpers
# ---------------------------------------------------------------------------

def _safe_identifier(name: str) -> str:
    """Sanitize identifier to contain only lowercase [a-z0-9_]."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "col"


def _generate_safe_index_name(table: str, cols: list[str], prefix: str = "idx") -> str:
    """
    Generate a safe MySQL index name adhering to the 64-character limit.
    Format: idx_<table>_<cols>
    If the name exceeds 64 characters, truncates the column segment and appends
    a deterministic 8-character MD5 hash.
    """
    clean_table = _safe_identifier(table)
    clean_cols = [_safe_identifier(c) for c in cols]
    col_str = "_".join(clean_cols)
    raw_name = f"{prefix}_{clean_table}_{col_str}"

    if len(raw_name) <= 64:
        return raw_name

    # MySQL identifier limit is 64 characters
    hash_suffix = hashlib.md5(col_str.encode()).hexdigest()[:8]
    # Keep prefix and table, allocate 9 chars for _<hash>
    base = f"{prefix}_{clean_table}"[:54]
    return f"{base}_{hash_suffix}"


# ---------------------------------------------------------------------------
# Query Extraction Helpers
# ---------------------------------------------------------------------------

def _extract_projected_columns(query: str) -> list[str]:
    """
    Extract explicitly projected column names from the SELECT clause.
    Returns an empty list if SELECT * is used.
    """
    m = re.search(r"\bSELECT\s+(.+?)\bFROM\b", query, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    select_clause = m.group(1).strip()
    if "*" in select_clause:
        return []

    cols = []
    # Split by comma outside parentheses
    tokens = re.split(r",(?![^(]*\))", select_clause)
    for tok in tokens:
        tok = tok.strip()
        # Remove alias (e.g., 'col AS alias' or 'col alias')
        tok = re.sub(r"\s+AS\s+[\w]+", "", tok, flags=re.IGNORECASE)
        # Remove scalar functions wrapping the column (e.g. UPPER(col) -> col)
        func_match = re.search(r"\b\w+\(([\w.]+)\)", tok)
        if func_match:
            tok = func_match.group(1)
        parts = tok.split()
        raw_col = parts[0] if parts else ""
        if "." in raw_col:
            raw_col = raw_col.split(".")[-1]
        clean_col = _safe_identifier(raw_col)
        if clean_col and clean_col not in ("distinct", "top", "null", "all", "true", "false", "count", "sum", "avg", "max", "min"):
            if clean_col not in cols:
                cols.append(clean_col)
    return cols


def _extract_table_column_pairs(query: str) -> list[tuple[str, str]]:
    """
    Return (table, column) tuples from WHERE and ON conditions.
    Handles alias resolution and unadorned columns.
    """
    pairs: list[tuple[str, str]] = []

    # Map table aliases: FROM <table> [AS] <alias>
    alias_map: dict[str, str] = {}
    alias_pattern = re.finditer(
        r"\b(?:FROM|JOIN)\s+([\w.]+)\s+(?:AS\s+)?([\w]+)",
        query,
        re.IGNORECASE,
    )
    for m in alias_pattern:
        table_name = m.group(1).split(".")[-1].lower()
        alias      = m.group(2).lower()
        if alias.upper() not in ("WHERE", "ON", "JOIN", "INNER", "LEFT", "RIGHT", "GROUP", "ORDER", "LIMIT"):
            alias_map[alias] = table_name

    # ON conditions: a.col = b.col
    for m in re.finditer(r"\bON\b\s+([\w.]+)\s*=\s*([\w.]+)", query, re.IGNORECASE):
        for grp in (m.group(1), m.group(2)):
            parts = grp.split(".")
            if len(parts) == 2:
                tbl = alias_map.get(parts[0].lower(), parts[0].lower())
                col = parts[1].lower()
                pairs.append((tbl, col))

    # WHERE conditions: col = val or table.col = val
    where_m = re.search(
        r"\bWHERE\b(.+?)(?:\bGROUP\b|\bORDER\b|\bHAVING\b|\bLIMIT\b|$)",
        query,
        re.IGNORECASE | re.DOTALL,
    )
    if where_m:
        clause = where_m.group(1)
        for m in re.finditer(
            r"([\w]+\.[\w]+|[\w]+)\s*(?:=|>|<|>=|<=|!=|LIKE|IN|BETWEEN)",
            clause,
            re.IGNORECASE,
        ):
            raw = m.group(1)
            parts = raw.split(".")
            if len(parts) == 2:
                tbl = alias_map.get(parts[0].lower(), parts[0].lower())
                col = parts[1].lower()
            else:
                from_m = re.search(r"\bFROM\s+([\w]+)", query, re.IGNORECASE)
                tbl = from_m.group(1).lower() if from_m else "table"
                col = parts[0].lower()

            if col not in ("and", "or", "not", "null", "true", "false", "is", "1", "0"):
                pairs.append((tbl, col))

    # Deduplicate while preserving order
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for p in pairs:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def _classify_filter_predicates(query: str) -> tuple[list[str], list[str]]:
    """
    Extract (equality_columns, range_columns) from WHERE clause to optimize composite index column ordering.
    """
    where_m = re.search(
        r"\bWHERE\b(.+?)(?:\bGROUP\b|\bORDER\b|\bHAVING\b|\bLIMIT\b|$)",
        query,
        re.IGNORECASE | re.DOTALL,
    )
    if not where_m:
        return [], []
    clause = where_m.group(1)

    eq_matches = re.findall(r"([\w.]+)\s*=", clause)
    range_matches = re.findall(r"([\w.]+)\s*(?:>|<|>=|<=|BETWEEN)", clause, re.IGNORECASE)

    def _clean(raw_list: list[str]) -> list[str]:
        cleaned = []
        for item in raw_list:
            col = item.split(".")[-1].lower()
            if col not in ("and", "or", "not", "null", "true", "false", "1", "0") and col not in cleaned:
                cleaned.append(col)
        return cleaned

    return _clean(eq_matches), _clean(range_matches)


def _composite_candidate(query: str) -> tuple[str, list[str]] | None:
    """
    Identify candidate table and columns for a composite index.
    Orders equality columns first, then range columns (leftmost prefix rule).
    """
    from_m = re.search(r"\bFROM\s+([\w]+)", query, re.IGNORECASE)
    if not from_m:
        return None

    table = from_m.group(1).lower()
    eq_cols, range_cols = _classify_filter_predicates(query)
    # Combine: equality columns first, then range columns
    ordered_cols = eq_cols + [c for c in range_cols if c not in eq_cols]

    if len(ordered_cols) >= 2:
        return (table, ordered_cols)
    return None


def _is_index_redundant(tbl: str, cols: list[str], schema: SchemaInfo | None) -> tuple[bool, str]:
    """Check if an index for cols on tbl is already covered by schema metadata."""
    if schema is None or not cols:
        return False, ""
    table_info = schema.get_table(tbl)
    if table_info is None:
        return False, ""
    is_covered, existing_idx, reason = table_info.has_index_for_prefix(cols)
    if is_covered:
        return True, reason
    return False, ""


def generate_index_recommendations(
    query: str,
    analysis: dict,
    dialect: Dialect | str | None = None,
    schema: SchemaInfo | None = None,
) -> list[dict]:
    """
    Generate concrete, valid MySQL 8.x CREATE INDEX recommendations.

    Parameters
    ----------
    query    : str  — original SQL query
    analysis : dict — output of analyzer.analyze_query()
    dialect  : Dialect | str | None — target database dialect (defaults to active dialect)

    Returns
    -------
    list of index recommendation dicts:
        index_name, ddl, reason, estimated_improvement, index_type
    """
    cfg = get_dialect_config(dialect)
    recs: list[dict] = []
    seen_names: set[str] = set()
    pairs = _extract_table_column_pairs(query)
    projected_cols = _extract_projected_columns(query)

    # 1. Single-column or prefix index recommendations
    for tbl, col in pairs:
        is_long_text = col.lower() in LONG_TEXT_COLUMN_NAMES

        if is_long_text and cfg.name == Dialect.MYSQL:
            # Prefix index on long text/VARCHAR column
            idx_name = _generate_safe_index_name(tbl, [col])
            ddl = (
                f"-- Verify existing table indexes before applying: SHOW INDEX FROM {tbl};\n"
                f"CREATE INDEX {idx_name}\n"
                f"    ON {tbl}({col}(191));"
            )
            reason = (
                f"Column `{col}` on `{tbl}` stores long text/VARCHAR data. A 191-character prefix "
                "index (764 bytes in utf8mb4) satisfies index page limits while supporting fast prefix lookups."
            )
            index_type = "Prefix B-tree (191 chars)"
        else:
            idx_name = _generate_safe_index_name(tbl, [col])
            ddl = (
                f"-- Verify existing table indexes before applying: SHOW INDEX FROM {tbl};\n"
                f"CREATE INDEX {idx_name}\n"
                f"    ON {tbl}({col});"
            )
            reason = (
                f"Supports WHERE / JOIN filter on `{tbl}.{col}`. Allows the MySQL optimizer to perform "
                "a `ref` or `range` index seek instead of a full table scan (`ALL`)."
            )
            index_type = "B-tree (Single Column)"

        # Check schema to avoid recommending an index that already exists or is prefix-covered
        redundant, red_reason = _is_index_redundant(tbl, [col], schema)
        if redundant:
            logger.info("Skipping recommendation on %s(%s): %s", tbl, col, red_reason)
            continue

        if idx_name not in seen_names:
            seen_names.add(idx_name)
            recs.append({
                "index_name": idx_name,
                "ddl": ddl,
                "reason": reason,
                "estimated_improvement": "Up to 10–100× faster for selective queries (estimated)",
                "index_type": index_type,
            })

    # 2. Composite index recommendations (Leftmost prefix rule)
    composite = _composite_candidate(query)
    if composite:
        tbl, cols = composite
        idx_name = _generate_safe_index_name(tbl, cols)
        col_def = ", ".join(cols)
        ddl = (
            f"-- Verify existing table indexes before applying: SHOW INDEX FROM {tbl};\n"
            f"CREATE INDEX {idx_name}\n"
            f"    ON {tbl}({col_def});"
        )
        redundant, red_reason = _is_index_redundant(tbl, cols, schema)
        if redundant:
            logger.info("Skipping composite recommendation on %s(%s): %s", tbl, cols, red_reason)
        elif idx_name not in seen_names:
            seen_names.add(idx_name)
            recs.append({
                "index_name": idx_name,
                "ddl": ddl,
                "reason": (
                    f"Composite B-tree index on `{tbl}({col_def})`. Ordered with equality predicates "
                    "first followed by range predicates, satisfying multiple WHERE conditions in a single seek."
                ),
                "estimated_improvement": "Up to 50× faster than single-column index merges (estimated)",
                "index_type": "Composite B-tree",
            })

    # 3. Covering index recommendations (MySQL composite index: filter leading + projection trailing)
    if pairs:
        tbl = pairs[0][0]
        filter_col = pairs[0][1]

        # Use explicitly projected columns or common hints
        covered_cols = [c for c in projected_cols if c != filter_col]
        if not covered_cols:
            covered_cols = ["col1", "col2"]

        all_covering_cols = [filter_col] + covered_cols
        idx_name = _generate_safe_index_name(tbl, all_covering_cols, prefix="idx_cov")

        if cfg.name == Dialect.MYSQL:
            cov_col_def = ", ".join(all_covering_cols)
            ddl = (
                f"-- Verify existing table indexes before applying: SHOW INDEX FROM {tbl};\n"
                f"CREATE INDEX {idx_name}\n"
                f"    ON {tbl}({cov_col_def});"
            )
            reason = (
                f"Covering index on `{tbl}({cov_col_def})`. By including both filter and projected columns, "
                "MySQL satisfies the entire query from the secondary index alone (`Using index` in EXPLAIN), "
                "eliminating clustered index row lookups."
            )
            index_type = "Covering Index (Composite B-tree)"
        else:
            # PostgreSQL fallback via dialect abstraction
            cov_col_def = ", ".join(covered_cols)
            ddl = (
                f"-- Verify existing table indexes before applying: SHOW INDEX FROM {tbl};\n"
                f"CREATE INDEX {idx_name}\n"
                f"    ON {tbl}({filter_col}) INCLUDE ({cov_col_def});"
            )
            reason = "Covering index with non-key payload columns for PostgreSQL."
            index_type = "Covering Index (INCLUDE)"

        redundant, red_reason = _is_index_redundant(tbl, all_covering_cols, schema)
        if redundant:
            logger.info("Skipping covering index recommendation on %s(%s): %s", tbl, all_covering_cols, red_reason)
        elif idx_name not in seen_names:
            seen_names.add(idx_name)
            recs.append({
                "index_name": idx_name,
                "ddl": ddl,
                "reason": reason,
                "estimated_improvement": "Index-only scan (`Using index`): avoids clustered index row lookups (estimated)",
                "index_type": index_type,
            })

    # 4. FULLTEXT index suggestion for wildcard LIKE patterns
    issue_codes = {i["code"] for i in analysis.get("issues", [])}
    warn_codes  = {w["code"] for w in analysis.get("warnings", [])}
    if "LEADING_WILDCARD" in (issue_codes | warn_codes):
        tbl = pairs[0][0] if pairs else "your_table"
        filter_col = pairs[0][1] if pairs else "column_name"
        fts_name = _generate_safe_index_name(tbl, [filter_col], prefix="fts")

        if cfg.name == Dialect.MYSQL:
            fts_ddl = (
                f"-- Verify existing table indexes before applying: SHOW INDEX FROM {tbl};\n"
                f"ALTER TABLE {tbl} ADD FULLTEXT INDEX {fts_name} ({filter_col});"
            )
            reason = (
                f"Leading wildcards (LIKE '%value') prevent B-tree seeks. A MySQL FULLTEXT index "
                f"on `{tbl}.{filter_col}` supports sub-millisecond keyword searches using `MATCH(...) AGAINST(...)`."
            )
            index_type = "FULLTEXT (InnoDB)"
        else:
            fts_ddl = f"CREATE INDEX {fts_name} ON {tbl} USING gin(to_tsvector('english', {filter_col}));"
            reason = "PostgreSQL GIN full-text index."
            index_type = "Full-text (GIN)"

        if fts_name not in seen_names:
            seen_names.add(fts_name)
            recs.append({
                "index_name": fts_name,
                "ddl": fts_ddl,
                "reason": reason,
                "estimated_improvement": "Sub-millisecond full-text lookup vs full table scan (estimated)",
                "index_type": index_type,
            })

    return recs


BEST_PRACTICES: list[str] = [
    "Avoid `SELECT *` — always specify only the columns you need to reduce I/O and enable covering indexes.",
    "Index columns that appear in WHERE, JOIN ON, and ORDER BY clauses.",
    "Use composite indexes when multiple columns are filtered together — column order matters (leftmost prefix rule).",
    "Avoid functions on indexed columns in WHERE (e.g. `UPPER(col) = …`) — they disable standard B-tree index seeks.",
    "Prefer `EXISTS` over `IN` for correlated subqueries against large tables.",
    "Use `LIMIT` to avoid unbounded result sets and excessive memory buffer consumption.",
    "Avoid leading wildcards (`LIKE '%value'`) — use MySQL InnoDB `FULLTEXT` indexing instead.",
    "Partition large tables by range, hash, or date to reduce scan size.",
    "Run `EXPLAIN FORMAT=JSON` or `EXPLAIN ANALYZE` (MySQL 8.0+) to inspect the actual optimizer execution plan.",
    "Run `ANALYZE TABLE` after bulk loads to refresh InnoDB table and index statistics for the query planner.",
    "Use connection pooling (ProxySQL, MySQL Router, or application-level pooling) to reduce connection overhead.",
    "Consider MySQL read replicas to offload analytical and reporting queries from the primary writer instance.",
]
