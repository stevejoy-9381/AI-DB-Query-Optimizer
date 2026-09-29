"""detectors/or_different_columns.py
Detects OR operators spanning across multiple distinct columns, which prevents single-index range scans.
"""

from __future__ import annotations

from typing import Optional
from sqlglot import exp

from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures
from db.schema import SchemaInfo


class OrDifferentColumnsDetector(BaseDetector):
    code = "OR_DIFFERENT_COLUMNS"
    severity = "MEDIUM"
    score_delta = -10
    label = "OR across different columns"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []
        if not features.raw_ast:
            return findings

        where_node = features.raw_ast.find(exp.Where)
        if not where_node:
            return findings

        for or_node in where_node.find_all(exp.Or):
            cols = set()
            for col in or_node.find_all(exp.Column):
                col_name = f"{col.table.lower()}.{col.name.lower()}" if col.table else col.name.lower()
                cols.add(col_name)

            if len(cols) >= 2:
                col_list = ", ".join(f"`{c}`" for c in sorted(cols)[:3])
                findings.append(Finding(
                    code=self.code,
                    severity=self.severity,
                    score_delta=self.score_delta,
                    message=(
                        f"OR condition spans across multiple distinct columns ({col_list}). "
                        "This typically defeats index range scans and triggers an index merge or full table scan."
                    ),
                    fix_example=(
                        "-- Before\n"
                        "SELECT * FROM orders WHERE customer_id = 42 OR status = 'pending';\n\n"
                        "-- After (UNION ALL with indexes on customer_id and status)\n"
                        "SELECT * FROM orders WHERE customer_id = 42\n"
                        "UNION ALL\n"
                        "SELECT * FROM orders WHERE status = 'pending' AND customer_id != 42;"
                    ),
                ))
                break

        return findings
