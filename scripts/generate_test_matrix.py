"""scripts/generate_test_matrix.py
Generates docs/TEST_MATRIX.md and docs/TEST_MATRIX.csv.
"""

import csv
import os

# Priority rank for sorting: High -> Medium -> Low
PRIORITY_ORDER = {"High": 1, "Medium": 2, "Low": 3}

MATRIX_ROWS = [
    # =========================================================================
    # 1. ANALYZER (Query pattern & anti-pattern detection)
    # =========================================================================
    {
        "id": "ANL-SEL-STAR",
        "feature_area": "Analyzer",
        "description": "Detects SELECT * projection retrieving all columns",
        "trigger_example": "SELECT * FROM users WHERE id = 10",
        "non_trigger_example": "SELECT id, name FROM users WHERE id = 10",
        "expected_result": "Produces issue with code 'SELECT_STAR' and severity 'HIGH'",
        "priority": "High",
    },
    {
        "id": "ANL-MISS-WHERE",
        "feature_area": "Analyzer",
        "description": "Detects SELECT statement missing a WHERE clause",
        "trigger_example": "SELECT id, name FROM customers",
        "non_trigger_example": "SELECT id, name FROM customers WHERE active = 1",
        "expected_result": "Produces issue with code 'MISSING_WHERE' and severity 'HIGH'",
        "priority": "High",
    },
    {
        "id": "ANL-EXCESS-JOIN",
        "feature_area": "Analyzer",
        "description": "Detects excessive JOIN count (> 2 JOINs)",
        "trigger_example": "SELECT o.id FROM orders o JOIN customers c ON o.customer_id = c.id JOIN items i ON o.id = i.order_id JOIN products p ON i.product_id = p.id",
        "non_trigger_example": "SELECT o.id FROM orders o JOIN customers c ON o.customer_id = c.id",
        "expected_result": "Produces issue with code 'EXCESSIVE_JOINS' and severity 'HIGH'",
        "priority": "High",
    },
    {
        "id": "ANL-CORR-SUBQ",
        "feature_area": "Analyzer",
        "description": "Detects correlated subqueries referencing outer table columns",
        "trigger_example": "SELECT c.name FROM customers c WHERE c.id IN (SELECT o.customer_id FROM orders o WHERE o.total > 500 AND o.customer_id = c.id)",
        "non_trigger_example": "SELECT c.name FROM customers c JOIN orders o ON c.id = o.customer_id WHERE o.total > 500",
        "expected_result": "Produces finding with code 'CORRELATED_SUBQUERY' and severity 'HIGH'",
        "priority": "High",
    },
    {
        "id": "ANL-TYPE-CONV",
        "feature_area": "Analyzer",
        "description": "Detects implicit type conversion comparing string/varchar column to numeric literal",
        "trigger_example": "SELECT id, name FROM customers WHERE phone = 1234567890",
        "non_trigger_example": "SELECT id, name FROM customers WHERE phone = '1234567890'",
        "expected_result": "Produces finding with code 'IMPLICIT_TYPE_CONVERSION' and severity 'HIGH'",
        "priority": "High",
    },
    {
        "id": "ANL-NOT-IN",
        "feature_area": "Analyzer",
        "description": "Detects NOT IN with subquery risking NULL trap and unnesting failures",
        "trigger_example": "SELECT id, name FROM customers WHERE id NOT IN (SELECT customer_id FROM orders)",
        "non_trigger_example": "SELECT id, name FROM customers c WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)",
        "expected_result": "Produces finding with code 'NOT_IN_SUBQUERY' and severity 'HIGH'",
        "priority": "High",
    },
    {
        "id": "ANL-ORD-RAND",
        "feature_area": "Analyzer",
        "description": "Detects ORDER BY RAND() forcing full table scan and filesort",
        "trigger_example": "SELECT id, name FROM products ORDER BY RAND() LIMIT 5",
        "non_trigger_example": "SELECT id, name FROM products ORDER BY id ASC LIMIT 5",
        "expected_result": "Produces finding with code 'ORDER_BY_RAND' and severity 'HIGH'",
        "priority": "High",
    },
    {
        "id": "ANL-MISS-JOIN-COND",
        "feature_area": "Analyzer",
        "description": "Detects accidental Cartesian product via CROSS JOIN or missing ON condition",
        "trigger_example": "SELECT c.name, o.id FROM customers c CROSS JOIN orders o",
        "non_trigger_example": "SELECT c.name, o.id FROM customers c JOIN orders o ON c.id = o.customer_id",
        "expected_result": "Produces finding with code 'MISSING_JOIN_CONDITION' and severity 'HIGH'",
        "priority": "High",
    },
    {
        "id": "ANL-INS-UNBOUND",
        "feature_area": "Analyzer",
        "description": "Detects unbounded INSERT...SELECT causing massive atomic locks",
        "trigger_example": "INSERT INTO archived_orders SELECT * FROM orders",
        "non_trigger_example": "INSERT INTO archived_orders SELECT id, total FROM orders WHERE status = 'delivered' LIMIT 1000",
        "expected_result": "Produces finding with code 'INSERT_SELECT_UNBOUNDED' and severity 'HIGH'",
        "priority": "High",
    },
    {
        "id": "ANL-UPD-NO-WHERE",
        "feature_area": "Analyzer",
        "description": "Detects catastrophic UPDATE statement without WHERE clause",
        "trigger_example": "UPDATE users SET status = 'inactive'",
        "non_trigger_example": "UPDATE users SET status = 'inactive' WHERE id = 42",
        "expected_result": "Produces finding with code 'UPDATE_WITHOUT_WHERE' and severity 'CRITICAL'",
        "priority": "High",
    },
    {
        "id": "ANL-DEL-NO-WHERE",
        "feature_area": "Analyzer",
        "description": "Detects catastrophic DELETE statement without WHERE clause",
        "trigger_example": "DELETE FROM logs",
        "non_trigger_example": "DELETE FROM logs WHERE created_at < '2023-01-01'",
        "expected_result": "Produces finding with code 'DELETE_WITHOUT_WHERE' and severity 'CRITICAL'",
        "priority": "High",
    },
    {
        "id": "ANL-DML-UNIDX-WHERE",
        "feature_area": "Analyzer",
        "description": "Detects UPDATE or DELETE filtering on unindexed column (lock escalation risk)",
        "trigger_example": "DELETE FROM audit_log WHERE event = 'login_failed'",
        "non_trigger_example": "DELETE FROM audit_log WHERE id = 105",
        "expected_result": "Produces finding with code 'UPDATE_DELETE_UNINDEXED_WHERE' and severity 'HIGH'",
        "priority": "High",
    },
    {
        "id": "ANL-SCHEMA-TBL",
        "feature_area": "Analyzer",
        "description": "Detects unknown table when schema metadata is provided",
        "trigger_example": "SELECT id FROM nonexistent_table_xyz WHERE id = 1",
        "non_trigger_example": "SELECT id FROM users WHERE id = 1",
        "expected_result": "Produces issue with code 'UNKNOWN_TABLE' and severity 'HIGH'",
        "priority": "High",
    },
    {
        "id": "ANL-SCHEMA-COL",
        "feature_area": "Analyzer",
        "description": "Detects unknown column when schema metadata is provided",
        "trigger_example": "SELECT nonexistent_column_xyz FROM users WHERE id = 1",
        "non_trigger_example": "SELECT name FROM users WHERE id = 1",
        "expected_result": "Produces issue with code 'UNKNOWN_COLUMN' and severity 'HIGH'",
        "priority": "High",
    },
    {
        "id": "ANL-JOIN-DET",
        "feature_area": "Analyzer",
        "description": "Detects standard JOIN requiring indexed join condition",
        "trigger_example": "SELECT o.id, c.name FROM orders o JOIN customers c ON o.customer_id = c.id WHERE o.status = 'shipped'",
        "non_trigger_example": "SELECT id, name FROM customers WHERE id = 10",
        "expected_result": "Produces issue with code 'JOIN_DETECTED' and severity 'MEDIUM'",
        "priority": "Medium",
    },
    {
        "id": "ANL-SUBQ-DET",
        "feature_area": "Analyzer",
        "description": "Detects subquery present in query",
        "trigger_example": "SELECT name FROM employees WHERE salary > (SELECT AVG(salary) FROM employees)",
        "non_trigger_example": "SELECT name, salary FROM employees WHERE salary > 50000",
        "expected_result": "Produces issue with code 'SUBQUERY_DETECTED' and severity 'MEDIUM'",
        "priority": "Medium",
    },
    {
        "id": "ANL-MISS-LIMIT",
        "feature_area": "Analyzer",
        "description": "Detects missing LIMIT on unbounded SELECT lacking WHERE",
        "trigger_example": "SELECT name FROM customers",
        "non_trigger_example": "SELECT name FROM customers LIMIT 50",
        "expected_result": "Produces issue with code 'MISSING_LIMIT' and severity 'MEDIUM'",
        "priority": "Medium",
    },
    {
        "id": "ANL-LEAD-WILD",
        "feature_area": "Analyzer",
        "description": "Detects leading wildcard in LIKE pattern (preventing index seeks)",
        "trigger_example": "SELECT id, name FROM users WHERE email LIKE '%@gmail.com'",
        "non_trigger_example": "SELECT id, name FROM users WHERE email LIKE 'john%'",
        "expected_result": "Produces warning with code 'LEADING_WILDCARD' and severity 'MEDIUM'",
        "priority": "Medium",
    },
    {
        "id": "ANL-FUNC-COL",
        "feature_area": "Analyzer",
        "description": "Detects function wrapped around column in WHERE (invalidating index seek)",
        "trigger_example": "SELECT id FROM users WHERE UPPER(email) = 'TEST@EXAMPLE.COM'",
        "non_trigger_example": "SELECT id FROM users WHERE email = 'test@example.com'",
        "expected_result": "Produces warning with code 'FUNCTION_ON_COLUMN' and severity 'MEDIUM'",
        "priority": "Medium",
    },
    {
        "id": "ANL-AGG-SCAN",
        "feature_area": "Analyzer",
        "description": "Detects aggregate function with no WHERE or GROUP BY (full table scan)",
        "trigger_example": "SELECT AVG(salary) FROM employees",
        "non_trigger_example": "SELECT AVG(salary) FROM employees WHERE department = 'IT'",
        "expected_result": "Produces warning with code 'AGGREGATE_FULL_SCAN' and severity 'MEDIUM'",
        "priority": "Medium",
    },
    {
        "id": "ANL-OR-DIFF-COL",
        "feature_area": "Analyzer",
        "description": "Detects OR condition across different columns preventing single index seek",
        "trigger_example": "SELECT id, total FROM orders WHERE customer_id = 42 OR status = 'pending'",
        "non_trigger_example": "SELECT id, total FROM orders WHERE customer_id = 42 OR customer_id = 99",
        "expected_result": "Produces finding with code 'OR_DIFFERENT_COLUMNS' and severity 'MEDIUM'",
        "priority": "Medium",
    },
    {
        "id": "ANL-UNIDX-ORD",
        "feature_area": "Analyzer",
        "description": "Detects ORDER BY on unindexed column requiring temporary filesort",
        "trigger_example": "SELECT id, name FROM customers ORDER BY name LIMIT 10",
        "non_trigger_example": "SELECT id, name FROM customers ORDER BY id LIMIT 10",
        "expected_result": "Produces finding with code 'UNINDEXED_ORDER_BY' and severity 'MEDIUM'",
        "priority": "Medium",
    },
    {
        "id": "ANL-LRG-OFFSET",
        "feature_area": "Analyzer",
        "description": "Detects deep pagination OFFSET (> 1000) scanning and discarding rows",
        "trigger_example": "SELECT id, total FROM orders ORDER BY id ASC LIMIT 20 OFFSET 5000",
        "non_trigger_example": "SELECT id, total FROM orders WHERE id > 5000 ORDER BY id ASC LIMIT 20",
        "expected_result": "Produces finding with code 'LARGE_OFFSET' and severity 'MEDIUM'",
        "priority": "Medium",
    },
    {
        "id": "ANL-NON-SARG-ARITH",
        "feature_area": "Analyzer",
        "description": "Detects non-sargable arithmetic expression on column in WHERE clause",
        "trigger_example": "SELECT id, price FROM products WHERE price + 15.00 > 100.00",
        "non_trigger_example": "SELECT id, price FROM products WHERE price > 85.00",
        "expected_result": "Produces finding with code 'NON_SARGABLE_ARITHMETIC' and severity 'MEDIUM'",
        "priority": "Medium",
    },
    {
        "id": "ANL-UNION-ALL",
        "feature_area": "Analyzer",
        "description": "Detects UNION instead of UNION ALL incurring temp table deduplication overhead",
        "trigger_example": "SELECT id FROM orders WHERE status = 'shipped' UNION SELECT id FROM orders WHERE status = 'delivered'",
        "non_trigger_example": "SELECT id FROM orders WHERE status = 'shipped' UNION ALL SELECT id FROM orders WHERE status = 'delivered'",
        "expected_result": "Produces finding with code 'UNION_INSTEAD_OF_UNION_ALL' and severity 'MEDIUM'",
        "priority": "Medium",
    },
    {
        "id": "ANL-CTE-MULT",
        "feature_area": "Analyzer",
        "description": "Detects CTE referenced multiple times risking duplicated evaluation in MySQL 8",
        "trigger_example": "WITH user_orders AS (SELECT customer_id, COUNT(*) AS cnt FROM orders GROUP BY customer_id) SELECT c.name, u1.cnt, u2.cnt FROM customers c JOIN user_orders u1 ON c.id = u1.customer_id JOIN user_orders u2 ON c.id = u2.customer_id",
        "non_trigger_example": "WITH recent_orders AS (SELECT * FROM orders WHERE created_at > '2024-01-01') SELECT * FROM recent_orders LIMIT 10",
        "expected_result": "Produces finding with code 'CTE_MULTIPLY_REFERENCED' and severity 'MEDIUM'",
        "priority": "Medium",
    },
    {
        "id": "ANL-WIN-NO-PART",
        "feature_area": "Analyzer",
        "description": "Detects window function without PARTITION BY forcing global filesort frame",
        "trigger_example": "SELECT id, total, ROW_NUMBER() OVER (ORDER BY total DESC) FROM orders",
        "non_trigger_example": "SELECT id, customer_id, total, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY total DESC) FROM orders",
        "expected_result": "Produces finding with code 'WINDOW_WITHOUT_PARTITION' and severity 'MEDIUM'",
        "priority": "Medium",
    },
    {
        "id": "ANL-DIST-JOIN",
        "feature_area": "Analyzer",
        "description": "Detects SELECT DISTINCT with JOIN (often masking duplicate join rows)",
        "trigger_example": "SELECT DISTINCT product_id FROM order_items JOIN orders ON order_items.order_id = orders.id",
        "non_trigger_example": "SELECT DISTINCT category FROM products",
        "expected_result": "Produces warning with code 'DISTINCT_WITH_JOIN' and severity 'Low'",
        "priority": "Low",
    },
    {
        "id": "ANL-HAV-AS-WHERE",
        "feature_area": "Analyzer",
        "description": "Detects non-aggregated column filtered in HAVING instead of WHERE",
        "trigger_example": "SELECT status, COUNT(*) FROM orders GROUP BY status HAVING status = 'completed'",
        "non_trigger_example": "SELECT status, COUNT(*) FROM orders WHERE status = 'completed' GROUP BY status",
        "expected_result": "Produces finding with code 'HAVING_AS_WHERE' and severity 'LOW'",
        "priority": "Low",
    },
    {
        "id": "ANL-CNT-DIST",
        "feature_area": "Analyzer",
        "description": "Detects COUNT(DISTINCT) requiring temporary hash table deduplication",
        "trigger_example": "SELECT COUNT(DISTINCT customer_id) FROM orders",
        "non_trigger_example": "SELECT COUNT(customer_id) FROM orders",
        "expected_result": "Produces finding with code 'COUNT_DISTINCT' and severity 'LOW'",
        "priority": "Low",
    },
    {
        "id": "ANL-INS-SINGLE",
        "feature_area": "Analyzer",
        "description": "Detects single-row INSERT when bulk insertion is preferred",
        "trigger_example": "INSERT INTO customers (id, name, email) VALUES (1, 'Alice', 'alice@example.com')",
        "non_trigger_example": "INSERT INTO customers (id, name, email) VALUES (1, 'Alice', 'alice@example.com'), (2, 'Bob', 'bob@example.com')",
        "expected_result": "Produces finding with code 'INSERT_SINGLE_ROW' and severity 'LOW'",
        "priority": "Low",
    },

    # =========================================================================
    # 2. SCORING (Explainable 0-100 Performance Score & Cost Estimation)
    # =========================================================================
    {
        "id": "SCR-BASE-CALC",
        "feature_area": "Scoring",
        "description": "Computes baseline score of 100 minus rule penalty deductions",
        "trigger_example": "SELECT * FROM users",
        "non_trigger_example": "SELECT id, name FROM users WHERE id = 1 LIMIT 1",
        "expected_result": "Calculates total score = 100 - penalties (e.g. SELECT_STAR -25, MISSING_WHERE -20, MISSING_LIMIT -10)",
        "priority": "High",
    },
    {
        "id": "SCR-SCORE-BOUNDS",
        "feature_area": "Scoring",
        "description": "Clips score strictly within 0 to 100 range regardless of excessive penalties/bonuses",
        "trigger_example": "UPDATE users SET name = 'X'",
        "non_trigger_example": "SELECT id FROM users WHERE id = 1 LIMIT 1",
        "expected_result": "Score is bounded: min score >= 0 and max score <= 100",
        "priority": "High",
    },
    {
        "id": "SCR-COST-TIERS",
        "feature_area": "Scoring",
        "description": "Categorizes score into cost tiers: >=80 LOW, 50-79 MEDIUM, <50 HIGH",
        "trigger_example": "SELECT * FROM users",
        "non_trigger_example": "SELECT id FROM users WHERE id = 1 LIMIT 1",
        "expected_result": "Returns cost_estimate in ('LOW', 'MEDIUM', 'HIGH') corresponding to numeric thresholds",
        "priority": "High",
    },
    {
        "id": "SCR-STMT-UPDATE",
        "feature_area": "Scoring",
        "description": "Applies statement-specific scoring rules for UPDATE statements",
        "trigger_example": "UPDATE users SET status = 'inactive'",
        "non_trigger_example": "SELECT status FROM users",
        "expected_result": "Applies UPDATE_WITHOUT_WHERE penalty (-50) resulting in score <= 50 and HIGH cost",
        "priority": "High",
    },
    {
        "id": "SCR-STMT-DELETE",
        "feature_area": "Scoring",
        "description": "Applies statement-specific scoring rules for DELETE statements",
        "trigger_example": "DELETE FROM sessions",
        "non_trigger_example": "SELECT * FROM sessions",
        "expected_result": "Applies DELETE_WITHOUT_WHERE penalty (-50) resulting in score <= 50 and HIGH cost",
        "priority": "High",
    },
    {
        "id": "SCR-TBL-MULTIPLIER",
        "feature_area": "Scoring",
        "description": "Scales penalties by table size multiplier (1.0x <10k, 1.5x 10k-1M, 2.0x >1M rows)",
        "trigger_example": "SELECT * FROM large_table_1m",
        "non_trigger_example": "SELECT * FROM small_table_500",
        "expected_result": "With schema table rows > 1,000,000, penalty deltas are multiplied by 2.0x",
        "priority": "High",
    },
    {
        "id": "SCR-BONUS-WHERE",
        "feature_area": "Scoring",
        "description": "Awards positive bonus (+10) for explicit WHERE filter clause",
        "trigger_example": "SELECT id FROM users WHERE status = 'active'",
        "non_trigger_example": "SELECT id FROM users",
        "expected_result": "Score breakdown includes HAS_WHERE bonus with delta +10",
        "priority": "Medium",
    },
    {
        "id": "SCR-BONUS-LIMIT",
        "feature_area": "Scoring",
        "description": "Awards positive bonus (+10) for result-capping LIMIT clause",
        "trigger_example": "SELECT id FROM users WHERE status = 'active' LIMIT 10",
        "non_trigger_example": "SELECT id FROM users WHERE status = 'active'",
        "expected_result": "Score breakdown includes HAS_LIMIT bonus with delta +10",
        "priority": "Medium",
    },
    {
        "id": "SCR-BONUS-COLS",
        "feature_area": "Scoring",
        "description": "Awards positive bonus (+10) for explicit projection instead of SELECT *",
        "trigger_example": "SELECT id, name FROM users WHERE id = 1",
        "non_trigger_example": "SELECT * FROM users WHERE id = 1",
        "expected_result": "Score breakdown includes SPECIFIC_COLUMNS bonus with delta +10",
        "priority": "Medium",
    },
    {
        "id": "SCR-SIM-OPTIMIZED",
        "feature_area": "Scoring",
        "description": "Projects simulated score after anti-patterns are resolved (simulate_optimized_score)",
        "trigger_example": "SELECT * FROM users",
        "non_trigger_example": "SELECT id FROM users WHERE id = 1 LIMIT 1",
        "expected_result": "Returns an optimized estimate score significantly higher than initial score",
        "priority": "Medium",
    },
    {
        "id": "SCR-BONUS-BULK",
        "feature_area": "Scoring",
        "description": "Awards positive bonus (+15) for multi-row bulk INSERT",
        "trigger_example": "INSERT INTO users (id, name) VALUES (1, 'A'), (2, 'B')",
        "non_trigger_example": "INSERT INTO users (id, name) VALUES (1, 'A')",
        "expected_result": "Score breakdown includes BULK_INSERT bonus with delta +15",
        "priority": "Low",
    },

    # =========================================================================
    # 3. OPTIMIZER (Recommendation Engine & Rule Insights)
    # =========================================================================
    {
        "id": "OPT-REC-STAR",
        "feature_area": "Optimizer",
        "description": "Generates recommendation to replace SELECT * with specific columns",
        "trigger_example": "SELECT * FROM users WHERE id = 10",
        "non_trigger_example": "SELECT id, name FROM users WHERE id = 10",
        "expected_result": "Emits recommendation with title 'Replace SELECT * with specific columns' and priority 'HIGH'",
        "priority": "High",
    },
    {
        "id": "OPT-REC-WHERE",
        "feature_area": "Optimizer",
        "description": "Generates recommendation to add WHERE clause on full table scan",
        "trigger_example": "SELECT name FROM customers",
        "non_trigger_example": "SELECT name FROM customers WHERE active = 1",
        "expected_result": "Emits recommendation with title 'Add a WHERE clause to filter rows early' and priority 'HIGH'",
        "priority": "High",
    },
    {
        "id": "OPT-REC-SORT",
        "feature_area": "Optimizer",
        "description": "Sorts optimization recommendations by priority order (CRITICAL -> HIGH -> MEDIUM -> LOW)",
        "trigger_example": "UPDATE users SET status = 'inactive'",
        "non_trigger_example": "SELECT 1",
        "expected_result": "Recommendations list has CRITICAL/HIGH priority items placed before MEDIUM/LOW items",
        "priority": "High",
    },
    {
        "id": "OPT-REC-JOIN",
        "feature_area": "Optimizer",
        "description": "Generates recommendation to index JOIN/ON columns",
        "trigger_example": "SELECT o.id, c.name FROM orders o JOIN customers c ON o.customer_id = c.id",
        "non_trigger_example": "SELECT id FROM orders WHERE id = 5",
        "expected_result": "Emits recommendation to index join columns with example CREATE INDEX",
        "priority": "Medium",
    },
    {
        "id": "OPT-REC-LIMIT",
        "feature_area": "Optimizer",
        "description": "Generates recommendation to add LIMIT to cap result set size",
        "trigger_example": "SELECT id, name FROM orders",
        "non_trigger_example": "SELECT id, name FROM orders LIMIT 10",
        "expected_result": "Emits recommendation with title 'Add LIMIT to cap result-set size'",
        "priority": "Medium",
    },
    {
        "id": "OPT-REC-WILDCARD",
        "feature_area": "Optimizer",
        "description": "Generates recommendation to avoid leading wildcards in LIKE",
        "trigger_example": "SELECT id FROM users WHERE email LIKE '%@gmail.com'",
        "non_trigger_example": "SELECT id FROM users WHERE email LIKE 'admin%'",
        "expected_result": "Emits recommendation with title 'Avoid leading wildcards in LIKE patterns'",
        "priority": "Medium",
    },
    {
        "id": "OPT-REC-FUNC",
        "feature_area": "Optimizer",
        "description": "Generates recommendation to remove function from WHERE column reference",
        "trigger_example": "SELECT id FROM users WHERE UPPER(email) = 'A@B.COM'",
        "non_trigger_example": "SELECT id FROM users WHERE email = 'a@b.com'",
        "expected_result": "Emits recommendation with title 'Remove functions from WHERE column references'",
        "priority": "Medium",
    },
    {
        "id": "OPT-INSIGHT-GEN",
        "feature_area": "Optimizer",
        "description": "Generates deterministic natural-language rule insight paragraph summarizing query complexity and issues",
        "trigger_example": "SELECT * FROM orders WHERE customer_id = 10",
        "non_trigger_example": "SELECT 1",
        "expected_result": "Returns markdown-formatted insight string stating query complexity, score, and key anti-patterns",
        "priority": "Medium",
    },

    # =========================================================================
    # 4. RECOMMENDATIONS (Index Generation & DDL Strategy)
    # =========================================================================
    {
        "id": "REC-IDX-SINGLE",
        "feature_area": "Recommendations",
        "description": "Generates single-column B-tree CREATE INDEX for isolated WHERE/JOIN filter",
        "trigger_example": "SELECT name FROM customers WHERE city = 'Hyderabad'",
        "non_trigger_example": "SELECT * FROM customers",
        "expected_result": "Generates valid DDL: CREATE INDEX idx_customers_city ON customers(city);",
        "priority": "High",
    },
    {
        "id": "REC-IDX-COMPOSITE",
        "feature_area": "Recommendations",
        "description": "Generates composite index ordered by Equality -> Range -> ORDER BY columns",
        "trigger_example": "SELECT id, name FROM products WHERE category_id = 5 AND price < 100 ORDER BY created_at",
        "non_trigger_example": "SELECT id FROM products WHERE id = 1",
        "expected_result": "Generates composite DDL with column order (category_id, price, created_at) and explanatory ordering notes",
        "priority": "High",
    },
    {
        "id": "REC-IDX-COVERING",
        "feature_area": "Recommendations",
        "description": "Generates covering index containing filter columns leading and projected columns trailing",
        "trigger_example": "SELECT name, email FROM customers WHERE status = 'active'",
        "non_trigger_example": "SELECT * FROM customers WHERE status = 'active'",
        "expected_result": "Generates covering index DDL: CREATE INDEX idx_cov_customers_... ON customers(status, name, email);",
        "priority": "High",
    },
    {
        "id": "REC-DUP-DETECT",
        "feature_area": "Recommendations",
        "description": "Detects exact duplicate indexes on the same table and suggests DROP INDEX",
        "trigger_example": "SELECT id FROM table_with_duplicate_indexes WHERE col_a = 1",
        "non_trigger_example": "SELECT id FROM table_with_unique_index WHERE col_a = 1",
        "expected_result": "detect_redundant_indexes returns DUPLICATE_INDEX record with valid DROP INDEX DDL",
        "priority": "High",
    },
    {
        "id": "REC-PREFIX-REDUND",
        "feature_area": "Recommendations",
        "description": "Detects leftmost prefix redundant indexes covered by existing composite index",
        "trigger_example": "SELECT id FROM table_with_prefix_index WHERE col_a = 1",
        "non_trigger_example": "SELECT id FROM table_with_distinct_indexes WHERE col_b = 1",
        "expected_result": "detect_redundant_indexes returns PREFIX_REDUNDANT record with DROP INDEX DDL",
        "priority": "High",
    },
    {
        "id": "REC-SKIP-EXIST",
        "feature_area": "Recommendations",
        "description": "Suppresses index recommendation when an index with matching leftmost prefix already exists in schema",
        "trigger_example": "SELECT id, name FROM users WHERE id = 5",
        "non_trigger_example": "SELECT id, name FROM users WHERE unindexed_col = 5",
        "expected_result": "Skips creating redundant recommendation for PRIMARY key column 'id'",
        "priority": "High",
    },
    {
        "id": "REC-IDX-CAP-4",
        "feature_area": "Recommendations",
        "description": "Caps composite index candidate columns at maximum of 4 to prevent write amplification",
        "trigger_example": "SELECT * FROM orders WHERE c1 = 1 AND c2 = 2 AND c3 = 3 AND c4 = 4 AND c5 = 5",
        "non_trigger_example": "SELECT * FROM orders WHERE c1 = 1 AND c2 = 2",
        "expected_result": "Generated composite index has at most 4 columns with flag is_capped=True",
        "priority": "Medium",
    },
    {
        "id": "REC-IDX-PREFIX",
        "feature_area": "Recommendations",
        "description": "Generates prefix index col(191) for long text / VARCHAR columns exceeding B-tree byte limits",
        "trigger_example": "SELECT id FROM articles WHERE body = 'sample'",
        "non_trigger_example": "SELECT id FROM articles WHERE id = 10",
        "expected_result": "Generates prefix index DDL containing ON articles(body(191))",
        "priority": "Medium",
    },
    {
        "id": "REC-IDX-FULLTEXT",
        "feature_area": "Recommendations",
        "description": "Recommends FULLTEXT index for leading/contains wildcard LIKE queries",
        "trigger_example": "SELECT id FROM articles WHERE content LIKE '%database%'",
        "non_trigger_example": "SELECT id FROM articles WHERE id = 10",
        "expected_result": "Recommends FULLTEXT index with ALTER TABLE ... ADD FULLTEXT INDEX",
        "priority": "Medium",
    },
    {
        "id": "REC-SAFE-NAME",
        "feature_area": "Recommendations",
        "description": "Enforces MySQL 64-character identifier length limit using MD5 hash truncation",
        "trigger_example": "SELECT * FROM very_long_table_name_exceeding_standard_limits WHERE extremely_long_column_name_part_one = 1 AND extremely_long_column_name_part_two = 2",
        "non_trigger_example": "SELECT * FROM users WHERE id = 1",
        "expected_result": "Generated index name is <= 64 characters and matches format idx_..._<hash>",
        "priority": "Medium",
    },
    {
        "id": "REC-SIZE-EST",
        "feature_area": "Recommendations",
        "description": "Estimates secondary index storage footprint in B/KB/MB based on column types and row counts",
        "trigger_example": "SELECT name FROM users WHERE email = 'test@example.com'",
        "non_trigger_example": "SELECT 1",
        "expected_result": "Returns estimated_size string with estimated KB/MB value and calculation rationale",
        "priority": "Low",
    },
    {
        "id": "REC-TRADE-OFFS",
        "feature_area": "Recommendations",
        "description": "Provides explicit trade-offs note covering read gains vs insert/update write amplification",
        "trigger_example": "SELECT name FROM users WHERE email = 'test@example.com'",
        "non_trigger_example": "SELECT 1",
        "expected_result": "Recommendation includes trade_offs explaining read speedup and secondary index maintenance overhead",
        "priority": "Low",
    },

    # =========================================================================
    # 5. EXECUTION PLAN (Simulated MySQL 8.x EXPLAIN Tree)
    # =========================================================================
    {
        "id": "PLN-SCAN-ALL",
        "feature_area": "ExecutionPlan",
        "description": "Generates Full Table Scan (ALL) node for unindexed or unconstrained queries",
        "trigger_example": "SELECT * FROM customers",
        "non_trigger_example": "SELECT * FROM customers WHERE id = 10",
        "expected_result": "Plan root or scan node has access_type='ALL' and high total_cost",
        "priority": "High",
    },
    {
        "id": "PLN-SCAN-REF",
        "feature_area": "ExecutionPlan",
        "description": "Generates non-unique index lookup (ref) node for equality filter on indexed column",
        "trigger_example": "SELECT * FROM orders WHERE customer_id = 42",
        "non_trigger_example": "SELECT * FROM orders",
        "expected_result": "Plan node has access_type='ref' with lower total_cost than ALL",
        "priority": "High",
    },
    {
        "id": "PLN-SCAN-RANGE",
        "feature_area": "ExecutionPlan",
        "description": "Generates index range scan (range) node for BETWEEN / inequality conditions",
        "trigger_example": "SELECT * FROM orders WHERE total BETWEEN 100 AND 500",
        "non_trigger_example": "SELECT * FROM orders",
        "expected_result": "Plan node has access_type='range' and 'Using index condition' in extra",
        "priority": "Medium",
    },
    {
        "id": "PLN-SCAN-INDEX",
        "feature_area": "ExecutionPlan",
        "description": "Generates covering index scan (index) node with 'Using index' in extra",
        "trigger_example": "SELECT customer_id FROM orders WHERE customer_id = 42",
        "non_trigger_example": "SELECT * FROM orders",
        "expected_result": "Plan node has access_type='index' and 'Using index' in extra list",
        "priority": "Medium",
    },
    {
        "id": "PLN-JOIN-HASH",
        "feature_area": "ExecutionPlan",
        "description": "Generates Hash Join node for join conditions lacking supporting index",
        "trigger_example": "SELECT * FROM orders o JOIN customers c ON o.notes = c.notes",
        "non_trigger_example": "SELECT * FROM orders o WHERE o.id = 1",
        "expected_result": "Plan contains node with node_type='Hash Join' and access_type='hash_join'",
        "priority": "Medium",
    },
    {
        "id": "PLN-JOIN-LOOP",
        "feature_area": "ExecutionPlan",
        "description": "Generates Nested Loop join node for indexed join lookups",
        "trigger_example": "SELECT * FROM orders o JOIN customers c ON o.customer_id = c.id",
        "non_trigger_example": "SELECT * FROM orders",
        "expected_result": "Plan contains node with node_type='Nested Loop' and access_type='nested_loop'",
        "priority": "Medium",
    },
    {
        "id": "PLN-FILTER-WHERE",
        "feature_area": "ExecutionPlan",
        "description": "Generates Filter node with 'Using where' attribute when row-level evaluation occurs",
        "trigger_example": "SELECT * FROM products WHERE price > 50",
        "non_trigger_example": "SELECT * FROM products",
        "expected_result": "Plan includes Filter node with 'Using where' in extra attribute",
        "priority": "Low",
    },

    # =========================================================================
    # 6. SIMULATOR (Before/After Index Impact Estimation)
    # =========================================================================
    {
        "id": "SIM-METRICS-CALC",
        "feature_area": "Simulator",
        "description": "Calculates projected improvements in score, cost, scanned rows, and estimated execution time",
        "trigger_example": "SELECT * FROM orders WHERE customer_id = 10",
        "non_trigger_example": "SELECT 1",
        "expected_result": "Returns dict with after_score > before_score, after_rows < before_rows, and calculated time_ms",
        "priority": "High",
    },
    {
        "id": "SIM-SPEEDUP-FACTOR",
        "feature_area": "Simulator",
        "description": "Calculates speedup factor as ratio of sequential scan time to indexed seek time",
        "trigger_example": "SELECT * FROM orders WHERE customer_id = 10",
        "non_trigger_example": "SELECT 1",
        "expected_result": "speedup_factor is a float >= 1.0 with label matching '~X.X× faster (est.)'",
        "priority": "High",
    },
    {
        "id": "SIM-WHERE-SELECTIVITY",
        "feature_area": "Simulator",
        "description": "Recognizes missing WHERE clause limits index impact (selectivity defaults to 0.8)",
        "trigger_example": "SELECT * FROM orders",
        "non_trigger_example": "SELECT * FROM orders WHERE id = 10",
        "expected_result": "When MISSING_WHERE is present, index simulation yields minor impact (selectivity 0.8)",
        "priority": "Medium",
    },
    {
        "id": "SIM-IMPACT-LEVEL",
        "feature_area": "Simulator",
        "description": "Classifies impact into Transformative (>=50x), Major (>=10x), Moderate (>=2x), or Minor (<2x)",
        "trigger_example": "SELECT * FROM orders WHERE customer_id = 10",
        "non_trigger_example": "SELECT * FROM orders",
        "expected_result": "impact_level string matches one of ('Transformative', 'Major', 'Moderate', 'Minor')",
        "priority": "Medium",
    },

    # =========================================================================
    # 7. REWRITE ENGINE (AST-Driven Query Transformations)
    # =========================================================================
    {
        "id": "RWT-IN-EXISTS",
        "feature_area": "RewriteEngine",
        "description": "Rewrites IN (subquery) to correlated EXISTS to avoid intermediate set materialization",
        "trigger_example": "SELECT name FROM customers WHERE id IN (SELECT customer_id FROM orders)",
        "non_trigger_example": "SELECT name FROM customers WHERE id = 10",
        "expected_result": "Query rewritten to use EXISTS (SELECT 1 FROM orders WHERE ...)",
        "priority": "High",
    },
    {
        "id": "RWT-NOTIN-NOTEXISTS",
        "feature_area": "RewriteEngine",
        "description": "Rewrites NOT IN (subquery) to NOT EXISTS eliminating NULL trap and suboptimal unnesting",
        "trigger_example": "SELECT id, name FROM customers WHERE id NOT IN (SELECT customer_id FROM orders)",
        "non_trigger_example": "SELECT id, name FROM customers WHERE id = 10",
        "expected_result": "Query rewritten to use NOT EXISTS (SELECT 1 FROM orders WHERE ...)",
        "priority": "High",
    },
    {
        "id": "RWT-DATE-RANGE",
        "feature_area": "RewriteEngine",
        "description": "Rewrites YEAR(col) = YYYY into sargable date range col >= 'YYYY-01-01' AND col <= 'YYYY-12-31'",
        "trigger_example": "SELECT * FROM orders WHERE YEAR(order_date) = 2024",
        "non_trigger_example": "SELECT * FROM orders WHERE order_date >= '2024-01-01'",
        "expected_result": "Query rewritten to range comparison enabling B-tree index seek on order_date",
        "priority": "High",
    },
    {
        "id": "RWT-SELECT-STAR",
        "feature_area": "RewriteEngine",
        "description": "Expands SELECT * into explicit table columns using schema or column hints",
        "trigger_example": "SELECT * FROM users WHERE id = 10",
        "non_trigger_example": "SELECT id, name FROM users WHERE id = 10",
        "expected_result": "Rewritten query contains explicit column projections (e.g. id, name, email, created_at)",
        "priority": "High",
    },
    {
        "id": "RWT-STATIC-VALID",
        "feature_area": "RewriteEngine",
        "description": "Validates syntactic correctness and semantic equivalence of generated rewrites (rewrite_validation)",
        "trigger_example": "SELECT * FROM users WHERE id IN (SELECT customer_id FROM orders)",
        "non_trigger_example": "SELECT 1",
        "expected_result": "validate_rewrite_static returns is_valid=True and equivalence_level in ('VERIFIED_EQUIVALENT', 'LIKELY_EQUIVALENT')",
        "priority": "High",
    },
    {
        "id": "RWT-UNION-ALL",
        "feature_area": "RewriteEngine",
        "description": "Rewrites UNION to UNION ALL when duplicate rows do not require deduplication",
        "trigger_example": "SELECT id FROM orders WHERE status = 'shipped' UNION SELECT id FROM orders WHERE status = 'delivered'",
        "non_trigger_example": "SELECT id FROM orders WHERE status = 'shipped' UNION ALL SELECT id FROM orders WHERE status = 'delivered'",
        "expected_result": "Rewrites UNION keyword to UNION ALL with explanation note",
        "priority": "Medium",
    },
    {
        "id": "RWT-FUNC-ARITH",
        "feature_area": "RewriteEngine",
        "description": "Rewrites non-sargable column arithmetic (e.g. col + 10 = 100 -> col = 90) into sargable comparison",
        "trigger_example": "SELECT id, price FROM products WHERE price + 15.00 = 100.00",
        "non_trigger_example": "SELECT id, price FROM products WHERE price = 85.00",
        "expected_result": "Rewritten query isolates column on left-hand side enabling B-tree seek",
        "priority": "Medium",
    },
    {
        "id": "RWT-REM-DISTINCT",
        "feature_area": "RewriteEngine",
        "description": "Removes redundant DISTINCT when query groups by all selected columns or filters on unique key",
        "trigger_example": "SELECT DISTINCT department, COUNT(*) FROM employees GROUP BY department",
        "non_trigger_example": "SELECT DISTINCT city FROM customers",
        "expected_result": "Rewrites query by stripping unnecessary DISTINCT keyword",
        "priority": "Low",
    },
    {
        "id": "RWT-LIMIT-INJECT",
        "feature_area": "RewriteEngine",
        "description": "Injects protective LIMIT clause on unbounded SELECT queries",
        "trigger_example": "SELECT id, name FROM customers",
        "non_trigger_example": "SELECT id, name FROM customers LIMIT 100",
        "expected_result": "Rewritten query appends LIMIT clause to bound result size",
        "priority": "Low",
    },

    # =========================================================================
    # 8. API ENDPOINTS (FastAPI REST Interface)
    # =========================================================================
    {
        "id": "API-ANALYZE-OK",
        "feature_area": "ApiEndpoints",
        "description": "POST /api/analyze returns 200 with structured analysis findings and query metadata",
        "trigger_example": "POST /api/analyze with {'query': 'SELECT * FROM users'}",
        "non_trigger_example": "POST /api/analyze with empty query",
        "expected_result": "HTTP 200 with JSON payload containing query_type, complexity, issues, and warnings",
        "priority": "High",
    },
    {
        "id": "API-SCORE-OK",
        "feature_area": "ApiEndpoints",
        "description": "POST /api/score returns 200 with numeric score, cost tier, and detailed rule breakdown",
        "trigger_example": "POST /api/score with {'query': 'SELECT * FROM users'}",
        "non_trigger_example": "POST /api/score with empty query",
        "expected_result": "HTTP 200 with JSON payload containing score (0-100), cost, and breakdown list",
        "priority": "High",
    },
    {
        "id": "API-OPTIMIZE-OK",
        "feature_area": "ApiEndpoints",
        "description": "POST /api/optimize returns 200 with prioritized recommendations and insight text",
        "trigger_example": "POST /api/optimize with {'query': 'SELECT * FROM users'}",
        "non_trigger_example": "POST /api/optimize with empty query",
        "expected_result": "HTTP 200 with JSON payload containing recommendations array and insight paragraph",
        "priority": "High",
    },
    {
        "id": "API-RECOMMEND-OK",
        "feature_area": "ApiEndpoints",
        "description": "POST /api/recommendations returns 200 with CREATE INDEX suggestions and trade-offs",
        "trigger_example": "POST /api/recommendations with {'query': 'SELECT * FROM customers WHERE city = \"Pune\"'}",
        "non_trigger_example": "POST /api/recommendations with empty query",
        "expected_result": "HTTP 200 with recommendations array containing index_name, ddl, and estimated_size",
        "priority": "High",
    },
    {
        "id": "API-REWRITE-OK",
        "feature_area": "ApiEndpoints",
        "description": "POST /api/rewrite returns 200 with rewritten query, applied rules, and diff",
        "trigger_example": "POST /api/rewrite with {'query': 'SELECT * FROM users WHERE id IN (SELECT customer_id FROM orders)'}",
        "non_trigger_example": "POST /api/rewrite with empty query",
        "expected_result": "HTTP 200 with rewritten_query string and applied_rules list",
        "priority": "High",
    },
    {
        "id": "API-EXEC-PLAN-OK",
        "feature_area": "ApiEndpoints",
        "description": "POST /api/execution-plan returns 200 with hierarchical plan tree and node cost metrics",
        "trigger_example": "POST /api/execution-plan with {'query': 'SELECT * FROM orders WHERE customer_id = 10'}",
        "non_trigger_example": "POST /api/execution-plan with empty query",
        "expected_result": "HTTP 200 with plan tree object containing node_type, estimated_rows, and total_cost",
        "priority": "High",
    },
    {
        "id": "API-SIM-INDEX-OK",
        "feature_area": "ApiEndpoints",
        "description": "POST /api/simulate-index returns 200 with before/after comparison and speedup factor",
        "trigger_example": "POST /api/simulate-index with {'query': 'SELECT * FROM orders WHERE customer_id = 10'}",
        "non_trigger_example": "POST /api/simulate-index with empty query",
        "expected_result": "HTTP 200 with simulation metrics (before_score, after_score, speedup_factor)",
        "priority": "High",
    },
    {
        "id": "API-SAMPLE-QUERIES",
        "feature_area": "ApiEndpoints",
        "description": "GET /api/sample-queries returns 200 with parsed list of sample queries from CSV",
        "trigger_example": "GET /api/sample-queries",
        "non_trigger_example": "GET /api/invalid-route",
        "expected_result": "HTTP 200 with array of objects containing query, description, and category",
        "priority": "Medium",
    },
    {
        "id": "API-HEALTH-OK",
        "feature_area": "ApiEndpoints",
        "description": "GET /api/health returns 200 with status 'ok' and application version",
        "trigger_example": "GET /api/health",
        "non_trigger_example": "N/A",
        "expected_result": "HTTP 200 with JSON payload {'status': 'ok', 'version': '1.0.0'}",
        "priority": "Medium",
    },

    # =========================================================================
    # 9. CROSS-CUTTING (Security, Edge Cases & Robustness)
    # =========================================================================
    {
        "id": "EDGE-EMPTY-INPUT",
        "feature_area": "CrossCutting",
        "description": "Rejects empty or whitespace-only query string with HTTP 422 Unprocessable Entity",
        "trigger_example": "POST /api/analyze with {'query': '   '}",
        "non_trigger_example": "POST /api/analyze with {'query': 'SELECT 1'}",
        "expected_result": "HTTP 422 with structured error message indicating query cannot be empty",
        "priority": "High",
    },
    {
        "id": "EDGE-OVERSIZE-INPUT",
        "feature_area": "CrossCutting",
        "description": "Rejects queries exceeding 20,000 characters with HTTP 422 without server memory saturation",
        "trigger_example": "POST /api/analyze with query consisting of 'SELECT 1 WHERE ' + '1=1 AND ' * 3000",
        "non_trigger_example": "POST /api/analyze with standard query under 20k chars",
        "expected_result": "HTTP 422 with message stating query exceeds maximum permitted length",
        "priority": "High",
    },
    {
        "id": "EDGE-COMMENTS-ONLY",
        "feature_area": "CrossCutting",
        "description": "Rejects SQL containing only comments without executable statement with HTTP 422",
        "trigger_example": "-- Just a comment\n/* block comment */",
        "non_trigger_example": "-- comment\nSELECT id FROM users;",
        "expected_result": "HTTP 422 indicating query contains only comments without executable SQL",
        "priority": "High",
    },
    {
        "id": "EDGE-MULTI-STMT",
        "feature_area": "CrossCutting",
        "description": "Rejects multiple semicolon-separated statements to prevent batch injection risks",
        "trigger_example": "SELECT id FROM users; DROP TABLE users;",
        "non_trigger_example": "SELECT id FROM users WHERE id = 1;",
        "expected_result": "HTTP 422 stating multiple SQL statements detected; submit single query",
        "priority": "High",
    },
    {
        "id": "EDGE-NULL-BYTES",
        "feature_area": "CrossCutting",
        "description": "Rejects queries containing null bytes (\x00) or non-printable binary characters",
        "trigger_example": "SELECT * FROM users\x00 WHERE id = 1",
        "non_trigger_example": "SELECT * FROM users WHERE id = 1",
        "expected_result": "HTTP 422 stating query contains invalid non-printable or null byte characters",
        "priority": "High",
    },
    {
        "id": "EDGE-MALFORMED-SQL",
        "feature_area": "CrossCutting",
        "description": "Handles malformed SQL syntax gracefully without leaking raw Python tracebacks or crashing server",
        "trigger_example": "SELECT FROM WHERE GROUP BY ORDER",
        "non_trigger_example": "SELECT id FROM users",
        "expected_result": "Returns HTTP 422 (or fallback analysis) with clear diagnostic error message and no HTTP 500",
        "priority": "High",
    },
    {
        "id": "EDGE-NON-SQL-TEXT",
        "feature_area": "CrossCutting",
        "description": "Rejects arbitrary plain non-SQL text input cleanly with HTTP 422",
        "trigger_example": "Hello world, please optimize my database query immediately!",
        "non_trigger_example": "SELECT name FROM employees",
        "expected_result": "HTTP 422 indicating SQL Syntax Error or failure to parse statement",
        "priority": "High",
    },
    {
        "id": "EDGE-CORS-RESTRICT",
        "feature_area": "CrossCutting",
        "description": "Restricts CORS headers to allowed development origin (http://localhost:5173)",
        "trigger_example": "OPTIONS request with Origin: http://malicious-site.com",
        "non_trigger_example": "OPTIONS request with Origin: http://localhost:5173",
        "expected_result": "Allowed origin receives CORS headers; unauthorized origin is disallowed",
        "priority": "High",
    },
    {
        "id": "EDGE-UNICODE",
        "feature_area": "CrossCutting",
        "description": "Correctly parses and processes queries containing Unicode characters in literals and aliases",
        "trigger_example": "SELECT id, name AS '名前' FROM users WHERE city = 'München' AND status = '⚡active'",
        "non_trigger_example": "SELECT id, name FROM users WHERE city = 'Munich'",
        "expected_result": "HTTP 200 with successful AST extraction and no encoding exceptions",
        "priority": "Medium",
    },
    {
        "id": "EDGE-CONCURRENCY",
        "feature_area": "CrossCutting",
        "description": "Handles concurrent simultaneous requests across API endpoints without race conditions or memory leak",
        "trigger_example": "10 concurrent requests dispatched simultaneously to /api/analyze and /api/score",
        "non_trigger_example": "Sequential single requests",
        "expected_result": "All 10 requests complete with HTTP 200 and identical deterministic outputs",
        "priority": "Medium",
    },

    # =========================================================================
    # 10. FRONTEND UI (React Test Harness Pages & Shared Components)
    # =========================================================================
    {
        "id": "UI-PAGE-ANALYZE",
        "feature_area": "FrontendUI",
        "description": "Analyze page renders QueryInput, executes POST /api/analyze, and displays structured issue/warning badges",
        "trigger_example": "Enter 'SELECT * FROM users' and click Run Analysis",
        "non_trigger_example": "Empty input submission",
        "expected_result": "Renders query metadata, issues list with HIGH badge, and raw JSON collapsible accordion",
        "priority": "High",
    },
    {
        "id": "UI-PAGE-SCORE",
        "feature_area": "FrontendUI",
        "description": "Score page renders score gauge/dial, cost level badge, and score breakdown delta table",
        "trigger_example": "Enter 'SELECT * FROM users' and click Calculate Score",
        "non_trigger_example": "Empty input submission",
        "expected_result": "Displays numeric score (e.g. 45/100), 'HIGH' cost badge, and breakdown rows with deltas",
        "priority": "High",
    },
    {
        "id": "UI-PAGE-RECOMMEND",
        "feature_area": "FrontendUI",
        "description": "Recommendations page displays generated CREATE INDEX DDL, copy-to-clipboard button, and trade-offs",
        "trigger_example": "Enter query with filter column and click Get Recommendations",
        "non_trigger_example": "Query with no filter columns",
        "expected_result": "Displays syntax-highlighted SQL card with valid CREATE INDEX statement and size estimate",
        "priority": "High",
    },
    {
        "id": "UI-PAGE-REWRITE",
        "feature_area": "FrontendUI",
        "description": "Rewrite page displays before/after query diff and list of applied rewrite rules",
        "trigger_example": "Enter 'SELECT * FROM users WHERE YEAR(created_at) = 2024' and click Rewrite Query",
        "non_trigger_example": "Optimal query with no rewrite rules triggered",
        "expected_result": "Displays side-by-side diff showing replaced syntax and applied rule explanation badges",
        "priority": "High",
    },
    {
        "id": "UI-PAGE-PLAN",
        "feature_area": "FrontendUI",
        "description": "Execution Plan page displays hierarchical tree visualization with access types (ALL, ref, range)",
        "trigger_example": "Enter query and click Generate Plan",
        "non_trigger_example": "Empty input",
        "expected_result": "Renders tree node hierarchy with access type icons, estimated rows, and node costs",
        "priority": "High",
    },
    {
        "id": "UI-PAGE-SIMULATE",
        "feature_area": "FrontendUI",
        "description": "Simulate Index page displays before/after metric comparison and speedup multiplier card",
        "trigger_example": "Enter query and click Simulate Index",
        "non_trigger_example": "Empty input",
        "expected_result": "Displays comparison cards: score diff, rows reduction %, time diff, and speedup badge",
        "priority": "High",
    },
    {
        "id": "UI-PAGE-SAMPLES",
        "feature_area": "FrontendUI",
        "description": "Sample Queries page fetches CSV catalog via API, supports category filter, and loads query into input",
        "trigger_example": "Open /samples and click 'Load into Analyzer' on an Anti-pattern card",
        "non_trigger_example": "Backend offline",
        "expected_result": "Populates query grid and routes to selected tool with query pre-filled in QueryInput",
        "priority": "High",
    },
    {
        "id": "UI-PAGE-HEALTH",
        "feature_area": "FrontendUI",
        "description": "Navbar health dot and Health page accurately reflect real-time backend status from GET /api/health",
        "trigger_example": "Backend running vs Backend stopped",
        "non_trigger_example": "N/A",
        "expected_result": "Green status badge with version when online; red badge with error message when backend is unreachable",
        "priority": "High",
    },
    {
        "id": "UI-LOADING-STATE",
        "feature_area": "FrontendUI",
        "description": "Displays LoadingSpinner component and disables action button while async API request is pending",
        "trigger_example": "Click Run on any feature page during API call latency",
        "non_trigger_example": "Idle form before submission",
        "expected_result": "Loading indicator visible, submit button disabled, preventing duplicate submission",
        "priority": "Medium",
    },
    {
        "id": "UI-ERROR-BANNER",
        "feature_area": "FrontendUI",
        "description": "Displays ErrorBanner component with exact backend error message on 400, 422, or 500 responses",
        "trigger_example": "Submit invalid query or simulate network drop",
        "non_trigger_example": "Successful API response",
        "expected_result": "Prominent error banner rendered displaying status code and detail message without blank screen",
        "priority": "Medium",
    },
    {
        "id": "UI-NAV-HISTORY",
        "feature_area": "FrontendUI",
        "description": "Browser back and forward navigation preserves route context and active page selection",
        "trigger_example": "Navigate from /analyze to /score and click browser Back button",
        "non_trigger_example": "Direct URL load",
        "expected_result": "Navigates back to /analyze with navbar active item synchronized and no uncaught exceptions",
        "priority": "Low",
    },
]


def generate_matrix():
    # Sort by feature_area then priority (High -> Medium -> Low)
    sorted_rows = sorted(
        MATRIX_ROWS,
        key=lambda r: (r["feature_area"], PRIORITY_ORDER.get(r["priority"], 99), r["id"]),
    )

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    md_path = os.path.join(docs_dir, "TEST_MATRIX.md")
    csv_path = os.path.join(docs_dir, "TEST_MATRIX.csv")

    # 1. Export CSV
    csv_headers = [
        "ID",
        "Feature Area",
        "Description",
        "Trigger Example SQL",
        "Non-Trigger Example SQL",
        "Expected Result",
        "Priority",
    ]
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers)
        for row in sorted_rows:
            writer.writerow(
                [
                    row["id"],
                    row["feature_area"],
                    row["description"],
                    row["trigger_example"],
                    row["non_trigger_example"],
                    row["expected_result"],
                    row["priority"],
                ]
            )

    # 2. Export Markdown
    with open(md_path, mode="w", encoding="utf-8") as f:
        f.write("# AI DB Query Optimizer — Complete QA Test Matrix\n\n")
        f.write(
            "This document establishes the exhaustive verification checklist for all modules, "
            "rules, API endpoints, cross-cutting security boundaries, and React frontend interactions. "
            "It serves as the definitive reference for unit, integration, and end-to-end test execution.\n\n"
        )

        # Summary statistics
        feature_counts = {}
        priority_counts = {"High": 0, "Medium": 0, "Low": 0}
        for r in sorted_rows:
            fa = r["feature_area"]
            feature_counts[fa] = feature_counts.get(fa, 0) + 1
            p = r["priority"]
            priority_counts[p] = priority_counts.get(p, 0) + 1

        f.write("## Matrix Summary Statistics\n\n")
        f.write(f"- **Total Behaviors Documented**: {len(sorted_rows)}\n")
        f.write(
            f"- **Priority Breakdown**: High: {priority_counts['High']}, "
            f"Medium: {priority_counts['Medium']}, Low: {priority_counts['Low']}\n"
        )
        f.write("- **Feature Area Coverage**:\n")
        for fa, count in sorted(feature_counts.items()):
            f.write(f"  - **{fa}**: {count} test rows\n")
        f.write("\n---\n\n")

        # Markdown Table
        f.write("## Test Matrix Table\n\n")
        f.write(
            "| ID | Feature Area | Description | Trigger Example SQL | Non-Trigger Example SQL | Expected Result | Priority |\n"
        )
        f.write(
            "|:---|:---|:---|:---|:---|:---|:---:|\n"
        )

        for r in sorted_rows:
            trig = r["trigger_example"].replace("|", "\\|").replace("\n", " ")
            non_trig = r["non_trigger_example"].replace("|", "\\|").replace("\n", " ")
            desc = r["description"].replace("|", "\\|")
            exp = r["expected_result"].replace("|", "\\|")

            f.write(
                f"| `{r['id']}` | **{r['feature_area']}** | {desc} | `{trig}` | `{non_trig}` | {exp} | **{r['priority']}** |\n"
            )

        f.write("\n\n---\n")
        f.write(
            "*Generated automatically by `scripts/generate_test_matrix.py` in accordance with Master Testing Rules (Prompt 3).*\n"
        )

    print(f"Generated {len(sorted_rows)} matrix rows.")
    print(f"Markdown: {md_path}")
    print(f"CSV: {csv_path}")


if __name__ == "__main__":
    generate_matrix()
