"""Database connectivity, schema introspection, EXPLAIN, and benchmarking for MySQL 8.x."""

from db.benchmark import (
    BenchmarkComparison,
    BenchmarkMetrics,
    benchmark_query,
    compare_queries,
)
from db.connection import DBConfig, build_engine, close_engine, test_connection
from db.explain import parse_mysql_explain_json, run_explain, validate_explainable_query
from db.schema import (
    ColumnInfo,
    IndexInfo,
    SchemaInfo,
    TableInfo,
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
    "benchmark_query",
    "compare_queries",
    "BenchmarkMetrics",
    "BenchmarkComparison",
]
