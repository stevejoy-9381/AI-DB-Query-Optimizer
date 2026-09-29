"""detectors/registry.py
Central registry for plugin-style anti-pattern detectors.
Adding a new detector is a single-file creation and registration here.
"""

from __future__ import annotations

from typing import Optional

from detectors.base import BaseDetector, Finding
from detectors.correlated_subquery import CorrelatedSubqueryDetector
from detectors.or_different_columns import OrDifferentColumnsDetector
from detectors.implicit_type_conversion import ImplicitTypeConversionDetector
from detectors.not_in_subquery import NotInSubqueryDetector
from detectors.order_by_unindexed import OrderByRandDetector, UnindexedOrderByDetector
from detectors.large_offset import LargeOffsetDetector
from detectors.missing_join_condition import MissingJoinConditionDetector
from detectors.non_sargable_arithmetic import NonSargableArithmeticDetector
from detectors.having_as_where import HavingAsWhereDetector
from detectors.count_distinct import CountDistinctDetector
from detectors.leading_wildcard import LeadingWildcardDetector
from detectors.union_all import UnionInsteadOfUnionAllDetector

from query_model import QueryFeatures
from db.schema import SchemaInfo


DETECTOR_REGISTRY: list[BaseDetector] = [
    CorrelatedSubqueryDetector(),
    OrDifferentColumnsDetector(),
    ImplicitTypeConversionDetector(),
    NotInSubqueryDetector(),
    OrderByRandDetector(),
    UnindexedOrderByDetector(),
    LargeOffsetDetector(),
    MissingJoinConditionDetector(),
    NonSargableArithmeticDetector(),
    HavingAsWhereDetector(),
    CountDistinctDetector(),
    LeadingWildcardDetector(),
    UnionInsteadOfUnionAllDetector(),
]


def run_all_detectors(
    query: str,
    features: QueryFeatures,
    schema: Optional[SchemaInfo] = None,
) -> list[Finding]:
    """Run all registered detectors and return combined list of findings."""
    all_findings: list[Finding] = []
    for detector in DETECTOR_REGISTRY:
        try:
            results = detector.detect(query, features, schema=schema)
            all_findings.extend(results)
        except Exception:
            # Detectors must fail open without crashing query analysis
            continue
    return all_findings
