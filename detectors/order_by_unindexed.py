"""detectors/order_by_unindexed.py
Detects ORDER BY RAND() and ORDER BY on unindexed columns when schema is available.
"""

from __future__ import annotations

from typing import Optional
from sqlglot import exp

from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures
from db.schema import SchemaInfo


class OrderByRandDetector(BaseDetector):
    code = "ORDER_BY_RAND"
    severity = "HIGH"
    score_delta = -20
    label = "ORDER BY RAND() usage"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []
        if not features.raw_ast:
            return findings

        order_node = features.raw_ast.find(exp.Order)
        if not order_node:
            return findings

        # Check for RAND() or RANDOM()
        for node in order_node.find_all(exp.Expression):
            if isinstance(node, exp.Rand) or getattr(node, "key", "").lower() in ("rand", "random") or getattr(node, "name", "").upper() in ("RAND", "RANDOM"):
                findings.append(Finding(
                    code=self.code,
                    severity=self.severity,
                    score_delta=self.score_delta,
                    message=(
                        "ORDER BY RAND() assigns a random number to every row in the table, "
                        "forcing a full table scan and an in-memory or on-disk temporary filesort."
                    ),
                    fix_example=(
                        "-- Before\n"
                        "SELECT * FROM products ORDER BY RAND() LIMIT 1;\n\n"
                        "-- After (Select random ID in application or join with random offset)\n"
                        "SELECT * FROM products JOIN (\n"
                        "    SELECT CEIL(RAND() * (SELECT MAX(id) FROM products)) AS r_id\n"
                        ") AS r WHERE products.id >= r.r_id ORDER BY products.id ASC LIMIT 1;"
                    ),
                ))
                return findings

        return findings


class UnindexedOrderByDetector(BaseDetector):
    code = "UNINDEXED_ORDER_BY"
    severity = "MEDIUM"
    score_delta = -10
    label = "ORDER BY without supporting index"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []
        if not schema or not features.raw_ast or not features.order_by_cols:
            return findings

        # Only check single-table simple queries or primary table
        if len(features.tables) != 1:
            return findings

        table_name = features.tables[0].lower()
        table_info = schema.get_table(table_name)
        if not table_info:
            return findings

        # Check if first ORDER BY column is indexed as a prefix
        first_order_col = features.order_by_cols[0].lower().split(".")[-1].strip("`\"' ")
        if first_order_col in ("rand()", "rand", "random()", "random"):
            return findings

        has_index = False
        indexes_iterable = table_info.indexes.values() if isinstance(table_info.indexes, dict) else table_info.indexes
        for idx in indexes_iterable:
            if idx.columns and idx.columns[0].lower() == first_order_col:
                has_index = True
                break

        if not has_index:
            findings.append(Finding(
                code=self.code,
                severity=self.severity,
                score_delta=self.score_delta,
                message=(
                    f"ORDER BY column `{first_order_col}` is not the leading column in any index on `{table_name}`. "
                    "This requires MySQL to perform an unindexed filesort."
                ),
                fix_example=(
                    f"-- Recommended Index\n"
                    f"CREATE INDEX idx_{table_name}_{first_order_col} ON {table_name}({first_order_col});"
                ),
            ))

        return findings
