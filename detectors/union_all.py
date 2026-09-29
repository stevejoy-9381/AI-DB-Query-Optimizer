"""detectors/union_all.py
Detects UNION statements where UNION ALL might be sufficient to avoid temporary table deduplication.
"""

from __future__ import annotations

from typing import Optional
from sqlglot import exp

from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures
from db.schema import SchemaInfo


class UnionInsteadOfUnionAllDetector(BaseDetector):
    code = "UNION_INSTEAD_OF_UNION_ALL"
    severity = "MEDIUM"
    score_delta = -10
    label = "UNION without ALL"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []
        if not features.raw_ast:
            return findings

        for union_node in features.raw_ast.find_all(exp.Union):
            # In sqlglot, union.distinct is True for UNION, False for UNION ALL
            if union_node.args.get("distinct", True):
                findings.append(Finding(
                    code=self.code,
                    severity=self.severity,
                    score_delta=self.score_delta,
                    message=(
                        "UNION performs implicit duplicate elimination using an internal temporary table "
                        "and filesort. If result sets are known to be disjoint or duplicates are acceptable, "
                        "UNION ALL is significantly faster and avoids disk/memory buffering."
                    ),
                    fix_example=(
                        "-- Before (Implicit DISTINCT with temporary table)\n"
                        "SELECT id, total FROM current_orders\n"
                        "UNION\n"
                        "SELECT id, total FROM archived_orders;\n\n"
                        "-- After (Fast streaming UNION ALL)\n"
                        "SELECT id, total FROM current_orders\n"
                        "UNION ALL\n"
                        "SELECT id, total FROM archived_orders;"
                    ),
                ))
                break

        return findings
