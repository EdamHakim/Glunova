"""DB I/O for the monitoring axis (Supabase via shared psycopg pool).

Reads patient health data + latest screening scores; writes RiskAssessment +
HealthAlert. All functions return None / empty on DB failures (graceful).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from core.db import get_connection_pool

logger = logging.getLogger(__name__)


# ─── Encoding tables matching the LightGBM training (Kaggle vocab) ───────────
# sklearn LabelEncoder sorts alphabetically on the unique input strings.
SMOKING_ENCODING = {
    "No Info": 0,
    "current": 1,
    "ever": 2,
    "former": 3,
    "never": 4,
    "not current": 5,
}

GENDER_ENCODING = {"Male": 0, "Female": 1}


# ─── Modality ↔ fusion-feature key mapping ───────────────────────────────────
# Maps screening_screeningresult.modality (Django enum) to the dict key
# expected by glunova_predictor.late_fusion_robust().
MODALITY_TO_FEATURE = {
    "retinopathy": "p_dr_v51",
    "infrared":    "p_thermal",
    "tongue":      "p_tongue",
    "foot_ulcer":  "p_ulcer",
    "cataract":    "p_cataract",
}


@dataclass
class PatientHealthData:
    """LightGBM-ready feature dict (encoded values)."""
    age: int
    bmi: float
    HbA1c_level: float
    blood_glucose_level: int
    hypertension: int
    heart_disease: int
    gender_enc: int
    smoking_enc: int

    def to_lgb_dict(self) -> dict:
        return {
            "age": self.age,
            "bmi": self.bmi,
            "HbA1c_level": self.HbA1c_level,
            "blood_glucose_level": self.blood_glucose_level,
            "hypertension": self.hypertension,
            "heart_disease": self.heart_disease,
            "gender_enc": self.gender_enc,
            "smoking_enc": self.smoking_enc,
        }


def _compute_age(date_of_birth) -> int | None:
    if date_of_birth is None:
        return None
    today = datetime.now().date()
    return (
        today.year - date_of_birth.year
        - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    )


def _compute_bmi(height_cm, weight_kg) -> float | None:
    if height_cm is None or weight_kg is None or float(height_cm) <= 0:
        return None
    h_m = float(height_cm) / 100.0
    return round(float(weight_kg) / (h_m * h_m), 2)


def fetch_patient_health_data(user_id: int) -> PatientHealthData | None:
    """Read 9 health fields from users_patientprofile (linked to users_user via
    user_id), convert to LightGBM-ready data.

    Returns None if patient is missing the 3 fields the fusion treats as required:
    age (date_of_birth), HbA1c_level, blood_glucose_level.
    """
    pool = get_connection_pool()
    if pool is None:
        logger.warning("Cannot fetch patient health data: DB pool unavailable")
        return None

    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT date_of_birth, gender, height_cm, weight_kg,
                   hypertension, heart_disease, smoking_status,
                   hba1c_level, blood_glucose_level
              FROM users_patientprofile
             WHERE user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()

    if not row:
        return None

    (dob, gender, height_cm, weight_kg, hypertension, heart_disease,
     smoking_status, hba1c, glucose) = row

    age = _compute_age(dob)
    bmi = _compute_bmi(height_cm, weight_kg)

    if age is None or hba1c is None or glucose is None:
        logger.info("Patient %s missing required health fields (age/hba1c/glucose)", user_id)
        return None

    return PatientHealthData(
        age=int(age),
        # Sane physiological default if patient skipped height/weight at signup.
        bmi=float(bmi) if bmi is not None else 25.0,
        HbA1c_level=float(hba1c),
        blood_glucose_level=int(glucose),
        hypertension=1 if hypertension else 0,
        heart_disease=1 if heart_disease else 0,
        gender_enc=GENDER_ENCODING.get(gender or "", 0),
        smoking_enc=SMOKING_ENCODING.get(smoking_status or "", 0),
    )


def fetch_latest_screening_scores(user_id: int) -> dict[str, dict]:
    """Read latest ScreeningResult per modality for this patient.

    Returns dict mapping fusion feature key (e.g. 'p_dr_v51') to:
        {'score': float, 'metadata': dict, 'captured_at': datetime}
    Modalities not yet captured for this patient are simply absent.
    """
    pool = get_connection_pool()
    if pool is None:
        return {}

    out: dict[str, dict] = {}
    with pool.connection() as conn, conn.cursor() as cur:
        # DISTINCT ON (modality) keeps only the most recent row per modality.
        cur.execute(
            """
            SELECT DISTINCT ON (modality)
                   modality, score, metadata, captured_at
              FROM screening_screeningresult
             WHERE patient_id = %s
             ORDER BY modality, captured_at DESC
            """,
            (user_id,),
        )
        for modality, score, metadata, captured_at in cur.fetchall():
            feature_key = MODALITY_TO_FEATURE.get(modality)
            if feature_key is None:
                continue
            out[feature_key] = {
                "score": float(score),
                "metadata": metadata if isinstance(metadata, dict) else {},
                "captured_at": captured_at,
            }
    return out


def persist_screening_result(
    user_id: int,
    modality: str,
    score: float,
    risk_label: str,
    model_version: str,
    metadata: dict | None = None,
    captured_at: datetime | None = None,
) -> int | None:
    """Insert a ScreeningResult row. Used by inference routes (DR, Thermal, Tongue)."""
    pool = get_connection_pool()
    if pool is None:
        return None

    captured_at = captured_at or datetime.now(timezone.utc)
    metadata = metadata or {}
    now = datetime.now(timezone.utc)

    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO screening_screeningresult
                (patient_id, modality, score, risk_label, model_version, metadata,
                 captured_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            RETURNING id
            """,
            (user_id, modality, score, risk_label, model_version,
             json.dumps(metadata), captured_at, now),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
    return int(new_id)


def persist_risk_assessment(user_id: int, fusion_result: dict) -> int | None:
    """Insert a RiskAssessment row. Returns the new id or None on failure/error."""
    if fusion_result.get("error"):
        logger.warning("Skipping persist: fusion error %s", fusion_result.get("error"))
        return None

    pool = get_connection_pool()
    if pool is None:
        logger.warning("Cannot persist RiskAssessment for patient %s: pool unavailable", user_id)
        return None

    # Django RiskAssessment.Tier choices use lowercase values.
    tier = (fusion_result.get("tier") or "low").lower()
    score = float(fusion_result.get("p_finale", 0.0))
    confidence = float(fusion_result.get("confidence_factor", 0.5))

    drivers = {
        "reasons": fusion_result.get("reasons", []),
        "recommendation": fusion_result.get("recommendation"),
        "contributions": fusion_result.get("contributions", {}),
        "n_models_used": fusion_result.get("n_models_used", 0),
        "override_active": fusion_result.get("override_active", False),
        "override_reason": fusion_result.get("override_reason"),
        "asymmetry_filtered": fusion_result.get("asymmetry_filtered", []),
        "features": fusion_result.get("features", {}),
        "dr_grade": fusion_result.get("dr_grade", 0),
        "dr_confidence": fusion_result.get("dr_confidence", 0.0),
    }

    now = datetime.now(timezone.utc)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO monitoring_riskassessment
                (patient_id, tier, score, confidence, drivers, assessed_at, created_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
            RETURNING id
            """,
            (user_id, tier, score, confidence, json.dumps(drivers), now, now),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
    return int(new_id)


_TIER_RANK = {"low": 0, "moderate": 1, "high": 2, "critical": 3}
_GRADE_NAMES = ("No DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "Proliferative DR")


def fetch_previous_tier(user_id: int, exclude_assessment_id: int | None = None) -> str | None:
    """Return the tier of the second-most-recent RiskAssessment (= the one before
    the current one). Used to decide whether a tier threshold was crossed.
    """
    pool = get_connection_pool()
    if pool is None:
        return None
    with pool.connection() as conn, conn.cursor() as cur:
        if exclude_assessment_id is not None:
            cur.execute(
                """
                SELECT tier FROM monitoring_riskassessment
                 WHERE patient_id = %s AND id <> %s
                 ORDER BY assessed_at DESC, created_at DESC
                 LIMIT 1
                """,
                (user_id, exclude_assessment_id),
            )
        else:
            cur.execute(
                """
                SELECT tier FROM monitoring_riskassessment
                 WHERE patient_id = %s
                 ORDER BY assessed_at DESC, created_at DESC
                 LIMIT 1
                """,
                (user_id,),
            )
        row = cur.fetchone()
    return str(row[0]).lower() if row else None


def _build_alert_content(
    new_tier: str, previous_tier: str | None, fusion_result: dict
) -> tuple[str, str]:
    """Build (title, message) using plain-language templates.

    Title encodes the threshold transition (escalated / improved / first time).
    Message bundles a brief explanation of contributing factors + next steps.
    """
    new_rank = _TIER_RANK.get(new_tier.lower(), 0)
    prev_rank = _TIER_RANK.get(previous_tier.lower(), -1) if previous_tier else -1

    # ── Title ──────────────────────────────────────────────────────────────
    if previous_tier is None:
        if new_tier == "CRITICAL":
            title = "Diabetes risk classified as CRITICAL"
        elif new_tier == "HIGH":
            title = "Diabetes risk classified as HIGH"
        else:
            title = f"Initial risk assessment: {new_tier}"
    elif new_rank > prev_rank:
        title = f"Risk escalated from {previous_tier.upper()} to {new_tier} - new signals confirmed risk"
    elif new_rank < prev_rank:
        title = f"Risk improved from {previous_tier.upper()} to {new_tier}"
    else:
        title = f"Risk reassessed: still {new_tier}"

    # ── Body : explanation + next steps ────────────────────────────────────
    p_finale_pct = float(fusion_result.get("p_finale", 0.0)) * 100
    confidence_pct = float(fusion_result.get("confidence_factor", 0.0)) * 100
    features = fusion_result.get("features", {}) or {}
    dr_grade = int(fusion_result.get("dr_grade", 0))

    lines = [
        f"AI fusion estimated diabetes probability at {p_finale_pct:.1f}% "
        f"(confidence {confidence_pct:.0f}%).",
        "",
        "Why:",
    ]

    p_tab = features.get("p_tabular")
    if p_tab is not None:
        lines.append(
            f"- Clinical profile (HbA1c, blood glucose, age, BMI): {float(p_tab) * 100:.0f}% diabetes risk."
        )
    p_dr = features.get("p_dr_v51")
    if p_dr is not None and dr_grade > 0:
        grade_label = _GRADE_NAMES[dr_grade] if dr_grade < len(_GRADE_NAMES) else f"grade {dr_grade}"
        lines.append(f"- Fundus scan detected {grade_label}.")
    elif p_dr is not None:
        lines.append("- Fundus scan analysed; no diabetic retinopathy detected.")
    p_th = features.get("p_thermal")
    if p_th is not None:
        lines.append(f"- Thermal foot scan diabetes signal: {float(p_th) * 100:.0f}%.")
    p_to = features.get("p_tongue")
    if p_to is not None:
        lines.append(f"- Tongue scan diabetes signal: {float(p_to) * 100:.0f}%.")
    p_ul = features.get("p_ulcer")
    if p_ul is not None:
        lines.append(f"- Foot ulcer detection signal: {float(p_ul) * 100:.0f}%.")
    p_ca = features.get("p_cataract")
    if p_ca is not None:
        lines.append(f"- Cataract detection signal: {float(p_ca) * 100:.0f}%.")

    if fusion_result.get("override_active"):
        lines.append(f"- Clinical override: {fusion_result.get('override_reason', 'severe finding')}.")

    lines.append("")
    lines.append("Next steps:")
    if new_tier == "CRITICAL":
        lines += [
            "1. Schedule an immediate consultation with your endocrinologist or specialist.",
            "2. Continue daily blood glucose monitoring and log every reading.",
            "3. Review medication compliance and lifestyle (diet, activity) with your doctor.",
        ]
    elif new_tier == "HIGH":
        lines += [
            "1. Book a consultation with a specialist within the next 3-6 months.",
            "2. Maintain regular blood glucose monitoring at home.",
            "3. Bring your latest fundus / foot / tongue scans to your next visit.",
        ]
    else:
        lines += [
            "1. Continue annual diabetes screening.",
            "2. Maintain a healthy diet and regular physical activity.",
        ]

    message = "\n".join(lines)
    return title, message


def persist_health_alert(
    user_id: int,
    assessment_id: int,
    fusion_result: dict,
    previous_tier: str | None = None,
) -> int | None:
    """Threshold-crossed alerts only.

    Skips the insert when the tier did not change vs the previous assessment.
    On a new tier (or the very first assessment when tier >= HIGH), inserts a
    plain-language alert with explanation + next steps.
    """
    tier = (fusion_result.get("tier") or "").upper()
    if tier not in ("HIGH", "CRITICAL"):
        return None

    new_tier_lower = tier.lower()
    if previous_tier is not None and previous_tier == new_tier_lower:
        # Not a threshold transition; don't spam the alerts feed.
        return None

    pool = get_connection_pool()
    if pool is None:
        return None

    severity = "warning" if tier == "HIGH" else "critical"
    # Try LLM first (Groq, monitoring key); fall back to deterministic templates.
    from monitoring.services.alert_generator import generate_alert_with_llm

    llm_output = generate_alert_with_llm(tier, previous_tier, fusion_result)
    if llm_output is not None:
        title, message = llm_output
    else:
        title, message = _build_alert_content(tier, previous_tier, fusion_result)

    now = datetime.now(timezone.utc)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO monitoring_healthalert
                (patient_id, risk_assessment_id, title, message, severity, status,
                 triggered_at, created_at)
            VALUES (%s, %s, %s, %s, %s, 'active', %s, %s)
            RETURNING id
            """,
            (user_id, assessment_id, title, message, severity, now, now),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
    return int(new_id)
