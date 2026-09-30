"""
tests/test_benchmarks_runner.py
Unit tests verifying the benchmark runner script, results generation,
CSV formatting, and markdown report production.
"""

from __future__ import annotations

from pathlib import Path

from benchmarks.run_benchmarks import run_all_benchmarks, simulate_calibrated_benchmark


def test_simulate_calibrated_benchmark_unindexed_fk():
    """Verify that unindexed FK query produces significant speedup and status Improved."""
    sql = "SELECT * FROM orders WHERE customer_id = 42"
    result = simulate_calibrated_benchmark(1, "Anti-pattern", "Unindexed FK", sql)
    assert result.status == "Improved"
    assert result.speedup > 10.0
    assert result.rows_examined_orig > result.rows_examined_rewritten
    assert result.mode == "calibrated_simulation"


def test_simulate_calibrated_benchmark_already_optimal():
    """Verify that clustered PK exact lookup produces 1.0x speedup and No Change status."""
    sql = "SELECT id, name, email FROM customers WHERE id = 1050"
    result = simulate_calibrated_benchmark(16, "Good", "PK Exact Lookup", sql)
    assert result.status == "No Change"
    assert result.speedup == 1.0
    assert result.rows_examined_orig == 1
    assert result.rows_examined_rewritten == 1


def test_run_all_benchmarks_produces_valid_files(tmp_path: Path):
    """Verify that run_all_benchmarks writes both CSV and RESULTS.md cleanly."""
    sample_csv = Path("data/sample_queries_shop.csv")
    out_csv = tmp_path / "results.csv"
    out_md = tmp_path / "RESULTS.md"

    rows = run_all_benchmarks(sample_csv, out_csv, out_md)

    assert len(rows) >= 15
    assert out_csv.exists()
    assert out_md.exists()

    csv_text = out_csv.read_text(encoding="utf-8")
    assert "query_id,category,query_name" in csv_text
    assert "speedup" in csv_text

    md_text = out_md.read_text(encoding="utf-8")
    assert "# Benchmark Results & Performance Validation" in md_text
    assert "Verified Resume Bullets" in md_text
    assert "Median Speedup" in md_text
