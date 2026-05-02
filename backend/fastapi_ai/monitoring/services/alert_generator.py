"""LLM-backed alert content generator (Groq).

Wraps Groq llama-3.3-70b-versatile to turn a fusion result + tier transition
into a patient-facing alert (title + plain-language explanation + next steps).

Falls back gracefully (returns None) on any failure so the caller can use
deterministic templates instead. Uses GROQ_MONITORING_API_KEY if set, else
GROQ_API_KEY (team key) so the team's existing modules keep working.
"""
from __future__ import annotations

import json
import logging
from threading import Lock

from core.config import settings

logger = logging.getLogger(__name__)


_TIER_LABELS = {"low": "LOW", "high": "HIGH", "critical": "CRITICAL"}
_GRADE_NAMES = ("No DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "Proliferative DR")


_client = None
_client_lock = Lock()
_client_failed = False


def _resolve_api_key() -> str:
    """Prefer the monitoring-dedicated key; fall back to the team key."""
    if settings.groq_monitoring_api_key:
        return settings.groq_monitoring_api_key
    return settings.groq_api_key or ""


def _get_client():
    global _client, _client_failed
    if _client_failed:
        return None
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        api_key = _resolve_api_key()
        if not api_key:
            logger.info("alert_generator: no Groq API key configured; skipping LLM")
            _client_failed = True
            return None
        try:
            from groq import Groq
        except ImportError:
            logger.warning("alert_generator: groq package not installed")
            _client_failed = True
            return None
        try:
            _client = Groq(api_key=api_key)
            logger.info(
                "alert_generator: Groq client initialized (monitoring key=%s)",
                "yes" if settings.groq_monitoring_api_key else "no (using team key)",
            )
            return _client
        except Exception:
            logger.exception("alert_generator: failed to initialize Groq client")
            _client_failed = True
            return None


def _build_signals_summary(features: dict, dr_grade: int) -> str:
    parts: list[str] = []
    p_tab = features.get("p_tabular")
    if p_tab is not None:
        parts.append(
            f"- Clinical profile (HbA1c, blood glucose, age, BMI): {float(p_tab) * 100:.0f}% diabetes risk"
        )
    p_dr = features.get("p_dr_v51")
    if p_dr is not None:
        if dr_grade > 0 and dr_grade < len(_GRADE_NAMES):
            parts.append(
                f"- Fundus scan: detected {_GRADE_NAMES[dr_grade]} (DR probability {float(p_dr) * 100:.0f}%)"
            )
        else:
            parts.append(f"- Fundus scan: no diabetic retinopathy detected ({float(p_dr) * 100:.0f}%)")
    p_th = features.get("p_thermal")
    if p_th is not None:
        parts.append(f"- Thermal foot scan: {float(p_th) * 100:.0f}% diabetes signal")
    p_to = features.get("p_tongue")
    if p_to is not None:
        parts.append(f"- Tongue scan: {float(p_to) * 100:.0f}% diabetes signal")
    p_ul = features.get("p_ulcer")
    if p_ul is not None:
        parts.append(f"- Foot ulcer detection: {float(p_ul) * 100:.0f}%")
    p_ca = features.get("p_cataract")
    if p_ca is not None:
        parts.append(f"- Cataract scan: {float(p_ca) * 100:.0f}%")
    return "\n".join(parts) if parts else "- (only clinical profile available)"


def _build_prompt(new_tier: str, previous_tier: str | None, fusion_result: dict) -> str:
    p_finale = float(fusion_result.get("p_finale", 0.0)) * 100
    confidence = float(fusion_result.get("confidence_factor", 0.0)) * 100
    n_models = int(fusion_result.get("n_models_used", 0))
    features = fusion_result.get("features", {}) or {}
    dr_grade = int(fusion_result.get("dr_grade", 0))
    override_active = bool(fusion_result.get("override_active", False))
    override_reason = fusion_result.get("override_reason")

    if previous_tier is None:
        transition = "First risk assessment ever for this patient."
    else:
        prev_up = previous_tier.upper()
        if prev_up == new_tier:
            transition = f"Re-assessed; tier is still {new_tier}."
        else:
            transition = f"Tier just changed from {prev_up} to {new_tier}."

    signals = _build_signals_summary(features, dr_grade)

    extra = ""
    if override_active and override_reason:
        extra = f"\n- Clinical override triggered: {override_reason}"

    return f"""You are a clinical AI assistant generating a patient-facing health alert about diabetes risk.

Generate ONE alert in English, plain-language, empathetic but factual. Address the patient directly using "you".

CONTEXT:
- New risk tier: {new_tier}
- {transition}
- AI fusion estimated diabetes probability: {p_finale:.1f}%
- AI confidence: {confidence:.0f}%
- Number of contributing models: {n_models}
- Contributing signals:
{signals}{extra}

OUTPUT (return ONLY this JSON, no markdown, no extra text):
{{
  "title": "Short headline (max 80 chars). For tier change, mention the change. For first assessment, mention current tier.",
  "explanation": "60-120 word paragraph explaining why this tier was assigned. Reference the most influential signals. No medical jargon (or define them). Use 'you'.",
  "next_steps": ["First concrete action", "Second concrete action", "Third concrete action"]
}}

RULES:
- title: plain English, no emoji
- explanation: empathetic, factual, second-person ("you"); decode acronyms like HbA1c
- next_steps: 2-4 concrete, time-framed actions the patient can act on this week
- For CRITICAL: emphasize urgency, use "as soon as possible"
- For HIGH: emphasize follow-up within 3-6 months
- For LOW: positive reinforcement + maintain healthy habits
- For tier improvement (e.g. CRITICAL -> HIGH): acknowledge the improvement explicitly
- For tier escalation (e.g. HIGH -> CRITICAL): explain what NEW signal triggered the change
"""


def generate_alert_with_llm(
    new_tier: str,
    previous_tier: str | None,
    fusion_result: dict,
) -> tuple[str, str] | None:
    """Generate (title, message) for a HealthAlert via Groq.

    Returns None on any failure (no API key, network error, malformed JSON,
    missing fields). The caller falls back to deterministic templates.
    """
    client = _get_client()
    if client is None:
        return None

    prompt = _build_prompt(new_tier, previous_tier, fusion_result)
    model_name = settings.groq_model or "llama-3.3-70b-versatile"

    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=600,
            timeout=30,
        )
        raw = completion.choices[0].message.content
        if not raw:
            logger.warning("alert_generator: Groq returned empty content")
            return None
        data = json.loads(raw)
    except Exception:
        logger.exception("alert_generator: Groq call failed")
        return None

    title = str(data.get("title", "")).strip()
    explanation = str(data.get("explanation", "")).strip()
    next_steps = data.get("next_steps", [])

    if not title or not explanation or not isinstance(next_steps, list) or len(next_steps) == 0:
        logger.warning("alert_generator: Groq returned incomplete data: %s", data)
        return None

    # Cap title length defensively (DB column is varchar; keep readable).
    if len(title) > 200:
        title = title[:197].rstrip() + "…"

    next_steps_lines = "\n".join(
        f"{idx + 1}. {str(step).strip()}" for idx, step in enumerate(next_steps) if str(step).strip()
    )
    message = f"{explanation}\n\nNext steps:\n{next_steps_lines}"
    return title, message
