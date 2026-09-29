"""tests/test_schema_parser.py
Unit tests for offline SQL DDL schema parser.
"""

import pytest

from db.schema_parser import load_sample_ddl_schema, parse_ddl_schema
from errors import SchemaParseError


def test_parse_single_create_table():
    sql = """
    CREATE TABLE users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) NOT NULL UNIQUE,
        email VARCHAR(100) NOT NULL,
        created_at DATETIME,
        INDEX idx_users_email (email)
    );
    """
    schema = parse_ddl_schema(sql, database_name="auth_db")
    assert schema.database == "auth_db"
    assert schema.source == "pasted"
    assert "users" in schema.tables

    tbl = schema.tables["users"]
    assert "id" in tbl.columns
    assert "username" in tbl.columns
    assert "email" in tbl.columns
    assert tbl.columns["username"].is_nullable is False

    # Check indexes
    assert "primary" in tbl.indexes
    assert any("email" in idx.columns for idx in tbl.indexes.values())


def test_parse_composite_primary_key_and_separate_index():
    sql = """
    CREATE TABLE order_items (
        order_id INT NOT NULL,
        item_id INT NOT NULL,
        price DECIMAL(10, 2),
        PRIMARY KEY (order_id, item_id)
    );
    CREATE INDEX idx_items_price ON order_items (price);
    """
    schema = parse_ddl_schema(sql)
    tbl = schema.tables["order_items"]
    assert "primary" in tbl.indexes
    assert tbl.indexes["primary"].columns == ["order_id", "item_id"]
    assert "idx_items_price" in tbl.indexes
    assert tbl.indexes["idx_items_price"].columns == ["price"]


def test_parse_empty_or_invalid_ddl():
    with pytest.raises(SchemaParseError):
        parse_ddl_schema("")

    with pytest.raises(SchemaParseError):
        parse_ddl_schema("SELECT * FROM foo;")

    with pytest.raises(SchemaParseError):
        parse_ddl_schema("NOT A VALID SQL STATEMENT AT ALL ###")


def test_load_sample_ddl_schema():
    schema = load_sample_ddl_schema()
    assert schema.database == "shop_db"
    assert schema.source == "pasted"
    assert "customers" in schema.tables
    assert "orders" in schema.tables
    assert "order_items" in schema.tables
    assert schema.tables["customers"].estimated_rows == 50_000
    assert schema.tables["orders"].estimated_rows == 200_000
