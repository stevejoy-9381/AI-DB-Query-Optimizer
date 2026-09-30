"""
tests/load/run_load_test.py
Automated runner for API Load & Performance Testing using Locust.
Spawns the FastAPI backend (if needed), executes headless Locust test, parses CSV metrics,
evaluates SLAs, and produces structured performance data.
"""

import csv
import os
import subprocess
import sys
import time
from pathlib import Path
import urllib.request
import urllib.error

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = WORKSPACE_ROOT / "tests" / "load" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

CSV_PREFIX = str(RESULTS_DIR / "load_test")
HTML_REPORT = str(RESULTS_DIR / "load_test.html")
HOST = "http://127.0.0.1:8000"


def is_backend_alive() -> bool:
    try:
        with urllib.request.urlopen(f"{HOST}/api/health", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_backend():
    print("[LOAD-TEST] Starting FastAPI backend via uvicorn...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(WORKSPACE_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Poll until ready
    for _ in range(30):
        if is_backend_alive():
            print("[LOAD-TEST] Backend is healthy and ready on port 8000.")
            return proc
        time.sleep(0.5)
    raise RuntimeError("Backend failed to start within 15 seconds.")


def run_locust(users: int = 30, spawn_rate: int = 10, run_time: str = "30s"):
    locustfile = WORKSPACE_ROOT / "tests" / "load" / "locustfile.py"
    cmd = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        str(locustfile),
        "--headless",
        "-u",
        str(users),
        "-r",
        str(spawn_rate),
        "--run-time",
        run_time,
        "--host",
        HOST,
        f"--csv={CSV_PREFIX}",
        f"--html={HTML_REPORT}",
    ]
    print(f"[LOAD-TEST] Executing Locust: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("[LOAD-TEST] Stderr output:", result.stderr)


def parse_and_report():
    stats_csv = RESULTS_DIR / "load_test_stats.csv"
    if not stats_csv.exists():
        print(f"[ERROR] Stats file not found: {stats_csv}")
        return False

    print("\n" + "=" * 100)
    print(f"{'Endpoint':<35} | {'Reqs':<7} | {'Fails':<6} | {'Avg (ms)':<9} | {'Med (ms)':<9} | {'P95 (ms)':<9} | {'RPS':<6}")
    print("=" * 100)

    total_reqs = 0
    total_fails = 0
    overall_p95 = 0.0

    with open(stats_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "")
            reqs = int(row.get("Request Count", 0))
            fails = int(row.get("Failure Count", 0))
            avg = float(row.get("Average Response Time", 0.0))
            med = float(row.get("Median Response Time", 0.0))
            p95 = float(row.get("95%", 0.0) or row.get("95% Line", 0.0) or 0.0)
            rps = float(row.get("Requests/s", 0.0))

            if name == "Aggregated":
                total_reqs = reqs
                total_fails = fails
                overall_p95 = p95
                print("-" * 100)

            print(f"{name:<35} | {reqs:<7} | {fails:<6} | {avg:<9.1f} | {med:<9.1f} | {p95:<9.1f} | {rps:<6.1f}")

    print("=" * 100 + "\n")

    # SLA Evaluations
    print("[SLA EVALUATION]")
    pass_failures = total_fails == 0
    pass_p95 = overall_p95 < 350.0

    print(f"  [STATUS] 0% Failure Rate: {'PASSED' if pass_failures else 'FAILED'} (Total failures: {total_fails})")
    print(f"  [STATUS] Aggregated P95 Latency < 350ms: {'PASSED' if pass_p95 else 'FAILED'} (Actual P95: {overall_p95:.1f}ms)")

    return pass_failures and pass_p95


def main():
    backend_proc = None
    started_ourself = False

    try:
        if not is_backend_alive():
            backend_proc = start_backend()
            started_ourself = True
        else:
            print("[LOAD-TEST] Using already running FastAPI backend at http://127.0.0.1:8000.")

        run_locust(users=30, spawn_rate=10, run_time="30s")
        success = parse_and_report()
        sys.exit(0 if success else 1)

    finally:
        if started_ourself and backend_proc:
            print("[LOAD-TEST] Shutting down spawned backend...")
            backend_proc.terminate()
            backend_proc.wait()


if __name__ == "__main__":
    main()
