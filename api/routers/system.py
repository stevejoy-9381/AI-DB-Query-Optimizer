"""
api/routers/system.py
FastAPI router for system health checks and sample queries catalog.
"""

from __future__ import annotations

import csv
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from api.schemas import HealthResponse, SampleQueryItem

router = APIRouter(prefix="/api", tags=["System & Sample Data"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_QUERIES_PATH = PROJECT_ROOT / "data" / "sample_queries.csv"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns current service status and API version.",
)
def get_health() -> HealthResponse:
    """Service liveness probe."""
    return HealthResponse(status="ok", version="1.0.0")


@router.get(
    "/sample-queries",
    response_model=list[SampleQueryItem],
    summary="List Preloaded Sample Queries",
    description="Loads data/sample_queries.csv and returns query definitions with categories.",
)
def get_sample_queries() -> list[SampleQueryItem]:
    """Return preloaded catalog of sample queries categorized by anti-pattern tier."""
    if not SAMPLE_QUERIES_PATH.exists():
        fallback_path = PROJECT_ROOT / "data" / "sample_queries_shop.csv"
        if not fallback_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sample queries dataset not found on server.",
            )
        target_path = fallback_path
    else:
        target_path = SAMPLE_QUERIES_PATH

    results: list[SampleQueryItem] = []
    try:
        with open(target_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                q = row.get("query", "").strip()
                desc = row.get("description", "").strip()
                cat = row.get("category", "General").strip()
                if q:
                    results.append(
                        SampleQueryItem(
                            query=q,
                            description=desc or "Sample query",
                            category=cat,
                        )
                    )
        return results
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read sample queries dataset: {exc}",
        ) from exc
