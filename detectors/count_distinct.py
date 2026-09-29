"""detectors/count_distinct.py
Detects COUNT(DISTINCT ...) and explains COUNT(col) vs COUNT(*) behavior.
"""

from __future__ import annotations

from typing import Optional
from sqlglot import exp

from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures
from db.schema import SchemaInfo


class CountDistinctDetector(BaseDetector):
    code = "COUNT_DISTINCT"
    severity = "LOW"
    score_delta = -5
    label = "COUNT(DISTINCT ...) or COUNT(col) usage"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []
        if not features.raw_ast:
            return findings

        # Check for COUNT(DISTINCT ...)
        for count_node in features.raw_ast.find_all(exp.Count):
            if count_node.find(exp.Distinct) is not None or count_node.args.get("distinct"):
                findings.append(Finding(
                    code=self.code,
                    severity=self.severity,
                    score_delta=self.score_delta,
                    message=(
                        "COUNT(DISTINCT ...) requires collecting all values in a temporary hash set or filesort "
                        "to eliminate duplicates, which degrades heavily on large datasets. "
                        "Also note that COUNT(col) skips NULL values whereas COUNT(*) counts all rows."
                    ),
                    fix_example=(
                        "-- On massive tables, consider summary/rollup tables or hyperloglog approximations:\n"
                        "SELECT COUNT(DISTINCT customer_id) FROM orders;\n\n"
                        "-- Or ensure an index covers the distinct column."
                    ),
                ))
                break

        return findings
