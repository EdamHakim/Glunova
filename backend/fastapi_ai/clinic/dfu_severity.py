"""Heuristic diabetic foot ulcer severity from segmentation (not a Wagner / UT grade).

Severity follows the calibrated lesion area in mm² (mask pixels × (mm_per_pixel)²).
Accurate mm/pixel calibration is required for meaningful tiers.
Thresholds are UX triage constants only — clinical staging remains with the care team.

Approximate bands: <1 cm² mild, ~1–4 cm² moderate, ~4–10 cm² severe, >10 cm² critical.
"""

from __future__ import annotations

from typing import Literal

DFUSeverity = Literal["none", "mild", "moderate", "severe", "critical"]

# Ulcer area (mm²) from segmented mask × physical calibration.
_MM2_MILD_MAX = 100.0       # < ~1 cm²
_MM2_MODERATE_MAX = 400.0  # ~1–4 cm²
_MM2_SEVERE_MAX = 1000.0    # ~4–10 cm²
# Above _MM2_SEVERE_MAX → critical


def classify_dfu_severity(*, ulcer_detected: bool, area_mm2: float) -> DFUSeverity:
    if not ulcer_detected:
        return "none"
    a = max(0.0, float(area_mm2))
    if a < _MM2_MILD_MAX:
        return "mild"
    if a < _MM2_MODERATE_MAX:
        return "moderate"
    if a < _MM2_SEVERE_MAX:
        return "severe"
    return "critical"
