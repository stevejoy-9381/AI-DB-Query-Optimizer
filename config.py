"""
config.py
Configuration module and database dialect abstraction.

Provides centralized configuration for database dialects (default: MySQL 8.x)
with modular traits so additional dialects (such as PostgreSQL) can be supported
without rewriting core logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Dialect(str, Enum):
    """Supported database dialects."""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"


@dataclass(frozen=True)
class DialectConfig:
    """Encapsulates dialect-specific syntax, features, and defaults."""
    name: Dialect
    display_name: str
    target_version: str
    default_port: int
    explain_command: str
    supports_include_indexes: bool
    connection_poolers: list[str]
    access_types: list[str] = field(default_factory=list)
    cost_units_description: str = ""

    def format_covering_index(
        self,
        table: str,
        index_name: str,
        filter_col: str,
        projected_cols: list[str],
    ) -> str:
        """
        Generate DDL for a covering index according to dialect rules.

        In MySQL InnoDB, secondary indexes must include all covered columns in the
        index key definition itself (e.g. `CREATE INDEX ... ON tbl(col1, col2)`).
        PostgreSQL allows non-key payload columns via `INCLUDE (col2)`.
        """
        if self.supports_include_indexes:
            proj_str = ", ".join(projected_cols) if projected_cols else "col1, col2"
            return (
                f"-- PostgreSQL covering index with non-key payload columns:\n"
                f"CREATE INDEX {index_name}\n"
                f"    ON {table}({filter_col}) INCLUDE ({proj_str});"
            )

        # MySQL 8.x: Composite index with filter column leading, followed by projected columns
        all_cols = [filter_col] + [c for c in projected_cols if c != filter_col]
        cols_str = ", ".join(all_cols)
        return (
            f"-- MySQL 8.x covering index (InnoDB composite B-tree):\n"
            f"CREATE INDEX {index_name}\n"
            f"    ON {table}({cols_str});"
        )

    def format_fulltext_index(
        self,
        table: str,
        index_name: str,
        column: str,
    ) -> str:
        """Generate DDL for full-text index according to dialect rules."""
        if self.name == Dialect.POSTGRESQL:
            return (
                f"-- PostgreSQL full-text index using GIN:\n"
                f"CREATE INDEX {index_name} ON {table} USING gin(to_tsvector('english', {column}));"
            )

        # MySQL 8.x InnoDB FULLTEXT index
        return (
            f"-- MySQL 8.x InnoDB full-text index:\n"
            f"ALTER TABLE {table} ADD FULLTEXT INDEX {index_name} ({column});"
        )


# ---------------------------------------------------------------------------
# Pre-configured dialect registry
# ---------------------------------------------------------------------------

DIALECT_REGISTRY: dict[Dialect, DialectConfig] = {
    Dialect.MYSQL: DialectConfig(
        name=Dialect.MYSQL,
        display_name="MySQL",
        target_version="8.0+",
        default_port=3306,
        explain_command="EXPLAIN FORMAT=JSON",
        supports_include_indexes=False,
        connection_poolers=["ProxySQL", "MySQL Router", "application-level pooling"],
        access_types=["const", "eq_ref", "ref", "range", "index", "ALL"],
        cost_units_description="MySQL cost model (memory_block_read_cost=0.25, io_block_read_cost=1.0, row_eval=0.10)",
    ),
    Dialect.POSTGRESQL: DialectConfig(
        name=Dialect.POSTGRESQL,
        display_name="PostgreSQL",
        target_version="15+",
        default_port=5432,
        explain_command="EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)",
        supports_include_indexes=True,
        connection_poolers=["PgBouncer", "pgpool-II"],
        access_types=["Seq Scan", "Index Scan", "Bitmap Index Scan", "Index Only Scan"],
        cost_units_description="PostgreSQL cost model (seq_page_cost=1.0, random_page_cost=4.0, cpu_tuple_cost=0.01)",
    ),
}

# Active dialect setting (default: MySQL 8.x)
_ACTIVE_DIALECT: Dialect = Dialect.MYSQL


def get_current_dialect() -> Dialect:
    """Return the active dialect enum."""
    return _ACTIVE_DIALECT


def get_dialect_config(dialect: Dialect | str | None = None) -> DialectConfig:
    """Return configuration for the requested or currently active dialect."""
    if dialect is None:
        target = _ACTIVE_DIALECT
    elif isinstance(dialect, Dialect):
        target = dialect
    else:
        try:
            target = Dialect(dialect.lower().strip())
        except ValueError:
            logger.warning("Unknown dialect '%s', falling back to MySQL", dialect)
            target = Dialect.MYSQL

    return DIALECT_REGISTRY[target]


def set_dialect(dialect: Dialect | str) -> None:
    """Set the active dialect for query analysis and recommendations."""
    global _ACTIVE_DIALECT
    if isinstance(dialect, Dialect):
        _ACTIVE_DIALECT = dialect
    else:
        try:
            _ACTIVE_DIALECT = Dialect(dialect.lower().strip())
        except ValueError as err:
            valid = ", ".join(d.value for d in Dialect)
            raise ValueError(f"Invalid dialect '{dialect}'. Supported dialects: {valid}") from err
    logger.info("Active dialect set to: %s", _ACTIVE_DIALECT.value)


def is_mysql() -> bool:
    """Convenience helper to check if active dialect is MySQL."""
    return _ACTIVE_DIALECT == Dialect.MYSQL
