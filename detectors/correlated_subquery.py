"""detectors/correlated_subquery.py
Detects correlated subqueries in SELECT projection or WHERE filters.
"""

from __future__ import annotations

from typing import Optional

from sqlglot import exp

from db.schema import SchemaInfo
from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures


class CorrelatedSubqueryDetector(BaseDetector):
    code = "CORRELATED_SUBQUERY"
    severity = "HIGH"
    score_delta = -15
    label = "Correlated subquery in SELECT or WHERE"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        if not features.raw_ast:
            return findings

        # Outer tables/aliases
        outer_tables = set(features.tables)
        for tbl, alias in features.alias_map.items():
            outer_tables.add(alias)
            outer_tables.add(tbl)

        # Look for subqueries inside the AST
        for subquery in features.raw_ast.find_all(exp.Select):
            # Check if this Select is nested inside the root AST
            if subquery is features.raw_ast:
                continue

            # Tables/aliases defined inside this subquery
            inner_tables = set()
            for t in subquery.find_all(exp.Table):
                inner_tables.add(t.name.lower())
                if t.alias:
                    inner_tables.add(t.alias.lower())

            # Find all column references in this subquery
            for col in subquery.find_all(exp.Column):
                if col.table:
                    tbl_ref = col.table.lower()
                    if tbl_ref in outer_tables and tbl_ref not in inner_tables:
                        findings.append(Finding(
                            code=self.code,
                            severity=self.severity,
                            score_delta=self.score_delta,
                            message=(
                                f"Correlated subquery references outer table/alias `{col.table}`. "
                                "This executes once per outer row (O(N^2) complexity)."
                            ),
                            fix_example=(
                                "-- Before (Correlated subquery in SELECT/WHERE)\n"
                                "SELECT c.name, (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.id) FROM customers c;\n\n"
                                "-- After (JOIN with aggregation / CTE)\n"
                                "SELECT c.name, COALESCE(o.order_count, 0)\n"
                                "FROM customers c\n"
                                "LEFT JOIN (\n"
                                "    SELECT customer_id, COUNT(*) AS order_count FROM orders GROUP BY customer_id\n"
                                ") o ON c.id = o.customer_id;"
                            ),
                        ))
                        return findings  # Return once per query to avoid spamming

        return findings
