"""
api/routers/optimization.py
FastAPI router for optimization guidance, index recommendations, and query rewriting.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from analyzer import analyze_query
from api.schemas import (
    OptimizeResponse,
    QueryRequest,
    RecommendationsResponse,
    RewriteResponse,
)
from optimizer import generate_optimizations, generate_rule_insight
from recommendations import generate_index_recommendations
from rewrite_engine import rewrite_query
from scoring import compute_score

router = APIRouter(prefix="/api", tags=["Optimization, Recommendations & Rewrites"])


@router.post(
    "/optimize",
    response_model=OptimizeResponse,
    summary="Generate Query Optimizations & Guidance",
    description="Returns ranked architectural optimization suggestions and natural-language insight.",
)
def post_optimize(payload: QueryRequest) -> OptimizeResponse:
    """Produce concrete, actionable optimization strategies with example SQL."""
    try:
        analysis = analyze_query(payload.query)
        score_res = compute_score(analysis)
        optimizations = generate_optimizations(payload.query, analysis)
        insight = generate_rule_insight(payload.query, analysis, score_res.total)

        return OptimizeResponse(
            query=payload.query,
            optimizations=optimizations,
            insight=insight,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization analysis failed: {exc}",
        ) from exc


@router.post(
    "/recommendations",
    response_model=RecommendationsResponse,
    summary="Generate MySQL 8.x Index Recommendations",
    description="Returns ranked CREATE INDEX DDLs enforcing leftmost prefix rules and covering indexes.",
)
def post_recommendations(payload: QueryRequest) -> RecommendationsResponse:
    """Generate ranked DDL index suggestions for MySQL 8.x InnoDB."""
    try:
        analysis = analyze_query(payload.query)
        recs = generate_index_recommendations(payload.query, analysis)

        return RecommendationsResponse(
            query=payload.query,
            count=len(recs),
            recommendations=recs,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Index recommendation failed: {exc}",
        ) from exc


@router.post(
    "/rewrite",
    response_model=RewriteResponse,
    summary="Safely Rewrite Inefficient SQL Query",
    description="Transforms non-sargable expressions, projection cuts, and applies semantic verification.",
)
def post_rewrite(payload: QueryRequest) -> RewriteResponse:
    """Perform AST-driven query rewrite with mathematical equivalence validation."""
    try:
        analysis = analyze_query(payload.query)
        rw_result = rewrite_query(payload.query, analysis=analysis)

        return RewriteResponse(
            original=rw_result.get("original", payload.query),
            rewritten=rw_result.get("rewritten", payload.query),
            is_changed=rw_result.get("is_changed", False),
            changes=rw_result.get("changes", []),
            rewrite_score_est=rw_result.get("rewrite_score_est", 0),
            validation=rw_result.get("validation", {}),
            supported=rw_result.get("supported", True),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query rewrite failed: {exc}",
        ) from exc
