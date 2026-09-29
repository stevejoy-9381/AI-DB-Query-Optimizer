"""detectors/base.py
Base classes and data structures for anti-pattern detectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from db.schema import SchemaInfo
    from query_model import QueryFeatures


@dataclass
class Finding:
    """Represents a single anti-pattern or issue discovered by a detector."""
    code: str
    severity: str        # "HIGH", "MEDIUM", "LOW"
    score_delta: int     # Negative penalty, e.g. -15
    message: str
    fix_example: str
    category: str = "performance"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "score_delta": self.score_delta,
            "message": self.message,
            "fix_example": self.fix_example,
            "category": self.category,
        }


class BaseDetector:
    """Abstract base class for all query anti-pattern detectors."""

    code: str = "BASE_DETECTOR"
    severity: str = "MEDIUM"
    score_delta: int = -10
    label: str = "Base detector"

    def detect(
        self,
        query: str,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
    ) -> list[Finding]:
        """Inspect the query AST and features, returning any detected Findings."""
        raise NotImplementedError
