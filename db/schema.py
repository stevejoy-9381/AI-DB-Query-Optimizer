"""Schema introspection and metadata models for MySQL 8.x."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


@dataclass
class ColumnInfo:
    """Metadata for a table column."""

    name: str
    data_type: str
    is_nullable: bool = True
    column_default: str | None = None
    ordinal_position: int = 1


@dataclass
class IndexInfo:
    """Metadata for an existing table index."""

    name: str
    table_name: str
    columns: list[str] = field(default_factory=list)  # Ordered index column parts
    is_unique: bool = False
    is_primary: bool = False
    index_type: str = "BTREE"
    cardinality: int | None = None

    def covers_prefix(self, cols: list[str]) -> bool:
        """Check if this index covers the specified column list as a leftmost prefix.

        MySQL B-tree indexes satisfy queries on prefix (col1, col2) if index is (col1, col2, col3).
        """
        if not cols or not self.columns:
            return False
        clean_target = [c.lower() for c in cols]
        clean_index = [c.lower() for c in self.columns]
        if len(clean_target) > len(clean_index):
            return False
        return clean_index[:len(clean_target)] == clean_target

    def is_exact_match(self, cols: list[str]) -> bool:
        """Check if index has the exact same columns in the same order."""
        return [c.lower() for c in self.columns] == [c.lower() for c in cols]


@dataclass
class TableInfo:
    """Metadata for a database table."""

    name: str
    columns: dict[str, ColumnInfo] = field(default_factory=dict)  # Keyed by lowercase column name
    indexes: dict[str, IndexInfo] = field(default_factory=dict)    # Keyed by lowercase index name
    estimated_rows: int = 0
    data_length_bytes: int = 0

    def get_column(self, col_name: str) -> ColumnInfo | None:
        """Retrieve column by case-insensitive name."""
        return self.columns.get(col_name.lower())

    def has_index_for_prefix(self, cols: list[str]) -> tuple[bool, str | None, str]:
        """Check if any index on this table covers the columns as a leftmost prefix.

        Returns:
            Tuple of (is_covered, index_name_or_None, reason_description).
        """
        clean_cols = [c.lower() for c in cols]
        for idx in self.indexes.values():
            if idx.is_exact_match(clean_cols):
                return True, idx.name, f"Identical index `{idx.name}` ({', '.join(idx.columns)}) already exists."
            if idx.covers_prefix(clean_cols):
                return True, idx.name, (
                    f"Composite index `{idx.name}` ({', '.join(idx.columns)}) already covers "
                    f"({', '.join(cols)}) via leftmost prefix."
                )
        return False, None, "No covering index found."


@dataclass
class SchemaInfo:
    """Complete metadata for a database schema."""

    database: str
    tables: dict[str, TableInfo] = field(default_factory=dict)  # Keyed by lowercase table name

    def get_table(self, table_name: str) -> TableInfo | None:
        """Retrieve table metadata by case-insensitive name."""
        return self.tables.get(table_name.lower())

    def validate_reference(
        self,
        table_name: str,
        col_name: str | None = None,
    ) -> tuple[bool, str | None]:
        """Validate if a table (and optional column) exists in the schema.

        Returns:
            Tuple of (is_valid, error_reason_if_invalid).
        """
        tbl = self.get_table(table_name)
        if tbl is None:
            return False, f"Table `{table_name}` does not exist in schema `{self.database}`."
        if col_name is not None and tbl.get_column(col_name) is None:
            return False, f"Column `{col_name}` does not exist in table `{table_name}`."
        return True, None


def load_schema_from_db(engine: Engine, database: str) -> SchemaInfo:
    """Introspect tables, columns, and indexes from MySQL information_schema.

    Args:
        engine: Connected SQLAlchemy Engine.
        database: Database name to inspect.

    Returns:
        Populated SchemaInfo object.
    """
    schema = SchemaInfo(database=database)

    with engine.connect() as conn:
        # 1. Fetch tables
        tables_sql = text("""
            SELECT TABLE_NAME, TABLE_ROWS, DATA_LENGTH
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = :db AND TABLE_TYPE = 'BASE TABLE'
        """)
        for row in conn.execute(tables_sql, {"db": database}):
            t_name = str(row[0])
            t_rows = int(row[1]) if row[1] is not None else 0
            t_data = int(row[2]) if row[2] is not None else 0
            schema.tables[t_name.lower()] = TableInfo(
                name=t_name,
                estimated_rows=t_rows,
                data_length_bytes=t_data,
            )

        # 2. Fetch columns
        cols_sql = text("""
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, ORDINAL_POSITION
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :db
            ORDER BY TABLE_NAME, ORDINAL_POSITION
        """)
        for row in conn.execute(cols_sql, {"db": database}):
            t_name = str(row[0]).lower()
            if t_name in schema.tables:
                col_name = str(row[1])
                schema.tables[t_name].columns[col_name.lower()] = ColumnInfo(
                    name=col_name,
                    data_type=str(row[2]),
                    is_nullable=(str(row[3]).upper() == "YES"),
                    column_default=str(row[4]) if row[4] is not None else None,
                    ordinal_position=int(row[5]) if row[5] is not None else 1,
                )

        # 3. Fetch indexes
        idx_sql = text("""
            SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX, NON_UNIQUE, INDEX_TYPE, CARDINALITY
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = :db
            ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
        """)
        for row in conn.execute(idx_sql, {"db": database}):
            t_name = str(row[0]).lower()
            if t_name in schema.tables:
                idx_name = str(row[1])
                col_name = str(row[2])
                non_unique = bool(row[4])
                idx_type = str(row[5]) if row[5] else "BTREE"
                card = int(row[6]) if row[6] is not None else None

                tbl = schema.tables[t_name]
                idx_key = idx_name.lower()
                if idx_key not in tbl.indexes:
                    tbl.indexes[idx_key] = IndexInfo(
                        name=idx_name,
                        table_name=tbl.name,
                        columns=[],
                        is_unique=(not non_unique),
                        is_primary=(idx_name.upper() == "PRIMARY"),
                        index_type=idx_type,
                        cardinality=card,
                    )
                tbl.indexes[idx_key].columns.append(col_name)

    logger.info("Successfully loaded schema for database '%s' with %d tables.", database, len(schema.tables))
    return schema
