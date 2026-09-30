"""detectors/implicit_type_conversion.py
Detects implicit type conversions in WHERE conditions when schema metadata is known (e.g., comparing VARCHAR column to a number).
"""

from __future__ import annotations

from typing import Optional

from sqlglot import exp

from db.schema import SchemaInfo
from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures


class ImplicitTypeConversionDetector(BaseDetector):
    code = "IMPLICIT_TYPE_CONVERSION"
    severity = "HIGH"
    score_delta = -15
    label = "Implicit type conversion on indexed column"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        if not schema or not features.raw_ast:
            return findings

        where_node = features.raw_ast.find(exp.Where)
        if not where_node:
            return findings

        # Check binary comparison operations
        for comp in where_node.find_all((exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE)):
            left, right = comp.this, comp.expression
            col_node = None
            literal_node = None

            if isinstance(left, exp.Column) and isinstance(right, exp.Literal):
                col_node = left
                literal_node = right
            elif isinstance(right, exp.Column) and isinstance(left, exp.Literal):
                col_node = right
                literal_node = left

            if col_node and literal_node:
                # Resolve table
                table_name = col_node.table.lower() if col_node.table else ""
                if not table_name and len(features.tables) == 1:
                    table_name = features.tables[0].lower()
                else:
                    table_name = features.alias_map.get(table_name, table_name)

                table_info = schema.get_table(table_name)
                if table_info:
                    col_info = table_info.get_column(col_node.name)
                    if col_info:
                        col_type = col_info.data_type.upper()
                        is_string_col = any(
                            t in col_type for t in ("VARCHAR", "CHAR", "TEXT", "ENUM")
                        )

                        if is_string_col and literal_node.is_number:
                            findings.append(
                                Finding(
                                    code=self.code,
                                    severity=self.severity,
                                    score_delta=self.score_delta,
                                    message=(
                                        f"Column `{col_node.name}` is {col_type}, but is compared to a numeric literal `{literal_node.this}`. "
                                        "MySQL converts the column to a floating-point number for every row, disabling index usage."
                                    ),
                                    fix_example=(
                                        f"-- Before (Forces full table scan)\n"
                                        f"WHERE {col_node.name} = {literal_node.this};\n\n"
                                        f"-- After (Uses index)\n"
                                        f"WHERE {col_node.name} = '{literal_node.this}';"
                                    ),
                                )
                            )
                            break

        return findings
