"""detectors/having_as_where.py
Detects HAVING filters that do not contain aggregate functions and could be pushed down to WHERE.
"""

from __future__ import annotations

from typing import Optional

from sqlglot import exp

from db.schema import SchemaInfo
from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures


class HavingAsWhereDetector(BaseDetector):
    code = "HAVING_AS_WHERE"
    severity = "LOW"
    score_delta = -5
    label = "HAVING clause filtering non-aggregates"

    AGGREGATE_FUNCS = (
        exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max, exp.Stddev, exp.Variance
    )

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        if not features.raw_ast:
            return findings

        having_node = features.raw_ast.find(exp.Having)
        if not having_node:
            return findings

        # Check conditions inside HAVING
        for cond in having_node.flatten():
            # If condition has a comparison but no aggregate function
            if isinstance(cond, (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE)):
                has_agg = bool(cond.find(*self.AGGREGATE_FUNCS))
                if not has_agg:
                    findings.append(Finding(
                        code=self.code,
                        severity=self.severity,
                        score_delta=self.score_delta,
                        message=(
                            "HAVING clause contains a filter on non-aggregated columns. "
                            "Filtering in HAVING forces MySQL to group all rows before filtering. "
                            "Moving the condition to WHERE reduces rows before grouping."
                        ),
                        fix_example=(
                            "-- Before (Filters after expensive aggregation)\n"
                            "SELECT customer_id, COUNT(*) FROM orders GROUP BY customer_id HAVING customer_id > 100;\n\n"
                            "-- After (Pre-filters rows before grouping)\n"
                            "SELECT customer_id, COUNT(*) FROM orders WHERE customer_id > 100 GROUP BY customer_id;"
                        ),
                    ))
                    break

        return findings
