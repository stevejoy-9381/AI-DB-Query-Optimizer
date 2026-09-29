# Technology Stack Truth & Resume Guidance

This document provides a factual accounting of the technologies present in the codebase today, clarifies which claimed technologies are pending implementation, and offers defensible, verified resume bullets.

---

## 1. Technologies in Codebase Today

| Technology | Used in Code? | Where Used | Notes / Reality |
|---|---|---|---|
| **Python 3.11+** | **Yes** | All `.py` modules | Core runtime environment; uses type hints, dataclasses, and modern standard library. |
| **Streamlit** | **Yes** | `app.py` | UI dashboard framework rendering input areas, metrics, tabs, and alerts. |
| **sqlparse** | **Yes** | `analyzer.py`, `rewrite_engine.py` | Tokenizes SQL queries for clause extraction and keyword inspection. |
| **Plotly** | **Yes** | `app.py` (`go`, `px`) | Generates charts for query score gauges, tree execution plans, and metrics. |
| **pandas** | **Yes** | `app.py`, `utils/helpers.py` | Loads and filters sample queries from CSV; formats tabular reports. |
| **MySQL 8.x (Target Dialect)** | **Yes (Heuristic / Syntax)** | `config.py`, `execution_plan.py`, `recommendations.py`, `simulator.py` | Generated DDL, simulated EXPLAIN operators (`ALL`, `ref`, `range`), and cost models adhere to MySQL 8.x standards. |
| **pytest** | **Yes** | `tests/test_mysql_alignment.py`, `tests/test_recommendations.py` | Test suite covering dialect alignment, plan vocabulary, and index DDL syntax generation. |
| **mysql-connector-python** | **Dormant** | `db_connection.py` | Imported only in an isolated, unused 10-line script with hardcoded credentials. Never executed by the web application. |
| **SQLAlchemy** | **No** | None | Listed in `requirements.txt` but not imported or called anywhere in the active code. |
| **PyMySQL** | **No** | None | Listed in `requirements.txt` but not imported or called anywhere in the active code. |

---

## 2. Technologies Permitted Only After Corresponding Prompts Are Completed

| Technology / Feature | Allowed to Claim After | Prompt Description & Deliverable |
|---|---|---|
| **Real MySQL EXPLAIN / Connection** | **Prompts 5 & 6** | `db/connection.py` (SQLAlchemy/PyMySQL) and `db/explain.py` running real `EXPLAIN FORMAT=JSON`. |
| **Schema-Aware Analysis** | **Prompt 7** | Reading `information_schema` to validate tables, columns, and existing indexes. |
| **Live Before/After Benchmarking** | **Prompt 8 & 35** | `db/benchmark.py` measuring actual execution wall-clock time and latency deltas. |
| **Docker & Docker Compose** | **Prompt 26** | `Dockerfile` and `docker-compose.yml` packaging the app with a reproducible MySQL 8 service. |
| **NLP / LLM Insights** | **Prompt 19** | `ai/client.py` invoking Gemini or provider APIs with structured JSON output and schema context. |
| **CI / Automated Testing** | **Prompt 27** | `.github/workflows/ci.yml` running linting, unit tests, and MySQL integration tests on push/PR. |
| **PostgreSQL Support** | **Future / Dialect Phase**| Implementing PostgreSQL-specific EXPLAIN parser and DDL rules via `Dialect.POSTGRESQL`. |
| **FastAPI** | **Separate Service Pack** | Exposing query analysis API endpoints over HTTP if decoupled from Streamlit. |

---

## 3. Resume Bullet Drafts: Codebase TODAY (Honest Version)

*All metrics use explicit placeholders `[MEASURE: ...]` to ensure zero invented numbers.*

### Option A (Focus on Static SQL Analysis & Rule-Based Tooling)
- Developed an interactive SQL query analyzer in **Python** and **Streamlit** using **sqlparse** to statically inspect query structures, identifying 10 common relational anti-patterns (such as non-sargable WHERE clauses and Cartesian joins) across a suite of [MEASURE: number of sample queries] test queries.

### Option B (Focus on Index Recommendation & Dialect Accuracy)
- Engineered an automated MySQL 8.x index recommendation engine in **Python**, parsing SQL query ASTs and predicates to generate valid DDL for composite and covering indexes adhering to leftmost-prefix rules, verified with [MEASURE: test count, e.g., 27+] automated **pytest** test cases.

### Option C (Focus on Database Systems & Simulated Optimization)
- Built a database education dashboard simulating MySQL 8.x execution plans (`ALL`, `range`, `ref`) and heuristic cost models, calculating latency reduction estimates and rendering visual query tree breakdowns with **Plotly** and **pandas**.

---

## 4. Resume Bullet Drafts: Future State (After Prompts 5–9, 19, 26, and 35)

*Use these drafts only once live database connectivity, benchmarking, and containerization are fully integrated.*

### Option A (Full-Stack DB Tooling & Live EXPLAIN)
- Built a full-stack database query optimization tool using **Python**, **Streamlit**, and **SQLAlchemy**, integrating live MySQL 8.x `EXPLAIN FORMAT=JSON` parsing and automated AST rewrites to achieve an average of [MEASURE: real median % latency reduction from benchmarks/results.csv] query speedup across [MEASURE: row count, e.g. 500K+] seeded rows.

### Option B (Benchmarking & Real-World Validation)
- Architected an automated SQL performance benchmarking pipeline executing warm-up runs and percentile latency comparisons (p50, p95), validating semantic query equivalence before recommending composite index DDL for unindexed predicates.

### Option C (Hybrid AI & Deterministic Rule Optimizer)
- Engineered a hybrid SQL optimization engine combining deterministic AST validation (**sqlglot**) with LLM-powered context-aware insights, containerized with **Docker Compose** and verified against live MySQL instances with [MEASURE: pytest coverage %] test coverage.
