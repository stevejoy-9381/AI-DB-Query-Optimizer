"""
api/schemas.py
Pydantic schemas for request validation and response models.
Enforces strict input limits (non-empty, <=20,000 characters) and standard error models.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    """Request payload containing SQL query to analyze."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description="SQL query string to analyze (1 to 20,000 characters)",
        examples=["SELECT * FROM orders WHERE customer_id = 42;"],
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_blank(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Query cannot be empty or contain only whitespace.")
        from utils.validation import validate_sql_input

        is_valid, err_msg = validate_sql_input(trimmed)
        if not is_valid:
            raise ValueError(err_msg)
        return trimmed


class SimulateIndexRequest(BaseModel):
    """Request payload to simulate query performance with a suggested index."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description="SQL query string to simulate",
        examples=["SELECT * FROM orders WHERE customer_id = 42;"],
    )
    index: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Index specification or CREATE INDEX DDL",
        examples=["CREATE INDEX idx_orders_customer_id ON orders(customer_id);"],
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_blank(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Query cannot be empty or contain only whitespace.")
        return trimmed

    @field_validator("index")
    @classmethod
    def validate_index_not_blank(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Index definition cannot be empty or contain only whitespace.")
        return trimmed


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field("ok", description="Server health status")
    version: str = Field(..., description="API semantic version")


class ErrorResponse(BaseModel):
    """Standard structured error response."""

    error: str = Field(..., description="Human-readable error description")
    detail: Optional[Any] = Field(None, description="Optional diagnostic details or validation errors")


class SampleQueryItem(BaseModel):
    """Item representing a sample database query."""

    query: str
    description: str
    category: str


class ScoreBreakdownItem(BaseModel):
    """Item in performance score deduction waterfall."""

    rule_code: str
    label: str
    delta: int
    severity: str
    explanation: str


class ScoreResponse(BaseModel):
    """Performance score and complexity rating."""

    score: int = Field(..., ge=0, le=100, description="Quality score from 0 to 100")
    cost_estimate: str = Field(..., description="Estimated cost tier (LOW, MEDIUM, HIGH, CRITICAL)")
    complexity: str = Field(..., description="Query structural complexity (Simple, Moderate, Complex)")
    rows_scanned_estimate: str = Field(..., description="Projected row scan magnitude")
    table_multiplier: float = Field(..., description="Applied schema cardinality multiplier")
    breakdown: list[dict[str, Any]] = Field(default_factory=list, description="Score deductions breakdown")


class AnalyzeResponse(BaseModel):
    """Full analysis findings from AST parser and anti-pattern detectors."""

    query: str
    query_type: str
    statement_type: str
    complexity: str
    issues: list[Any] = Field(default_factory=list)
    warnings: list[Any] = Field(default_factory=list)
    filter_columns: list[str] = Field(default_factory=list)
    join_count: int = 0
    subquery_count: int = 0
    has_aggregation: bool = False
    has_group_by: bool = False
    has_order_by: bool = False
    has_limit: bool = False
    has_distinct: bool = False
    select_star: bool = False
    has_where: bool = False
    analysis_engine: str = "sqlglot_ast"
    score: Optional[ScoreResponse] = None


class RecommendationItem(BaseModel):
    """Recommended MySQL 8.x index suggestion."""

    index_type: str
    table: str
    columns: list[str]
    ddl: str
    reason: str
    priority: str
    estimated_speedup: Optional[str] = None


class RecommendationsResponse(BaseModel):
    """List of index recommendations."""

    query: str
    count: int
    recommendations: list[dict[str, Any]] = Field(default_factory=list)


class OptimizeResponse(BaseModel):
    """Optimizer recommendations and strategic guidance."""

    query: str
    optimizations: list[dict[str, Any]] = Field(default_factory=list)
    insight: str = Field(..., description="Actionable architectural guidance insight")


class RewriteResponse(BaseModel):
    """AST query rewrite outcome with validation badge."""

    original: str
    rewritten: str
    is_changed: bool
    changes: list[str] = Field(default_factory=list)
    rewrite_score_est: int = 0
    validation: dict[str, Any] = Field(default_factory=dict)
    supported: bool = True


class ExecutionPlanResponse(BaseModel):
    """Execution plan tree and summary."""

    query: str
    plan_root: dict[str, Any]
    flattened_nodes: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class SimulateIndexResponse(BaseModel):
    """Before vs After performance simulation metrics."""

    query: str
    index: str
    simulation: dict[str, Any]
