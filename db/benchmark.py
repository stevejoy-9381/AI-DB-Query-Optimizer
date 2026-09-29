"""Real database execution time benchmarking and query comparison for MySQL 8.x."""

from __future__ import annotations

import logging
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from db.explain import validate_explainable_query

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkMetrics:
    """Execution timing statistics for a query."""

    runs: int = 5
    warmup_runs: int = 1
    min_ms: float = 0.0
    median_ms: float = 0.0
    p95_ms: float = 0.0
    mean_ms: float = 0.0
    rows_returned: int = 0
    raw_timings_ms: list[float] = field(default_factory=list)
    success: bool = True
    error: str | None = None


@dataclass
class BenchmarkComparison:
    """Side-by-side comparison of original vs rewritten query performance."""

    original: BenchmarkMetrics
    rewritten: BenchmarkMetrics
    speedup_factor: float
    row_counts_match: bool
    warning: str | None = None
    buffer_cache_notice: str = (
        "Warmup runs load referenced InnoDB data pages into the MySQL Buffer Pool. "
        "Measured timings reflect steady-state execution with warm buffer caches."
    )


def _compute_p95(values: list[float]) -> float:
    """Compute 95th percentile value from a list of floats."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * 0.95
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    d = k - f
    return round(sorted_vals[f] * (1 - d) + sorted_vals[c] * d, 3)


def benchmark_query(
    engine: Engine,
    query: str,
    runs: int = 5,
    warmup: int = 1,
    timeout_s: int = 30,
) -> BenchmarkMetrics:
    """Execute a query repeatedly and return timing percentiles.

    Args:
        engine: Connected SQLAlchemy Engine.
        query: Single SELECT SQL statement.
        runs: Number of timed executions (minimum 1).
        warmup: Number of untimed warmup runs (minimum 0).
        timeout_s: Maximum execution timeout in seconds.

    Returns:
        BenchmarkMetrics containing min, median, p95, and mean latencies in ms.
    """
    is_valid, reason = validate_explainable_query(query)
    if not is_valid:
        return BenchmarkMetrics(
            runs=runs,
            warmup_runs=warmup,
            success=False,
            error=f"Benchmark security guard rejected query: {reason}",
        )

    clean_sql = query.strip().rstrip(";")
    timings: list[float] = []
    rows_count = 0

    try:
        with engine.connect() as conn:
            # Enforce server-side execution timeout
            try:
                conn.execute(text(f"SET SESSION max_execution_time = {timeout_s * 1000}"))
            except Exception:
                pass  # Optional session variable depending on user permissions

            # 1. Warm-up iterations (fills buffer pool pages)
            for _ in range(max(0, warmup)):
                res = conn.execute(text(clean_sql))
                res.fetchall()

            # 2. Measured iterations
            for _ in range(max(1, runs)):
                t0 = time.perf_counter()
                res = conn.execute(text(clean_sql))
                rows = res.fetchall()
                t1 = time.perf_counter()
                rows_count = len(rows)
                timings.append((t1 - t0) * 1000.0)

        min_val = round(min(timings), 3)
        median_val = round(statistics.median(timings), 3)
        mean_val = round(statistics.mean(timings), 3)
        p95_val = _compute_p95(timings)

        return BenchmarkMetrics(
            runs=len(timings),
            warmup_runs=warmup,
            min_ms=min_val,
            median_ms=median_val,
            p95_ms=p95_val,
            mean_ms=mean_val,
            rows_returned=rows_count,
            raw_timings_ms=timings,
            success=True,
        )

    except Exception as err:
        logger.exception("Benchmark execution error: %s", err)
        return BenchmarkMetrics(
            runs=runs,
            warmup_runs=warmup,
            success=False,
            error=f"Execution error during benchmarking: {str(err)}",
        )


def compare_queries(
    engine: Engine,
    original: str,
    rewritten: str,
    runs: int = 5,
    warmup: int = 1,
    timeout_s: int = 30,
) -> BenchmarkComparison:
    """Benchmark original and rewritten queries and compute comparative speedup factor.

    Args:
        engine: Connected SQLAlchemy Engine.
        original: Original SQL query.
        rewritten: Rewritten SQL query.
        runs: Number of timed executions.
        warmup: Number of warmup runs.
        timeout_s: Execution timeout in seconds.

    Returns:
        BenchmarkComparison with both metrics and computed speedup factor.
    """
    orig_metrics = benchmark_query(engine, original, runs=runs, warmup=warmup, timeout_s=timeout_s)
    rew_metrics = benchmark_query(engine, rewritten, runs=runs, warmup=warmup, timeout_s=timeout_s)

    if not orig_metrics.success or not rew_metrics.success:
        return BenchmarkComparison(
            original=orig_metrics,
            rewritten=rew_metrics,
            speedup_factor=1.0,
            row_counts_match=False,
            warning="One or both queries failed during benchmark execution.",
        )

    row_match = (orig_metrics.rows_returned == rew_metrics.rows_returned)
    warn_msg = None
    if not row_match:
        warn_msg = (
            f"Row count mismatch! Original returned {orig_metrics.rows_returned} rows, "
            f"while rewritten returned {rew_metrics.rows_returned} rows. "
            "Verify semantic equivalence before applying this rewrite."
        )

    speedup = round(orig_metrics.median_ms / max(0.001, rew_metrics.median_ms), 2)

    return BenchmarkComparison(
        original=orig_metrics,
        rewritten=rew_metrics,
        speedup_factor=speedup,
        row_counts_match=row_match,
        warning=warn_msg,
    )
