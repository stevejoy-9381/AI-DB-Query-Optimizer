"""tests/test_history.py
Unit tests for persistent SQLite query history storage.
"""

import os
import tempfile

import pytest

from history_store import HistoryStore


@pytest.fixture
def temp_history_store():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_history.db")
        store = HistoryStore(db_path=db_path)
        yield store


def test_add_and_get_history(temp_history_store):
    store = temp_history_store
    rec_id = store.add(
        query="SELECT * FROM customers WHERE id = 1;",
        score=85,
        report_dict={"score": 85, "findings_count": 0},
        statement_type="SELECT",
        complexity="O(1)",
        cost=1.2,
        dialect="mysql",
        mode="offline",
        source_badges="Rule-based",
    )
    assert rec_id > 0

    record = store.get(rec_id)
    assert record is not None
    assert record["score"] == 85
    assert record["query"] == "SELECT * FROM customers WHERE id = 1;"
    assert record["report"]["score"] == 85
    assert record["statement_type"] == "SELECT"


def test_list_and_search(temp_history_store):
    store = temp_history_store
    store.add(query="SELECT * FROM orders;", score=40, report_dict={})
    store.add(query="SELECT name FROM customers;", score=90, report_dict={})
    store.add(query="SELECT count(*) FROM products;", score=75, report_dict={})

    # Total count
    assert store.count() == 3

    # Search
    orders_list = store.list(search="orders")
    assert len(orders_list) == 1
    assert "orders" in orders_list[0]["query"]

    # Score range filter
    high_scores = store.list(min_score=70, max_score=100)
    assert len(high_scores) == 2


def test_delete_and_clear_all(temp_history_store):
    store = temp_history_store
    r1 = store.add(query="SELECT 1;", score=100, report_dict={})
    _r2 = store.add(query="SELECT 2;", score=100, report_dict={})
    assert store.count() == 2

    assert store.delete(r1) is True
    assert store.count() == 1

    store.clear_all()
    assert store.count() == 0


def test_export_csv_and_json(temp_history_store):
    store = temp_history_store
    store.add(query="SELECT * FROM users;", score=60, report_dict={"test": True})

    csv_data = store.export_csv()
    assert "SELECT * FROM users;" in csv_data
    assert "Score" in csv_data

    json_data = store.export_json()
    assert "SELECT * FROM users;" in json_data
    assert '"score": 60' in json_data
