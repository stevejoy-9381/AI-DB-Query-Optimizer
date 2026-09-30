"""
api/main.py
FastAPI Application Entrypoint for AI DB Query Optimizer REST Service.

Wraps the core analysis, scoring, optimization, and simulation engines in a
type-safe, CORS-restricted REST API designed for QA test harnesses and client frontends.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import analyzer, optimization, simulation, system

logger = logging.getLogger("api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="AI DB Query Optimizer API",
    version="1.0.0",
    description=(
        "REST API exposing SQL query AST analysis, MySQL 8.x index recommendations, "
        "semantic rewrites, and execution plan simulation."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# 1. CORS Configuration (Restricted strictly to Vite frontend dev server)
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 2. Global Exception Handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Format input validation errors into clean client response with HTTP 422."""
    errors = exc.errors()
    msg = "Invalid input payload."
    clean_errors = []
    for err in errors:
        loc = list(err.get("loc", []))
        err_msg = err.get("msg", "Invalid value")
        clean_errors.append({
            "loc": loc,
            "msg": err_msg,
            "type": str(err.get("type", "validation_error")),
        })
    if clean_errors:
        first = clean_errors[0]
        field_name = " -> ".join(str(loc_part) for loc_part in first["loc"])
        msg = f"Validation error on '{field_name}': {first['msg']}"

    logger.warning("Input validation rejected on %s: %s", request.url.path, msg)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": msg, "detail": clean_errors},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Normalize HTTPException details into standard {error: ...} shape."""
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": detail},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all safety net: logs traceback server-side and shields client from raw leaks."""
    logger.exception("Unhandled server error processing %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "An internal server error occurred while processing the request."},
    )


# ---------------------------------------------------------------------------
# 3. Mount Routers
# ---------------------------------------------------------------------------
app.include_router(analyzer.router)
app.include_router(optimization.router)
app.include_router(simulation.router)
app.include_router(system.router)
