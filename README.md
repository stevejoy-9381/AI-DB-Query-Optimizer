# Rule-Based SQL Query Analyzer & Index Recommender

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-red?logo=streamlit)](https://streamlit.io/)
[![Plotly](https://img.shields.io/badge/Plotly-5.18+-purple?logo=plotly)](https://plotly.com/)
[![sqlparse](https://img.shields.io/badge/sqlparse-0.4.4-green)](https://github.com/andialbrecht/sqlparse)
[![Target: MySQL 8.x](https://img.shields.io/badge/Target%20DB-MySQL%208.x-orange?logo=mysql)](https://dev.mysql.com/doc/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Note on Project Naming:**
> This repository is currently titled **Rule-Based SQL Query Analyzer & Index Recommender** to accurately describe its current codebase: a static, heuristic-driven SQL query analyzer and educational dashboard targeting **MySQL 8.x**. Once live database verification (safe `EXPLAIN` against MySQL 8.x) and optional LLM-assisted query explanations are integrated, the project will be updated to reflect those capabilities.

---

## 📌 Overview

**Rule-Based SQL Query Analyzer & Index Recommender** is an interactive developer tool built with Streamlit for inspecting and analyzing SQL queries without requiring an active database server. It parses SQL queries statically using regular expressions and the `sqlparse` library to identify common query anti-patterns (such as full table scans, Cartesian products, leading wildcards, and unindexed filter predicates), computes a deterministic heuristic quality score (0–100), recommends MySQL 8.x indexes, and demonstrates query rewrites.

The codebase defaults to **MySQL 8.x** conventions and features a modular dialect abstraction (`config.py`) so additional engines (such as PostgreSQL) can be supported without rewriting core logic.

---

## ⚡ What It Does Today

The following table reflects the actual state of the codebase today:

| Feature | Implemented? | Implementing File | Reality / Verification Notes |
|---|---|---|---|
| **SQL Query Input** | **Yes** | [`app.py`](app.py) | Streamlit text area accepts SQL query strings (`SELECT`, `JOIN`, subqueries, aggregations). |
| **Query Anti-Pattern Analyzer** | **Yes** | [`analyzer.py`](analyzer.py) | Detects 10 specific anti-patterns via regex and `sqlparse` tokens. |
| **Deterministic Scoring (0–100)** | **Yes** | [`scoring.py`](scoring.py) | Evaluates 16 fixed rules (10 penalties, 6 bonuses), clamped to 0–100. |
| **Complexity Classification** | **Yes** | [`analyzer.py`](analyzer.py) | Classifies query as `Simple`, `Moderate`, or `Complex` based on join count, subquery count, WHERE clauses, and aggregation. |
| **Optimization Strategies** | **Yes** | [`optimizer.py`](optimizer.py) | 8 rule-based recommendation handlers that return guidance and static before/after code examples. |
| **MySQL 8.x Index Recommendations** | **Yes** | [`recommendations.py`](recommendations.py) | Extracts filter and join columns using regex to generate valid MySQL 8.x `CREATE INDEX` DDL (composite B-tree indexes, covering indexes, and InnoDB FULLTEXT DDL). |
| **Dialect Configuration** | **Yes** | [`config.py`](config.py) | Centralized dialect abstraction (default: `mysql`), allowing modular extension to PostgreSQL. |
| **Query Rewriter** | **Partial** | [`rewrite_engine.py`](rewrite_engine.py) | Applies 5 regex/string transformations (e.g. replaces `SELECT *` with column hints, converts simple `IN` subqueries to `INNER JOIN`, appends `LIMIT`). |
| **Simulated MySQL Execution Plan** | **Simulated** | [`execution_plan.py`](execution_plan.py) | Generates a synthetic plan tree modeled on MySQL 8.x `EXPLAIN` vocabulary (`ALL`, `ref`, `range`, `index`, `filesort`, `Using where`, `Using index`) and MySQL cost factors. Does **not** execute `EXPLAIN` against a live engine. |
| **Index Impact Simulator** | **Simulated** | [`simulator.py`](simulator.py) | Estimates row reductions and latency improvements using heuristic MySQL InnoDB B-tree models (e.g. 2.0 ms/1K sequential rows, 0.05 ms/1K indexed rows). |
| **Cost & Row Estimates** | **Simulated** | [`scoring.py`](scoring.py) | Returns static string bands (`LOW`, `MEDIUM`, `HIGH`) derived purely from score brackets (≥80, ≥50, <50). |
| **Natural Language Insight** | **Simulated / Rule-based** | [`optimizer.py`](optimizer.py) | Assembles templated string paragraphs from detected issue codes. No LLM or external AI API is called. |
| **Interactive Visualizations** | **Yes** | [`app.py`](app.py) | Renders Plotly score gauge, simulation comparisons, and anti-pattern radar/bar charts. |
| **Session Query History** | **Yes** | [`app.py`](app.py), [`utils/helpers.py`](utils/helpers.py) | In-memory session tracking of analyzed queries and score trends. |
| **Sample Query Library** | **Yes** | [`data/sample_queries.csv`](data/sample_queries.csv), [`app.py`](app.py) | 25 annotated test queries across good, moderate, and anti-pattern categories. |
| **MySQL Best Practices** | **Yes** | [`recommendations.py`](recommendations.py) | 12 curated MySQL performance guidelines displayed in Tab 4. |
| **Architecture Diagram** | **Yes** | [`app.py`](app.py) | System workflow visualizer embedded in the Streamlit UI. |
| **Report Export** | **Yes** | [`utils/helpers.py`](utils/helpers.py) | Exports query analysis and recommendations as JSON, CSV, or formatted plain text. |
| **Live Database Connection** | **Yes** | [`db/connection.py`](db/connection.py) | Connect to local or remote MySQL 8.x instances using SQLAlchemy + PyMySQL with connection pooling and password masking. |

---

## ⚖️ What Is Simulated vs. Real

To maintain complete technical honesty, the distinction between real operations and simulated heuristics in this repository is outlined below:

### Real (Executed in Code)
- **SQL Tokenization & Parsing:** The `sqlparse` library breaks queries into tokens to inspect statements, identifiers, and clauses.
- **Static Anti-Pattern Detection:** 10 regex- and token-based detectors evaluate query strings for structural issues.
- **Rule-Based Scoring:** A deterministic starting score of 100 is adjusted by strictly defined penalty and bonus deltas.
- **MySQL 8.x DDL Generation:** Generates valid MySQL secondary index DDL (composite indexes, InnoDB covering indexes where all columns are part of the index key, and `ALTER TABLE ... ADD FULLTEXT INDEX`).
- **Dialect Management:** `config.py` centralizes dialect traits and default settings.
- **Code Transformations:** The rewrite engine transforms query strings using regex pattern substitution.
- **UI & Export:** Fully functional Streamlit interface, Plotly charts, and file export helpers (JSON/CSV/TXT).

### Simulated (Heuristic Approximations)
- **Execution Plans:** Generated synthetically in `execution_plan.py` using MySQL 8.x optimizer cost constants (`_IO_BLOCK_READ_COST = 1.0`, `_MEMORY_BLOCK_READ_COST = 0.25`, `_ROW_EVALUATE_COST = 0.10`, `_ROWS_BASE = 100,000`). They illustrate how a MySQL 8.x planner constructs node trees (`ALL`, `ref`, `range`, `index`, `Hash Join`, `filesort`, `temporary`), but **do not reflect real database optimizer output**.
- **Performance Projections & Speedups:** Metrics such as `speedup_factor` and `after_time_ms` in `simulator.py` are computed using static arithmetic multipliers approximating InnoDB B-tree lookups rather than real execution metrics.
- **Cost & Row Scanning Tiers:** `LOW`, `MEDIUM`, and `HIGH` cost tiers are mapped directly from the computed score rather than table cardinality or disk page estimates.
- **"AI Insights":** The natural-language summary in `optimizer.py` is a rule-based conditional string template, not the output of a machine learning model or LLM.

### Not Implemented / Inactive
- **Live Database Execution:** Queries are analyzed purely as disconnected text strings. No connection is made to MySQL or any other RDBMS, and no queries or `EXPLAIN` statements are executed against a live database.

---

## 📊 Scoring Rules Reference

The performance score starts at **100** and is adjusted based on detected anti-patterns and good practices from [`scoring.py`](scoring.py). The final score is clamped between **0** and **100**.

| Code | Type | Delta | Trigger / Condition |
|---|---|---|---|
| `SELECT_STAR` | Penalty | −25 | Use of `SELECT *` without explicit column projection |
| `MISSING_WHERE` | Penalty | −20 | `SELECT` query lacking a `WHERE` filter clause |
| `EXCESSIVE_JOINS` | Penalty | −15 | Query containing more than 2 `JOIN` operations |
| `JOIN_DETECTED` | Penalty | −10 | Query containing 1 or 2 `JOIN` operations |
| `SUBQUERY_DETECTED` | Penalty | −10 | Query containing one or more nested `SELECT` statements |
| `MISSING_LIMIT` | Penalty | −10 | `SELECT` query lacking a `LIMIT` clause |
| `LEADING_WILDCARD` | Penalty | −10 | `LIKE` predicate with a leading wildcard (e.g. `LIKE '%val'`) |
| `FUNCTION_ON_COLUMN` | Penalty | −10 | Scalar function applied to a column in `WHERE` (e.g. `UPPER(col) = ...`) |
| `AGGREGATE_FULL_SCAN` | Penalty | −10 | Aggregate function used without a `WHERE` or `GROUP BY` clause |
| `DISTINCT_WITH_JOIN` | Penalty | −5 | `SELECT DISTINCT` combined with `JOIN` operations |
| `HAS_WHERE` | Bonus | +10 | Query contains a `WHERE` clause |
| `HAS_LIMIT` | Bonus | +10 | Query contains a `LIMIT` clause |
| `SPECIFIC_COLUMNS` | Bonus | +10 | Query specifies explicit columns instead of `SELECT *` |
| `HAS_GROUP_BY` | Bonus | +5 | Query uses `GROUP BY` |
| `HAS_ORDER_BY` | Bonus | +5 | Query uses `ORDER BY` |
| `HAS_FILTER_COLS` | Bonus | +5 | Query contains extractable filter or join columns |

### Cost Tiers
- **LOW Cost (80–100 Score):** Projected scan size of `~1K–10K rows`.
- **MEDIUM Cost (50–79 Score):** Projected scan size of `~10K–500K rows`.
- **HIGH Cost (0–49 Score):** Projected scan size of `~1M+ rows`.

---

## 🔬 Pattern Detection Reference

The 10 anti-patterns in [`analyzer.py`](analyzer.py) are detected using the following logic:

| Pattern Code | Severity | Detection Mechanism | Issue Description |
|---|---|---|---|
| `SELECT_STAR` | HIGH | Regex: `\bSELECT\s+\*` | Fetches all columns, increasing I/O and preventing covering indexes. |
| `MISSING_WHERE` | HIGH | Absence of `WHERE` keyword in `SELECT` statements | Risk of an unconstrained full table scan (`ALL`). |
| `EXCESSIVE_JOINS` | HIGH | Join count > 2 via regex `\b(JOIN\|INNER JOIN\|...)\b` | High join cardinality may severely degrade execution performance. |
| `JOIN_DETECTED` | MEDIUM | Join count > 0 | Unindexed join columns can trigger nested loop full scans. |
| `SUBQUERY_DETECTED` | MEDIUM | Subquery count > 0 (count of `SELECT` tokens minus 1) | Correlated or unoptimized subqueries can lead to O(n²) row processing. |
| `MISSING_LIMIT` | MEDIUM | Absence of `WHERE` and absence of `LIMIT / ROWNUM / TOP` | Unbounded result sets can overwhelm application memory. |
| `LEADING_WILDCARD` | MEDIUM | Regex: `LIKE\s+['"]%` | Leading wildcards prevent B-tree index seeks. |
| `FUNCTION_ON_COLUMN` | MEDIUM | Regex: `WHERE.*\b(UPPER\|LOWER\|YEAR\|...)\s*\(` | Functions wrapped around columns in predicates invalidate standard B-tree index scans. |
| `AGGREGATE_FULL_SCAN` | MEDIUM | Aggregation present, but no `GROUP BY` and no `WHERE` | Aggregates without filters necessitate scanning the entire table. |
| `DISTINCT_WITH_JOIN` | LOW | Both `SELECT DISTINCT` and `JOIN` detected | Distinct joins often mask duplicate join keys and introduce costly deduplication sorts. |

---

## 🔄 Query Rewrite Engine

[`rewrite_engine.py`](rewrite_engine.py) provides 5 automated regex-based transformations:

1. **Subquery to INNER JOIN:** Converts simple `WHERE col IN (SELECT col FROM ...)` subqueries to `INNER JOIN` constructs.
2. **SELECT \* Replacement:** Replaces `SELECT *` with standard projected columns based on a built-in dictionary of common table schemas (`users`, `orders`, `products`, etc.).
3. **Function-on-Column Normalization:** Shifts scalar operations (e.g. `UPPER(col) = 'VAL'`) to the literal constant side (`col = LOWER('VAL')`).
4. **Leading Wildcard Annotation:** Appends SQL comments cautioning that `LIKE '%...'` cannot utilize standard B-tree indexes and suggests MySQL `FULLTEXT` search.
5. **LIMIT Clause Injection:** Automatically appends `LIMIT 100;` to unbounded queries.

---

## ⚠️ Known Limitations

1. **Static Analysis Only:** Queries are evaluated purely through regex and basic tokenization. The system has no awareness of real table schemas, actual row cardinalities, or data distributions unless connected to a database.
2. **Dialect Abstraction & Targeting:** The system is configured for MySQL 8.x by default, generating valid InnoDB composite indexes and FULLTEXT DDL. A modular `config.py` abstraction is in place to support PostgreSQL or other dialects in the future.
3. **Regex Fragility:** Complex queries with CTEs (`WITH` clauses), nested sub-selects within projections, or unconventional formatting may confuse the regex-based column and table extractors.
4. **Hardcoded Mathematical Simulations:** Execution times, speedup factors, and row counts are synthetic estimates designed for educational comparison, not empirical benchmarks.
5. **Unused Database Connector:** The file `db_connection.py` is not wired into the application. No credentials should be placed in it, as it is non-functional in the current architecture.

---

## 🗺️ Roadmap

The planned engineering milestones to evolve this project into a production-grade database developer tool are:

- [ ] **Milestone 1 — Real MySQL 8.x Integration:**
  - Safely connect to a target MySQL database via user-supplied credentials or environment variables.
  - Enforce read-only validation (execute only `EXPLAIN FORMAT=JSON` or safe `SELECT` statements; reject DDL/DML).
  - Inspect actual MySQL table schemas, column types, and existing indexes from `information_schema`.
- [x] **Milestone 2 — Dialect-Specific Index Generation (Completed):**
  - Generated valid MySQL 8.x DDL (composite indexes with proper column ordering and MySQL `FULLTEXT` syntax).
  - Added modular dialect configuration in `config.py`.
- [ ] **Milestone 3 — Real Execution Plan Visualization:**
  - Parse real `EXPLAIN FORMAT=JSON` output from MySQL 8.x and render true query execution plans.
- [ ] **Milestone 4 — LLM Integration:**
  - Integrate an LLM provider (e.g., Google Gemini API or OpenAI) to generate context-aware query explanations based on real execution plan metrics and schema metadata.
- [ ] **Milestone 5 — Automated Test Suite:**
  - Add unit and integration tests with `pytest` covering all parser rules, scoring logic, rewrites, and database connectors.

---

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.11 or higher
- `pip` (Python package manager)

### 1. Clone the repository
```bash
git clone https://github.com/your-username/AI-DB-Query-Optimizer.git
cd AI-DB-Query-Optimizer
```

### 2. Create and activate a virtual environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. (Optional) Create & Seed Sample Database (`shop_db`)
To run benchmarks with real tables, generate the reproducible 100k+ row benchmark database:
```bash
# Set connection environment variables if needed (defaults to localhost:3306, user root, empty password)
export DB_HOST=localhost
export DB_USER=root
export DB_PASSWORD=your_password

# Run the seed script (creates 50k customers, 2k products, 200k orders, 500k order items)
python scripts/seed_db.py --reset

# For a quick smoke test on lower-resource machines, use a scale factor:
python scripts/seed_db.py --reset --scale 0.05
```

### 5. (Optional) Configure a Read-Only MySQL User
To safely connect to a live database without risk of data modification or unwanted DDL execution, configure a read-only user:
```sql
CREATE USER 'optimizer_ro'@'%' IDENTIFIED BY 'StrongPasswordHere!';
GRANT SELECT ON shop_db.* TO 'optimizer_ro'@'%';
FLUSH PRIVILEGES;
```

### 6. Run the Streamlit dashboard
```bash
streamlit run app.py
```
Open your browser and navigate to **http://localhost:8501**.

---

## 🧱 Tech Stack

### Active Technologies
- **[Python 3.11+](https://www.python.org/):** Core application language.
- **[Streamlit](https://streamlit.io/):** Interactive web dashboard framework.
- **[SQLAlchemy 2.x](https://www.sqlalchemy.org/) & [PyMySQL](https://github.com/PyMySQL/PyMySQL):** Database connection management, EXPLAIN execution, and latency benchmarking.
- **[Plotly](https://plotly.com/):** Interactive data visualizations (Score Gauge, Comparison Bar Charts, Tree Visualizer).
- **[sqlparse](https://github.com/andialbrecht/sqlparse):** Non-validating SQL parser and tokenization library.
- **[Pandas](https://pandas.pydata.org/):** Query history management and CSV dataset loading.

---

## 📁 Project Structure

```
.
├── app.py                   # Main Streamlit dashboard (5 tabs, UI components, charts)
├── config.py                # Dialect abstraction & settings (default: MySQL 8.x)
├── analyzer.py              # Pattern detection engine (10 anti-pattern checks + schema validation)
├── scoring.py               # Deterministic scoring engine (16 rules, 0-100 scale)
├── optimizer.py             # Rule-based optimization suggestions & insight templates
├── recommendations.py       # MySQL 8.x CREATE INDEX DDL generator & leftmost-prefix deduplication
├── execution_plan.py        # Simulated execution plan tree generator (MySQL 8.x EXPLAIN model)
├── simulator.py             # Synthetic index impact metrics simulator (labeled estimates)
├── rewrite_engine.py        # Regex-based SQL query rewriter (5 transformations)
├── db/                      # Live database integration package
│   ├── __init__.py
│   ├── connection.py        # DBConfig, SQLAlchemy engine builder & categorized error handling
│   ├── explain.py           # Real EXPLAIN JSON parser, safety validator, and ANALYZE runner
│   ├── schema.py            # Information schema introspection (tables, columns, indexes)
│   └── benchmark.py         # Real query execution benchmarking (min, median, p95)
├── sql/
│   └── schema.sql           # Realistic shop_db DDL (intentionally unindexed for demo impact)
├── scripts/
│   └── seed_db.py           # Reproducible data seeder (50k customers, 200k orders, 500k items)
├── data/
│   ├── sample_queries.csv   # 25 annotated general queries
│   └── sample_queries_shop.csv # 20 realistic shop_db benchmark queries
├── tests/                   # Pytest automated test suite
│   ├── test_connection.py
│   ├── test_explain.py
│   ├── test_benchmark.py
│   ├── test_schema.py
│   ├── test_recommendations.py
│   └── test_mysql_alignment.py
├── requirements.txt         # Project dependencies
└── README.md                # Project documentation
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

