"""detectors/insert_patterns.py
Detectors for INSERT statements:
1. INSERT single row (suggest multi-row batching)
2. INSERT...SELECT without WHERE or LIMIT (massive undo log / table lock)
"""

from __future__ import annotations

from typing import Optional

from db.schema import SchemaInfo
from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures


class InsertSingleRowDetector(BaseDetector):
    code = "INSERT_SINGLE_ROW"
    severity = "LOW"
    score_delta = -5
    label = "Single-row INSERT"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []
        if features.statement_type == "INSERT" and features.insert_row_count == 1:
            table_name = features.tables[0] if features.tables else "target_table"
            findings.append(
                Finding(
                    code=self.code,
                    severity=self.severity,
                    score_delta=self.score_delta,
                    message=(
                        f"Single-row INSERT into `{table_name}`. If executed in an application loop, each statement "
                        "incurs round-trip network latency and individual transaction redo-log flushes. "
                        "Batch multiple records into a multi-row INSERT."
                    ),
                    fix_example=(
                        f"-- Before (Executed N times in a loop)\n"
                        f"INSERT INTO {table_name} (col1, col2) VALUES ('a', 1);\n\n"
                        f"-- After (Batch 500-1000 rows per transaction)\n"
                        f"INSERT INTO {table_name} (col1, col2) VALUES\n"
                        f"  ('a', 1),\n"
                        f"  ('b', 2),\n"
                        f"  ('c', 3);"
                    ),
                    category="throughput",
                )
            )
        return findings


class InsertSelectUnboundedDetector(BaseDetector):
    code = "INSERT_SELECT_UNBOUNDED"
    severity = "HIGH"
    score_delta = -20
    label = "Unbounded INSERT...SELECT statement"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []
        if features.is_insert_select or features.statement_type == "INSERT...SELECT":
            if not features.has_where and features.limit is None:
                dest_table = features.tables[0] if features.tables else "destination"
                findings.append(
                    Finding(
                        code=self.code,
                        severity=self.severity,
                        score_delta=self.score_delta,
                        message=(
                            f"INSERT...SELECT into `{dest_table}` has no WHERE filter or LIMIT clause. "
                            "This copies the entire source table in a single atomic transaction, holding shared read locks "
                            "on the source and blowing up the InnoDB undo log and transaction buffer."
                        ),
                        fix_example=(
                            f"-- Before (Full table copy)\n"
                            f"INSERT INTO {dest_table} SELECT * FROM source_table;\n\n"
                            f"-- After (Chunked migration with filter)\n"
                            f"INSERT INTO {dest_table} SELECT * FROM source_table WHERE created_at < '2024-01-01' LIMIT 5000;"
                        ),
                        category="performance",
                    )
                )
        return findings
