# Backend Unit & API Test Execution Report

**Execution Date:** 2026-09-30  
**Test Framework:** pytest 8.2.2 with pytest-cov  
**Environment:** Python 3.11.4 (win32)  
**Total Tests Executed:** 124  
**Passing:** 124 (100%)  
**Failing:** 0  
**Overall Backend Coverage:** 73% (1,266 / 1,740 statements)

---

## 1. Code Coverage Summary

| Module | Statements | Missed | Real Coverage | Notes |
|:---|:---:|:---:|:---:|:---|
| `scoring.py` | 112 | 5 | **96%** | High coverage across all penalty and bonus rules |
| `api/main.py` | 39 | 4 | **90%** | App setup, CORS middleware, exception handlers |
| `recommendations.py` | 334 | 46 | **86%** | Single, composite, covering, prefix, FULLTEXT DDL |
| `api/routers/simulation.py` | 29 | 4 | **86%** | Index simulation endpoint |
| `optimizer.py` | 82 | 13 | **84%** | Rule insights and prioritized strategies |
| `rewrite_engine.py` | 272 | 45 | **83%** | AST transformations, safety checks, rule registry |
| `api/routers/analyzer.py` | 23 | 4 | **83%** | POST /api/analyze and POST /api/score |
| `api/routers/optimization.py`| 35 | 6 | **83%** | POST /api/optimize, /recommendations, /rewrite |
| `api/routers/system.py` | 32 | 6 | **81%** | GET /api/health and GET /api/sample-queries |
| `execution_plan.py` | 191 | 42 | **78%** | Node constructors, cost models, plan flattening |
| `simulator.py` | 69 | 19 | **72%** | Execution time, rows reduction, speedup factor |
| `utils/validation.py` | 47 | 16 | **66%** | Input sanitization, length, comments, null bytes |
| `analyzer.py` | 194 | 94 | **52%** | Primary sqlglot AST parsing + regex fallback paths |
| `api/schemas.py` | 108 | 0 | **100%** | Request and response Pydantic models |
| `api/__init__.py` | 2 | 0 | **100%** | Package root |
| **TOTAL** | **1,740** | **474** | **73%** | **Consolidated Core Backend** |

---

## 2. Test Matrix Execution Mapping

Every backend row from `docs/TEST_MATRIX.md` was executed via dedicated automated pytest tests. (Frontend UI rows are slated for execution in Prompts 5 and 6).

### 2.1 Analyzer Behaviors (31 Rows)

| Matrix ID | Description | Priority | Test Name | File | Status |
|:---|:---|:---:|:---|:---|:---:|
| `ANL-SEL-STAR` | Detects SELECT * projection | High | `test_anl_sel_star` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-MISS-WHERE` | Detects SELECT without WHERE | High | `test_anl_miss_where` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-EXCESS-JOIN` | Detects excessive JOINs (> 2) | High | `test_anl_excess_join` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-CORR-SUBQ` | Detects correlated subquery | High | `test_anl_corr_subq` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-TYPE-CONV` | Detects implicit type conversion | High | `test_anl_type_conv` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-NOT-IN` | Detects NOT IN subquery NULL trap | High | `test_anl_not_in` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-ORD-RAND` | Detects ORDER BY RAND() filesort | High | `test_anl_ord_rand` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-MISS-JOIN-COND` | Detects Cartesian CROSS JOIN | High | `test_anl_miss_join_cond` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-INS-UNBOUND` | Detects unbounded INSERT...SELECT | High | `test_anl_ins_unbound` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-UPD-NO-WHERE` | Detects UPDATE without WHERE | High | `test_anl_upd_no_where` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-DEL-NO-WHERE` | Detects DELETE without WHERE | High | `test_anl_del_no_where` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-DML-UNIDX-WHERE`| Detects unindexed DML WHERE | High | `test_anl_dml_unidx_where` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-SCHEMA-TBL` | Detects unknown table | High | `test_anl_schema_tbl` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-SCHEMA-COL` | Detects unknown column | High | `test_anl_schema_col` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-JOIN-DET` | Detects standard JOIN | Medium | `test_anl_join_det` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-SUBQ-DET` | Detects nested subquery | Medium | `test_anl_subq_det` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-MISS-LIMIT` | Detects missing LIMIT | Medium | `test_anl_miss_limit` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-LEAD-WILD` | Detects leading wildcard in LIKE | Medium | `test_anl_lead_wild` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-FUNC-COL` | Detects function on WHERE column | Medium | `test_anl_func_col` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-AGG-SCAN` | Detects aggregate full scan | Medium | `test_anl_agg_scan` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-OR-DIFF-COL` | Detects OR across different columns | Medium | `test_anl_or_diff_col` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-UNIDX-ORD` | Detects unindexed ORDER BY | Medium | `test_anl_unidx_ord` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-LRG-OFFSET` | Detects deep pagination OFFSET | Medium | `test_anl_lrg_offset` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-NON-SARG-ARITH` | Detects non-sargable arithmetic | Medium | `test_anl_non_sarg_arith` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-UNION-ALL` | Detects UNION instead of UNION ALL | Medium | `test_anl_union_all` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-CTE-MULT` | Detects multiply referenced CTE | Medium | `test_anl_cte_mult` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-WIN-NO-PART` | Detects window function without PARTITION | Medium | `test_anl_win_no_part` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-DIST-JOIN` | Detects DISTINCT with JOIN | Low | `test_anl_dist_join` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-HAV-AS-WHERE` | Detects HAVING on non-aggregate column | Low | `test_anl_hav_as_where` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-CNT-DIST` | Detects COUNT(DISTINCT) deduplication | Low | `test_anl_cnt_dist` | `tests/unit/test_matrix_analyzer.py` | **PASS** |
| `ANL-INS-SINGLE` | Detects single-row INSERT | Low | `test_anl_ins_single` | `tests/unit/test_matrix_analyzer.py` | **PASS** |

### 2.2 Scoring Behaviors (11 Rows)

| Matrix ID | Description | Priority | Test Name | File | Status |
|:---|:---|:---:|:---|:---|:---:|
| `SCR-BASE-CALC` | Computes baseline score minus penalties | High | `test_scr_base_calc` | `tests/unit/test_matrix_scoring.py` | **PASS** |
| `SCR-SCORE-BOUNDS` | Strict [0, 100] score clipping | High | `test_scr_score_bounds` | `tests/unit/test_matrix_scoring.py` | **PASS** |
| `SCR-COST-TIERS` | Cost classification (LOW, MEDIUM, HIGH) | High | `test_scr_cost_tiers` | `tests/unit/test_matrix_scoring.py` | **PASS** |
| `SCR-STMT-UPDATE` | Statement-specific rules for UPDATE | High | `test_scr_stmt_update` | `tests/unit/test_matrix_scoring.py` | **PASS** |
| `SCR-STMT-DELETE` | Statement-specific rules for DELETE | High | `test_scr_stmt_delete` | `tests/unit/test_matrix_scoring.py` | **PASS** |
| `SCR-TBL-MULTIPLIER`| Multipliers (1.0x, 1.5x, 2.0x) | High | `test_scr_tbl_multiplier` | `tests/unit/test_matrix_scoring.py` | **PASS** |
| `SCR-BONUS-WHERE` | Bonus (+10) for WHERE clause | Medium | `test_scr_bonus_where` | `tests/unit/test_matrix_scoring.py` | **PASS** |
| `SCR-BONUS-LIMIT` | Bonus (+10) for LIMIT clause | Medium | `test_scr_bonus_limit` | `tests/unit/test_matrix_scoring.py` | **PASS** |
| `SCR-BONUS-COLS` | Bonus (+10) for explicit columns | Medium | `test_scr_bonus_cols` | `tests/unit/test_matrix_scoring.py` | **PASS** |
| `SCR-SIM-OPTIMIZED` | Projected score after optimization | Medium | `test_scr_sim_optimized` | `tests/unit/test_matrix_scoring.py` | **PASS** |
| `SCR-BONUS-BULK` | Bonus (+15) for multi-row INSERT | Low | `test_scr_bonus_bulk` | `tests/unit/test_matrix_scoring.py` | **PASS** |

### 2.3 Optimizer Behaviors (8 Rows)

| Matrix ID | Description | Priority | Test Name | File | Status |
|:---|:---|:---:|:---|:---|:---:|
| `OPT-REC-STAR` | Fix recommendation for SELECT * | High | `test_opt_rec_star` | `tests/unit/test_matrix_optimizer.py` | **PASS** |
| `OPT-REC-WHERE` | Fix recommendation for missing WHERE | High | `test_opt_rec_where` | `tests/unit/test_matrix_optimizer.py` | **PASS** |
| `OPT-REC-SORT` | Priority ordering of strategies | High | `test_opt_rec_sort` | `tests/unit/test_matrix_optimizer.py` | **PASS** |
| `OPT-REC-JOIN` | Fix recommendation for unindexed JOIN | Medium | `test_opt_rec_join` | `tests/unit/test_matrix_optimizer.py` | **PASS** |
| `OPT-REC-LIMIT` | Fix recommendation for missing LIMIT | Medium | `test_opt_rec_limit` | `tests/unit/test_matrix_optimizer.py` | **PASS** |
| `OPT-REC-WILDCARD`| Fix recommendation for wildcard LIKE | Medium | `test_opt_rec_wildcard` | `tests/unit/test_matrix_optimizer.py` | **PASS** |
| `OPT-REC-FUNC` | Fix recommendation for function on column | Medium | `test_opt_rec_func` | `tests/unit/test_matrix_optimizer.py` | **PASS** |
| `OPT-INSIGHT-GEN` | Deterministic natural-language insight | Medium | `test_opt_insight_gen` | `tests/unit/test_matrix_optimizer.py` | **PASS** |

### 2.4 Recommendations Behaviors (12 Rows)

| Matrix ID | Description | Priority | Test Name | File | Status |
|:---|:---|:---:|:---|:---|:---:|
| `REC-IDX-SINGLE` | Single-column B-tree CREATE INDEX | High | `test_rec_idx_single` | `tests/unit/test_matrix_recommendations.py` | **PASS** |
| `REC-IDX-COMPOSITE`| Composite index ordering (Eq -> Range -> Sort) | High | `test_rec_idx_composite` | `tests/unit/test_matrix_recommendations.py` | **PASS** |
| `REC-IDX-COVERING` | Covering index (filter leading, projection trailing)| High | `test_rec_idx_covering` | `tests/unit/test_matrix_recommendations.py` | **PASS** |
| `REC-DUP-DETECT` | Exact duplicate index detection | High | `test_rec_dup_detect` | `tests/unit/test_matrix_recommendations.py` | **PASS** |
| `REC-PREFIX-REDUND`| Leftmost prefix redundant index detection | High | `test_rec_prefix_redund` | `tests/unit/test_matrix_recommendations.py` | **PASS** |
| `REC-SKIP-EXIST` | Suppress existing index recommendation | High | `test_rec_skip_exist` | `tests/unit/test_matrix_recommendations.py` | **PASS** |
| `REC-IDX-CAP-4` | Cap composite index at 4 columns | Medium | `test_rec_idx_cap_4` | `tests/unit/test_matrix_recommendations.py` | **PASS** |
| `REC-IDX-PREFIX` | Prefix index col(191) for long text | Medium | `test_rec_idx_prefix` | `tests/unit/test_matrix_recommendations.py` | **PASS** |
| `REC-IDX-FULLTEXT`| FULLTEXT index for wildcard LIKE | Medium | `test_rec_idx_fulltext` | `tests/unit/test_matrix_recommendations.py` | **PASS** |
| `REC-SAFE-NAME` | 64-character safe name MD5 truncation | Medium | `test_rec_safe_name` | `tests/unit/test_matrix_recommendations.py` | **PASS** |
| `REC-SIZE-EST` | Index footprint size estimation | Low | `test_rec_size_est` | `tests/unit/test_matrix_recommendations.py` | **PASS** |
| `REC-TRADE-OFFS` | Read gains vs write penalty notes | Low | `test_rec_trade_offs` | `tests/unit/test_matrix_recommendations.py` | **PASS** |

### 2.5 Execution Plan Behaviors (7 Rows)

| Matrix ID | Description | Priority | Test Name | File | Status |
|:---|:---|:---:|:---|:---|:---:|
| `PLN-SCAN-ALL` | Full table scan (ALL) node | High | `test_pln_scan_all` | `tests/unit/test_matrix_execution_plan.py` | **PASS** |
| `PLN-SCAN-REF` | Index lookup (ref) node | High | `test_pln_scan_ref` | `tests/unit/test_matrix_execution_plan.py` | **PASS** |
| `PLN-SCAN-RANGE` | Index range scan (range) node | Medium | `test_pln_scan_range` | `tests/unit/test_matrix_execution_plan.py` | **PASS** |
| `PLN-SCAN-INDEX` | Covering scan (index) node | Medium | `test_pln_scan_index` | `tests/unit/test_matrix_execution_plan.py` | **PASS** |
| `PLN-JOIN-HASH` | Hash Join node for unindexed joins | Medium | `test_pln_join_hash` | `tests/unit/test_matrix_execution_plan.py` | **PASS** |
| `PLN-JOIN-LOOP` | Nested Loop node for indexed joins | Medium | `test_pln_join_loop` | `tests/unit/test_matrix_execution_plan.py` | **PASS** |
| `PLN-FILTER-WHERE`| Filter node with Using where | Low | `test_pln_filter_where` | `tests/unit/test_matrix_execution_plan.py` | **PASS** |

### 2.6 Simulator Behaviors (4 Rows)

| Matrix ID | Description | Priority | Test Name | File | Status |
|:---|:---|:---:|:---|:---|:---:|
| `SIM-METRICS-CALC`| Before/after metrics computation | High | `test_sim_metrics_calc` | `tests/unit/test_matrix_simulator.py` | **PASS** |
| `SIM-SPEEDUP-FACTOR`| Speedup factor ratio calculation | High | `test_sim_speedup_factor` | `tests/unit/test_matrix_simulator.py` | **PASS** |
| `SIM-WHERE-SELECTIVITY`| Missing WHERE selectivity cap (0.8) | Medium | `test_sim_where_selectivity` | `tests/unit/test_matrix_simulator.py` | **PASS** |
| `SIM-IMPACT-LEVEL`| Impact tier classification | Medium | `test_sim_impact_level` | `tests/unit/test_matrix_simulator.py` | **PASS** |

### 2.7 Rewrite Engine Behaviors (9 Rows)

| Matrix ID | Description | Priority | Test Name | File | Status |
|:---|:---|:---:|:---|:---|:---:|
| `RWT-IN-EXISTS` | IN (subquery) to correlated EXISTS | High | `test_rwt_in_exists` | `tests/unit/test_matrix_rewrite.py` | **PASS** |
| `RWT-NOTIN-NOTEXISTS`| NOT IN to NOT EXISTS NULL trap fix | High | `test_rwt_notin_notexists` | `tests/unit/test_matrix_rewrite.py` | **PASS** |
| `RWT-DATE-RANGE` | YEAR(col) to sargable date range | High | `test_rwt_date_range` | `tests/unit/test_matrix_rewrite.py` | **PASS** |
| `RWT-SELECT-STAR`| SELECT * to explicit column projection | High | `test_rwt_select_star` | `tests/unit/test_matrix_rewrite.py` | **PASS** |
| `RWT-STATIC-VALID`| Static AST semantic validation | High | `test_rwt_static_valid` | `tests/unit/test_matrix_rewrite.py` | **PASS** |
| `RWT-UNION-ALL` | UNION to UNION ALL deduplication fix | Medium | `test_rwt_union_all` | `tests/unit/test_matrix_rewrite.py` | **PASS** |
| `RWT-FUNC-ARITH` | FunctionOnColumn case inversion | Medium | `test_rwt_func_on_column` | `tests/unit/test_matrix_rewrite.py` | **PASS** |
| `RWT-REM-DISTINCT`| Redundant DISTINCT elimination | Low | `test_rwt_rem_distinct` | `tests/unit/test_matrix_rewrite.py` | **PASS** |
| `RWT-LIMIT-INJECT`| Unbounded query LIMIT injection | Low | `test_rwt_limit_inject` | `tests/unit/test_matrix_rewrite.py` | **PASS** |

### 2.8 API Endpoints (9 Rows)

| Matrix ID | Description | Priority | Test Name | File | Status |
|:---|:---|:---:|:---|:---|:---:|
| `API-ANALYZE-OK` | POST /api/analyze returns 200 findings | High | `test_api_analyze_ok` | `tests/api/test_matrix_api.py` | **PASS** |
| `API-SCORE-OK` | POST /api/score returns 200 breakdown | High | `test_api_score_ok` | `tests/api/test_matrix_api.py` | **PASS** |
| `API-OPTIMIZE-OK`| POST /api/optimize returns strategies | High | `test_api_optimize_ok` | `tests/api/test_matrix_api.py` | **PASS** |
| `API-RECOMMEND-OK`| POST /api/recommendations returns DDL | High | `test_api_recommend_ok` | `tests/api/test_matrix_api.py` | **PASS** |
| `API-REWRITE-OK` | POST /api/rewrite returns rewritten SQL | High | `test_api_rewrite_ok` | `tests/api/test_matrix_api.py` | **PASS** |
| `API-EXEC-PLAN-OK`| POST /api/execution-plan returns tree | High | `test_api_exec_plan_ok` | `tests/api/test_matrix_api.py` | **PASS** |
| `API-SIM-INDEX-OK`| POST /api/simulate-index returns metrics | High | `test_api_sim_index_ok` | `tests/api/test_matrix_api.py` | **PASS** |
| `API-SAMPLE-QUERIES`| GET /api/sample-queries returns CSV catalog | Medium | `test_api_sample_queries_ok` | `tests/api/test_matrix_api.py` | **PASS** |
| `API-HEALTH-OK` | GET /api/health returns status ok | Medium | `test_api_health_ok` | `tests/api/test_matrix_api.py` | **PASS** |

### 2.9 Cross-Cutting & Security Boundaries (10 Rows)

| Matrix ID | Description | Priority | Test Name | File | Status |
|:---|:---|:---:|:---|:---|:---:|
| `EDGE-EMPTY-INPUT`| Empty/whitespace rejected with HTTP 422 | High | `test_edge_empty_input` | `tests/api/test_matrix_api.py` | **PASS** |
| `EDGE-OVERSIZE-INPUT`| Query >20,000 chars rejected with HTTP 422 | High | `test_edge_oversize_input` | `tests/api/test_matrix_api.py` | **PASS** |
| `EDGE-COMMENTS-ONLY`| Comments-only SQL rejected with HTTP 422 | High | `test_edge_comments_only` | `tests/api/test_matrix_api.py` | **PASS** |
| `EDGE-MULTI-STMT` | Multi-statement SQL rejected with HTTP 422 | High | `test_edge_multi_stmt` | `tests/api/test_matrix_api.py` | **PASS** |
| `EDGE-NULL-BYTES` | Null bytes (\x00) rejected with HTTP 422 | High | `test_edge_null_bytes` | `tests/api/test_matrix_api.py` | **PASS** |
| `EDGE-MALFORMED-SQL`| Malformed SQL handled cleanly (no 500) | High | `test_edge_malformed_sql` | `tests/api/test_matrix_api.py` | **PASS** |
| `EDGE-NON-SQL-TEXT`| Non-SQL arbitrary text rejected with HTTP 422 | High | `test_edge_non_sql_text` | `tests/api/test_matrix_api.py` | **PASS** |
| `EDGE-CORS-RESTRICT`| CORS restricted to allowed localhost | High | `test_edge_cors_restrict` | `tests/api/test_matrix_api.py` | **PASS** |
| `EDGE-UNICODE` | Unicode characters handled in literals/aliases | Medium | `test_edge_unicode` | `tests/api/test_matrix_api.py` | **PASS** |
| `EDGE-CONCURRENCY`| 10 simultaneous concurrent requests | Medium | `test_edge_concurrency` | `tests/api/test_matrix_api.py` | **PASS** |

### 2.10 Frontend UI Rows (Slated for Prompts 5 & 6)

| Matrix ID | Description | Status |
|:---|:---|:---:|
| `UI-PAGE-ANALYZE` | Analyze page loads, accepts query, renders findings | **NOT-TESTED** (Slated for Prompt 5 & 6) |
| `UI-PAGE-SCORE` | Score page renders gauge, badge, and breakdown table | **NOT-TESTED** (Slated for Prompt 5 & 6) |
| `UI-PAGE-RECOMMEND`| Recommendations page displays CREATE INDEX DDL | **NOT-TESTED** (Slated for Prompt 5 & 6) |
| `UI-PAGE-REWRITE` | Rewrite page displays query diff and rules | **NOT-TESTED** (Slated for Prompt 5 & 6) |
| `UI-PAGE-PLAN` | Execution plan page renders tree and costs | **NOT-TESTED** (Slated for Prompt 5 & 6) |
| `UI-PAGE-SIMULATE` | Simulate index page compares before/after metrics | **NOT-TESTED** (Slated for Prompt 5 & 6) |
| `UI-PAGE-SAMPLES` | Sample queries page loads catalog and filters | **NOT-TESTED** (Slated for Prompt 5 & 6) |
| `UI-PAGE-HEALTH` | Health dot and page reflect real backend health | **NOT-TESTED** (Slated for Prompt 5 & 6) |
| `UI-LOADING-STATE`| LoadingSpinner renders while API is pending | **NOT-TESTED** (Slated for Prompt 5 & 6) |
| `UI-ERROR-BANNER` | ErrorBanner displays structured backend error | **NOT-TESTED** (Slated for Prompt 5 & 6) |
| `UI-NAV-HISTORY` | Route navigation preserves state cleanly | **NOT-TESTED** (Slated for Prompt 5 & 6) |

---

## 3. Data-Driven Benchmark Results

- **Source File:** `data/sample_queries.csv`
- **Total Queries Evaluated:** 140 queries
- **Target Endpoints:** `POST /api/analyze` and `POST /api/score`
- **Total Requests Dispatched:** 280 HTTP POST requests
- **Unhandled Exceptions (500s):** **0**
- **Score Out-of-Bounds Violations (< 0 or > 100):** **0**
- **Test Function:** `test_data_driven_all_sample_queries` in `tests/api/test_matrix_api.py`

---

## 4. Discovered Bugs & Architectural Findings

### Finding 1: Incomplete Table Propagation in `analyzer.py`
- **Component:** `analyzer.py` -> `_analyze_with_features()`
- **Observed Behavior:** The dictionary returned by `analyze_query()` omitted the top-level `"tables"` list (which was extracted onto `features.tables`).
- **Impact:** In `scoring.py`, when applying table-size multipliers, `query_tables = analysis.get("tables", [])` returned `[]`. As a fallback, `scoring.py` evaluated all tables present in the connected schema. If any table in the schema had > 1M rows, the 2.0x multiplier was inadvertently applied to every query regardless of which table was actually queried.
- **Severity:** Major.

### Finding 2: Exact Boundary Categorization in `scoring.py`
- **Component:** `scoring.py` -> `COST_THRESHOLDS`
- **Observed Behavior:** `COST_THRESHOLDS` defines `MEDIUM` as `(50, 79)` and `HIGH` as `(0, 49)`. A query starting at base 100 with a single critical violation of -50 (e.g., `UPDATE_WITHOUT_WHERE` or `DELETE_WITHOUT_WHERE`) produces a score of exactly `50`. Because `score >= 50` is evaluated first, this boundary score is categorized as `MEDIUM` rather than `HIGH`.
- **Impact:** Unfiltered updates/deletes appear as `MEDIUM` cost unless an additional penalty (such as unindexed WHERE) pushes the score to 49 or lower.
- **Severity:** Minor / Cosmetic.

### Finding 3: Arithmetic Simplification Unsupported in Rewrite Engine
- **Component:** `rewrite_engine.py` -> `REWRITE_RULES_REGISTRY`
- **Observed Behavior:** While `detectors/non_sargable_arithmetic.py` flags expressions like `price + 15.00 > 100.00`, the rewrite engine only implements `FunctionOnColumnRule` for case inversion (`UPPER(col) = 'CONST' -> col = 'const'`). It does not contain an AST arithmetic solver to invert `col + 15 = 100` into `col = 85`.
- **Impact:** Queries with column arithmetic receive detector warnings and optimization advice, but are not rewritten to sargable equivalents by the rewrite engine.
- **Severity:** Moderate.

### Finding 4: Incomplete Edge-Case Validation in Initial REST Wrapper
- **Component:** `api/schemas.py` -> `QueryRequest`
- **Observed Behavior:** The initial Pydantic schema only validated string length and whitespace. Non-SQL plain text, null bytes (`\x00`), and comment-only inputs passed through to `analyzer.py`, which silently caught AST parse exceptions and returned HTTP 200 with regex fallback.
- **Fix Applied:** Integrated `validate_sql_input()` into `QueryRequest`'s Pydantic field validator. Malformed SQL, null bytes, comments-only, and multi-statement inputs are now cleanly rejected with HTTP 422 before reaching the analyzer.
- **Severity:** Major (Security / Input Sanitization).
