# API Performance, Load & Concurrency Test Report (Prompt 7)

**Project:** AI DB Query Optimizer — FastAPI Backend Performance & Scalability  
**Date:** September 30, 2026  
**Load Generator:** Locust v2.46.6 (Headless distributed engine)  
**Host Target:** `http://127.0.0.1:8000` (FastAPI + Uvicorn)  
**Concurrency Profile:**
- **Simulated Concurrent Users:** 30 users
- **Ramp-Up Rate:** 10 users / second
- **Duration:** 30 seconds
- **Think Time:** 100ms – 500ms
**Total Requests Dispatched:** **1,917 requests**  
**Total Failures:** **0 failures (0.00% Error Rate)**  
**Aggregate Throughput:** **73.2 Requests / Second (RPS)**  
**Overall SLA Compliance:** **100% PASSED**

---

## 1. Executive Summary

Prompt 7 evaluated the performance envelope, concurrency resilience, and CPU-bound AST parsing efficiency of the FastAPI backend service under sustained multi-user load.

The load generation suite ([tests/load/locustfile.py](file:///f:/AI-DB-Query-Optimizer-main/AI-DB-Query-Optimizer-main/tests/load/locustfile.py)) simulates realistic developer persona patterns across 9 distinct endpoint operations, ranging from lightweight health probes to compute-heavy SQL AST transformations, InnoDB execution plan node simulations, and performance score deduction calculations.

### Key Achievements:
- **Zero Request Drops:** Out of 1,917 requests dispatched under 30 concurrent user threads, **0 requests failed** (100% availability).
- **Fast Response Latencies:** Median response time across all endpoints was **60.0 ms**, with an overall average of **94.0 ms**.
- **P95 Latency SLA Met:** 95% of all requests completed within **300.0 ms**, well within the 350 ms interactive SLA target.
- **Graceful Error Handling Under Concurrency:** Input validation rejections (HTTP 422 for empty queries) completed in an ultra-fast **33.8 ms average** without blocking or degrading the ASGI event loop.

---

## 2. Granular Endpoint Performance Breakdown

The following metrics were captured directly via Locust CSV telemetry during the 30-second sustained load window:

| Endpoint Tested | HTTP Method | Total Reqs | Failures | Error Rate | Avg Latency | Median Latency | P95 Latency | Throughput (RPS) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `POST /api/analyze` | POST | 496 | 0 | 0.0% | 85.4 ms | 52.0 ms | 280.0 ms | 18.9 req/s |
| `POST /api/score` | POST | 301 | 0 | 0.0% | 97.1 ms | 59.0 ms | 290.0 ms | 11.5 req/s |
| `POST /api/execution-plan` | POST | 217 | 0 | 0.0% | 97.2 ms | 60.0 ms | 300.0 ms | 8.3 req/s |
| `POST /api/simulate-index` | POST | 202 | 0 | 0.0% | 98.1 ms | 61.0 ms | 310.0 ms | 7.7 req/s |
| `POST /api/rewrite` | POST | 200 | 0 | 0.0% | 140.2 ms | 110.0 ms | 350.0 ms | 7.6 req/s |
| `POST /api/recommendations` | POST | 191 | 0 | 0.0% | 98.1 ms | 71.0 ms | 300.0 ms | 7.3 req/s |
| `GET /api/sample-queries` | GET | 114 | 0 | 0.0% | 90.3 ms | 57.0 ms | 330.0 ms | 4.4 req/s |
| `POST /api/analyze [Invalid 422]` | POST | 99 | 0 | 0.0% | 33.8 ms | 24.0 ms | 110.0 ms | 3.8 req/s |
| `GET /api/health` | GET | 97 | 0 | 0.0% | 75.0 ms | 44.0 ms | 240.0 ms | 3.7 req/s |
| **Aggregated Totals** | — | **1,917** | **0** | **0.00%** | **94.0 ms** | **60.0 ms** | **300.0 ms** | **73.2 req/s** |

---

## 3. SLA Scorecard

| SLA Dimension | Target Threshold | Actual Measured | Result |
|:---|:---:|:---:|:---:|
| **Availability / Error Rate** | < 0.1% failures | **0.00% (0 / 1,917)** | **PASSED** |
| **Median Response Time** | < 100 ms | **60.0 ms** | **PASSED** |
| **Average Response Time** | < 150 ms | **94.0 ms** | **PASSED** |
| **95th Percentile (P95) Latency** | < 350 ms | **300.0 ms** | **PASSED** |
| **Throughput Capacity** | > 50 RPS | **73.2 RPS** | **PASSED** |
| **Event Loop Starvation Check** | Zero timeouts | **0 timeouts** | **PASSED** |

---

## 4. Workload Analysis & Performance Observations

1. **AST Transformation Overhead (`POST /api/rewrite`):**
   - The rewrite endpoint exhibits the highest latency profile (avg: 140.2 ms, median: 110.0 ms) among all endpoints.
   - *Technical Cause:* `rewrite_engine.py` constructs a full `sqlglot` Expression tree, traverses predicates with pattern-matching transforms (e.g. converting `YEAR(col) = Y` into range bounds), unparses back to SQL, and runs secondary semantic validation.
   - *Assessment:* Under 30 concurrent users, P95 stays at 350 ms, which is well within acceptable real-time interactive boundaries for developer tooling.

2. **Validation Layer Efficiency:**
   - Injected invalid queries (`POST /api/analyze [Invalid 422]`) were intercepted immediately by Pydantic V2 before invoking downstream parsers.
   - With an average latency of only **33.8 ms**, the system rejects bad requests swiftly, preventing denial-of-service or thread pool exhaustion.

3. **CSV Benchmark Dataset Access:**
   - `GET /api/sample-queries` (avg: 90.3 ms) efficiently reads and caches the 15 preloaded SQL benchmark records without file-lock contention.

---

## 5. Artifacts and Reproduction

All test scripts, automation runners, and output logs are preserved in the repository:

- **Locust Load Definition:** [tests/load/locustfile.py](file:///f:/AI-DB-Query-Optimizer-main/AI-DB-Query-Optimizer-main/tests/load/locustfile.py)
- **Automated Runner Script:** [tests/load/run_load_test.py](file:///f:/AI-DB-Query-Optimizer-main/AI-DB-Query-Optimizer-main/tests/load/run_load_test.py)
- **Raw CSV Statistics:** `tests/load/results/load_test_stats.csv`
- **Interactive HTML Report:** `tests/load/results/load_test.html`

To run the load test on any machine:
```powershell
python tests/load/run_load_test.py
```
