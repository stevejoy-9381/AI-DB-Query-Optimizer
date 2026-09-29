<USER_REQUEST>
# Antigravity Prompt Pack: AI DB Query Optimizer

37 ready-to-paste prompts: 1 master prompt, 36 feature prompts, 1 final audit.

## How to use
1. Open the project folder in Antigravity.
2. Paste **Prompt 0 (Master Rules)** first. If your version supports workspace rules or an instructions file, save it there. Otherwise paste it at the start of each new conversation.
3. Paste **one feature prompt at a time**, in the order given at the end of this file.
4. Each prompt makes the agent explain its understanding and plan first. Read it, correct it, then reply "approved".
5. After each prompt: run `pytest`, run `streamlit run app.py`, and commit to git before the next prompt.

---

## Prompt 0: Master Rules (paste first, always)

```text
You are a senior Python engineer with 15 years of experience in databases and developer tooling. You are helping a final-year student turn a Streamlit project into a resume-ready, honest, well-tested portfolio project.

PROJECT: "AI DB Query Optimizer", a Streamlit dashboard that analyzes SQL queries.

CURRENT REALITY (verified from the code):
- app.py (~36 KB, one file) is the Streamlit UI with 5 tabs.
- analyzer.py detects 10 anti-patterns using regex + sqlparse.
- scoring.py gives a 0-100 score from 16 fixed rules.
- optimizer.py generates recommendations and a templated "AI insight" (NOT a real AI/LLM).
- recommendations.py generates CREATE INDEX text (includes PostgreSQL-only INCLUDE syntax).
- execution_plan.py SIMULATES a PostgreSQL-style plan. It never runs EXPLAIN.
- simulator.py estimates index impact with hardcoded math.
- rewrite_engine.py applies 5 regex-based rewrites.
- db_connection.py has a hardcoded MySQL connection and is NEVER imported anywhere.
- requirements.txt lists sqlalchemy and pymysql, which are unused.
- utils/helpers.py has formatting, export and history helpers. data/sample_queries.csv has the sample queries.
- README claims "real MySQL", "true AI-driven", "18 features verified". Some of these are not true.

WORKING RULES (apply to every task in this conversation):
1. PLAN FIRST. Before editing any file, reply with (a) your understanding of the task, (b) the files you will read and change, (c) a step-by-step plan, (d) risks. Then STOP and wait for my approval.
2. HONESTY. Never claim a feature exists unless the code implements it. Never invent benchmark numbers, metrics, or test results. If something cannot be verified, say so.
3. SMALL SAFE STEPS. Work on one topic at a time. Keep the app runnable after every step. Do not rewrite unrelated code.
4. BACKWARD COMPATIBLE. Keep existing function names and return shapes unless the task says otherwise. If you must change one, update every caller.
5. TESTS. Add or update pytest tests for everything you change. Run them and show me the results.
6. SECURITY. No hardcoded credentials. Never execute anything other than SELECT / EXPLAIN against a user database. Use parameterized or validated input. Never log passwords.
7. CODE QUALITY. Type hints, docstrings, small functions, no bare except, use the logging module.
8. KEEP STREAMLIT as the UI framework.
9. TARGET DATABASE: MySQL 8.x is the primary database. The design must allow adding PostgreSQL later.
10. AFTER EACH TASK, report: files changed, what was added, how to run and test it, known limitations, and a suggested git commit message.

Reply only with "Master rules understood" and one sentence of what you will wait for.
```

---

## Prompt 1: Fix README claims

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Make README.md 100% truthful and useful.

TASKS:
1. Read every module and build a table: feature -> implemented? (yes/partial/no) -> file that implements it.
2. Rewrite README.md so it only claims what the code does today. Remove "real MySQL", "true AI-driven", "Implemented & Verified", and the fixed "Features-18" badge unless they are true.
3. Rename the title to "Rule-Based SQL Query Analyzer & Index Recommender" until the LLM feature (Prompt 19) and the real DB feature (Prompts 5-8) exist. Add a note on how to rename it after.
4. Add sections: Overview, What it does today, What is simulated vs real, Limitations, Roadmap (list the planned improvements), Setup, Tech stack (only what is really used), Project structure (match the real files), License.
5. Fix the scoring rules table and pattern table so they match scoring.py and analyzer.py exactly.
6. Remove unused dependencies from the "Technologies Used" section.

FILES: README.md (read all .py files, do not edit them in this task).

DONE WHEN: every sentence in the README can be traced to code, and I can read a "Limitations" section that is honest.
```

---

## Prompt 2: Choose one database (MySQL) and make everything consistent

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Make the whole project consistently MySQL 8.x instead of mixing MySQL and PostgreSQL.

TASKS:
1. Audit every file for PostgreSQL-specific wording or logic: execution_plan.py (seq_page_cost, "Seq Scan", "Hash Join", "Bitmap Index Scan" and similar), simulator.py, recommendations.py, README, and UI text.
2. Add a `dialect` setting in a new config module (default "mysql"). Keep a small dialect abstraction so PostgreSQL can be added later without a rewrite.
3. Change the simulated execution plan to MySQL EXPLAIN vocabulary: access type (ALL, index, range, ref, eq_ref, const), possible_keys, key, rows, filtered, Extra (Using where, Using index, Using filesort, Using temporary). Keep the existing Plotly tree visualization working with the new node data.
4. Remove PostgreSQL cost constants and replace them with a clearly documented, simple MySQL-oriented estimate. Label every simulated number as "estimated".
5. Update the UI labels and README to say MySQL.

FILES: execution_plan.py, simulator.py, recommendations.py, app.py (only labels), config.py (new), README.md.

DONE WHEN: no PostgreSQL-only terms remain in user-facing output, the plan visualizer still renders, and tests pass.
```

---

## Prompt 3: Fix index recommendation syntax

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Generate only valid MySQL 8 index DDL.

TASKS:
1. In recommendations.py remove the `INCLUDE (...)` covering-index syntax (not supported by MySQL).
2. Implement "covering index" the MySQL way: a composite index whose trailing columns are the selected columns.
3. Support: single-column, composite, covering, FULLTEXT (for LIKE '%x%' patterns), and prefix indexes for long VARCHAR/TEXT columns, e.g. `INDEX idx (col(191))`.
4. Generate safe index names: `idx_<table>_<cols>`, max 64 characters, deduplicated, only [a-z0-9_].
5. Do not use `IF NOT EXISTS` on CREATE INDEX (MySQL does not support it). Add a comment line telling the user to check existing indexes first.
6. Add a short reason to each recommendation ("supports WHERE on customer_id").
7. Add pytest tests with at least 10 queries, each with the expected DDL.

FILES: recommendations.py, tests/test_recommendations.py.

DONE WHEN: every generated statement is valid MySQL 8 syntax and tests pass.
```

---

## Prompt 4: Align resume with the real project

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Produce a truthful technology summary and safe resume bullets for this project.

TASKS:
1. Scan requirements.txt and all imports. Produce docs/TECH_STACK_TRUTH.md with a table: technology -> used in code? -> where -> notes. Mark unused ones (for example sqlalchemy, pymysql) clearly.
2. Add a second table "Technologies I may only claim after these prompts are done": FastAPI, PostgreSQL, Docker, NLP/LLM, real MySQL EXPLAIN, CI. For each, state which prompt in this pack makes the claim true.
3. Write 3 alternative resume bullet drafts for the project TODAY (honest version). Use the format: action verb + what + tech + measurable result. Where a number is needed, use the placeholder [MEASURE: what to measure] and NEVER invent a number.
4. Write a second set of bullets to use after Prompts 5-9, 19, 26 and 35 are completed, again with placeholders.

FILES: docs/TECH_STACK_TRUTH.md only. Do not edit code.

DONE WHEN: I can copy bullets that I could defend line by line in an interview.
```

---

## Prompt 5: Real database connection UI

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Let the user connect the app to a real MySQL database from the Streamlit sidebar.

TASKS:
1. Create package `db/` with `connection.py`: a `DBConfig` dataclass (host, port, user, password, database), `build_engine(config)` using SQLAlchemy + pymysql, and `test_connection(config)` returning success or a categorized error.
2. Sidebar form: host, port (default 3306), user, password (masked input), database, "Test connection", "Connect", "Disconnect". Store the engine in `st.session_state`, never the raw password after connecting if avoidable.
3. Connection settings: connect timeout (5 s), read timeout (30 s), pool_pre_ping.
4. Recommend and document a read-only MySQL user (give the exact GRANT SELECT statement in the README).
5. Two modes with a visible badge: "Offline (simulated)" and "Connected: <database>". The whole app must still work offline exactly as before.
6. Categorize errors: wrong password, unknown database, host unreachable, timeout. Show friendly messages, never a stack trace.
7. Tests: unit tests with mocked engine; one integration test marked `@pytest.mark.db` that is skipped when no DB is available.

FILES: db/__init__.py, db/connection.py, app.py (sidebar only), tests/test_connection.py.

DONE WHEN: I can connect to a local MySQL, see the badge change, disconnect, and the offline mode is unaffected.
```

---

## Prompt 6: Real EXPLAIN / EXPLAIN ANALYZE

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: When connected, show the REAL MySQL execution plan instead of the simulated one.

TASKS:
1. Create `db/explain.py` with `run_explain(engine, query, analyze=False)` that runs `EXPLAIN FORMAT=JSON <query>` (and `EXPLAIN ANALYZE` when requested, which needs MySQL 8.0.18+; detect the version and disable the option if unsupported).
2. SAFETY: allow only a single SELECT statement. Reject multiple statements, comments that hide statements, and any non-SELECT. For EXPLAIN ANALYZE warn the user that the query is really executed, and apply a `MAX_EXECUTION_TIME` hint or session timeout. Use a read-only transaction.
3. Parse the JSON plan into the existing `PlanNode` structure so the current Plotly tree visualizer works for real plans.
4. Highlight problems in the real plan: full table scan (type=ALL), Using filesort, Using temporary, large `rows` examined, no key used.
5. Show a side-by-side "Real plan vs Simulated plan" toggle and label the source clearly.
6. If not connected or EXPLAIN fails, fall back to the simulated plan with a notice.
7. Tests: parse saved sample EXPLAIN JSON fixtures (store them in tests/fixtures/), and test the SELECT-only guard with malicious inputs.

FILES: db/explain.py, execution_plan.py (adapter), app.py (Advanced Analysis tab), tests/test_explain.py, tests/fixtures/.

DONE WHEN: with a connected DB, the Advanced tab shows a real plan; unsafe SQL is rejected; tests pass.
```

---

## Prompt 7: Schema-aware analysis

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Read the real schema (tables, columns, indexes, row counts) and use it to make analysis and recommendations specific.

TASKS:
1. Create `db/schema.py` with dataclasses `ColumnInfo`, `IndexInfo`, `TableInfo`, `SchemaInfo`.
2. Load them from `information_schema.TABLES`, `COLUMNS` and `STATISTICS` (row estimates, data types, index names, column order, cardinality, uniqueness). Cache the result with `st.cache_data` and add a "Refresh schema" button.
3. Make schema optional: every consumer must work when `schema=None`.
4. analyzer.py: with schema, check that referenced tables and columns exist and report "unknown column/table".
5. recommendations.py: skip an index that already exists or is covered by an existing composite index (leftmost-prefix rule) and say why.
6. scoring.py: pass table row counts to the scoring function so large tables affect the score (implemented fully in Prompt 14; here just expose the data).
7. UI: a "Schema" panel listing tables, row counts and indexes.
8. Tests with a hand-built SchemaInfo (no database needed).

FILES: db/schema.py, analyzer.py, recommendations.py, app.py, tests/test_schema.py.

DONE WHEN: recommending an index that already exists is no longer possible, and offline mode still works.
```

---

## Prompt 8: Before/after benchmarking

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Measure real execution time of the original query vs the rewritten (or indexed) query.

TASKS:
1. Create `db/benchmark.py` with `benchmark_query(engine, query, runs=5, warmup=1, timeout_s=30)` returning min, median, p95 and mean in ms plus rows returned.
2. Only SELECT, using the same safety guard as Prompt 6. Apply a hard timeout.
3. Add `compare_queries(engine, original, rewritten)` returning both results and a speedup factor (median original / median rewritten).
4. Verify both queries return the same number of rows and warn if not.
5. Warn that the buffer cache makes later runs faster, and describe the warm-up policy.
6. Optional index test: a "Try index in a transaction" mode is NOT allowed (DDL auto-commits in MySQL). Instead output the DDL and tell the user to test it on a copy of the database.
7. UI: a "Benchmark" section with a run button, a progress indicator, a Plotly bar chart, and the speedup number.
8. Tests with a mocked engine that returns controlled timings.

FILES: db/benchmark.py, app.py, tests/test_benchmark.py.

DONE WHEN: a connected user can see measured milliseconds for both queries, with honest caveats.
```

---

## Prompt 9: Sample database with 100k+ rows

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Give every user (and the live demo) a realistic MySQL sample database so improvements are measurable.

TASKS:
1. Create `sql/schema.sql` for database `shop_db` with tables: customers, products, orders, order_items. Use primary keys, foreign keys, and realistic column types. Deliberately DO NOT create secondary indexes so that recommendations have real impact.
2. Create `scripts/seed_db.py` that generates at least: 50,000 customers, 2,000 products, 200,000 orders, 500,000 order_items. Use a fixed random seed for reproducibility, batch inserts (e.g. 5,000 rows), and a progress display. Read connection settings from environment variables.
3. Add `data/sample_queries_shop.csv` with 20 queries for this schema, each labeled Good, Moderate or Anti-pattern, and each one meant to show a clear before/after improvement.
4. Add a `--reset` flag and safety check so the script never drops a database it did not create (only drops `shop_db`).
5. README: exact steps to create the DB and seed it.

FILES: sql/schema.sql, scripts/seed_db.py, data/sample_queries_shop.csv, README.md.

DONE WHEN: running the seed script produces the promised row counts, and a query like `SELECT * FROM orders WHERE customer_id = 123` is visibly slow without an index.
```

---

## Prompt 10: Remove or properly use db_connection.py

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Remove dead and duplicate database code and unused dependencies.

TASKS:
1. Confirm with a repo-wide search that root `db_connection.py` is not imported anywhere.
2. After Prompt 5 is done, delete `db_connection.py` (its job is now `db/connection.py`). If Prompt 5 is not done yet, stop and tell me.
3. Decide for each dependency in requirements.txt (streamlit, pandas, plotly, sqlparse, mysql-connector-python, sqlalchemy, pymysql, plus any new ones): used or unused. Remove unused, and use one MySQL driver only (pymysql via SQLAlchemy is preferred).
4. Pin versions with compatible-release ranges (e.g. `streamlit>=1.32,<2`). Create `requirements-dev.txt` for pytest, ruff, mypy, coverage.
5. Confirm a fresh virtual environment can install and run the app.

FILES: db_connection.py (delete), requirements.txt, requirements-dev.txt.

DONE WHEN: no dead file, no unused dependency, and the app runs in a clean virtualenv.
```

---

## Prompt 11: Replace regex analysis with AST parsing

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Make query analysis accurate by parsing SQL into a syntax tree.

TASKS:
1. Add `sqlglot` and parse with the `mysql` dialect.
2. Create `query_model.py` with a `QueryFeatures` dataclass: statement type, tables and aliases, selected columns, star usage, joins (type, condition, columns), WHERE predicates (column, operator, literal, whether wrapped in a function), GROUP BY, HAVING, ORDER BY, LIMIT/OFFSET, subqueries (scalar, IN, EXISTS, correlated or not), CTEs, DISTINCT, aggregates.
3. Refactor analyzer.py to build its findings from QueryFeatures. Keep the SAME output dictionary keys so scoring, optimizer, recommendations, simulator and the UI keep working.
4. Fallback: if sqlglot raises a ParseError, fall back to the old regex path and show a "limited analysis" notice.
5. Fix known regex weaknesses: patterns inside string literals or comments, aliases, nested subqueries, multi-line queries.
6. Build a golden test: run every row in data/sample_queries.csv through the new analyzer, compare the detected patterns with the old analyzer, and list every difference for me to review.
7. Add at least 25 tests.

FILES: query_model.py (new), analyzer.py, requirements.txt, tests/test_analyzer.py.

DONE WHEN: all previously detected patterns still work, false positives inside strings or comments are gone, and I have a written list of behavior differences.
```

---

## Prompt 12: More anti-pattern detectors

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Detect the anti-patterns that matter most in real MySQL workloads. Requires Prompt 11.

ADD THESE DETECTORS (each with code, severity, score delta, message, fix example):
1. Correlated subquery in SELECT or WHERE.
2. OR across different columns (defeats index use).
3. Implicit type conversion (compare a string column to a number), only when schema is known.
4. NOT IN with a subquery (NULL trap and slow plans).
5. ORDER BY on non-indexed columns / ORDER BY RAND().
6. Large OFFSET pagination.
7. Missing JOIN condition (accidental cartesian product).
8. Non-sargable arithmetic on a column (`WHERE price + 10 > 100`).
9. HAVING that could be a WHERE.
10. COUNT(DISTINCT ...) on large tables and `COUNT(col)` vs `COUNT(*)` mismatch.
11. LIKE with a leading wildcard (already exists, keep it).
12. UNION where UNION ALL is enough.

REQUIREMENTS:
- Register detectors in a list (plugin style) so adding one is a one-file change.
- Add matching scoring rules in scoring.py with clear labels.
- Add optimization advice in optimizer.py for each.
- Add at least 2 positive and 2 negative tests per detector.
- Add 15 new example queries to data/sample_queries.csv.

FILES: analyzer.py or a new detectors/ package, scoring.py, optimizer.py, data/sample_queries.csv, tests/test_detectors.py.

DONE WHEN: each detector fires on its bad example, stays silent on the good example, and the UI shows the new findings.
```

---

## Prompt 13: Support more statement types

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Analyze more than SELECT. Requires Prompt 11.

TASKS:
1. Detect statement type: SELECT, INSERT, UPDATE, DELETE, INSERT...SELECT, CTE (WITH), UNION, window functions.
2. Add statement-specific rules:
   - UPDATE or DELETE without WHERE: CRITICAL severity.
   - UPDATE or DELETE with a non-indexed WHERE column: full table lock risk.
   - INSERT one row at a time in a loop pattern: suggest a multi-row insert.
   - INSERT...SELECT without WHERE or LIMIT.
   - CTE referenced multiple times, and window functions without PARTITION BY.
3. Scoring: separate rule sets per statement type, still clamped to 0-100.
4. SAFETY: non-SELECT statements are ANALYZED ONLY. Never execute or EXPLAIN-ANALYZE them. Show a clear "analysis only" badge.
5. Update the rewrite engine to say "no automatic rewrite available" when it does not support the statement type instead of failing.
6. Add 15 sample queries and tests.

FILES: analyzer.py, scoring.py, optimizer.py, rewrite_engine.py, db/explain.py (guard), tests/.

DONE WHEN: an UPDATE without WHERE gets a critical warning, and nothing but SELECT can ever reach the database.
```

---

## Prompt 14: Smarter scoring

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Make the 0-100 score meaningful, explainable and data-aware.

TASKS:
1. Move all rules into a data-driven config (`scoring_rules.py` or YAML) with code, delta, severity, label and explanation, so tuning does not need code changes.
2. Add multipliers when schema is known: penalty x1.0 for small tables (<10k rows), x1.5 for medium (10k-1M), x2.0 for large (>1M). Add a bonus when the filter columns are already indexed.
3. Keep offline behavior identical to today when no schema is present. Write a regression test that proves it using every query in data/sample_queries.csv.
4. Return a clear breakdown list (rule, delta, reason) and show it as a waterfall or bar chart in the UI.
5. Replace the fake "rows scanned" ranges with a computed estimate when the schema is known, and label the offline value "rough estimate".
6. Calibration report: with the sample DB and benchmark results (Prompts 8-9), produce a script `scripts/calibrate_scoring.py` that prints the correlation between score and measured time. Report the real result even if it is weak. Do not adjust numbers to fake a good correlation.

FILES: scoring.py, scoring_rules.py, app.py, scripts/calibrate_scoring.py, tests/test_scoring.py.

DONE WHEN: scores stay within 0-100, the breakdown adds up exactly, and the regression test passes.
```

---

## Prompt 15: Validate rewrites

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Never show a rewritten query as "better" unless it is safe and equivalent.

TASKS:
1. Create `rewrite_validation.py`.
2. Static checks (always available): the rewritten SQL parses; it references the same tables; selected columns are equal or a documented subset; the WHERE logic was not weakened.
3. Data checks (when connected): run both queries with a row cap and compare result sets as multisets (order-insensitive unless the query has ORDER BY). Report "Equivalent on sample data" and explain that this is evidence, not proof.
4. Label every rewrite: "Verified equivalent", "Equivalent on sample data", "Unverified", or "Changes results".
5. Flag rules that change semantics. Example: injecting LIMIT changes the result set, so mark it "Changes results (opt-in)" and let the user tick a checkbox.
6. UI: show the label as a colored badge next to each rewrite.
7. Tests: include rewrites that are equivalent and ones that break equivalence (for example a wrong NOT IN to JOIN change with NULLs).

FILES: rewrite_validation.py, rewrite_engine.py, app.py, tests/test_rewrite_validation.py.

DONE WHEN: an unsafe rewrite is visibly labeled and a safe one is visibly verified.
```

---

## Prompt 16: More rewrite rules

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Grow the rewrite engine from 5 regex tricks to a clean rule registry. Requires Prompts 11 and 15.

TASKS:
1. Restructure rewrite_engine.py: an abstract `RewriteRule` with `name`, `description`, `safety_level`, `applies(features)`, `apply(ast)`, and a registry list. Rules work on the sqlglot AST, not regex.
2. Keep the existing 5 rules (IN subquery to JOIN, SELECT * to explicit columns, function-on-column fix, leading wildcard annotation, LIMIT injection).
3. Add rules:
   - `IN (subquery)` to `EXISTS`.
   - `NOT IN (subquery)` to `NOT EXISTS`.
   - `WHERE YEAR(col) = 2024` to a range `col >= '2024-01-01' AND col < '2025-01-01'` (and the same for MONTH/DATE).
   - Remove redundant DISTINCT when a unique key is selected (needs schema).
   - `UNION` to `UNION ALL` when both sides are provably disjoint or the user confirms.
   - Replace `OFFSET` pagination with a keyset-pagination suggestion (text advice, not automatic).
4. When SELECT * is expanded, use the real column list from the schema if connected; otherwise ask the user to list columns instead of guessing.
5. Every rule returns: the new SQL, an explanation, and its safety label.
6. Each rule needs before/after unit tests.

FILES: rewrite_engine.py, tests/test_rewrite_engine.py.

DONE WHEN: rules are individually testable, the old rules behave the same, and the UI lists which rules were applied and why.
```

---

## Prompt 17: Side-by-side diff view

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Let the user see exactly what changed between the original and rewritten query.

TASKS:
1. Format both queries with the same formatter (sqlglot pretty print) so the diff shows real changes only.
2. Build a diff view with `difflib`: two columns (original | rewritten) and highlighted added/removed lines. Use `st.columns` and HTML or code blocks. Make it readable in dark and light themes.
3. Under the diff list each applied rule (name, explanation, safety badge from Prompt 15).
4. Add a copy-friendly `st.code` block of the final SQL and a download button (.sql).
5. Handle the "nothing to rewrite" case with a friendly message.
6. Tests for the diff helper (pure function returning structured diff lines).

FILES: utils/helpers.py or utils/diff.py, app.py, tests/test_diff.py.

DONE WHEN: I can see at a glance what the optimizer changed and why.
```

---

## Prompt 18: Smarter index advice

```text
Follow the Master Rules. Plan first, then wait for my approval. Requires Prompts 7 and 11.

GOAL: Recommend indexes the way an experienced DBA would.

TASKS:
1. Column-order rule for composite indexes: equality columns first, then range column, then ORDER BY/GROUP BY columns. Explain the order in plain language.
2. Limit composite indexes to 4 columns and warn about write overhead.
3. Detect duplicate and redundant indexes among the existing indexes (same columns, or a prefix of a longer index) and suggest `DROP INDEX` with a clear warning, never automatically.
4. Skip recommendations already satisfied by an existing index (leftmost-prefix rule).
5. Rank recommendations by expected benefit (uses table size and selectivity when known) and show only the top N with an "Advanced" expander for the rest.
6. Estimate the index size when column types and row counts are known and label it "estimate".
7. Add a "trade-offs" note per recommendation: faster reads, slower writes, more storage.
8. Tests with hand-built schemas covering each rule.

FILES: recommendations.py, tests/test_recommendations.py.

DONE WHEN: recommendations are ordered correctly, never duplicate existing indexes, and each has a plain-English reason.
```

---

## Prompt 19: Real AI with an LLM

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Add a genuine LLM-powered explanation and rewrite suggestion, while keeping the rule engine as the safe fallback.

TASKS:
1. Create package `ai/`: `client.py` with a provider-agnostic `LLMClient` interface and implementations for Gemini and one other provider (choose via `LLM_PROVIDER`). Keys come from environment variables or `st.secrets`, never from code.
2. `ai/prompts.py`: a prompt template that sends ONLY the SQL query, the schema (table and column names, types, indexes), the rule-engine findings and the plan. Never send table row data. Ask for strict JSON: {explanation, issues[], suggested_query, suggested_indexes[], confidence}.
3. Validate the response with pydantic. Retry once on invalid JSON; then fall back to the rule-based insight.
4. Any `suggested_query` must pass the Prompt 15 validation before it can be shown as verified. Otherwise show it as "AI suggestion (unverified)".
5. Guards: timeout, max query length, per-session call limit, response caching by (query, schema hash), and a visible "Use AI insights" toggle that is OFF by default.
6. Privacy notice in the UI describing exactly what is sent.
7. Tests with a fake LLM client that returns valid, invalid and malicious outputs (for example a DROP TABLE suggestion must be rejected by the guard).

FILES: ai/__init__.py, ai/client.py, ai/prompts.py, ai/schemas.py, optimizer.py, app.py, tests/test_ai.py.

DONE WHEN: the app works with and without an API key, and no LLM output can ever execute unvalidated SQL.
```

---

## Prompt 20: Honest AI labels

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Every insight must show where it came from.

TASKS:
1. Rename the function `generate_ai_insight` to `generate_rule_insight` (keep a deprecated alias that forwards to it) and update all callers.
2. In the UI show a source badge on each insight: "Rule-based" or "AI (LLM: <model>)".
3. Include the source in JSON, CSV and TXT exports.
4. Replace "AI-powered" wording in the UI and README with accurate wording, unless the LLM feature (Prompt 19) is active.
5. Add a test that the badge and export field are present.

FILES: optimizer.py, utils/helpers.py, app.py, README.md, tests/.

DONE WHEN: nothing in the app calls a template "AI".
```

---

## Prompt 21: Split app.py into modules

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Break the 36 KB app.py into clean, small modules without changing behavior.

TASKS:
1. Read app.py and list its sections (sidebar, each tab, charts, export).
2. Propose this structure and wait for approval:
   ui/sidebar.py, ui/tab_analyzer.py, ui/tab_history.py, ui/tab_dataset.py, ui/tab_practices.py, ui/tab_advanced.py, ui/charts.py, ui/state.py (session_state helpers), ui/components.py.
3. Move code in small steps; after every step the app must run.
4. app.py becomes an entry point of under 100 lines: page config, sidebar, tabs.
5. Centralize `st.session_state` keys as constants to avoid typos.
6. Avoid circular imports and duplicate code; extract repeated chart code into functions.
7. Add a smoke test using `streamlit.testing.v1.AppTest` that the app loads, a sample query runs and a score appears.

FILES: app.py, ui/*.py, tests/test_app_smoke.py.

DONE WHEN: behavior is identical, app.py is short, and the smoke test passes.
```

---

## Prompt 22: Unit and integration tests

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Build a real test suite with coverage of at least 80% on core logic.

TASKS:
1. Set up pytest with `pytest.ini` or `pyproject.toml`, a `tests/` package and `conftest.py` with reusable fixtures (sample queries, sample SchemaInfo, fake engine).
2. Unit tests for: analyzer, query_model, scoring, optimizer, recommendations, execution_plan, simulator, rewrite_engine, rewrite_validation, utils/helpers (exports, history).
3. Data-driven test: read every row of data/sample_queries.csv, run the full pipeline, and assert it never crashes and that the score is between 0 and 100. Also assert that "Good" queries score higher on average than "Anti-pattern" queries.
4. Integration tests marked `@pytest.mark.db` that run only when `TEST_DB_URL` is set (real MySQL): connection, schema load, EXPLAIN, benchmark.
5. Edge cases: empty string, whitespace, only comments, 100 KB query, unicode, semicolon-separated multiple statements, invalid SQL, SQL injection style input.
6. Add `pytest-cov`, print a coverage report, and list any file under 60% coverage.
7. Do not weaken a test to make it pass. If a test reveals a real bug, report it to me first.

FILES: tests/, conftest.py, pytest.ini or pyproject.toml, requirements-dev.txt.

DONE WHEN: `pytest` passes, coverage is reported, and bugs found are listed for me.
```

---

## Prompt 23: .gitignore, cleanup, LICENSE

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Clean the repository so it looks professional on GitHub.

TASKS:
1. Add a `.gitignore` for Python, virtualenvs, `.env`, `.streamlit/secrets.toml`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, coverage files, `.DS_Store`, IDE folders.
2. Remove tracked cache files with `git rm -r --cached` (for example utils/__pycache__/). Do not delete real source files.
3. The README says "License: MIT" but there is no LICENSE file. Add an MIT LICENSE with my name: D Steven Son, and the current year.
4. Add `.env.example` listing every environment variable with dummy values.
5. Add a `.gitattributes` for line endings (optional) and an `.editorconfig`.
6. Check the git history for accidentally committed secrets (search for "password" strings) and tell me if anything must be rotated.

FILES: .gitignore, LICENSE, .env.example, .editorconfig.

DONE WHEN: `git status` is clean of junk files and the repo has a valid license file.
```

---

## Prompt 24: Type hints, docstrings, logging, error handling

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Raise code quality to professional level with tools, not just words.

TASKS:
1. Add `pyproject.toml` configuring ruff (lint and format), mypy (start non-strict, list the errors), and pytest.
2. Add type hints to every public function and dataclass; fix mypy errors without using `Any` everywhere.
3. Add Google-style docstrings (what, args, returns, raises) to every public function and class.
4. Create `logging_config.py` and replace print calls with `logging`. Log to console and a rotating file `logs/app.log`. Never log passwords, API keys or full result data.
5. Create `errors.py` with custom exceptions (QueryParseError, UnsafeQueryError, DBConnectionError, LLMError) and use them instead of bare `except` or generic exceptions.
6. Add `.pre-commit-config.yaml` with ruff and trailing-whitespace hooks.
7. Show me the `ruff` and `mypy` summary before and after.

FILES: pyproject.toml, logging_config.py, errors.py, .pre-commit-config.yaml, and small edits across modules.

DONE WHEN: ruff passes cleanly, mypy errors are at zero (or an explicit short ignore list), and no bare except remains.
```

---

## Prompt 25: Configuration and secrets management

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: One safe place for all settings, no secrets in code.

TASKS:
1. Create `config.py` using `pydantic-settings` (or plain dataclasses + os.environ) with: DB host, port, user, password, database, connect and read timeouts, dialect, LLM provider, LLM model, API key, benchmark runs, max query length, log level.
2. Precedence: Streamlit `st.secrets` > environment variables > `.env` file > defaults.
3. Validate on startup and show a friendly message for missing or invalid values.
4. Mask secrets in logs, UI and exception messages.
5. Provide `.env.example` and `.streamlit/secrets.toml.example` and document both in the README.
6. Search the whole repo for hardcoded credentials (like "yourpassword") and remove them.
7. Tests for precedence and masking.

FILES: config.py, .env.example, .streamlit/secrets.toml.example, README.md, tests/test_config.py.

DONE WHEN: the repo contains zero hardcoded secrets and configuration can be changed without editing code.
```

---

## Prompt 26: Docker and docker-compose

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: One command to run the app and a MySQL database with sample data.

TASKS:
1. `Dockerfile`: python:3.11-slim base, install requirements first (layer caching), copy the app, run as a non-root user, expose 8501, add a HEALTHCHECK against Streamlit's health endpoint, command `streamlit run app.py --server.address=0.0.0.0`.
2. `.dockerignore`: .git, venv, caches, logs, .env, tests output.
3. `docker-compose.yml`: services `app` and `mysql` (mysql:8), a named volume, a healthcheck on MySQL, `depends_on` with `condition: service_healthy`, and environment variables read from `.env`. Mount `sql/schema.sql` for initialization. Add an optional `seed` service or profile that runs scripts/seed_db.py.
4. Never put real passwords in the compose file; use variables with a documented default for local use only.
5. README section "Run with Docker" with exact commands: build, up, seed, open http://localhost:8501, down, reset.
6. Verify the build succeeds and tell me exactly what you ran and what output you saw.

FILES: Dockerfile, .dockerignore, docker-compose.yml, README.md.

DONE WHEN: `docker compose up` starts the app connected to a seeded MySQL, and I can run a query end to end.
```

---

## Prompt 27: CI with GitHub Actions

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Automatically test every push and pull request.

TASKS:
1. Create `.github/workflows/ci.yml` triggered on push and pull_request.
2. Job `lint`: ruff check and ruff format --check, mypy.
3. Job `test`: matrix Python 3.11 and 3.12, pip cache, install requirements and requirements-dev, run `pytest --cov`, upload the coverage report as an artifact.
4. Job `integration`: a MySQL 8 service container with a health check, run the tests marked `db` using `TEST_DB_URL`.
5. Job `docker`: build the Docker image (no push).
6. Add a status badge and coverage info to the README.
7. Use least-privilege `permissions: contents: read`, and never echo secrets.

FILES: .github/workflows/ci.yml, README.md.

DONE WHEN: the workflow file is valid YAML, and I know exactly which jobs will run and why.
```

---

## Prompt 28: Stable live demo

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: The public Streamlit demo must work for anyone without a private database.

TASKS:
1. Add a "Demo mode" that is on by default when no DB is configured: analysis, scoring, rewrite, simulated plan and a built-in sample schema all work offline. Show a banner "Demo mode: estimates only, not connected to a database".
2. Keep requirements minimal for Streamlit Community Cloud. Make heavy or optional packages (DB drivers, LLM SDKs) optional imports with graceful messages when absent.
3. Read secrets from `st.secrets`; provide an example file. The demo must run with zero secrets.
4. Handle cold starts and errors with friendly messages.
5. Add a deployment checklist to the README: repo, main file path `app.py`, Python version, secrets, custom subdomain.
6. Keep the live demo link in the README badge accurate.
7. Test the app by launching it with no environment variables and running three sample queries.

FILES: app.py/ui, requirements.txt, README.md, .streamlit/config.toml.

DONE WHEN: a stranger can open the demo and get useful output within 10 seconds.
```

---

## Prompt 29: Paste-your-schema mode

```text
Follow the Master Rules. Plan first, then wait for my approval. Requires Prompt 7.

GOAL: Users without a database can still get schema-aware advice.

TASKS:
1. Add a "Schema" input: a text area for `CREATE TABLE` (and `CREATE INDEX`) statements, a `.sql` file upload, and a "Load sample schema" button (shop_db from Prompt 9).
2. Parse with sqlglot into the same `SchemaInfo` used by the live database mode. Support PRIMARY KEY, UNIQUE, KEY/INDEX inside CREATE TABLE.
3. Let the user optionally enter approximate row counts per table (numeric inputs) to drive the scoring multipliers.
4. Validation with friendly errors that point at the failing statement.
5. The source badge must say "Schema: pasted" or "Schema: live DB".
6. Store the pasted schema in session state, not on disk.
7. Tests with several real-world CREATE TABLE snippets, including bad input.

FILES: db/schema_parser.py, ui/sidebar.py or the schema panel, tests/test_schema_parser.py.

DONE WHEN: pasting a schema makes recommendations skip existing indexes and flag unknown columns, without any database.
```

---

## Prompt 30: Persistent history

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Query history that survives refresh and can be searched and compared.

TASKS:
1. Store history in a local SQLite file `data/history.db` using the standard `sqlite3` module. Table: id, created_at, query, statement_type, score, complexity, cost, dialect, mode (offline/live), source badges, JSON of the full report.
2. Provide a small repository class: add, list (pagination, search text, filter by score range), get, delete, clear all.
3. UI: a searchable, paginated table; click a row to reload the query; select two rows to compare (score, findings, plan); score trend chart.
4. Export history to CSV/JSON. Add a "Clear history" button with a confirmation.
5. Privacy: a sidebar toggle "Save history" and a note that queries are stored locally only. Add data/history.db to .gitignore.
6. Migrate the current in-session history logic without losing features.
7. Tests using a temporary database file.

FILES: history_store.py, ui/tab_history.py, utils/helpers.py, .gitignore, tests/test_history.py.

DONE WHEN: history persists across app restarts and two queries can be compared.
```

---

## Prompt 31: Cleaner layout and visuals

```text
Follow the Master Rules. Plan first, then wait for my approval. Prefer doing this after Prompt 21.

GOAL: Make the dashboard look professional and easy to follow, with no feature removed.

TASKS:
1. Propose a simplified navigation (for example: Analyze, Plan & Index, Rewrite, History, Learn) mapping every existing feature to a place. Wait for approval.
2. Add `.streamlit/config.toml` with a consistent theme (colors, font).
3. Results layout: a KPI row (score, complexity, cost, rows scanned, potential gain) using consistent cards, then details in expanders. Put the most important information first.
4. Use color-blind-safe colors and always pair color with an icon or text.
5. Charts: consistent Plotly template, readable labels, no clutter, working in both dark and light themes.
6. Make it usable on a narrow screen (avoid more than 3 columns).
7. Add clear empty states ("Paste a query to begin") with a one-click sample query.
8. Provide before/after screenshots (use the browser tool if available).

FILES: ui/*.py, .streamlit/config.toml.

DONE WHEN: a first-time user knows what to do in 5 seconds, and all previous functionality is still reachable.
```

---

## Prompt 32: Loading states and error messages

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: The app must never crash or show a stack trace to the user.

TASKS:
1. Wrap long operations (schema load, EXPLAIN, benchmark, LLM call) in `st.spinner` or `st.status` with step messages.
2. Input validation: empty input, only comments, over the max length (default 20,000 characters), multiple statements, non-text characters. Show a specific message for each.
3. SQL syntax errors: show the message and, if available, the line and column, with a suggestion to check.
4. Connection errors: wrong password, unknown database, host unreachable, timeout, lost connection. Each has a clear "what to do" line.
5. LLM errors: missing key, rate limit, timeout, invalid response. Fall back to rule-based insights with a notice.
6. A global error boundary in the app entry point: catch unexpected exceptions, show "Something went wrong (ref: <id>)", and log the full details with that id.
7. Tests for each validation and error path.

FILES: ui/*.py, errors.py, utils/validation.py, tests/test_validation.py.

DONE WHEN: I cannot make the app show a traceback by entering bad input.
```

---

## Prompt 33: Screenshots and demo GIF

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Add real visuals to the README so recruiters understand the project in 10 seconds.

TASKS:
1. Run the app locally. Using the browser tool, load a sample query and capture clean screenshots: the Analyze tab result, the score gauge, index recommendations, the execution plan, the rewrite diff, the history tab, and the live-connection badge (if a DB is available).
2. Save them to `docs/screenshots/` with descriptive names, and keep each under 500 KB (resize or compress).
3. Record a short demo (15-30 seconds) as a GIF or MP4 if the tooling allows. Otherwise give me a step-by-step script to record it myself.
4. Embed the images in README.md right after the overview, with alt text and captions.
5. Do NOT show real credentials or personal data in any screenshot.

FILES: docs/screenshots/*, README.md.

DONE WHEN: the README top section shows what the product looks like before any text explanation.
```

---

## Prompt 34: Architecture diagram that matches the code

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Diagrams that reflect the real code, generated from it.

TASKS:
1. Analyze the actual imports between modules and write a Mermaid component diagram in README.md.
2. Add a Mermaid sequence diagram for the "Analyze query" flow: UI -> validation -> parser -> analyzer -> scoring -> optimizer/recommendations -> rewrite + validation -> plan (real or simulated) -> UI.
3. Add a second sequence diagram for the connected mode: connect -> schema load -> EXPLAIN -> benchmark.
4. Show which parts are simulated vs real using different colors or labels.
5. Update the in-app "Architecture Viewer" so it matches the new structure.
6. Add `docs/ARCHITECTURE.md` explaining each module in one paragraph and the main design decisions (why sqlglot, why SQLite for history, why fallback modes).

FILES: README.md, docs/ARCHITECTURE.md, ui component for the architecture viewer.

DONE WHEN: every box in the diagram maps to a real file.
```

---

## Prompt 35: Benchmarks and resume bullets with real numbers

```text
Follow the Master Rules. Plan first, then wait for my approval. Requires Prompts 8, 9, 15 and 16.

GOAL: Produce measured results I can put on my resume, honestly.

TASKS:
1. Create `benchmarks/run_benchmarks.py`. For each query in data/sample_queries_shop.csv that has a rewrite or an index recommendation: run the original 5 times (after 1 warm-up), apply the tool's rewrite and/or create the recommended index on a COPY of the database, run again, and record median times and speedups. Save raw results to `benchmarks/results.csv`.
2. Record the environment: MySQL version, row counts, hardware summary, and date.
3. Create `benchmarks/RESULTS.md` with a summary table and the median, best and worst speedups. Include queries that got NO improvement or got worse. Do not hide them.
4. Verify each rewrite with Prompt 15 validation; exclude non-equivalent rewrites from headline numbers.
5. Generate resume bullets using ONLY numbers found in results.csv. Give 3 versions (short, medium, technical). If a number is missing, print [NOT MEASURED] instead of guessing.
6. Add a README section "Benchmark results" with the summary and the exact command to reproduce.

FILES: benchmarks/run_benchmarks.py, benchmarks/results.csv, benchmarks/RESULTS.md, README.md.

DONE WHEN: every number I put on my resume can be reproduced with one command.
```

---

## Prompt 36: Interview notes

```text
Follow the Master Rules. Plan first, then wait for my approval.

GOAL: Prepare me to defend this project in a technical interview.

TASKS:
1. Create `docs/INTERVIEW_NOTES.md`. Every answer must reference real files in this repo (for example "see analyzer.py, function X") and must be honest about limitations.
2. Section A, project pitch: a 30-second, a 2-minute and a 5-minute explanation, plus "why I built it".
3. Section B, database concepts with short, correct answers and examples from this project: B-tree index, clustered vs secondary index in InnoDB, composite index and leftmost-prefix rule, covering index, selectivity and cardinality, sargable predicates, why leading-wildcard LIKE and function-on-column skip indexes, EXPLAIN columns (type, key, rows, Extra), join algorithms (nested loop, hash join), filesort and temporary tables, index write overhead, N+1 queries, pagination (OFFSET vs keyset).
4. Section C, design and engineering questions: why sqlglot vs regex, why a rule-based engine plus an LLM, how you validated rewrites, how you prevented unsafe SQL, how you tested, how you would scale, what you would improve next.
5. Section D, honest weaknesses and how I would respond ("Is it really AI?", "Does it work on PostgreSQL?", "How accurate is the score?").
6. Section E, behavioral questions answered in STAR format using true events from this project.
7. End with 10 practice questions with no answers, for me to self-test.

FILES: docs/INTERVIEW_NOTES.md.

DONE WHEN: I can answer any question about any file in the repo.
```

---

## Prompt 37: Final audit (run last)

```text
Follow the Master Rules. This is a READ-ONLY audit: do not edit files, only report.

GOAL: Check the finished project for honesty, quality and resume-readiness.

TASKS:
1. Verify every claim in README.md and docs/ against the code. List each claim as TRUE, PARTIAL or FALSE with file evidence.
2. Run the full test suite, ruff and mypy; report results and coverage.
3. Start the app in offline mode and (if a database is available) live mode; run 5 different queries and report any errors.
4. Security review: hardcoded secrets, SQL execution paths, input validation, logging of sensitive data, dependency issues.
5. Check that unsafe SQL (DROP, DELETE, multiple statements) can never reach the database.
6. Check that the technologies listed on my resume for this project all exist in the code, and list any mismatch.
7. Give a score out of 10 for: correctness, code quality, testing, documentation, security, UX, resume value. Explain each score and give the top 5 remaining fixes.

DONE WHEN: I have an evidence-based report and no unverified claims.
```

---

## Recommended order

| Step | Prompts | Why |
|---|---|---|
| 1 | 0, 23, 10 | Rules, clean repo, remove dead code |
| 2 | 1, 2, 3 | Make claims and database dialect honest |
| 3 | 11, 12, 13 | Better parsing and detectors (foundation for everything) |
| 4 | 22, 24, 25 | Tests, quality, configuration |
| 5 | 5, 6, 7, 9 | Real database, EXPLAIN, schema, sample data |
| 6 | 14, 15, 16, 17, 18 | Scoring, rewrites, indexes, diff |
| 7 | 8, 35 | Benchmarks and real numbers |
| 8 | 19, 20 | Real AI, honest labels |
| 9 | 21, 29, 30, 31, 32 | UI structure, schema paste, history, layout, errors |
| 10 | 26, 27, 28 | Docker, CI, live demo |
| 11 | 33, 34, 4, 36 | Screenshots, diagrams, resume alignment, interview notes |
| 12 | 37 | Final audit |
this complete prompt
you started and finished some
continue from that 
i approved everything
</USER_REQUEST>
<ADDITIONAL_METADATA>
The current local time is: 2026-09-29T10:31:57+05:30.

The user's current state is as follows:
Active Document: f:\AI-DB-Query-Optimizer-main\AI-DB-Query-Optimizer-main\README.md (LANGUAGE_MARKDOWN)
Cursor is on line: 1
Other open documents:
- f:\AI-DB-Query-Optimizer-main\AI-DB-Query-Optimizer-main\README.md (LANGUAGE_MARKDOWN)
- f:\AI-DB-Query-Optimizer-main\AI-DB-Query-Optimizer-main\tests\__init__.py (LANGUAGE_PYTHON)
- f:\AI-DB-Query-Optimizer-main\AI-DB-Query-Optimizer-main\tests\test_recommendations.py (LANGUAGE_PYTHON)
- f:\AI-DB-Query-Optimizer-main\AI-DB-Query-Optimizer-main\recommendations.py (LANGUAGE_PYTHON)
- f:\AI-DB-Query-Optimizer-main\AI-DB-Query-Optimizer-main\tests\test_mysql_alignment.py (LANGUAGE_PYTHON)
</ADDITIONAL_METADATA>
<USER_SETTINGS_CHANGE>
The user changed setting `Model Selection` from None to Gemini 3.8 Flash (Medium). No need to comment on this change if the user doesn't ask about it. If reporting what model you are, please use a human readable name instead of the exact string.
</USER_SETTINGS_CHANGE>