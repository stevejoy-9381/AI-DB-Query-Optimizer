"""detectors package.
Modular anti-pattern detectors for MySQL 8.x query optimization.
"""

from detectors.base import BaseDetector, Finding
from detectors.registry import DETECTOR_REGISTRY, run_all_detectors

__all__ = ["BaseDetector", "Finding", "DETECTOR_REGISTRY", "run_all_detectors"]
