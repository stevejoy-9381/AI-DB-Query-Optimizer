"""detectors/update_delete_where.py
Detectors for UPDATE and DELETE safety and locking rules:
1. UPDATE without WHERE (CRITICAL)
2. DELETE without WHERE (CRITICAL)
3. UPDATE/DELETE with unindexed WHERE columns (HIGH lock escalation risk)
"""

from __future__ import annotations

from typing import Optional

from db.schema import SchemaInfo
from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures


class UpdateWithoutWhereDetector(BaseDetector):
    code = "UPDATE_WITHOUT_WHERE"
    severity = "CRITICAL"
    score_delta = -50
    label = "UPDATE statement without WHERE clause"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []
        if features.statement_type == "UPDATE" and not features.has_where:
            table_name = features.tables[0] if features.tables else "target_table"
            findings.append(Finding(
                code=self.code,
                severity=self.severity,
                score_delta=self.score_delta,
                message=(
                    f"CRITICAL: UPDATE on `{table_name}` has no WHERE clause! "
                    "Executing this will overwrite every single row in the table."
                ),
                fix_example=(
                    f"-- Before (Accidentally updates all rows)\n"
                    f"UPDATE {table_name} SET status = 'inactive';\n\n"
                    f"-- After (Always include a specific filter or primary key)\n"
                    f"UPDATE {table_name} SET status = 'inactive' WHERE id = 123;"
                ),
                category="safety",
            ))
        return findings


class DeleteWithoutWhereDetector(BaseDetector):
    code = "DELETE_WITHOUT_WHERE"
    severity = "CRITICAL"
    score_delta = -50
    label = "DELETE statement without WHERE clause"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []
        if features.statement_type == "DELETE" and not features.has_where:
            table_name = features.tables[0] if features.tables else "target_table"
            findings.append(Finding(
                code=self.code,
                severity=self.severity,
                score_delta=self.score_delta,
                message=(
                    f"CRITICAL: DELETE on `{table_name}` has no WHERE clause! "
                    "Executing this will truncate/delete every single row in the table."
                ),
                fix_example=(
                    f"-- Before (Deletes all rows)\n"
                    f"DELETE FROM {table_name};\n\n"
                    f"-- After (Target specific rows by identifier or criteria)\n"
                    f"DELETE FROM {table_name} WHERE status = 'expired' AND created_at < NOW() - INTERVAL 90 DAY;"
                ),
                category="safety",
            ))
        return findings


class UpdateDeleteUnindexedWhereDetector(BaseDetector):
    code = "UPDATE_DELETE_UNINDEXED_WHERE"
    severity = "HIGH"
    score_delta = -20
    label = "UPDATE/DELETE with unindexed WHERE filter"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        if not schema or features.statement_type not in ("UPDATE", "DELETE") or not features.has_where:
            return findings

        if not features.tables or not features.filter_columns:
            return findings

        table_name = features.tables[0].lower()
        table_info = schema.get_table(table_name)
        if not table_info:
            return findings

        # Check if any filter column matches an index prefix
        has_index = False
        filter_cols = [c.lower() for c in features.filter_columns]
        indexes_iterable = table_info.indexes.values() if isinstance(table_info.indexes, dict) else table_info.indexes
        for idx in indexes_iterable:
            if idx.columns and idx.columns[0].lower() in filter_cols:
                has_index = True
                break

        if not has_index:
            col_list = ", ".join(f"`{c}`" for c in filter_cols)
            findings.append(Finding(
                code=self.code,
                severity=self.severity,
                score_delta=self.score_delta,
                message=(
                    f"{features.statement_type} on `{table_name}` filters on unindexed columns ({col_list}). "
                    "In InnoDB, row updates without an index force a full table scan while acquiring exclusive (X) "
                    "next-key locks on every examined row, blocking concurrent transactions and causing deadlocks."
                ),
                fix_example=(
                    f"-- Recommended Index to prevent table-wide locking:\n"
                    f"CREATE INDEX idx_{table_name}_{filter_cols[0]} ON {table_name}({filter_cols[0]});"
                ),
                category="concurrency",
            ))

        return findings
