"""
tests/conftest.py
Global test configuration and reusable fixtures for the SQL Query Optimizer test suite.
"""

from __future__ import annotations

import os
import pytest
from sqlalchemy import create_engine

from config import Dialect, set_dialect
from db.schema import ColumnInfo, IndexInfo, SchemaInfo, TableInfo


@pytest.fixture(autouse=True)
def default_dialect():
    """Ensure tests run under MySQL dialect by default."""
    set_dialect(Dialect.MYSQL)
    yield
    set_dialect(Dialect.MYSQL)


@pytest.fixture
def sample_schema() -> SchemaInfo:
    """Fixture providing a complete, realistic e-commerce SchemaInfo structure."""
    schema = SchemaInfo(database="shop_db")

    # 1. users table
    users = TableInfo(name="users", estimated_rows=100_000, data_length_bytes=10_485_760)
    users.columns["id"] = ColumnInfo(name="id", data_type="int", is_nullable=False, ordinal_position=1)
    users.columns["email"] = ColumnInfo(name="email", data_type="varchar(255)", is_nullable=False, ordinal_position=2)
    users.columns["created_at"] = ColumnInfo(name="created_at", data_type="datetime", is_nullable=False, ordinal_position=3)
    users.columns["status"] = ColumnInfo(name="status", data_type="varchar(32)", is_nullable=False, ordinal_position=4)
    users.indexes["primary"] = IndexInfo(name="PRIMARY", table_name="users", columns=["id"], is_primary=True, is_unique=True)
    users.indexes["idx_users_email"] = IndexInfo(name="idx_users_email", table_name="users", columns=["email"], is_unique=True)
    schema.tables["users"] = users

    # 2. orders table
    orders = TableInfo(name="orders", estimated_rows=500_000, data_length_bytes=52_428_800)
    orders.columns["id"] = ColumnInfo(name="id", data_type="int", is_nullable=False, ordinal_position=1)
    orders.columns["user_id"] = ColumnInfo(name="user_id", data_type="int", is_nullable=False, ordinal_position=2)
    orders.columns["order_date"] = ColumnInfo(name="order_date", data_type="datetime", is_nullable=False, ordinal_position=3)
    orders.columns["total"] = ColumnInfo(name="total", data_type="decimal(10,2)", is_nullable=False, ordinal_position=4)
    orders.columns["status"] = ColumnInfo(name="status", data_type="varchar(32)", is_nullable=False, ordinal_position=5)
    orders.indexes["primary"] = IndexInfo(name="PRIMARY", table_name="orders", columns=["id"], is_primary=True, is_unique=True)
    orders.indexes["idx_orders_user_id"] = IndexInfo(name="idx_orders_user_id", table_name="orders", columns=["user_id"])
    orders.indexes["idx_orders_status_date"] = IndexInfo(name="idx_orders_status_date", table_name="orders", columns=["status", "order_date"])
    schema.tables["orders"] = orders

    # 3. products table
    products = TableInfo(name="products", estimated_rows=10_000, data_length_bytes=2_097_152)
    products.columns["id"] = ColumnInfo(name="id", data_type="int", is_nullable=False, ordinal_position=1)
    products.columns["title"] = ColumnInfo(name="title", data_type="varchar(255)", is_nullable=False, ordinal_position=2)
    products.columns["category_id"] = ColumnInfo(name="category_id", data_type="int", is_nullable=False, ordinal_position=3)
    products.columns["price"] = ColumnInfo(name="price", data_type="decimal(10,2)", is_nullable=False, ordinal_position=4)
    products.columns["description"] = ColumnInfo(name="description", data_type="text", is_nullable=True, ordinal_position=5)
    products.indexes["primary"] = IndexInfo(name="PRIMARY", table_name="products", columns=["id"], is_primary=True, is_unique=True)
    products.indexes["idx_products_category"] = IndexInfo(name="idx_products_category", table_name="products", columns=["category_id"])
    schema.tables["products"] = products

    return schema


@pytest.fixture
def fake_engine():
    """In-memory SQLite engine for offline database testing."""
    engine = create_engine("sqlite:///:memory:")
    yield engine
    engine.dispose()
