"""scoring_rules.py
Data-driven configuration for query performance scoring rules.
Defines base deltas, labels, explanations, statement-specific overrides, and table-size multipliers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ScoreRuleConfig:
    code: str
    delta: int
    severity: str
    label: str
    explanation: str


# ---------------------------------------------------------------------------
# Base Rules Catalog
# ---------------------------------------------------------------------------

SCORE_RULES_CATALOG: list[ScoreRuleConfig] = [
    # Penalties
    ScoreRuleConfig(
        code="SELECT_STAR",
        delta=-25,
        severity="HIGH",
        label="SELECT * usage",
        explanation="Fetching all columns increases network I/O and prevents covering index scans.",
    ),
    ScoreRuleConfig(
        code="MISSING_WHERE",
        delta=-20,
        severity="HIGH",
        label="Missing WHERE clause",
        explanation="Absence of filter requires scanning the entire table.",
    ),
    ScoreRuleConfig(
        code="EXCESSIVE_JOINS",
        delta=-15,
        severity="HIGH",
        label="Excessive JOINs (>2)",
        explanation="Multiple table joins exponentially increase planner permutations and join buffer usage.",
    ),
    ScoreRuleConfig(
        code="JOIN_DETECTED",
        delta=-10,
        severity="MEDIUM",
        label="JOIN without verified index",
        explanation="Unverified join conditions may default to nested-loop block scans.",
    ),
    ScoreRuleConfig(
        code="SUBQUERY_DETECTED",
        delta=-10,
        severity="MEDIUM",
        label="Nested subquery",
        explanation="Subqueries can result in unmaterialized re-evaluation per row.",
    ),
    ScoreRuleConfig(
        code="MISSING_LIMIT",
        delta=-10,
        severity="MEDIUM",
        label="No LIMIT on large potential result",
        explanation="Unbounded queries risk client memory exhaustion and buffer saturation.",
    ),
    ScoreRuleConfig(
        code="LEADING_WILDCARD",
        delta=-10,
        severity="MEDIUM",
        label="Leading wildcard LIKE",
        explanation="Prefix wildcards (%term) defeat B-tree index seeks, causing full index scans.",
    ),
    ScoreRuleConfig(
        code="FUNCTION_ON_COLUMN",
        delta=-10,
        severity="MEDIUM",
        label="Function applied on WHERE column",
        explanation="Wrapping columns in functions (e.g. UPPER(col)) invalidates standard B-tree indexes.",
    ),
    ScoreRuleConfig(
        code="DISTINCT_WITH_JOIN",
        delta=-5,
        severity="LOW",
        label="SELECT DISTINCT with JOINs",
        explanation="DISTINCT with joins often masks Cartesian duplication and requires temp table deduplication.",
    ),
    ScoreRuleConfig(
        code="AGGREGATE_FULL_SCAN",
        delta=-10,
        severity="MEDIUM",
        label="Aggregate without filter",
        explanation="Aggregating all rows without a WHERE clause requires a complete table scan.",
    ),
    ScoreRuleConfig(
        code="CORRELATED_SUBQUERY",
        delta=-15,
        severity="HIGH",
        label="Correlated subquery in SELECT/WHERE",
        explanation="Inner subquery references outer table rows, forcing repeated O(N^2) evaluations.",
    ),
    ScoreRuleConfig(
        code="OR_DIFFERENT_COLUMNS",
        delta=-10,
        severity="MEDIUM",
        label="OR across different columns",
        explanation="OR conditions across distinct columns typically prevent single-index seeks.",
    ),
    ScoreRuleConfig(
        code="IMPLICIT_TYPE_CONVERSION",
        delta=-15,
        severity="HIGH",
        label="Implicit type conversion on column",
        explanation="Comparing string column to integer forces MySQL to cast the column, disabling index.",
    ),
    ScoreRuleConfig(
        code="NOT_IN_SUBQUERY",
        delta=-15,
        severity="HIGH",
        label="NOT IN with subquery (NULL trap)",
        explanation="NOT IN with subquery produces NULL-trap failures and suboptimal execution plans.",
    ),
    ScoreRuleConfig(
        code="ORDER_BY_RAND",
        delta=-20,
        severity="HIGH",
        label="ORDER BY RAND() full filesort",
        explanation="ORDER BY RAND() assigns random numbers to all rows and performs an expensive filesort.",
    ),
    ScoreRuleConfig(
        code="UNINDEXED_ORDER_BY",
        delta=-10,
        severity="MEDIUM",
        label="ORDER BY on unindexed column",
        explanation="Sorting rows without a matching index prefix forces an in-memory or disk filesort.",
    ),
    ScoreRuleConfig(
        code="LARGE_OFFSET",
        delta=-10,
        severity="MEDIUM",
        label="Deep OFFSET pagination scan",
        explanation="Large offsets force the database to read and discard thousands of rows before returning.",
    ),
    ScoreRuleConfig(
        code="MISSING_JOIN_CONDITION",
        delta=-25,
        severity="HIGH",
        label="Missing JOIN condition (Cartesian product)",
        explanation="Cartesian joins multiply table rows (M x N), producing catastrophic resource strain.",
    ),
    ScoreRuleConfig(
        code="NON_SARGABLE_ARITHMETIC",
        delta=-10,
        severity="MEDIUM",
        label="Non-sargable arithmetic on column",
        explanation="Arithmetic on columns (e.g. col + 10 > 100) disables B-tree range seek.",
    ),
    ScoreRuleConfig(
        code="HAVING_AS_WHERE",
        delta=-5,
        severity="LOW",
        label="HAVING filtering non-aggregate column",
        explanation="Filters on non-aggregated columns should be in WHERE to filter rows before grouping.",
    ),
    ScoreRuleConfig(
        code="COUNT_DISTINCT",
        delta=-5,
        severity="LOW",
        label="COUNT(DISTINCT) / column mismatch",
        explanation="COUNT(DISTINCT) collects values into temporary structures to deduplicate.",
    ),
    ScoreRuleConfig(
        code="UNION_INSTEAD_OF_UNION_ALL",
        delta=-10,
        severity="MEDIUM",
        label="UNION instead of UNION ALL",
        explanation="UNION uses temporary tables for duplicate elimination. Use UNION ALL if duplicates are acceptable.",
    ),
    ScoreRuleConfig(
        code="UPDATE_WITHOUT_WHERE",
        delta=-50,
        severity="CRITICAL",
        label="UPDATE without WHERE clause (Critical)",
        explanation="UPDATE without a WHERE clause updates every single row in the table.",
    ),
    ScoreRuleConfig(
        code="DELETE_WITHOUT_WHERE",
        delta=-50,
        severity="CRITICAL",
        label="DELETE without WHERE clause (Critical)",
        explanation="DELETE without a WHERE clause truncates/deletes every single row in the table.",
    ),
    ScoreRuleConfig(
        code="UPDATE_DELETE_UNINDEXED_WHERE",
        delta=-20,
        severity="HIGH",
        label="Unindexed WHERE filter (Lock escalation)",
        explanation="Updating/deleting with unindexed filters forces full table scan and holds exclusive locks on all rows.",
    ),
    ScoreRuleConfig(
        code="INSERT_SINGLE_ROW",
        delta=-5,
        severity="LOW",
        label="Single-row INSERT (Prefer bulk)",
        explanation="Single-row inserts in application loops incur high network round-trips and redo flushes.",
    ),
    ScoreRuleConfig(
        code="INSERT_SELECT_UNBOUNDED",
        delta=-20,
        severity="HIGH",
        label="Unbounded INSERT...SELECT (Massive write)",
        explanation="INSERT...SELECT without WHERE or LIMIT creates a massive atomic transaction and undo log surge.",
    ),
    ScoreRuleConfig(
        code="CTE_MULTIPLY_REFERENCED",
        delta=-10,
        severity="MEDIUM",
        label="CTE evaluated multiple times",
        explanation="In MySQL 8.0, CTEs are inlined unless materialized, risking duplicated compute.",
    ),
    ScoreRuleConfig(
        code="WINDOW_WITHOUT_PARTITION",
        delta=-10,
        severity="MEDIUM",
        label="Window function without PARTITION BY",
        explanation="Window functions without PARTITION BY process all rows in a single frame with global filesort.",
    ),
    # Bonuses
    ScoreRuleConfig(
        code="HAS_WHERE",
        delta=+10,
        severity="INFO",
        label="WHERE clause present",
        explanation="Row filtering condition reduces the working set.",
    ),
    ScoreRuleConfig(
        code="HAS_LIMIT",
        delta=+10,
        severity="INFO",
        label="LIMIT clause present",
        explanation="Limits result set size and memory allocation.",
    ),
    ScoreRuleConfig(
        code="HAS_GROUP_BY",
        delta=+5,
        severity="INFO",
        label="GROUP BY used",
        explanation="Explicit grouping defines clear aggregation boundaries.",
    ),
    ScoreRuleConfig(
        code="HAS_ORDER_BY",
        delta=+5,
        severity="INFO",
        label="ORDER BY used",
        explanation="Deterministic result ordering specified.",
    ),
    ScoreRuleConfig(
        code="SPECIFIC_COLUMNS",
        delta=+10,
        severity="INFO",
        label="Specific columns selected",
        explanation="Restricting projected columns conserves bandwidth and enables index-only scans.",
    ),
    ScoreRuleConfig(
        code="HAS_FILTER_COLS",
        delta=+5,
        severity="INFO",
        label="Filterable columns identified",
        explanation="Clear predicates can be matched against database indexes.",
    ),
    ScoreRuleConfig(
        code="INDEXED_FILTER_COLUMN",
        delta=+10,
        severity="INFO",
        label="Indexed filter column verified",
        explanation="Schema analysis confirmed an existing index matches the WHERE filter prefix.",
    ),
    ScoreRuleConfig(
        code="BULK_INSERT",
        delta=+15,
        severity="INFO",
        label="Bulk multi-row INSERT",
        explanation="Batching rows reduces transaction overhead and network latency.",
    ),
]

SCORE_RULES_DICT: dict[str, ScoreRuleConfig] = {r.code: r for r in SCORE_RULES_CATALOG}


# ---------------------------------------------------------------------------
# Statement-Specific Rules
# ---------------------------------------------------------------------------

STATEMENT_SCORE_RULES: dict[str, list[ScoreRuleConfig]] = {
    "UPDATE": [
        SCORE_RULES_DICT["UPDATE_WITHOUT_WHERE"],
        SCORE_RULES_DICT["UPDATE_DELETE_UNINDEXED_WHERE"],
        SCORE_RULES_DICT["NON_SARGABLE_ARITHMETIC"],
        SCORE_RULES_DICT["FUNCTION_ON_COLUMN"],
        ScoreRuleConfig("HAS_WHERE", +15, "INFO", "Specific row filter present", "Targeted update with WHERE"),
        ScoreRuleConfig("HAS_LIMIT", +5, "INFO", "LIMIT clause caps row updates", "LIMIT protects against runaway updates"),
    ],
    "DELETE": [
        SCORE_RULES_DICT["DELETE_WITHOUT_WHERE"],
        SCORE_RULES_DICT["UPDATE_DELETE_UNINDEXED_WHERE"],
        SCORE_RULES_DICT["NON_SARGABLE_ARITHMETIC"],
        SCORE_RULES_DICT["FUNCTION_ON_COLUMN"],
        ScoreRuleConfig("HAS_WHERE", +15, "INFO", "Specific row filter present", "Targeted delete with WHERE"),
        ScoreRuleConfig("HAS_LIMIT", +5, "INFO", "LIMIT clause caps deletions", "LIMIT protects against runaway deletes"),
    ],
    "INSERT": [
        SCORE_RULES_DICT["INSERT_SELECT_UNBOUNDED"],
        SCORE_RULES_DICT["INSERT_SINGLE_ROW"],
        SCORE_RULES_DICT["BULK_INSERT"],
        SCORE_RULES_DICT["HAS_WHERE"],
    ],
    "INSERT...SELECT": [
        SCORE_RULES_DICT["INSERT_SELECT_UNBOUNDED"],
        SCORE_RULES_DICT["SELECT_STAR"],
        ScoreRuleConfig("HAS_WHERE", +15, "INFO", "Source table filtered with WHERE", "Source rows filtered"),
        ScoreRuleConfig("HAS_LIMIT", +10, "INFO", "LIMIT caps transaction batch size", "Batch size bounded"),
    ],
}


# ---------------------------------------------------------------------------
# Schema-Aware Table Multipliers
# ---------------------------------------------------------------------------

def get_table_size_multiplier(estimated_rows: Optional[int]) -> float:
    """Return penalty multiplier based on estimated table row count.

    Multipliers:
    - Small table (<10,000 rows): 1.0x (standard baseline)
    - Medium table (10,000 to 1,000,000 rows): 1.5x (significant performance impact)
    - Large table (>1,000,000 rows): 2.0x (severe production impact)
    """
    if estimated_rows is None:
        return 1.0
    if estimated_rows > 1_000_000:
        return 2.0
    if estimated_rows >= 10_000:
        return 1.5
    return 1.0
