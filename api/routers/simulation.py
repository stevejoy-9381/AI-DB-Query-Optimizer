"""
api/routers/simulation.py
FastAPI router for simulated execution plan trees and index impact simulation.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status

from analyzer import analyze_query
from api.schemas import (
    ExecutionPlanResponse,
    QueryRequest,
    SimulateIndexRequest,
    SimulateIndexResponse,
)
from execution_plan import (
    flatten_plan,
    generate_execution_plan,
    plan_summary,
)
from scoring import compute_score
from simulator import simulate_index_impact

router = APIRouter(prefix="/api", tags=["Simulation & Plan Trees"])


@router.post(
    "/execution-plan",
    response_model=ExecutionPlanResponse,
    summary="Generate Simulated Execution Plan Tree",
    description="Simulates MySQL 8.x cost-based optimizer tree (ALL, ref, range, filesort, temporary).",
)
def post_execution_plan(payload: QueryRequest) -> ExecutionPlanResponse:
    """Generate hierarchical execution plan tree based on InnoDB optimizer heuristics."""
    try:
        analysis = analyze_query(payload.query)
        plan_root = generate_execution_plan(payload.query, analysis)
        flattened = flatten_plan(plan_root)
        summary = plan_summary(plan_root)

        return ExecutionPlanResponse(
            query=payload.query,
            plan_root=asdict(plan_root),
            flattened_nodes=flattened,
            summary=summary,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution plan generation failed: {exc}",
        ) from exc


@router.post(
    "/simulate-index",
    response_model=SimulateIndexResponse,
    summary="Simulate Index Performance Impact",
    description="Projects latency, rows scanned, and speedup factor after applying an index.",
)
def post_simulate_index(payload: SimulateIndexRequest) -> SimulateIndexResponse:
    """Calculate before/after performance projections for a proposed index."""
    try:
        analysis = analyze_query(payload.query)
        score_res = compute_score(analysis)
        sim_data = simulate_index_impact(payload.query, analysis, score_res)

        # Attach target index to simulation details
        sim_data["target_index"] = payload.index

        return SimulateIndexResponse(
            query=payload.query,
            index=payload.index,
            simulation=sim_data,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Index simulation failed: {exc}",
        ) from exc
