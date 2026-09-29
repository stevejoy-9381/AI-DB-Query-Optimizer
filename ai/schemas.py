"""
ai/schemas.py
Pydantic schemas for structured LLM responses and validation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AIInsightResponse(BaseModel):
    """Structured response required from any LLM provider."""

    explanation: str = Field(
        ...,
        description="Clear, technical explanation of the query's performance and execution behavior.",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="List of detected anti-patterns, bottlenecks, or index gaps.",
    )
    suggested_query: str | None = Field(
        default=None,
        description="Optional optimized SQL rewrite. Must be SELECT-only; dangerous statements are rejected.",
    )
    suggested_indexes: list[str] = Field(
        default_factory=list,
        description="List of recommended CREATE INDEX statements.",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0.",
    )
