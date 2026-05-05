"""RiskReasonerAgent — Groq LLM (llama-3.3-70b-versatile, JSON mode).

Receives a PatientContext, produces a ReasoningOutput containing:
- risk tier and priority level
- key clinical signals
- pre-drafted messages for each recipient role
- should_dispatch flag (False when signals are reassuringly LOW)
"""

from __future__ import annotations

import json
import logging

from groq import Groq

from agent.schemas import PatientContext, ReasoningOutput
from core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a proactive clinical care coordinator for Glunova, a diabetes management platform.
You receive structured health data for a diabetic patient and must produce a JSON response.

Rules:
- Synthesise ALL signals (risk score, alerts, nutrition adherence, emotional state).
- Correlate: a HIGH risk tier combined with skipped meals AND elevated anxiety is more urgent
  than any single signal alone.
- CRITICAL tier always sets priority=urgent and should_dispatch=true.
- LOW tier with no concerning signals sets should_dispatch=false (no messages needed).
- Messages must be empathetic, concise, and role-appropriate:
  - patient_nudge: motivational, non-alarming (max 2 sentences).
  - caregiver_update: practical, what to watch for (max 3 sentences). null if no caregivers.
  - doctor_summary: clinical, includes risk tier + key drivers + suggested action (max 4 sentences). null if no doctor.
- Output ONLY valid JSON. No preamble.

Output schema:
{
  "risk_tier": "LOW" | "HIGH" | "CRITICAL",
  "priority_level": "low" | "medium" | "high" | "urgent",
  "key_signals": ["<signal>", ...],
  "should_dispatch": true | false,
  "patient_nudge": "<message>",
  "caregiver_update": "<message>" | null,
  "doctor_summary": "<message>" | null
}
"""


async def run(context: PatientContext) -> ReasoningOutput:
    client = Groq(api_key=(settings.groq_api_key or "").strip())

    has_doctor    = bool((context.care_team or {}).get("doctor"))
    has_caregiver = bool((context.care_team or {}).get("caregivers"))

    user_prompt = (
        f"Patient ID: {context.patient_id}\n"
        f"Has linked doctor: {has_doctor}\n"
        f"Has linked caregivers: {has_caregiver}\n\n"
        f"MONITORING:\n{json.dumps(context.monitoring, indent=2)}\n\n"
        f"NUTRITION:\n{json.dumps(context.nutrition, indent=2)}\n\n"
        f"PSYCHOLOGY:\n{json.dumps(context.psychology, indent=2)}\n\n"
        "Generate the care coordination reasoning output as JSON."
    )

    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=1024,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("[RiskReasonerAgent] JSON parse failed: %s", raw[:200])
        data = {}

    # Safe defaults if LLM output is malformed.
    risk_tier      = data.get("risk_tier", "LOW")
    priority_level = data.get("priority_level", "low")
    key_signals    = data.get("key_signals", [])
    should_dispatch = data.get("should_dispatch", risk_tier in ("HIGH", "CRITICAL"))

    logger.info(
        "[RiskReasonerAgent] patient=%s tier=%s priority=%s dispatch=%s signals=%s",
        context.patient_id, risk_tier, priority_level, should_dispatch, len(key_signals),
    )

    return ReasoningOutput(
        patient_id=context.patient_id,
        risk_tier=risk_tier,
        priority_level=priority_level,
        key_signals=key_signals,
        should_dispatch=should_dispatch,
        patient_nudge=data.get("patient_nudge", ""),
        caregiver_update=data.get("caregiver_update"),
        doctor_summary=data.get("doctor_summary"),
    )
