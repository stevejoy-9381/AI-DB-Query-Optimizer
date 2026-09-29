"""detectors/large_offset.py
Detects large OFFSET pagination (e.g. OFFSET 1000 or LIMIT 1000, 20) which wastes substantial I/O.
"""

from __future__ import annotations

from typing import Optional
from sqlglot import exp

from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures
from db.schema import SchemaInfo


class LargeOffsetDetector(BaseDetector):
    code = "LARGE_OFFSET"
    severity = "MEDIUM"
    score_delta = -10
    label = "Deep OFFSET pagination"

    OFFSET_THRESHOLD = 500

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []

        offset_val = features.offset
        if offset_val is not None and offset_val >= self.OFFSET_THRESHOLD:
            findings.append(Finding(
                code=self.code,
                severity=self.severity,
                score_delta=self.score_delta,
                message=(
                    f"Query uses a large OFFSET ({offset_val}). MySQL must read and discard {offset_val} rows "
                    "before returning results, causing increasing latency as users paginate deeper."
                ),
                fix_example=(
                    "-- Keyset / Cursor Pagination (O(1) seek instead of O(N) scan)\n"
                    "WHERE id > :last_seen_id ORDER BY id ASC LIMIT 20;\n\n"
                    "-- Deferred Join (late row lookup)\n"
                    "SELECT o.* FROM orders o\n"
                    "JOIN (SELECT id FROM orders ORDER BY created_at LIMIT 20 OFFSET 10000) AS sub\n"
                    "ON o.id = sub.id;"
                ),
            ))

        return findings
