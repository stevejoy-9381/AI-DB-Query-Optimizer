"""Database connectivity, schema introspection, and EXPLAIN module for MySQL 8.x."""

from db.connection import DBConfig, build_engine, test_connection, close_engine
from db.explain import run_explain, parse_mysql_explain_json, validate_explainable_query
from db.schema import (
    ColumnInfo,
    IndexInfo,
    TableInfo,
    SchemaInfo,
    load_schema_from_db,
)

__all__ = [
    "DBConfig",
    "build_engine",
    "test_connection",
    "close_engine",
    "run_explain",
    "parse_mysql_explain_json",
    "validate_explainable_query",
    "ColumnInfo",
    "IndexInfo",
    "TableInfo",
    "SchemaInfo",
    "load_schema_from_db",
]
