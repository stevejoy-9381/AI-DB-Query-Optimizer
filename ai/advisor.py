"""
ai/advisor.py
AI insight orchestration with strict safety guards, caching, retry logic,
rewrite validation, and automatic rule-engine fallback.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from ai.client import LLMClient, get_llm_client
from ai.prompts import build_analysis_prompt
from ai.schemas import AIInsightResponse
from optimizer import generate_rule_insight
from rewrite_validation import EquivalenceLevel, validate_rewrite_static

if TYPE_CHECKING:
    from db.schema import SchemaInfo

logger = logging.getLogger(__name__)

# Guards configuration
MAX_QUERY_LENGTH = 10_000
MAX_SESSION_CALLS = 20

# Global in-memory cache: (query_hash, schema_hash) -> AIInsightResponse
_INSIGHT_CACHE: dict[str, dict[str, Any]] = {}
_SESSION_CALL_COUNT = 0

# Forbidden SQL statements in LLM rewrites for safety
FORBIDDEN_SQL_KEYWORDS = {
    "DROP", "DELETE", "TRUNCATE", "ALTER", "GRANT", "REVOKE",
    "INSERT", "UPDATE", "REPLACE", "CREATE", "CALL", "EXEC"
}


def reset_session_counter() -> None:
    """Reset per-session LLM call counter."""
    global _SESSION_CALL_COUNT
    _SESSION_CALL_COUNT = 0


def clear_insight_cache() -> None:
    """Clear in-memory insight cache."""
    _INSIGHT_CACHE.clear()


def _is_safe_select_query(sql: str | None) -> bool:
    """Verify that suggested query contains only read operations and no destructive DDL/DML."""
    if not sql or not sql.strip():
        return False
    # Strip comments and string literals
    cleaned = re.sub(r"--[^\n]*", " ", sql)
    cleaned = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"'[^']*'", " ", cleaned)
    cleaned = re.sub(r'"[^"]*"', " ", cleaned)

    tokens = [t.upper() for t in re.findall(r"\b[A-Za-z_]+\b", cleaned)]
    for forbidden in FORBIDDEN_SQL_KEYWORDS:
        if forbidden in tokens:
            logger.warning("Rejected unsafe LLM query containing forbidden keyword: %s", forbidden)
            return False
    return True


def get_ai_insight(
    query: str,
    analysis: dict[str, Any],
    score: int,
    schema: SchemaInfo | None = None,
    plan_summary: str | None = None,
    client: LLMClient | None = None,
    enabled: bool = False,
) -> dict[str, Any]:
    """
    Generate an optimization insight, using an LLM if enabled and configured,
    with full safety guards, response caching, retry logic, and rule-based fallback.

    Returns a dict with:
        - "insight": str (formatted markdown insight text)
        - "source": str ("Rule-based Engine" or "AI (LLM: <model>)")
        - "suggested_query": str | None
        - "rewrite_status": str ("Verified equivalent" | "AI suggestion (unverified)" | None)
        - "confidence": float | None
        - "is_llm": bool
    """
    global _SESSION_CALL_COUNT

    # Fallback default: rule-based engine
    rule_insight = generate_rule_insight(query, analysis, score)
    fallback_result = {
        "insight": rule_insight,
        "source": "Rule-based Engine",
        "suggested_query": None,
        "rewrite_status": None,
        "confidence": 1.0,
        "is_llm": False,
    }

    if not enabled:
        return fallback_result

    # Guard 1: Query length
    if len(query) > MAX_QUERY_LENGTH:
        logger.warning("Query length %d exceeds max %d; falling back to rule engine.", len(query), MAX_QUERY_LENGTH)
        return fallback_result

    # Resolve client
    if client is None:
        client = get_llm_client()

    if client is None:
        logger.info("No LLM client or API keys configured; falling back to rule engine.")
        return fallback_result

    # Guard 2: Session call limit
    if _SESSION_CALL_COUNT >= MAX_SESSION_CALLS:
        logger.warning("Session LLM call limit reached (%d calls); falling back to rule engine.", MAX_SESSION_CALLS)
        return fallback_result

    # Guard 3: Cache lookup
    cache_key = hashlib.sha256(
        f"{query}:{schema.database if schema else 'none'}:{score}".encode()
    ).hexdigest()
    if cache_key in _INSIGHT_CACHE:
        logger.info("Retrieved LLM insight from in-memory cache.")
        return _INSIGHT_CACHE[cache_key]

    # Build prompt
    prompt = build_analysis_prompt(
        query=query,
        analysis=analysis,
        score=score,
        schema=schema,
        plan_summary=plan_summary,
    )

    # Call LLM with 1 retry on invalid format
    raw_response: str | None = None
    structured: AIInsightResponse | None = None

    for attempt in range(2):
        try:
            current_prompt = prompt if attempt == 0 else (
                prompt + "\n\nCRITICAL: Your previous response was invalid JSON. "
                "Output ONLY a raw JSON object matching the required schema without code fences."
            )
            raw_response = client.generate(current_prompt, timeout_seconds=10)
            _SESSION_CALL_COUNT += 1

            # Clean markdown code fences if LLM wrapped it
            cleaned_text = raw_response.strip()
            if cleaned_text.startswith("```"):
                cleaned_text = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned_text)
                cleaned_text = re.sub(r"\n?```$", "", cleaned_text)
                cleaned_text = cleaned_text.strip()

            parsed_data = json.loads(cleaned_text)
            structured = AIInsightResponse.model_validate(parsed_data)
            break
        except (json.JSONDecodeError, ValidationError, RuntimeError) as e:
            logger.warning("LLM attempt %d failed: %s", attempt + 1, e)
            if attempt == 1:
                return fallback_result

    if structured is None:
        return fallback_result

    # Guard 4: Validate suggested_query
    suggested = structured.suggested_query
    rewrite_status = None

    if suggested:
        if not _is_safe_select_query(suggested):
            logger.warning("Unsafe query suggested by LLM; discarding rewrite.")
            suggested = None
        else:
            # Validate equivalence via static AST checks (Prompt 15)
            val_result = validate_rewrite_static(query, suggested)
            if val_result.level == EquivalenceLevel.VERIFIED_EQUIVALENT.value:
                rewrite_status = "Verified equivalent"
            else:
                rewrite_status = "AI suggestion (unverified)"

    # Format final insight text
    parts = [structured.explanation]
    if structured.issues:
        issues_formatted = "\n".join(f"- {iss}" for iss in structured.issues)
        parts.append(f"\n**Identified Considerations:**\n{issues_formatted}")

    result = {
        "insight": "\n\n".join(parts),
        "source": f"AI (LLM: {client.name})",
        "suggested_query": suggested,
        "rewrite_status": rewrite_status,
        "confidence": structured.confidence,
        "is_llm": True,
    }

    _INSIGHT_CACHE[cache_key] = result
    return result
