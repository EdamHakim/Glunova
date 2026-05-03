"""Monitoring fusion service - orchestrates the v11 risk stratification.

Loads ONLY the TabularPredictor (the only image-free model). Image-based scores
(DR, Thermal, Tongue) come from screening_screeningresult — written by their
respective inference routes whenever the doctor uploads a new image.

Trigger points (caller's responsibility):
  1. After patient signup       → tabular only (no screenings yet)
  2. After each screening insert → tabular + all available scores
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock

from monitoring.fusion_v11 import glunova_predictor as gp
from monitoring.services.persistence import (
    fetch_latest_screening_scores,
    fetch_patient_health_data,
    fetch_previous_tier,
    persist_health_alert,
    persist_risk_assessment,
)

logger = logging.getLogger(__name__)


# ─── Local model paths (override the Colab paths in glunova_config.json) ─────
_FASTAPI_ROOT = Path(__file__).resolve().parents[2]  # backend/fastapi_ai/
TABULAR_MODEL_PATH = _FASTAPI_ROOT / "clinic" / "models" / "tabular" / "tabular_diabetes_lgb.joblib"
TABULAR_FEATURES_PATH = _FASTAPI_ROOT / "clinic" / "models" / "tabular" / "tabular_feature_columns.json"

# Config JSON ships clinical_weights + confidence_factors; we apply them as module
# globals on glunova_predictor before any call to late_fusion_robust.
CONFIG_PATH = Path(__file__).resolve().parent.parent / "fusion_v11" / "glunova_config.json"


class MonitoringFusionService:
    """Lazy singleton: TabularPredictor + late_fusion_robust orchestrator."""

    def __init__(self) -> None:
        self._tabular: gp.TabularPredictor | None = None
        self._config_loaded = False
        self._load_lock = Lock()
        self._inference_lock = Lock()

    @property
    def is_loaded(self) -> bool:
        return self._tabular is not None and self._config_loaded

    # JSON config key  ->  glunova_predictor module-level global it overrides.
    _THRESHOLD_GLOBAL_MAP = {
        "tier_critical":          "TIER_CRITICAL_THRESHOLD",
        "tier_high":              "TIER_HIGH_THRESHOLD",
        "override_confidence":    "OVERRIDE_CONFIDENCE_THRESHOLD",
        "complication_asymmetry": "COMPLICATION_THRESHOLD",
        "tabular_high":           "TABULAR_HIGH_THRESHOLD",
        "dr_detected":            "DR_DETECTED_THRESHOLD",
        "dfu_override":           "DFU_OVERRIDE_THRESHOLD",
    }

    def _apply_config(self) -> None:
        """Load CLINICAL_WEIGHTS / CONFIDENCE_FACTORS / thresholds into glunova_predictor globals.

        Without this, late_fusion_robust raises NameError on CLINICAL_WEIGHTS
        (only defined inside GlunovaSystem.__init__). The thresholds override lets
        clinicians tune cut-offs (e.g. CRITICAL >= 0.95) by editing JSON only.
        """
        if self._config_loaded:
            return
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"glunova_config.json not found at {CONFIG_PATH}")
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        if "clinical_weights" in config:
            gp.CLINICAL_WEIGHTS = config["clinical_weights"]
        if "confidence_factors" in config:
            gp.CONFIDENCE_FACTORS = {int(k): v for k, v in config["confidence_factors"].items()}
        thresholds = config.get("thresholds") or {}
        for json_key, python_global in self._THRESHOLD_GLOBAL_MAP.items():
            if json_key in thresholds:
                value = float(thresholds[json_key])
                setattr(gp, python_global, value)
                logger.info("Override %s = %s (from glunova_config.json)", python_global, value)
        self._config_loaded = True

    def ensure_loaded(self) -> None:
        if self.is_loaded:
            return
        with self._load_lock:
            if self.is_loaded:
                return
            self._apply_config()
            if not TABULAR_MODEL_PATH.exists():
                raise FileNotFoundError(
                    f"Tabular LightGBM model not found at {TABULAR_MODEL_PATH.as_posix()}"
                )
            if not TABULAR_FEATURES_PATH.exists():
                raise FileNotFoundError(
                    f"Tabular features JSON not found at {TABULAR_FEATURES_PATH.as_posix()}"
                )
            self._tabular = gp.TabularPredictor(
                str(TABULAR_MODEL_PATH), str(TABULAR_FEATURES_PATH)
            )
            logger.info("MonitoringFusionService: TabularPredictor loaded")

    def predict_for_patient(self, user_id: int) -> dict:
        """Run fusion for a patient (no persistence).

        Returns the late_fusion_robust dict, augmented with features + dr_grade
        + available_modalities. On error: {'error': ..., 'tier': None}.
        """
        self.ensure_loaded()
        assert self._tabular is not None

        patient = fetch_patient_health_data(user_id)
        if patient is None:
            return {
                "error": "PATIENT_INCOMPLETE",
                "message": (
                    f"Patient {user_id} missing required health fields "
                    "(date_of_birth, hba1c_level, blood_glucose_level)."
                ),
                "tier": None,
            }

        with self._inference_lock:
            try:
                p_tabular = self._tabular.predict(patient.to_lgb_dict())
            except ValueError as exc:
                return {"error": "TABULAR_FAILED", "message": str(exc), "tier": None}

        scores = fetch_latest_screening_scores(user_id)

        def _score_or_none(key: str) -> float | None:
            entry = scores.get(key)
            return float(entry["score"]) if entry else None

        features = {
            "p_tabular":  p_tabular,
            "p_dr_v51":   _score_or_none("p_dr_v51"),
            "p_thermal":  _score_or_none("p_thermal"),
            "p_ulcer":    _score_or_none("p_ulcer"),
            "p_tongue":   _score_or_none("p_tongue"),
            "p_cataract": _score_or_none("p_cataract"),
        }

        # DR V8 grade + confidence are persisted in the DR ScreeningResult metadata
        # by the DR cascade route. The fusion override rules expect ICDR (0-4 with
        # 0=No DR, 3=Severe, 4=Proliferative), but V8 returns grade_idx in 0-3
        # (Mild/Moderate/Severe/Proliferative — V8 only runs once V5.1 confirms DR).
        # We prefer clinical_grade when available (already ICDR), and fall back to
        # converting V8's grade_idx using the v51_dr_detected flag.
        dr_meta = (scores.get("p_dr_v51") or {}).get("metadata", {})
        if "clinical_grade" in dr_meta:
            dr_grade = int(dr_meta.get("clinical_grade", 0))
        else:
            v8_idx = int(dr_meta.get("dr_v8_grade", 0))
            v51_detected = bool(dr_meta.get("v51_dr_detected", False))
            dr_grade = v8_idx + 1 if v51_detected else 0
        dr_confidence = float(dr_meta.get("dr_v8_confidence", 0.0))

        cat_meta = (scores.get("p_cataract") or {}).get("metadata", {})
        cataract_grade = int(cat_meta.get("cataract_grade", 0))
        cataract_confidence = float(cat_meta.get("cataract_confidence", 0.0))

        result = gp.late_fusion_robust(
            features,
            dr_grade=dr_grade,
            dr_grade_confidence=dr_confidence,
            cataract_grade=cataract_grade,
            cataract_confidence=cataract_confidence,
        )

        # Augment with the same fields GlunovaSystem.predict adds, for downstream
        # consumers / persistence / debugging.
        result["features"] = features
        result["dr_grade"] = dr_grade
        result["dr_confidence"] = dr_confidence
        result["cataract_grade"] = cataract_grade
        result["cataract_confidence"] = cataract_confidence
        result["available_modalities"] = sorted(scores.keys())
        return result

    def refresh_tier_for_patient(self, user_id: int) -> dict:
        """Run fusion + persist RiskAssessment (+ HealthAlert if tier crossed a threshold)."""
        result = self.predict_for_patient(user_id)
        if result.get("error"):
            return result
        # Capture the previous tier BEFORE inserting the new RiskAssessment, so
        # the alert can decide whether the new tier represents a threshold change.
        previous_tier = fetch_previous_tier(user_id)
        result["previous_tier"] = previous_tier
        assessment_id = persist_risk_assessment(user_id, result)
        result["risk_assessment_id"] = assessment_id
        if assessment_id is not None:
            alert_id = persist_health_alert(
                user_id, assessment_id, result, previous_tier=previous_tier
            )
            if alert_id is not None:
                result["health_alert_id"] = alert_id
        return result


_service: MonitoringFusionService | None = None
_singleton_lock = Lock()


def get_fusion_service() -> MonitoringFusionService:
    global _service
    if _service is not None:
        return _service
    with _singleton_lock:
        if _service is None:
            _service = MonitoringFusionService()
    return _service
