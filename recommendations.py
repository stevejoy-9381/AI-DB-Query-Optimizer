"""
recommendations.py
Index Recommendation Engine for MySQL 8.x.

Analyses a SQL query's filter, join, and projection columns to produce concrete,
valid MySQL 8.x CREATE INDEX statements along with clear explanations, trade-offs,
size estimates, and redundant index detection.

Features:
- Single-column indexes for isolated predicates.
- Composite indexes with optimal column ordering:
    Equality columns -> Range column -> ORDER BY / GROUP BY columns.
- Maximum 4 columns on composite indexes with write overhead warnings.
- Plain-English column-ordering explanation for composite recommendations.
- Index size estimation (in KB/MB) based on column types and row counts.
- Explicit trade-offs (faster reads, slower writes, storage impact).
- Ranking of recommendations by expected benefit (table size and selectivity).
- Detection of duplicate and redundant existing indexes (suggesting DROP INDEX).
- Skipping recommendations already covered by existing indexes (leftmost prefix rule).
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
from typing import TYPE_CHECKING, Any

from config import Dialect, get_dialect_config
from query_model import extract_query_features

if TYPE_CHECKING:
    from db.schema import SchemaInfo, TableInfo

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

# Approximate byte width per MySQL data type for index size estimation
TYPE_BYTE_SIZES: dict[str, int] = {
    "tinyint": 1,
    "smallint": 2,
    "mediumint": 3,
    "int": 4,
    "integer": 4,
    "bigint": 8,
    "float": 4,
    "double": 8,
    "decimal": 6,
    "numeric": 6,
    "date": 3,
    "time": 3,
    "datetime": 5,
    "timestamp": 4,
    "year": 1,
    "json": 64,
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
# Size and Storage Estimation
# ---------------------------------------------------------------------------

def estimate_index_size_bytes(
    table_name: str,
    cols: list[str],
    schema: SchemaInfo | None,
) -> tuple[int | None, str]:
    """
    Estimate InnoDB secondary index size in bytes for the specified columns.
    Formula: estimated_rows * (col_bytes + 6 bytes pointer) * 1.25 B-tree overhead factor.

    Returns (bytes_or_None, formatted_str_labeled_estimate).
    """
    if schema is None:
        return None, "Unknown (schema statistics unavailable)"

    tbl = schema.get_table(table_name)
    if tbl is None or tbl.estimated_rows <= 0:
        return None, "Unknown (row count unavailable)"

    rows = tbl.estimated_rows
    total_col_bytes = 0

    for col in cols:
        clean_col = col.lower()
        col_info = tbl.get_column(clean_col)
        if col_info:
            dtype = col_info.data_type.lower()
            base_type = dtype.split("(")[0].strip()
            if base_type in TYPE_BYTE_SIZES:
                total_col_bytes += TYPE_BYTE_SIZES[base_type]
            elif "char" in base_type:
                # Extract length from e.g. varchar(100)
                len_m = re.search(r"\((\d+)\)", dtype)
                length = int(len_m.group(1)) if len_m else 32
                if "varchar" in base_type:
                    total_col_bytes += min(length * 2, 64)  # Average utf8mb4 filled length
                else:
                    total_col_bytes += length * 4  # Fixed CHAR in utf8mb4
            elif "text" in base_type or "blob" in base_type:
                total_col_bytes += 191 * 4  # Typical prefix
            else:
                total_col_bytes += 16
        else:
            total_col_bytes += 16  # Default fallback width

    # InnoDB secondary index includes 6-byte clustered PK pointer + 1.25 B-tree fragmentation/fill factor
    row_index_bytes = total_col_bytes + 6
    estimated_total = int(rows * row_index_bytes * 1.25)

    if estimated_total < 1024:
        fmt = f"~{estimated_total} B (InnoDB B-tree estimate for {rows:,} rows)"
    elif estimated_total < 1024 * 1024:
        fmt = f"~{estimated_total / 1024:.1f} KB (InnoDB B-tree estimate for {rows:,} rows)"
    elif estimated_total < 1024 * 1024 * 1024:
        fmt = f"~{estimated_total / (1024 * 1024):.1f} MB (InnoDB B-tree estimate for {rows:,} rows)"
    else:
        fmt = f"~{estimated_total / (1024 * 1024 * 1024):.2f} GB (InnoDB B-tree estimate for {rows:,} rows)"

    return estimated_total, fmt


def _build_trade_offs_note(table: str, cols: list[str], size_str: str) -> str:
    """Generate trade-offs explanation covering read speedup, write penalty, and storage."""
    col_str = ", ".join(f"`{c}`" for c in cols)
    return (
        f"Trade-offs: Faster reads for queries filtering or sorting on ({col_str}); "
        "modest write overhead on INSERT/UPDATE/DELETE (InnoDB must maintain secondary B-tree pages); "
        f"storage impact: {size_str}."
    )


# ---------------------------------------------------------------------------
# Redundant and Duplicate Index Detection
# ---------------------------------------------------------------------------

def detect_redundant_indexes(
    schema: SchemaInfo,
    table_name: str | None = None,
) -> list[dict]:
    """
    Detect duplicate and redundant indexes among existing table indexes.
    Identifies:
    1. Exact duplicates: two indexes on the same table with identical columns.
    2. Prefix redundancy: index A is a strict leftmost prefix of composite index B.

    Returns a list of recommendations with DROP INDEX DDL and warnings.
    """
    redundancies: list[dict] = []
    tables_to_check = (
        [schema.get_table(table_name)] if table_name and schema.get_table(table_name)
        else list(schema.tables.values())
    )

    for tbl in tables_to_check:
        if tbl is None:
            continue
        idx_list = list(tbl.indexes.values())

        for i, idx_a in enumerate(idx_list):
            # Skip primary keys and unique indexes from being marked as redundant
            if idx_a.is_primary or idx_a.is_unique:
                continue

            for j, idx_b in enumerate(idx_list):
                if i == j:
                    continue

                cols_a = [c.lower() for c in idx_a.columns]
                cols_b = [c.lower() for c in idx_b.columns]

                # Case 1: Exact duplicate
                if cols_a == cols_b:
                    if idx_b.is_primary or idx_b.is_unique or idx_a.name > idx_b.name:
                        drop_ddl = f"DROP INDEX {idx_a.name} ON {tbl.name};"
                        redundancies.append({
                            "type": "DUPLICATE_INDEX",
                            "table": tbl.name,
                            "index_name": idx_a.name,
                            "parent_index": idx_b.name,
                            "columns": idx_a.columns,
                            "ddl": drop_ddl,
                            "reason": (
                                f"Index `{idx_a.name}` on `{tbl.name}` is an exact duplicate of `{idx_b.name}` "
                                f"({', '.join(idx_a.columns)})."
                            ),
                            "warning": (
                                "Warning: Review index usage before dropping. Dropping duplicate indexes "
                                "eliminates write amplification on DML statements and frees disk space. "
                                "Never drop automatically without verifying application dependencies."
                            ),
                        })
                        break

                # Case 2: Strict leftmost prefix redundancy
                elif len(cols_b) > len(cols_a) and cols_b[:len(cols_a)] == cols_a:
                    drop_ddl = f"DROP INDEX {idx_a.name} ON {tbl.name};"
                    redundancies.append({
                        "type": "PREFIX_REDUNDANT",
                        "table": tbl.name,
                        "index_name": idx_a.name,
                        "parent_index": idx_b.name,
                        "columns": idx_a.columns,
                        "ddl": drop_ddl,
                        "reason": (
                            f"Index `{idx_a.name}` ({', '.join(idx_a.columns)}) on `{tbl.name}` is a strict "
                            f"leftmost prefix of composite index `{idx_b.name}` ({', '.join(idx_b.columns)}). "
                            f"MySQL's leftmost prefix rule allows `{idx_b.name}` to satisfy all queries using "
                            f"({', '.join(idx_a.columns)})."
                        ),
                        "warning": (
                            "Warning: Before dropping, verify that no FOREIGN KEY constraint explicitly relies "
                            "on this index name. Dropping redundant indexes reduces storage and write overhead."
                        ),
                    })
                    break

    return redundancies


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
    tokens = re.split(r",(?![^(]*\))", select_clause)
    for tok in tokens:
        tok = tok.strip()
        tok = re.sub(r"\s+AS\s+[\w]+", "", tok, flags=re.IGNORECASE)
        func_match = re.search(r"\b\w+\(([\w.]+)\)", tok)
        if func_match:
            tok = func_match.group(1)
        parts = tok.split()
        raw_col = parts[0] if parts else ""
        if "." in raw_col:
            raw_col = raw_col.split(".")[-1]
        clean_col = _safe_identifier(raw_col)
        if clean_col and clean_col not in (
            "distinct", "top", "null", "all", "true", "false", "count", "sum", "avg", "max", "min"
        ):
            if clean_col not in cols:
                cols.append(clean_col)
    return cols


def _extract_table_column_pairs(query: str) -> list[tuple[str, str]]:
    """
    Return (table, column) tuples from WHERE and ON conditions.
    Handles alias resolution and unadorned columns.
    """
    pairs: list[tuple[str, str]] = []

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

    for m in re.finditer(r"\bON\b\s+([\w.]+)\s*=\s*([\w.]+)", query, re.IGNORECASE):
        for grp in (m.group(1), m.group(2)):
            parts = grp.split(".")
            if len(parts) == 2:
                tbl = alias_map.get(parts[0].lower(), parts[0].lower())
                col = parts[1].lower()
                pairs.append((tbl, col))

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


def _composite_candidate(query: str) -> tuple[str, list[str], dict[str, Any]] | None:
    """
    Identify candidate table and columns for a composite index following the optimal order:
    1. Equality columns
    2. Range column (at most 1)
    3. ORDER BY / GROUP BY columns

    Caps at 4 columns and provides plain-English ordering explanations.
    """
    from_m = re.search(r"\bFROM\s+([\w]+)", query, re.IGNORECASE)
    if not from_m:
        return None

    table = from_m.group(1).lower()
    eq_cols, range_cols = _classify_filter_predicates(query)

    # Also extract ORDER BY and GROUP BY columns using AST if possible
    sort_cols: list[str] = []
    try:
        features = extract_query_features(query)
        for ob in features.order_by_cols:
            col_clean = ob.split(".")[-1].lower()
            if col_clean not in sort_cols and col_clean not in eq_cols and col_clean not in range_cols:
                sort_cols.append(col_clean)
        for gb in features.group_by_cols:
            col_clean = gb.split(".")[-1].lower()
            if col_clean not in sort_cols and col_clean not in eq_cols and col_clean not in range_cols:
                sort_cols.append(col_clean)
    except Exception:
        pass

    # Ordering rule:
    # 1. Equality columns first
    ordered_cols = list(eq_cols)

    # 2. Range column next (first range column only, as B-tree cannot use subsequent range keys for seeking)
    range_col_used = None
    for rc in range_cols:
        if rc not in ordered_cols:
            ordered_cols.append(rc)
            range_col_used = rc
            break

    # 3. Sort columns next (to satisfy ORDER BY / GROUP BY without filesort)
    sort_cols_used = []
    for sc in sort_cols:
        if sc not in ordered_cols:
            ordered_cols.append(sc)
            sort_cols_used.append(sc)

    if len(ordered_cols) < 2:
        return None

    # Cap composite indexes at 4 columns
    is_capped = len(ordered_cols) > 4
    final_cols = ordered_cols[:4]

    # Build plain-English explanation
    exp_parts = []
    if eq_cols:
        exp_parts.append(f"Equality column(s) ({', '.join(eq_cols)}) placed first to prune non-matching rows immediately")
    if range_col_used:
        exp_parts.append(f"Range column (`{range_col_used}`) placed next to bound the B-tree seek interval")
    if sort_cols_used:
        exp_parts.append(f"Sorting column(s) ({', '.join(sort_cols_used)}) placed last to allow reading rows in index order without a filesort pass")

    explanation = "; ".join(exp_parts) + "."

    meta = {
        "eq_cols": eq_cols,
        "range_col": range_col_used,
        "sort_cols": sort_cols_used,
        "explanation": explanation,
        "is_capped": is_capped,
        "original_count": len(ordered_cols),
    }

    return (table, final_cols, meta)


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


# ---------------------------------------------------------------------------
# Recommendation Generator and Ranker
# ---------------------------------------------------------------------------

def generate_index_recommendations(
    query: str,
    analysis: dict,
    dialect: Dialect | str | None = None,
    schema: SchemaInfo | None = None,
) -> list[dict]:
    """
    Generate concrete, valid MySQL 8.x CREATE INDEX recommendations, ranked by expected benefit.

    Parameters
    ----------
    query    : str — original SQL query
    analysis : dict — output of analyzer.analyze_query()
    dialect  : Dialect | str | None — target database dialect (defaults to active dialect)
    schema   : SchemaInfo | None — live or introspected schema metadata

    Returns
    -------
    list of index recommendation dicts:
        index_name, ddl, reason, estimated_improvement, index_type,
        estimated_size, trade_offs, benefit_score, rank, column_order_explanation
    """
    cfg = get_dialect_config(dialect)
    recs: list[dict] = []
    seen_names: set[str] = set()
    pairs = _extract_table_column_pairs(query)
    projected_cols = _extract_projected_columns(query)

    # 1. Single-column or prefix index recommendations
    for tbl, col in pairs:
        is_long_text = col.lower() in LONG_TEXT_COLUMN_NAMES
        _, size_str = estimate_index_size_bytes(tbl, [col], schema)
        trade_offs = _build_trade_offs_note(tbl, [col], size_str)

        if is_long_text and cfg.name == Dialect.MYSQL:
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
            benefit_score = 45
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
            benefit_score = 60

        # Adjust score if table size is known
        if schema:
            tbl_info = schema.get_table(tbl)
            if tbl_info and tbl_info.estimated_rows > 100_000:
                benefit_score += 25
            elif tbl_info and tbl_info.estimated_rows > 10_000:
                benefit_score += 15

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
                "estimated_size": size_str,
                "trade_offs": trade_offs,
                "benefit_score": benefit_score,
                "column_order_explanation": None,
            })

    # 2. Composite index recommendations (Leftmost prefix rule with equality -> range -> sort)
    composite = _composite_candidate(query)
    if composite:
        tbl, cols, meta = composite
        idx_name = _generate_safe_index_name(tbl, cols)
        col_def = ", ".join(cols)
        ddl = (
            f"-- Verify existing table indexes before applying: SHOW INDEX FROM {tbl};\n"
            f"CREATE INDEX {idx_name}\n"
            f"    ON {tbl}({col_def});"
        )
        _, size_str = estimate_index_size_bytes(tbl, cols, schema)
        trade_offs = _build_trade_offs_note(tbl, cols, size_str)

        reason_text = (
            f"Composite B-tree index on `{tbl}({col_def})`. Ordered with equality predicates "
            "first followed by range predicates, satisfying multiple WHERE conditions in a single seek."
        )
        if meta.get("is_capped"):
            reason_text += (
                f" (Capped at 4 columns from {meta['original_count']} candidate columns to prevent write overhead)."
            )

        redundant, red_reason = _is_index_redundant(tbl, cols, schema)
        if redundant:
            logger.info("Skipping composite recommendation on %s(%s): %s", tbl, cols, red_reason)
        elif idx_name not in seen_names:
            seen_names.add(idx_name)
            comp_score = 75
            if schema:
                tbl_info = schema.get_table(tbl)
                if tbl_info and tbl_info.estimated_rows > 100_000:
                    comp_score += 25
                elif tbl_info and tbl_info.estimated_rows > 10_000:
                    comp_score += 15

            recs.append({
                "index_name": idx_name,
                "ddl": ddl,
                "reason": reason_text,
                "estimated_improvement": "Up to 50× faster than single-column index merges (estimated)",
                "index_type": "Composite B-tree",
                "estimated_size": size_str,
                "trade_offs": trade_offs,
                "benefit_score": comp_score,
                "column_order_explanation": meta.get("explanation"),
                "is_capped": meta.get("is_capped", False),
            })

    # 3. Covering index recommendations (MySQL composite index: filter leading + projection trailing)
    if pairs:
        tbl = pairs[0][0]
        filter_col = pairs[0][1]

        covered_cols = [c for c in projected_cols if c != filter_col]
        if not covered_cols:
            covered_cols = ["col1", "col2"]

        all_covering_cols = [filter_col] + covered_cols
        # Cap covering indexes at 4 columns for safety as well
        if len(all_covering_cols) > 4:
            all_covering_cols = all_covering_cols[:4]

        idx_name = _generate_safe_index_name(tbl, all_covering_cols, prefix="idx_cov")
        _, size_str = estimate_index_size_bytes(tbl, all_covering_cols, schema)
        trade_offs = _build_trade_offs_note(tbl, all_covering_cols, size_str)

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
            cov_score = 80
            if schema:
                tbl_info = schema.get_table(tbl)
                if tbl_info and tbl_info.estimated_rows > 100_000:
                    cov_score += 25
                elif tbl_info and tbl_info.estimated_rows > 10_000:
                    cov_score += 15

            recs.append({
                "index_name": idx_name,
                "ddl": ddl,
                "reason": reason,
                "estimated_improvement": "Index-only scan (`Using index`): avoids clustered index row lookups (estimated)",
                "index_type": index_type,
                "estimated_size": size_str,
                "trade_offs": trade_offs,
                "benefit_score": cov_score,
                "column_order_explanation": (
                    f"Leftmost filter column `{filter_col}` satisfies the WHERE clause, followed by projected columns "
                    f"({', '.join(covered_cols[:3])}) to satisfy the SELECT list without touching the clustered table."
                ),
            })

    # 4. FULLTEXT index suggestion for wildcard LIKE patterns
    issue_codes = {i["code"] for i in analysis.get("issues", [])}
    warn_codes  = {w["code"] for w in analysis.get("warnings", [])}
    if "LEADING_WILDCARD" in (issue_codes | warn_codes):
        tbl = pairs[0][0] if pairs else "your_table"
        filter_col = pairs[0][1] if pairs else "column_name"
        fts_name = _generate_safe_index_name(tbl, [filter_col], prefix="fts")
        _, size_str = estimate_index_size_bytes(tbl, [filter_col], schema)
        trade_offs = _build_trade_offs_note(tbl, [filter_col], size_str)

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
                "estimated_size": size_str,
                "trade_offs": trade_offs,
                "benefit_score": 70,
                "column_order_explanation": None,
            })

    # Rank recommendations by benefit score descending
    recs.sort(key=lambda r: r.get("benefit_score", 0), reverse=True)
    for rank, r in enumerate(recs, 1):
        r["rank"] = rank

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
