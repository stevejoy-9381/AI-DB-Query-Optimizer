"""Tests for db/schema.py and schema-aware analysis and recommendations."""

import pytest

from analyzer import analyze_query
from db.schema import ColumnInfo, IndexInfo, SchemaInfo, TableInfo
from recommendations import generate_index_recommendations
from scoring import compute_score


@pytest.fixture
def sample_schema() -> SchemaInfo:
    """Hand-built SchemaInfo representing a realistic e-commerce shop_db."""
    schema = SchemaInfo(database="shop_db")

    # Table: customers
    customers = TableInfo(name="customers", estimated_rows=50_000, data_length_bytes=4_000_000)
    customers.columns = {
        "id": ColumnInfo("id", "int", is_nullable=False, ordinal_position=1),
        "name": ColumnInfo("name", "varchar(100)", is_nullable=False, ordinal_position=2),
        "email": ColumnInfo("email", "varchar(150)", is_nullable=False, ordinal_position=3),
    }
    customers.indexes = {
        "primary": IndexInfo("PRIMARY", "customers", ["id"], is_unique=True, is_primary=True),
        "idx_cust_email": IndexInfo("idx_cust_email", "customers", ["email"], is_unique=True),
    }
    schema.tables["customers"] = customers

    # Table: orders
    orders = TableInfo(name="orders", estimated_rows=200_000, data_length_bytes=24_000_000)
    orders.columns = {
        "id": ColumnInfo("id", "int", is_nullable=False, ordinal_position=1),
        "customer_id": ColumnInfo("customer_id", "int", is_nullable=False, ordinal_position=2),
        "order_date": ColumnInfo("order_date", "datetime", is_nullable=False, ordinal_position=3),
        "total_amount": ColumnInfo("total_amount", "decimal(10,2)", is_nullable=False, ordinal_position=4),
        "status": ColumnInfo("status", "varchar(20)", is_nullable=False, ordinal_position=5),
    }
    orders.indexes = {
        "primary": IndexInfo("PRIMARY", "orders", ["id"], is_unique=True, is_primary=True),
        # Composite index on (customer_id, order_date)
        "idx_orders_cust_date": IndexInfo(
            "idx_orders_cust_date", "orders", ["customer_id", "order_date"], is_unique=False
        ),
    }
    schema.tables["orders"] = orders

    return schema


def test_index_prefix_coverage():
    """Verify leftmost-prefix index coverage rule logic."""
    idx = IndexInfo("idx_test", "orders", ["customer_id", "order_date", "status"])

    # Leftmost prefixes: valid
    assert idx.covers_prefix(["customer_id"])
    assert idx.covers_prefix(["customer_id", "order_date"])
    assert idx.covers_prefix(["customer_id", "order_date", "status"])

    # Not leftmost prefix: invalid
    assert not idx.covers_prefix(["order_date"])
    assert not idx.covers_prefix(["status"])
    assert not idx.covers_prefix(["order_date", "status"])
    assert not idx.covers_prefix([])


def test_table_has_index_for_prefix(sample_schema):
    """Verify TableInfo.has_index_for_prefix detects exact matches and prefixes."""
    orders = sample_schema.get_table("orders")
    assert orders is not None

    # Primary key prefix
    covered, name, reason = orders.has_index_for_prefix(["id"])
    assert covered is True
    assert name == "PRIMARY"

    # Composite index prefix
    covered, name, reason = orders.has_index_for_prefix(["customer_id"])
    assert covered is True
    assert name == "idx_orders_cust_date"

    # Unindexed column
    covered, name, reason = orders.has_index_for_prefix(["total_amount"])
    assert covered is False
    assert name is None


def test_schema_validate_reference(sample_schema):
    """Verify schema table and column reference validation."""
    ok, err = sample_schema.validate_reference("orders", "customer_id")
    assert ok is True
    assert err is None

    # Missing table
    ok, err = sample_schema.validate_reference("nonexistent")
    assert not ok
    assert "does not exist in schema" in err

    # Missing column in existing table
    ok, err = sample_schema.validate_reference("orders", "fake_col")
    assert not ok
    assert "Column `fake_col` does not exist" in err


def test_analyzer_with_schema_unknown_table(sample_schema):
    """Verify analyzer flags unknown table when schema is provided."""
    query = "SELECT * FROM missing_table WHERE id = 10"
    report = analyze_query(query, schema=sample_schema)
    assert report["schema_validated"] is True
    assert "missing_table" in report["unknown_tables"]
    assert any(i["code"] == "UNKNOWN_TABLE" for i in report["issues"])


def test_analyzer_with_schema_unknown_column(sample_schema):
    """Verify analyzer flags unknown column when qualified with table name."""
    query = "SELECT orders.invalid_col FROM orders WHERE orders.id = 1"
    report = analyze_query(query, schema=sample_schema)
    assert report["schema_validated"] is True
    assert "orders.invalid_col" in report["unknown_columns"]
    assert any(i["code"] == "UNKNOWN_COLUMN" for i in report["issues"])


def test_analyzer_offline_mode_without_schema():
    """Verify analyzer functions identically with schema=None."""
    query = "SELECT * FROM orders WHERE customer_id = 10"
    report = analyze_query(query, schema=None)
    assert report["schema_validated"] is False
    assert report["unknown_tables"] == []
    assert report["unknown_columns"] == []


def test_recommendations_skip_already_indexed_column(sample_schema):
    """Verify recommendations engine skips columns covered by existing indexes."""
    # Query on customer_id, which is already covered by idx_orders_cust_date
    query = "SELECT * FROM orders WHERE customer_id = 10"
    analysis = analyze_query(query, schema=sample_schema)

    # With schema: index on customer_id is skipped!
    recs_with_schema = generate_index_recommendations(query, analysis, schema=sample_schema)
    assert not any("idx_orders_customer_id" in r["index_name"] for r in recs_with_schema)

    # Without schema: recommended as usual
    recs_offline = generate_index_recommendations(query, analysis, schema=None)
    assert any("idx_orders_customer_id" in r["index_name"] for r in recs_offline)


def test_recommendations_generates_for_unindexed_column(sample_schema):
    """Verify recommendations engine still generates index for unindexed columns."""
    query = "SELECT * FROM orders WHERE total_amount > 100.00"
    analysis = analyze_query(query, schema=sample_schema)
    recs = generate_index_recommendations(query, analysis, schema=sample_schema)
    assert any("total_amount" in r["index_name"] for r in recs)


def test_scoring_receives_schema_row_counts(sample_schema):
    """Verify scoring exposes schema table row counts."""
    query = "SELECT * FROM orders"
    analysis = analyze_query(query, schema=sample_schema)
    score_breakdown = compute_score(analysis, schema=sample_schema)
    assert score_breakdown.table_row_counts.get("orders") == 200_000
    assert score_breakdown.table_row_counts.get("customers") == 50_000
