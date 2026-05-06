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
- Your messages MUST be directly relevant to the TRIGGER that caused this run. Focus on what
  actually happened, not on unrelated clinical findings in the data.
- Synthesise signals in priority order: what the trigger highlights first, then correlated signals.
- CRITICAL tier always sets priority=urgent and should_dispatch=true.
- LOW tier with no concerning signals sets should_dispatch=false (no messages needed).
- Messages must be empathetic, concise, and role-appropriate:
  - patient_nudge: motivational, directly addresses the trigger reason (max 2 sentences).
  - caregiver_update: practical, what to watch for given the trigger (max 3 sentences). null if no caregivers.
  - doctor_summary: clinical, includes risk tier + trigger context + suggested action (max 4 sentences). null if no doctor.
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

_TRIGGER_FOCUS = {
    "nutrition_skip": (
        "TRIGGER — NUTRITION SKIP: The patient just skipped a single meal or exercise session. "
        "patient_nudge: gentle, warm, non-judgmental check-in. Acknowledge the skip and encourage "
        "them to stay on track. Do NOT escalate or mention unrelated clinical findings. "
        "caregiver_update: set to null — a single skip does not warrant notifying the caregiver. "
        "Only provide caregiver_update if the risk tier is HIGH or CRITICAL. "
        "doctor_summary: set to null unless the risk tier is HIGH or CRITICAL."
    ),
    "alert": (
        "TRIGGER — HEALTH ALERT: A risk tier escalation or high-risk event was detected. "
        "Focus on the monitoring signals: current risk tier, active alerts, and disease progression. "
        "Lead with the clinical finding that drove the alert."
    ),
    "cron": (
        "TRIGGER — NIGHTLY CHECK: Routine scheduled review. Provide a balanced assessment "
        "across all signals. Only dispatch if there is a meaningful concern to report."
    ),
    "crisis": (
        "TRIGGER — PSYCHOLOGICAL CRISIS: A crisis event was detected during the patient's therapy "
        "session. Focus entirely on the patient's emotional and psychological state. The "
        "patient_nudge must be warm, supportive, and urge the patient to reach out to their care "
        "team or a trusted person immediately."
    ),
}


async def run(context: PatientContext, trigger: str = "cron") -> ReasoningOutput:
    client = Groq(api_key=(settings.groq_api_key or "").strip())

    has_doctor    = bool((context.care_team or {}).get("doctor"))
    has_caregiver = bool((context.care_team or {}).get("caregivers"))

    trigger_block = _TRIGGER_FOCUS.get(trigger, _TRIGGER_FOCUS["cron"])

    user_prompt = (
        f"{trigger_block}\n\n"
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
