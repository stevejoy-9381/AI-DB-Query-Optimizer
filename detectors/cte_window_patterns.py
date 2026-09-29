"""detectors/cte_window_patterns.py
Detectors for CTE and Window Function patterns:
1. CTE referenced multiple times (non-materialized CTE risk in MySQL 8.0)
2. Window function without PARTITION BY (global window framing)
"""

from __future__ import annotations

from typing import Optional

from db.schema import SchemaInfo
from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures


class CteMultiplyReferencedDetector(BaseDetector):
    code = "CTE_MULTIPLY_REFERENCED"
    severity = "MEDIUM"
    score_delta = -10
    label = "CTE referenced multiple times"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []
        for cte_name, count in features.cte_references.items():
            if count >= 2:
                findings.append(Finding(
                    code=self.code,
                    severity=self.severity,
                    score_delta=self.score_delta,
                    message=(
                        f"Common Table Expression (CTE) `{cte_name}` is referenced {count} times in the outer query. "
                        "In MySQL 8.0, CTEs without materialization may be re-executed multiple times. "
                        "Consider evaluating into a temporary table if execution time is significant."
                    ),
                    fix_example=(
                        f"-- Note: In MySQL 8.0, CTEs are inlined unless recursive or materialized.\n"
                        f"-- For expensive computations used repeatedly, consider:\n"
                        f"CREATE TEMPORARY TABLE temp_{cte_name} AS SELECT ...;"
                    ),
                    category="architecture",
                ))
        return findings


class WindowWithoutPartitionDetector(BaseDetector):
    code = "WINDOW_WITHOUT_PARTITION"
    severity = "MEDIUM"
    score_delta = -10
    label = "Window function without PARTITION BY"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []
        if features.has_window_functions:
            for win in features.window_functions:
                if not win.get("has_partition"):
                    func_name = win.get("function", "WINDOW")
                    findings.append(Finding(
                        code=self.code,
                        severity=self.severity,
                        score_delta=self.score_delta,
                        message=(
                            f"Window function `{func_name}` lacks a PARTITION BY clause. "
                            "It evaluates across the entire result set in a single window frame, "
                            "forcing a global filesort and memory buffering."
                        ),
                        fix_example=(
                            f"-- Before (All rows sorted globally)\n"
                            f"SELECT id, {func_name}() OVER (ORDER BY created_at) FROM table_name;\n\n"
                            f"-- After (Partitioned by entity/tenant)\n"
                            f"SELECT id, {func_name}() OVER (PARTITION BY tenant_id ORDER BY created_at) FROM table_name;"
                        ),
                        category="performance",
                    ))
                    break
        return findings
