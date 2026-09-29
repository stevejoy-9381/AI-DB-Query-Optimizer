"""detectors/non_sargable_arithmetic.py
Detects non-sargable arithmetic expressions performed on columns in WHERE predicates (e.g. WHERE price + 10 > 100).
"""

from __future__ import annotations

from typing import Optional

from sqlglot import exp

from db.schema import SchemaInfo
from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures


class NonSargableArithmeticDetector(BaseDetector):
    code = "NON_SARGABLE_ARITHMETIC"
    severity = "MEDIUM"
    score_delta = -10
    label = "Non-sargable arithmetic on WHERE column"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        if not features.raw_ast:
            return findings

        where_node = features.raw_ast.find(exp.Where)
        if not where_node:
            return findings

        comparisons = (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE)
        arithmetics = (exp.Add, exp.Sub, exp.Mul, exp.Div, exp.Mod)

        for comp in where_node.find_all(comparisons):
            for side in (comp.this, comp.expression):
                if side and isinstance(side, arithmetics):
                    # Check if there is a column inside this arithmetic expr
                    col = side.find(exp.Column)
                    if col:
                        col_name = col.name
                        findings.append(Finding(
                            code=self.code,
                            severity=self.severity,
                            score_delta=self.score_delta,
                            message=(
                                f"Arithmetic expression performed on column `{col_name}` in WHERE filter makes the condition non-sargable. "
                                "MySQL cannot use an index on this column because each row must be evaluated."
                            ),
                            fix_example=(
                                "-- Before (Non-sargable)\n"
                                f"WHERE {col_name} + 10 > 100;\n\n"
                                "-- After (Sargable - column isolated)\n"
                                f"WHERE {col_name} > 100 - 10;"
                            ),
                        ))
                        return findings

        return findings
