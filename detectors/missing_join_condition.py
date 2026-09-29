"""detectors/missing_join_condition.py
Detects missing JOIN conditions causing accidental Cartesian products (CROSS JOINs / table multiplications).
"""

from __future__ import annotations

from typing import Optional
from sqlglot import exp

from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures
from db.schema import SchemaInfo


class MissingJoinConditionDetector(BaseDetector):
    code = "MISSING_JOIN_CONDITION"
    severity = "HIGH"
    score_delta = -25
    label = "Missing JOIN condition / Cartesian product"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []
        if not features.raw_ast:
            return findings

        # Check explicit JOINs without ON or USING
        joins = list(features.raw_ast.find_all(exp.Join))
        for j in joins:
            # Cross join or join without ON/USING
            is_cross = j.kind and j.kind.upper() == "CROSS"
            has_on = bool(j.args.get("on"))
            has_using = bool(j.args.get("using"))

            if (is_cross or not (has_on or has_using)) and not j.args.get("natural"):
                # Also check if WHERE connects them
                where_node = features.raw_ast.find(exp.Where)
                where_has_join = False
                if where_node:
                    for eq in where_node.find_all(exp.EQ):
                        cols = list(eq.find_all(exp.Column))
                        if len(cols) == 2 and cols[0].table and cols[1].table and cols[0].table.lower() != cols[1].table.lower():
                            where_has_join = True
                            break

                if not where_has_join:
                    findings.append(Finding(
                        code=self.code,
                        severity=self.severity,
                        score_delta=self.score_delta,
                        message=(
                            "JOIN without an ON or USING condition produces a full Cartesian product (M x N rows), "
                            "severely exhausting database CPU, memory, and buffer pool."
                        ),
                        fix_example=(
                            "-- Before (Accidental Cartesian Product)\n"
                            "SELECT * FROM customers c JOIN orders o;\n\n"
                            "-- After (Explicit ON condition)\n"
                            "SELECT * FROM customers c JOIN orders o ON c.id = o.customer_id;"
                        ),
                    ))
                    return findings

        # Check comma joins (e.g., FROM customers, orders)
        from_node = features.raw_ast.find(exp.From)
        if from_node and len(from_node.expressions) > 1:
            where_node = features.raw_ast.find(exp.Where)
            has_join_eq = False
            if where_node:
                for eq in where_node.find_all(exp.EQ):
                    cols = list(eq.find_all(exp.Column))
                    if len(cols) == 2 and cols[0].table and cols[1].table and cols[0].table.lower() != cols[1].table.lower():
                        has_join_eq = True
                        break

            if not has_join_eq:
                findings.append(Finding(
                    code=self.code,
                    severity=self.severity,
                    score_delta=self.score_delta,
                    message=(
                        "Comma-separated tables in FROM clause without a connecting WHERE condition "
                        "creates an accidental Cartesian product."
                    ),
                    fix_example=(
                        "-- Before\n"
                        "SELECT * FROM customers, orders;\n\n"
                        "-- After\n"
                        "SELECT * FROM customers c JOIN orders o ON c.id = o.customer_id;"
                    ),
                ))

        return findings
