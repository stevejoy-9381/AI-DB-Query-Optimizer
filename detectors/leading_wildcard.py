"""detectors/leading_wildcard.py
Detects leading wildcards in LIKE patterns ('%term' or '_term').
"""

from __future__ import annotations

from typing import Optional
from sqlglot import exp

from detectors.base import BaseDetector, Finding
from query_model import QueryFeatures
from db.schema import SchemaInfo


class LeadingWildcardDetector(BaseDetector):
    code = "LEADING_WILDCARD"
    severity = "MEDIUM"
    score_delta = -10
    label = "Leading wildcard LIKE pattern"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        findings = []

        if features.wildcard_likes:
            patterns = ", ".join(f"'{p}'" for p in features.wildcard_likes[:3])
            findings.append(Finding(
                code=self.code,
                severity=self.severity,
                score_delta=self.score_delta,
                message=(
                    f"Leading wildcard pattern detected ({patterns}). "
                    "B-tree indexes cannot be used for prefix-unknown searches, forcing a full index or table scan."
                ),
                fix_example=(
                    "-- Before (Index cannot be used)\n"
                    "WHERE name LIKE '%smith';\n\n"
                    "-- After (Trailing wildcard uses index)\n"
                    "WHERE name LIKE 'smith%';\n\n"
                    "-- For substring search, use MySQL FULLTEXT index:\n"
                    "WHERE MATCH(name) AGAINST('smith' IN BOOLEAN MODE);"
                ),
            ))

        return findings
