"""
tests/test_ai.py
Unit tests for AI advisor, provider client abstraction, security guards,
caching, validation, and honest source attribution.
"""

from __future__ import annotations

import json
import pytest

from ai.advisor import (
    clear_insight_cache,
    get_ai_insight,
    reset_session_counter,
    _is_safe_select_query,
)
from ai.client import MockLLMClient, get_llm_client
from ai.prompts import build_analysis_prompt
from analyzer import analyze_query
from db.schema import ColumnInfo, SchemaInfo, TableInfo
from optimizer import generate_ai_insight, generate_rule_insight
from utils.helpers import build_csv_report, build_json_report, build_text_report


@pytest.fixture(autouse=True)
def clean_ai_state():
    """Reset AI session count and cache before each test."""
    reset_session_counter()
    clear_insight_cache()
    yield
    reset_session_counter()
    clear_insight_cache()


def test_rule_insight_rename_and_deprecated_alias():
    """Verify generate_rule_insight runs and generate_ai_insight issues DeprecationWarning."""
    query = "SELECT * FROM users;"
    analysis = analyze_query(query)
    score = 40

    rule_out = generate_rule_insight(query, analysis, score)
    assert "This is a" in rule_out
    assert "SELECT *" in rule_out

    with pytest.deprecated_call():
        alias_out = generate_ai_insight(query, analysis, score)
    assert alias_out == rule_out


def test_ai_disabled_returns_rule_based():
    """When enabled=False, returns rule engine without calling client."""
    query = "SELECT id FROM users WHERE email = 'test@example.com';"
    analysis = analyze_query(query)
    score = 85

    res = get_ai_insight(query, analysis, score, enabled=False)
    assert res["is_llm"] is False
    assert res["source"] == "Rule-based Engine"
    assert "SELECT" not in (res["suggested_query"] or "")


def test_ai_valid_mock_response():
    """Valid JSON from LLM is parsed and attributed honestly."""
    query = "SELECT * FROM orders WHERE total > 100;"
    analysis = analyze_query(query)
    score = 65

    mock_json = json.dumps({
        "explanation": "Query uses SELECT * and unindexed filter on total.",
        "issues": ["SELECT * detected", "Missing index on total"],
        "suggested_query": "SELECT id, total FROM orders WHERE total > 100;",
        "suggested_indexes": ["CREATE INDEX idx_orders_total ON orders(total);"],
        "confidence": 0.92,
    })
    client = MockLLMClient(response_text=mock_json, name="Mock-GPT-4")

    res = get_ai_insight(query, analysis, score, client=client, enabled=True)
    assert res["is_llm"] is True
    assert res["source"] == "AI (LLM: Mock-GPT-4)"
    assert "Query uses SELECT *" in res["insight"]
    assert res["suggested_query"] == "SELECT id, total FROM orders WHERE total > 100;"
    assert res["confidence"] == 0.92
    assert res["rewrite_status"] in ("Verified equivalent", "AI suggestion (unverified)")


def test_ai_invalid_json_falls_back_to_rule_engine():
    """Invalid JSON output falls back cleanly to the rule-based engine."""
    query = "SELECT id FROM users;"
    analysis = analyze_query(query)
    score = 90

    # Completely non-JSON response
    client = MockLLMClient(response_text="I am an AI and I think this query is good!", name="BrokenLLM")

    res = get_ai_insight(query, analysis, score, client=client, enabled=True)
    assert res["is_llm"] is False
    assert res["source"] == "Rule-based Engine"
    assert "This is a" in res["insight"]


def test_ai_malicious_query_rejected_by_guard():
    """Destructive SQL commands (DROP, DELETE, TRUNCATE) are rejected by security guard."""
    assert not _is_safe_select_query("DROP TABLE users;")
    assert not _is_safe_select_query("DELETE FROM orders WHERE id = 1;")
    assert not _is_safe_select_query("TRUNCATE TABLE logs;")
    assert not _is_safe_select_query("ALTER TABLE users ADD COLUMN h INT;")
    assert not _is_safe_select_query("/* comment */ DROP DATABASE prod;")
    assert _is_safe_select_query("SELECT id FROM users WHERE status = 'active';")
    assert _is_safe_select_query("WITH cte AS (SELECT id FROM users) SELECT * FROM cte;")

    # Test that get_ai_insight strips dangerous suggested_query
    query = "SELECT * FROM users;"
    analysis = analyze_query(query)
    mock_json = json.dumps({
        "explanation": "Dangerous advice from untrusted source.",
        "issues": [],
        "suggested_query": "DROP TABLE users; SELECT 1;",
        "suggested_indexes": [],
        "confidence": 0.5,
    })
    client = MockLLMClient(response_text=mock_json)
    res = get_ai_insight(query, analysis, 50, client=client, enabled=True)

    assert res["suggested_query"] is None
    assert res["rewrite_status"] is None


def test_ai_max_query_length_guard():
    """Queries exceeding MAX_QUERY_LENGTH bypass LLM and use rule engine."""
    giant_query = "SELECT * FROM users WHERE id IN (" + ",".join(str(i) for i in range(5000)) + ");"
    assert len(giant_query) > 10_000

    analysis = analyze_query(giant_query)
    client = MockLLMClient()
    res = get_ai_insight(giant_query, analysis, 50, client=client, enabled=True)

    assert res["is_llm"] is False
    assert res["source"] == "Rule-based Engine"


def test_ai_session_call_limit_guard():
    """Exceeding 20 calls in a session stops further calls and falls back."""
    query = "SELECT id FROM users;"
    analysis = analyze_query(query)
    client = MockLLMClient()

    for i in range(20):
        # vary score to avoid cache
        get_ai_insight(query, analysis, score=i, client=client, enabled=True)

    # 21st call must fall back
    res = get_ai_insight("SELECT name FROM customers;", analysis, score=99, client=client, enabled=True)
    assert res["is_llm"] is False
    assert res["source"] == "Rule-based Engine"


def test_ai_caching_behavior():
    """Identical query and schema retrieves from cache without re-invoking LLM."""
    query = "SELECT id FROM products WHERE price > 50;"
    analysis = analyze_query(query)
    mock_json = json.dumps({
        "explanation": "Cached explanation test.",
        "issues": [],
        "suggested_query": None,
        "suggested_indexes": [],
        "confidence": 0.9,
    })
    client = MockLLMClient(response_text=mock_json)

    res1 = get_ai_insight(query, analysis, score=70, client=client, enabled=True)
    assert res1["is_llm"] is True

    # Mutate client response; cache should still return old one
    client.set_response(json.dumps({"explanation": "Different text."}))
    res2 = get_ai_insight(query, analysis, score=70, client=client, enabled=True)
    assert res2["insight"] == "Cached explanation test."


def test_prompt_never_contains_table_row_data():
    """Verify that build_analysis_prompt only sends metadata and zero row data."""
    schema = SchemaInfo(database="shop")
    tbl = TableInfo(name="customers", estimated_rows=1500)
    tbl.columns["email"] = ColumnInfo(name="email", data_type="varchar(255)")
    tbl.columns["balance"] = ColumnInfo(name="balance", data_type="decimal(10,2)")
    schema.tables["customers"] = tbl

    query = "SELECT email, balance FROM customers WHERE balance > 1000;"
    analysis = analyze_query(query, schema=schema)
    prompt = build_analysis_prompt(query, analysis, score=80, schema=schema)

    assert "email (varchar(255))" in prompt
    assert "balance (decimal(10,2))" in prompt
    assert "customers" in prompt
    # Ensure no rows/data are ever mentioned
    assert "INSERT INTO" not in prompt
    assert "VALUES" not in prompt


def test_export_reports_include_source_badge():
    """Verify that JSON, CSV, and text export reports include insight_source field."""
    from scoring import compute_score

    query = "SELECT id, name FROM users WHERE id = 10;"
    analysis = analyze_query(query)
    score_res = compute_score(analysis)
    source = "AI (LLM: Gemini-1.5-flash)"

    # 1. JSON
    json_rep = build_json_report(query, analysis, score_res, [], [], 90, insight_source=source)
    data = json.loads(json_rep)
    assert data["insight"]["source"] == source

    # 2. CSV
    csv_rep = build_csv_report(query, analysis, score_res, 90, insight_source=source)
    assert "Insight Source,AI (LLM: Gemini-1.5-flash)" in csv_rep

    # 3. Text
    text_rep = build_text_report(query, analysis, score_res, [], [], 90, "Sample insight", insight_source=source)
    assert f"Insight Source: {source}" in text_rep
    assert f"INSIGHT ({source})" in text_rep
