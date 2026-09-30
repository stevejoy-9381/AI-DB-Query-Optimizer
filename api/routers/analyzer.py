"""
api/routers/analyzer.py
FastAPI router for query analysis and performance scoring endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from analyzer import analyze_query
from api.schemas import AnalyzeResponse, QueryRequest, ScoreResponse
from scoring import compute_score

router = APIRouter(prefix="/api", tags=["Analyzer & Scoring"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze SQL Query",
    description="Parses SQL via sqlglot AST, detects anti-patterns, and returns structured findings.",
)
def post_analyze(payload: QueryRequest) -> AnalyzeResponse:
    """Analyze SQL query using core AST engine and 12+ anti-pattern plugins."""
    try:
        raw_analysis = analyze_query(payload.query)
        score_res = compute_score(raw_analysis)

        score_model = ScoreResponse(
            score=score_res.total,
            cost_estimate=score_res.cost_estimate,
            complexity=raw_analysis.get("complexity", "Simple"),
            rows_scanned_estimate=score_res.rows_scanned_estimate,
            table_multiplier=score_res.table_multiplier,
            breakdown=score_res.breakdown,
        )

        return AnalyzeResponse(
            query=payload.query,
            query_type=raw_analysis.get("query_type", "SELECT"),
            statement_type=raw_analysis.get("statement_type", "SELECT"),
            complexity=raw_analysis.get("complexity", "Simple"),
            issues=raw_analysis.get("issues", []),
            warnings=raw_analysis.get("warnings", []),
            filter_columns=raw_analysis.get("filter_columns", []),
            join_count=raw_analysis.get("join_count", 0),
            subquery_count=raw_analysis.get("subquery_count", 0),
            has_aggregation=raw_analysis.get("has_aggregation", False),
            has_group_by=raw_analysis.get("has_group_by", False),
            has_order_by=raw_analysis.get("has_order_by", False),
            has_limit=raw_analysis.get("has_limit", False),
            has_distinct=raw_analysis.get("has_distinct", False),
            select_star=raw_analysis.get("select_star", False),
            has_where=raw_analysis.get("has_where", False),
            analysis_engine=raw_analysis.get("analysis_engine", "sqlglot_ast"),
            score=score_model,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query analysis failed: {exc}",
        ) from exc


@router.post(
    "/score",
    response_model=ScoreResponse,
    summary="Compute Query Performance Score",
    description="Calculates deterministic 0-100 score, complexity tier, and deduction breakdown.",
)
def post_score(payload: QueryRequest) -> ScoreResponse:
    """Compute performance score and cost breakdown for given SQL query."""
    try:
        raw_analysis = analyze_query(payload.query)
        score_res = compute_score(raw_analysis)

        return ScoreResponse(
            score=score_res.total,
            cost_estimate=score_res.cost_estimate,
            complexity=raw_analysis.get("complexity", "Simple"),
            rows_scanned_estimate=score_res.rows_scanned_estimate,
            table_multiplier=score_res.table_multiplier,
            breakdown=score_res.breakdown,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scoring calculation failed: {exc}",
        ) from exc
