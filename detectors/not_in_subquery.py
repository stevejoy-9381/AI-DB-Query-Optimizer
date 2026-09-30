"""detectors/not_in_subquery.py
Detects NOT IN (<subquery>) anti-pattern (NULL trap and poor query optimizer plans).
"""

from __future__ import annotations

from typing import Optional

from sqlglot import exp

from db.schema import SchemaInfo
from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures


class NotInSubqueryDetector(BaseDetector):
    code = "NOT_IN_SUBQUERY"
    severity = "HIGH"
    score_delta = -15
    label = "NOT IN with subquery"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        if not features.raw_ast:
            return findings

        # Check for NOT IN
        for in_node in features.raw_ast.find_all(exp.In):
            # Check if negated
            is_negated = in_node.args.get("is_negated") or isinstance(in_node.parent, exp.Not)
            if is_negated:
                subquery = in_node.find(exp.Select)
                if subquery:
                    findings.append(
                        Finding(
                            code=self.code,
                            severity=self.severity,
                            score_delta=self.score_delta,
                            message=(
                                "NOT IN with a subquery is risky and slow. If the subquery returns any NULL, "
                                "the entire condition evaluates to UNKNOWN, returning zero rows. "
                                "Furthermore, MySQL cannot optimize NOT IN as effectively as NOT EXISTS or an anti-join."
                            ),
                            fix_example=(
                                "-- Before\n"
                                "SELECT * FROM customers WHERE id NOT IN (SELECT customer_id FROM orders);\n\n"
                                "-- After (NOT EXISTS - NULL-safe and index-friendly)\n"
                                "SELECT * FROM customers c WHERE NOT EXISTS (\n"
                                "    SELECT 1 FROM orders o WHERE o.customer_id = c.id\n"
                                ");\n\n"
                                "-- Or Anti-Join\n"
                                "SELECT c.* FROM customers c\n"
                                "LEFT JOIN orders o ON c.id = o.customer_id\n"
                                "WHERE o.customer_id IS NULL;"
                            ),
                        )
                    )
                    break

        return findings
