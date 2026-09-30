"""Tests for db/benchmark.py module."""

from unittest.mock import MagicMock, patch

from db.benchmark import (
    BenchmarkMetrics,
    benchmark_query,
    compare_queries,
)


def test_benchmark_safety_guard_rejects_dml():
    """Verify non-SELECT statements are rejected before reaching database."""
    mock_engine = MagicMock()
    bad_queries = [
        "DROP TABLE customers",
        "DELETE FROM orders WHERE id = 1",
        "UPDATE orders SET status = 'CANCELLED'",
        "SELECT 1; DROP TABLE orders;",
    ]
    for q in bad_queries:
        metrics = benchmark_query(mock_engine, q)
        assert not metrics.success
        assert "guard rejected" in metrics.error
        mock_engine.connect.assert_not_called()


@patch("time.perf_counter")
def test_benchmark_query_mock_timings(mock_perf):
    """Verify benchmark calculations with deterministic mock timings."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    mock_res = MagicMock()
    mock_res.fetchall.return_value = [("row1",), ("row2",), ("row3",)]
    mock_conn.execute.return_value = mock_res

    # Provide sequential timestamps: warmup (t0, t1) then 5 runs (t0, t1 pairs)
    # Warmup takes 0.05s
    # Run 1: 0.010s (10ms)
    # Run 2: 0.020s (20ms)
    # Run 3: 0.030s (30ms)
    # Run 4: 0.040s (40ms)
    # Run 5: 0.050s (50ms)
    timestamps = [
        1.0,
        1.05,  # warmup
        2.0,
        2.01,  # 10ms
        3.0,
        3.02,  # 20ms
        4.0,
        4.03,  # 30ms
        5.0,
        5.04,  # 40ms
        6.0,
        6.05,  # 50ms
    ]
    mock_perf.side_effect = timestamps

    query = "SELECT * FROM orders WHERE customer_id = 1"
    metrics = benchmark_query(mock_engine, query, runs=5, warmup=1)

    assert metrics.success is True
    assert metrics.runs == 5
    assert metrics.warmup_runs == 1
    assert metrics.rows_returned == 3
    assert metrics.min_ms == 10.0
    assert metrics.median_ms == 30.0
    assert metrics.mean_ms == 30.0
    assert metrics.p95_ms > 40.0


def test_compare_queries_calculates_speedup():
    """Verify compare_queries calculates speedup ratio and checks row counts."""
    mock_engine = MagicMock()

    with patch("db.benchmark.benchmark_query") as mock_bm:
        # Original: median 100ms, 50 rows
        orig_m = BenchmarkMetrics(
            runs=5,
            warmup_runs=1,
            min_ms=90.0,
            median_ms=100.0,
            p95_ms=110.0,
            mean_ms=100.0,
            rows_returned=50,
            success=True,
        )
        # Rewritten: median 20ms, 50 rows
        rew_m = BenchmarkMetrics(
            runs=5,
            warmup_runs=1,
            min_ms=18.0,
            median_ms=20.0,
            p95_ms=25.0,
            mean_ms=21.0,
            rows_returned=50,
            success=True,
        )
        mock_bm.side_effect = [orig_m, rew_m]

        comp = compare_queries(mock_engine, "SELECT * FROM orders", "SELECT id FROM orders")
        assert comp.speedup_factor == 5.0  # 100 / 20 = 5.0x
        assert comp.row_counts_match is True
        assert comp.warning is None


def test_compare_queries_flags_row_mismatch():
    """Verify compare_queries raises warning if row counts differ."""
    mock_engine = MagicMock()

    with patch("db.benchmark.benchmark_query") as mock_bm:
        orig_m = BenchmarkMetrics(runs=3, median_ms=50.0, rows_returned=100, success=True)
        # Rewritten accidentally limited to 10 rows
        rew_m = BenchmarkMetrics(runs=3, median_ms=5.0, rows_returned=10, success=True)
        mock_bm.side_effect = [orig_m, rew_m]

        comp = compare_queries(mock_engine, "SELECT * FROM orders", "SELECT * FROM orders LIMIT 10")
        assert comp.row_counts_match is False
        assert comp.warning is not None
        assert "Row count mismatch" in comp.warning
