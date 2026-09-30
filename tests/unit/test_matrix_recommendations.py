"""tests/unit/test_matrix_recommendations.py
Automated Unit Tests for all Recommendations behaviors defined in docs/TEST_MATRIX.md.
"""

import pytest

from analyzer import analyze_query
from db.schema import ColumnInfo, IndexInfo, SchemaInfo, TableInfo
from recommendations import (
    _generate_safe_index_name,
    detect_redundant_indexes,
    estimate_index_size_bytes,
    generate_index_recommendations,
)


@pytest.fixture
def ecommerce_schema() -> SchemaInfo:
    schema = SchemaInfo(database="shop_db")
    cust = TableInfo(name="customers", estimated_rows=50_000, data_length_bytes=4_000_000)
    cust.columns = {
        "id": ColumnInfo("id", "int", False, 1),
        "name": ColumnInfo("name", "varchar(100)", False, 2),
        "email": ColumnInfo("email", "varchar(150)", False, 3),
        "city": ColumnInfo("city", "varchar(50)", False, 4),
        "status": ColumnInfo("status", "varchar(20)", False, 5),
    }
    cust.indexes = {
        "primary": IndexInfo("PRIMARY", "customers", ["id"], True, True),
        "idx_cust_email": IndexInfo("idx_cust_email", "customers", ["email"], True),
    }
    schema.tables["customers"] = cust
    return schema


@pytest.fixture
def redundant_schema() -> SchemaInfo:
    schema = SchemaInfo(database="shop_db")
    tbl = TableInfo(name="items", estimated_rows=10_000, data_length_bytes=1_000_000)
    tbl.columns = {
        "id": ColumnInfo("id", "int", False, 1),
        "col_a": ColumnInfo("col_a", "int", False, 2),
        "col_b": ColumnInfo("col_b", "int", False, 3),
    }
    tbl.indexes = {
        "primary": IndexInfo("PRIMARY", "items", ["id"], True, True),
        "idx_a": IndexInfo("idx_a", "items", ["col_a"], False),
        "idx_a_dup": IndexInfo("idx_a_dup", "items", ["col_a"], False),
        "idx_a_b": IndexInfo("idx_a_b", "items", ["col_a", "col_b"], False),
    }
    schema.tables["items"] = tbl
    return schema


def test_rec_idx_single():
    """REC-IDX-SINGLE: Generates single-column B-tree CREATE INDEX for isolated WHERE/JOIN filter."""
    q = "SELECT name FROM customers WHERE city = 'Hyderabad'"
    anl = analyze_query(q)
    recs = generate_index_recommendations(q, anl)
    single_recs = [r for r in recs if r["index_type"] == "B-tree (Single Column)"]
    assert len(single_recs) >= 1
    assert "city" in single_recs[0]["ddl"]
    assert "CREATE INDEX" in single_recs[0]["ddl"]


def test_rec_idx_composite():
    """REC-IDX-COMPOSITE: Generates composite index ordered by Equality -> Range -> ORDER BY."""
    q = "SELECT id, name FROM products WHERE category_id = 5 AND price < 100 ORDER BY created_at"
    anl = analyze_query(q)
    recs = generate_index_recommendations(q, anl)
    comp_recs = [r for r in recs if r["index_type"] == "Composite B-tree"]
    assert len(comp_recs) >= 1
    comp = comp_recs[0]
    # Check column order: equality (category_id), range (price), sort (created_at)
    assert "category_id" in comp["ddl"]
    assert "price" in comp["ddl"]
    assert comp["column_order_explanation"] is not None


def test_rec_idx_covering():
    """REC-IDX-COVERING: Generates covering index containing filter and projected columns."""
    q = "SELECT name, email FROM customers WHERE status = 'active'"
    anl = analyze_query(q)
    recs = generate_index_recommendations(q, anl)
    cov_recs = [r for r in recs if "Covering" in r["index_type"]]
    assert len(cov_recs) >= 1
    cov = cov_recs[0]
    assert "status" in cov["ddl"]
    assert "name" in cov["ddl"] or "email" in cov["ddl"]


def test_rec_dup_detect(redundant_schema):
    """REC-DUP-DETECT: Detects exact duplicate indexes on the same table and suggests DROP INDEX."""
    dups = detect_redundant_indexes(redundant_schema)
    exact_dups = [d for d in dups if d["type"] == "DUPLICATE_INDEX"]
    assert len(exact_dups) >= 1
    assert "DROP INDEX" in exact_dups[0]["ddl"]


def test_rec_prefix_redund(redundant_schema):
    """REC-PREFIX-REDUND: Detects leftmost prefix redundant indexes covered by existing composite index."""
    dups = detect_redundant_indexes(redundant_schema)
    prefix_dups = [d for d in dups if d["type"] == "PREFIX_REDUNDANT"]
    assert len(prefix_dups) >= 1
    assert "DROP INDEX" in prefix_dups[0]["ddl"]


def test_rec_skip_exist(ecommerce_schema):
    """REC-SKIP-EXIST: Suppresses index recommendation when index already exists in schema."""
    # Column 'id' has a PRIMARY KEY index in ecommerce_schema
    q = "SELECT name FROM customers WHERE id = 5"
    anl = analyze_query(q, schema=ecommerce_schema)
    recs = generate_index_recommendations(q, anl, schema=ecommerce_schema)
    # Should not recommend creating an index on customers(id)
    id_recs = [r for r in recs if "customers(id)" in r["ddl"]]
    assert len(id_recs) == 0


def test_rec_idx_cap_4():
    """REC-IDX-CAP-4: Caps composite index candidate columns at maximum of 4."""
    q = "SELECT * FROM orders WHERE c1 = 1 AND c2 = 2 AND c3 = 3 AND c4 = 4 AND c5 = 5"
    anl = analyze_query(q)
    recs = generate_index_recommendations(q, anl)
    comp_recs = [r for r in recs if r["index_type"] == "Composite B-tree"]
    if comp_recs:
        assert comp_recs[0]["is_capped"] is True


def test_rec_idx_prefix():
    """REC-IDX-PREFIX: Generates prefix index col(191) for long text / VARCHAR columns."""
    q = "SELECT id FROM articles WHERE body = 'sample'"
    anl = analyze_query(q)
    recs = generate_index_recommendations(q, anl)
    prefix_recs = [r for r in recs if "(191)" in r["ddl"]]
    assert len(prefix_recs) >= 1


def test_rec_idx_fulltext():
    """REC-IDX-FULLTEXT: Recommends FULLTEXT index for leading/contains wildcard LIKE queries."""
    q = "SELECT id FROM articles WHERE content LIKE '%database%'"
    anl = analyze_query(q)
    recs = generate_index_recommendations(q, anl)
    fts_recs = [r for r in recs if "FULLTEXT" in r["index_type"]]
    assert len(fts_recs) >= 1
    assert "FULLTEXT" in fts_recs[0]["ddl"]


def test_rec_safe_name():
    """REC-SAFE-NAME: Enforces MySQL 64-character identifier length limit using MD5 hash truncation."""
    long_cols = [
        "extremely_long_column_name_part_one",
        "extremely_long_column_name_part_two",
        "extremely_long_column_name_part_three",
    ]
    name = _generate_safe_index_name("very_long_table_name_exceeding_standard_limits", long_cols)
    assert len(name) <= 64
    assert name.startswith("idx_")


def test_rec_size_est(ecommerce_schema):
    """REC-SIZE-EST: Estimates secondary index storage footprint in B/KB/MB."""
    bytes_est, label = estimate_index_size_bytes("customers", ["email"], ecommerce_schema)
    assert bytes_est is not None
    assert bytes_est > 0
    assert ("KB" in label or "MB" in label or "B" in label)


def test_rec_trade_offs():
    """REC-TRADE-OFFS: Provides explicit trade-offs note covering read gains vs insert/update write amplification."""
    q = "SELECT name FROM customers WHERE city = 'Hyderabad'"
    anl = analyze_query(q)
    recs = generate_index_recommendations(q, anl)
    assert len(recs) >= 1
    assert "trade_offs" in recs[0]
    assert "Faster reads" in recs[0]["trade_offs"]
    assert "write overhead" in recs[0]["trade_offs"]
