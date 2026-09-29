"""
ai package
LLM-powered query optimization insights with safe rule fallback and security guards.
"""

from ai.advisor import (
    clear_insight_cache,
    get_ai_insight,
    reset_session_counter,
)
from ai.client import (
    GeminiLLMClient,
    LLMClient,
    MockLLMClient,
    OpenAILLMClient,
    get_llm_client,
)
from ai.schemas import AIInsightResponse

__all__ = [
    "get_ai_insight",
    "LLMClient",
    "GeminiLLMClient",
    "OpenAILLMClient",
    "MockLLMClient",
    "get_llm_client",
    "AIInsightResponse",
    "reset_session_counter",
    "clear_insight_cache",
]
