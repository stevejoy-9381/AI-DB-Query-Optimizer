"""
tests/test_recommendations.py
Comprehensive unit tests for MySQL 8.x index recommendations.

Verifies:
- Valid MySQL 8.x DDL syntax (single-column, composite, covering, FULLTEXT, prefix).
- No unsupported PostgreSQL constructs (INCLUDE clause, USING gin, IF NOT EXISTS).
- Safe identifier generation (max 64 chars, [a-z0-9_]).
- Pre-execution SHOW INDEX verification comments.
- Leftmost prefix rule ordering (equality before range).
"""

import re

import pytest

from analyzer import analyze_query
from config import Dialect, set_dialect
from recommendations import generate_index_recommendations


@pytest.fixture(autouse=True)
def ensure_mysql():
    """Ensure tests run against MySQL dialect."""
    set_dialect(Dialect.MYSQL)
    yield
    set_dialect(Dialect.MYSQL)


# ---------------------------------------------------------------------------
# Test Cases (10+ Diverse Query Scenarios)
# ---------------------------------------------------------------------------


def test_query_1_single_column_equality():
    """Query 1: Simple single-column equality predicate."""
    query = "SELECT id, name FROM users WHERE email = 'alice@example.com';"
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    assert len(recs) >= 1
    rec = next(r for r in recs if r["index_name"] == "idx_users_email")
    assert "CREATE INDEX idx_users_email" in rec["ddl"]
    assert "ON users(email);" in rec["ddl"]
    assert "SHOW INDEX FROM users" in rec["ddl"]
    assert "supports where / join filter on `users.email`" in rec["reason"].lower()


def test_query_2_multiple_columns_composite_equality():
    """Query 2: Multiple equality predicates producing a composite index."""
    query = "SELECT total FROM orders WHERE customer_id = 10 AND status = 'completed';"
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    comp_rec = next((r for r in recs if r["index_type"] == "Composite B-tree"), None)
    assert comp_rec is not None
    assert "CREATE INDEX idx_orders_customer_id_status" in comp_rec["ddl"]
    assert "ON orders(customer_id, status);" in comp_rec["ddl"]
    assert "SHOW INDEX FROM orders" in comp_rec["ddl"]


def test_query_3_composite_equality_and_range_ordering():
    """Query 3: Composite index ordering: equality columns must precede range columns."""
    query = "SELECT id FROM orders WHERE customer_id = 10 AND created_at >= '2024-01-01';"
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    comp_rec = next((r for r in recs if r["index_type"] == "Composite B-tree"), None)
    assert comp_rec is not None
    # customer_id (=) must come before created_at (>=)
    assert "ON orders(customer_id, created_at);" in comp_rec["ddl"]


def test_query_4_covering_index_with_explicit_projection():
    """Query 4: MySQL covering index (filter leading, projected columns trailing)."""
    query = "SELECT name, email FROM customers WHERE region = 'US';"
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    cov_rec = next((r for r in recs if "Covering" in r["index_type"]), None)
    assert cov_rec is not None
    assert "INCLUDE" not in cov_rec["ddl"]
    # Filter 'region' leading, projected 'name, email' trailing
    assert "ON customers(region, name, email);" in cov_rec["ddl"]
    assert "Using index" in cov_rec["reason"]


def test_query_5_covering_index_select_star():
    """Query 5: Covering index suggestion when SELECT * is used."""
    query = "SELECT * FROM orders WHERE customer_id = 5;"
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    cov_rec = next((r for r in recs if "Covering" in r["index_type"]), None)
    assert cov_rec is not None
    assert "INCLUDE" not in cov_rec["ddl"]
    assert "ON orders(customer_id" in cov_rec["ddl"]


def test_query_6_wildcard_like_fulltext():
    """Query 6: Leading wildcard LIKE triggers MySQL InnoDB FULLTEXT index."""
    query = "SELECT * FROM articles WHERE body LIKE '%database%';"
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    fts_rec = next((r for r in recs if "FULLTEXT" in r["index_type"]), None)
    assert fts_rec is not None
    assert "ALTER TABLE articles ADD FULLTEXT INDEX" in fts_rec["ddl"]
    assert "(body);" in fts_rec["ddl"]
    assert "USING gin" not in fts_rec["ddl"]


def test_query_7_long_text_prefix_index():
    """Query 7: Long text / VARCHAR column triggers prefix index (col(191))."""
    query = "SELECT id FROM posts WHERE content = 'tutorial text';"
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    prefix_rec = next((r for r in recs if "Prefix" in r["index_type"]), None)
    assert prefix_rec is not None
    assert "ON posts(content(191));" in prefix_rec["ddl"]
    assert "191-character prefix" in prefix_rec["reason"]


def test_query_8_join_on_predicates():
    """Query 8: Join conditions generate indexes for join columns."""
    query = (
        "SELECT o.id, c.name "
        "FROM orders o "
        "JOIN customers c ON o.customer_id = c.id "
        "WHERE o.status = 'shipped';"
    )
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    ddls = " ".join(r["ddl"] for r in recs)
    # Check for join column indexing
    assert "customer_id" in ddls
    assert "id" in ddls


def test_query_9_long_identifiers_bounded_to_64_chars():
    """Query 9: Extremely long table and column names are truncated safely to 64 chars."""
    query = (
        "SELECT id FROM organization_enterprise_subscription_billing_ledger_entries "
        "WHERE historical_quarterly_aggregate_revenue_cents = 5000000;"
    )
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    assert len(recs) >= 1
    for rec in recs:
        idx_name = rec["index_name"]
        assert len(idx_name) <= 64, f"Index name '{idx_name}' exceeds 64 chars ({len(idx_name)})"
        assert re.match(r"^[a-z0-9_]+$", idx_name), (
            f"Invalid characters in index name: '{idx_name}'"
        )


def test_query_10_no_if_not_exists_and_has_verification_comment():
    """Query 10: Ensures NO 'IF NOT EXISTS' is used and SHOW INDEX verification is present."""
    query = "SELECT id, title FROM products WHERE category_id = 3;"
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    for rec in recs:
        assert "IF NOT EXISTS" not in rec["ddl"]
        assert "SHOW INDEX FROM" in rec["ddl"]


def test_query_11_sanitized_identifier_characters():
    """Query 11: SQL with aliases and special symbols produces clean identifiers."""
    query = "SELECT `u`.`id` FROM `user_accounts` AS `u` WHERE `u`.`is_active` = 1;"
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    for rec in recs:
        assert "`" not in rec["index_name"]
        assert re.match(r"^[a-z0-9_]+$", rec["index_name"])


def test_query_12_deduplication_of_index_names():
    """Query 12: Asserts all generated index names in a single recommendation run are unique."""
    query = (
        "SELECT id, name, email FROM customers "
        "WHERE status = 'active' AND region = 'US' AND status = 'active';"
    )
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    names = [r["index_name"] for r in recs]
    assert len(names) == len(set(names)), f"Duplicate index names found: {names}"


def test_query_13_composite_equality_range_sort_ordering():
    """Query 13: Order composite index by equality -> range -> ORDER BY columns."""
    query = (
        "SELECT id, total FROM orders "
        "WHERE status = 'pending' AND total > 100.00 "
        "ORDER BY order_date;"
    )
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    comp_rec = next((r for r in recs if r["index_type"] == "Composite B-tree"), None)
    assert comp_rec is not None
    # Expected order: status (eq) -> total (range) -> order_date (sort)
    assert "ON orders(status, total, order_date);" in comp_rec["ddl"]
    assert comp_rec["column_order_explanation"] is not None
    assert "Equality column" in comp_rec["column_order_explanation"]
    assert "Range column" in comp_rec["column_order_explanation"]
    assert "Sorting column" in comp_rec["column_order_explanation"]


def test_query_14_composite_index_capped_at_four_columns():
    """Query 14: Composite candidate with >4 columns is capped at 4 with a warning."""
    query = (
        "SELECT id FROM events WHERE c1 = '1' AND c2 = '2' AND c3 = '3' AND c4 = '4' AND c5 > '5';"
    )
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    comp_rec = next((r for r in recs if r["index_type"] == "Composite B-tree"), None)
    assert comp_rec is not None
    # Verify index has at most 4 columns in the DDL
    m = re.search(r"ON events\((.+?)\);", comp_rec["ddl"])
    assert m is not None
    cols = [c.strip() for c in m.group(1).split(",")]
    assert len(cols) <= 4
    assert comp_rec.get("is_capped") is True
    assert "Capped at 4 columns" in comp_rec["reason"]


def test_query_15_size_estimation_and_trade_offs_with_schema():
    """Query 15: Index size estimation and trade-offs notes."""
    from db.schema import ColumnInfo, SchemaInfo, TableInfo
    from recommendations import estimate_index_size_bytes

    schema = SchemaInfo(database="testdb")
    tbl = TableInfo(name="orders", estimated_rows=100_000)
    tbl.columns["customer_id"] = ColumnInfo(name="customer_id", data_type="int")
    tbl.columns["status"] = ColumnInfo(name="status", data_type="varchar(20)")
    schema.tables["orders"] = tbl

    bytes_est, label = estimate_index_size_bytes("orders", ["customer_id", "status"], schema)
    assert bytes_est is not None
    assert bytes_est > 0
    assert "estimate" in label.lower()
    assert "InnoDB B-tree" in label

    query = "SELECT id FROM orders WHERE customer_id = 10 AND status = 'shipped';"
    analysis = analyze_query(query, schema=schema)
    recs = generate_index_recommendations(query, analysis, schema=schema)

    for rec in recs:
        assert "trade_offs" in rec
        assert "Trade-offs:" in rec["trade_offs"]
        assert "write overhead" in rec["trade_offs"].lower()
        assert "estimate" in rec["estimated_size"].lower()


def test_query_16_detect_duplicate_and_prefix_redundant_indexes():
    """Query 16: Detect redundant existing indexes in schema and suggest DROP INDEX."""
    from db.schema import ColumnInfo, IndexInfo, SchemaInfo, TableInfo
    from recommendations import detect_redundant_indexes

    schema = SchemaInfo(database="testdb")
    tbl = TableInfo(name="orders", estimated_rows=50_000)
    tbl.columns["id"] = ColumnInfo(name="id", data_type="int")
    tbl.columns["customer_id"] = ColumnInfo(name="customer_id", data_type="int")
    tbl.columns["status"] = ColumnInfo(name="status", data_type="varchar(20)")

    # Primary key
    tbl.indexes["primary"] = IndexInfo(
        name="PRIMARY", table_name="orders", columns=["id"], is_primary=True
    )
    # Composite index
    tbl.indexes["idx_cust_status"] = IndexInfo(
        name="idx_cust_status", table_name="orders", columns=["customer_id", "status"]
    )
    # Redundant prefix index
    tbl.indexes["idx_cust"] = IndexInfo(
        name="idx_cust", table_name="orders", columns=["customer_id"]
    )
    # Duplicate of idx_cust_status
    tbl.indexes["idx_dup"] = IndexInfo(
        name="idx_dup", table_name="orders", columns=["customer_id", "status"]
    )
    schema.tables["orders"] = tbl

    redundant = detect_redundant_indexes(schema)
    assert len(redundant) >= 2

    # Check for duplicate detection
    dup = next((r for r in redundant if r["type"] == "DUPLICATE_INDEX"), None)
    assert dup is not None
    assert "DROP INDEX idx_dup ON orders;" in dup["ddl"]
    assert "Never drop automatically" in dup["warning"]

    # Check for prefix redundancy detection
    pref = next((r for r in redundant if r["type"] == "PREFIX_REDUNDANT"), None)
    assert pref is not None
    assert "DROP INDEX idx_cust ON orders;" in pref["ddl"]
    assert "strict leftmost prefix" in pref["reason"]


def test_query_17_leftmost_prefix_skips_recommendation():
    """Query 17: Existing composite index skips single-column prefix recommendation."""
    from db.schema import ColumnInfo, IndexInfo, SchemaInfo, TableInfo

    schema = SchemaInfo(database="testdb")
    tbl = TableInfo(name="users", estimated_rows=10_000)
    tbl.columns["email"] = ColumnInfo(name="email", data_type="varchar(255)")
    tbl.columns["created_at"] = ColumnInfo(name="created_at", data_type="datetime")
    tbl.indexes["idx_email_created"] = IndexInfo(
        name="idx_email_created", table_name="users", columns=["email", "created_at"]
    )
    schema.tables["users"] = tbl

    query = "SELECT email FROM users WHERE email = 'test@example.com';"
    analysis = analyze_query(query, schema=schema)
    recs = generate_index_recommendations(query, analysis, schema=schema)

    # Since idx_email_created starts with email, idx_users_email should be skipped
    assert not any(r["index_name"] == "idx_users_email" for r in recs)


def test_query_18_recommendations_ranked_by_expected_benefit():
    """Query 18: Recommendations are assigned rank and ordered by benefit_score."""
    query = "SELECT total FROM orders WHERE customer_id = 10 AND status = 'completed';"
    analysis = analyze_query(query)
    recs = generate_index_recommendations(query, analysis)

    assert len(recs) >= 2
    # Verify rank is assigned sequentially 1, 2, ...
    for i, r in enumerate(recs, 1):
        assert r["rank"] == i
    # Verify sorted descending by benefit_score
    scores = [r["benefit_score"] for r in recs]
    assert scores == sorted(scores, reverse=True)
