"""db/schema_parser.py
Parses CREATE TABLE and CREATE INDEX DDL statements using sqlglot AST
into SchemaInfo objects for offline, schema-aware analysis and recommendations.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import sqlglot
from sqlglot import exp

from db.schema import ColumnInfo, IndexInfo, SchemaInfo, TableInfo
from errors import SchemaParseError

logger = logging.getLogger(__name__)


def _extract_column_name(node: exp.Expression) -> str:
    """Helper to extract a clean string column name from various AST node structures."""
    if isinstance(node, exp.Ordered):
        node = node.this
    if isinstance(node, exp.Column):
        node = node.this
    if hasattr(node, "name"):
        return str(node.name).strip("`'\"")
    if hasattr(node, "this"):
        return str(node.this).strip("`'\"")
    return str(node).strip("`'\"")


def parse_ddl_schema(
    ddl_sql: str,
    database_name: str = "pasted_schema",
    dialect: str = "mysql",
) -> SchemaInfo:
    """Parse one or more CREATE TABLE and CREATE INDEX statements into SchemaInfo.

    Args:
        ddl_sql: String containing raw SQL DDL statements.
        database_name: Logical schema name.
        dialect: SQL dialect for sqlglot (default: mysql).

    Returns:
        SchemaInfo: Populated schema metadata marked with source='pasted'.

    Raises:
        SchemaParseError: If syntax is invalid or no valid table definitions found.
    """
    if not ddl_sql or not ddl_sql.strip():
        raise SchemaParseError("Schema SQL cannot be empty.")

    try:
        parsed_statements = sqlglot.parse(ddl_sql, read=dialect)
    except Exception as exc:
        raise SchemaParseError(
            f"Failed to parse DDL statements: {exc}",
            details=str(exc),
        ) from exc

    tables: dict[str, TableInfo] = {}

    for stmt in parsed_statements:
        if not stmt:
            continue

        if isinstance(stmt, exp.Create):
            target = stmt.this

            # 1. CREATE TABLE
            if isinstance(target, exp.Schema):
                raw_table = target.this
                table_name = raw_table.name if hasattr(raw_table, "name") else str(raw_table)
                table_name_clean = table_name.strip("`'\"")
                lower_tbl = table_name_clean.lower()

                if lower_tbl not in tables:
                    tables[lower_tbl] = TableInfo(name=table_name_clean)

                table_info = tables[lower_tbl]
                col_ordinal = 1

                for item in target.expressions:
                    # Column Definition
                    if isinstance(item, exp.ColumnDef):
                        raw_col = item.this
                        col_name = raw_col.name if hasattr(raw_col, "name") else str(raw_col)
                        col_name_clean = col_name.strip("`'\"")
                        data_type = item.kind.sql(dialect=dialect) if item.kind else "VARCHAR(255)"

                        is_nullable = True
                        is_pk = False

                        for constraint in item.constraints or []:
                            c_kind = constraint.kind
                            if isinstance(c_kind, exp.NotNullColumnConstraint):
                                is_nullable = False
                            elif isinstance(c_kind, exp.PrimaryKeyColumnConstraint):
                                is_pk = True
                                is_nullable = False
                            elif isinstance(c_kind, exp.UniqueColumnConstraint):
                                idx_name = f"uq_{lower_tbl}_{col_name_clean.lower()}"
                                table_info.indexes[idx_name] = IndexInfo(
                                    name=idx_name,
                                    table_name=table_name_clean,
                                    columns=[col_name_clean],
                                    is_unique=True,
                                )

                        table_info.columns[col_name_clean.lower()] = ColumnInfo(
                            name=col_name_clean,
                            data_type=data_type,
                            is_nullable=is_nullable,
                            ordinal_position=col_ordinal,
                        )
                        col_ordinal += 1

                        if is_pk:
                            pk_idx = IndexInfo(
                                name="PRIMARY",
                                table_name=table_name_clean,
                                columns=[col_name_clean],
                                is_unique=True,
                                is_primary=True,
                            )
                            table_info.indexes["primary"] = pk_idx

                    # Table Constraint: PRIMARY KEY (col1, col2)
                    elif isinstance(item, exp.PrimaryKey):
                        pk_cols = [_extract_column_name(c) for c in item.expressions]
                        table_info.indexes["primary"] = IndexInfo(
                            name="PRIMARY",
                            table_name=table_name_clean,
                            columns=pk_cols,
                            is_unique=True,
                            is_primary=True,
                        )

                    # Table Constraint: UNIQUE KEY / INDEX
                    elif isinstance(item, exp.UniqueColumnConstraint):
                        schema_node = item.this
                        idx_name = f"uq_{lower_tbl}"
                        uq_cols = []
                        if isinstance(schema_node, exp.Schema):
                            if hasattr(schema_node.this, "name"):
                                idx_name = str(schema_node.this.name).strip("`'\"")
                            uq_cols = [_extract_column_name(c) for c in schema_node.expressions]
                        table_info.indexes[idx_name.lower()] = IndexInfo(
                            name=idx_name,
                            table_name=table_name_clean,
                            columns=uq_cols,
                            is_unique=True,
                        )

                    # Table Constraint: KEY / INDEX (col1, col2)
                    elif isinstance(item, exp.IndexColumnConstraint):
                        idx_name = item.this.name if hasattr(item.this, "name") else f"idx_{lower_tbl}"
                        idx_cols = [_extract_column_name(c) for c in item.expressions]
                        table_info.indexes[idx_name.lower()] = IndexInfo(
                            name=idx_name,
                            table_name=table_name_clean,
                            columns=idx_cols,
                            is_unique=False,
                        )

            # 2. Standalone CREATE [UNIQUE] INDEX
            elif isinstance(target, exp.Index):
                raw_idx = target.this
                idx_name = raw_idx.name if hasattr(raw_idx, "name") else "idx"
                table_target = target.args.get("table") or target.find(exp.Table)
                if table_target:
                    tbl_name = table_target.name.strip("`'\"")
                    lower_tbl = tbl_name.lower()
                    if lower_tbl not in tables:
                        tables[lower_tbl] = TableInfo(name=tbl_name)

                    params = target.args.get("params")
                    col_nodes = params.args.get("columns", []) if params else target.expressions
                    cols = [_extract_column_name(c) for c in col_nodes]
                    is_unique = "UNIQUE" in stmt.sql().upper()

                    tables[lower_tbl].indexes[idx_name.lower()] = IndexInfo(
                        name=idx_name,
                        table_name=tbl_name,
                        columns=cols,
                        is_unique=is_unique,
                    )

    if not tables:
        raise SchemaParseError("No valid CREATE TABLE or CREATE INDEX statements found in input.")

    return SchemaInfo(
        database=database_name,
        tables=tables,
        source="pasted",
    )


def load_sample_ddl_schema(file_path: Optional[str] = None) -> SchemaInfo:
    """Load the built-in shop_db schema DDL directly without a live database.

    Args:
        file_path: Path to SQL schema file. Defaults to sql/schema.sql.

    Returns:
        SchemaInfo: Parsed schema metadata with realistic estimated row counts.
    """
    if not file_path:
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sql", "schema.sql")

    if not os.path.exists(file_path):
        file_path = os.path.join("sql", "schema.sql")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    schema = parse_ddl_schema(content, database_name="shop_db")

    row_estimates = {
        "customers": 50_000,
        "products": 10_000,
        "orders": 200_000,
        "order_items": 500_000,
        "product_categories": 100,
        "audit_logs": 100_000,
    }
    for tbl_name, rows in row_estimates.items():
        if tbl_name in schema.tables:
            schema.tables[tbl_name].estimated_rows = rows

    return schema
