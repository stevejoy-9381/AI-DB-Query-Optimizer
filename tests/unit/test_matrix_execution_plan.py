"""tests/unit/test_matrix_execution_plan.py
Automated Unit Tests for all Execution Plan behaviors defined in docs/TEST_MATRIX.md.
"""

from analyzer import analyze_query
from execution_plan import (
    _covering_index_node,
    _filter_node,
    _hash_join_node,
    _index_lookup_node,
    _index_range_node,
    _nested_loop_node,
    _table_scan_node,
    generate_execution_plan,
    get_all_nodes,
)


def test_pln_scan_all():
    """PLN-SCAN-ALL: Generates Full Table Scan (ALL) node for unconstrained query."""
    q = "SELECT * FROM customers"
    anl = analyze_query(q)
    root = generate_execution_plan(q, anl)
    nodes = get_all_nodes(root)
    all_scan_nodes = [n for n in nodes if n.access_type == "ALL"]
    assert len(all_scan_nodes) >= 1
    assert all_scan_nodes[0].total_cost > 0


def test_pln_scan_ref():
    """PLN-SCAN-REF: Generates index lookup (ref) node."""
    node = _index_lookup_node("orders", "customer_id")
    assert node.access_type == "ref"
    assert "idx_orders_customer_id" in node.possible_keys
    assert node.total_cost > 0


def test_pln_scan_range():
    """PLN-SCAN-RANGE: Generates index range scan (range) node."""
    node = _index_range_node("orders", "total")
    assert node.access_type == "range"
    assert "Using index condition" in node.extra


def test_pln_scan_index():
    """PLN-SCAN-INDEX: Generates covering index scan (index) node."""
    node = _covering_index_node("orders", "customer_id")
    assert node.access_type == "index"
    assert "Using index" in node.extra


def test_pln_join_hash():
    """PLN-JOIN-HASH: Generates Hash Join node for join operations."""
    left = _table_scan_node("orders")
    right = _table_scan_node("customers")
    hash_node = _hash_join_node(left, right, "orders.notes = customers.notes")
    assert hash_node.access_type == "hash_join"
    assert len(hash_node.children) == 2


def test_pln_join_loop():
    """PLN-JOIN-LOOP: Generates Nested Loop join node."""
    outer = _table_scan_node("orders")
    inner = _index_lookup_node("customers", "id")
    loop_node = _nested_loop_node(outer, inner, "orders.customer_id = customers.id")
    assert loop_node.access_type == "nested_loop"
    assert len(loop_node.children) == 2


def test_pln_filter_where():
    """PLN-FILTER-WHERE: Generates Filter node with 'Using where' attribute."""
    child = _table_scan_node("products")
    filt = _filter_node(child, "price > 50")
    assert filt.node_type == "Filter"
    assert "Using where" in filt.extra
