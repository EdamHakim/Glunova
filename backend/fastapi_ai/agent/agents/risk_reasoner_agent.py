"""RiskReasonerAgent — Groq LLM (llama-3.3-70b-versatile, JSON mode).

Receives a PatientContext (nutrition + weekly activity adherence, psychology only),
produces a ReasoningOutput containing coordination priority, key signals from those
domains, pre-drafted messages, and should_dispatch.
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
You receive structured data for a patient and must produce a JSON response.

Data scope (strict):
- You ONLY see NUTRITION (weekly wellness plan, macro goals, exercise skip counts) and PSYCHOLOGY
  (emotion check-ins, recent therapy session count, open crisis flags).
- You do NOT have screening outputs (e.g. retinopathy grades), formal risk-stratification scores,
  risk-assessment drivers, disease-progression timelines, or lab-based monitoring feeds. Never invent
  or cite those. The field name "risk_tier" means coordination urgency inferred ONLY from the JSON
  blocks you are given (nutrition / activity adherence and psychology), not from clinical screening.

Rules:
- Your messages MUST be directly relevant to the TRIGGER that caused this run. Focus on what
  actually happened, not on unrelated findings.
- Synthesise signals in priority order: what the trigger highlights first, then correlated signals
  from the allowed blocks only.
- CRITICAL tier always sets priority=urgent and should_dispatch=true (use only when open crisis or
  severe distress in the PSYCHOLOGY block warrants it).
- LOW tier with no concerning signals sets should_dispatch=false (no messages needed).
- Messages must be empathetic, concise, and role-appropriate:
  - patient_nudge: motivational, directly addresses the trigger reason (max 2 sentences).
  - caregiver_update: practical, what to watch for given the trigger (max 3 sentences). null if no caregivers.
  - doctor_summary: includes coordination priority + trigger context + suggested action (max 4 sentences). null if no doctor.
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
    "cron": (
        "TRIGGER — NIGHTLY CHECK: Routine scheduled review. Provide a balanced assessment "
        "from NUTRITION_AND_ACTIVITY and PSYCHOLOGY only. Only dispatch if there is a meaningful concern."
    ),
    "crisis": (
        "TRIGGER — PSYCHOLOGICAL CRISIS: A crisis event was detected during the patient's therapy "
        "session. Focus entirely on the patient's emotional and psychological state. The "
        "patient_nudge must be warm, supportive, and urge the patient to reach out to their care "
        "team or a trusted person immediately."
    ),
    "therapy_session": (
        "TRIGGER — THERAPY SESSION COMPLETE: The patient just finished a guided therapy session. "
        "Use last_completed_session.summary (themes, last_state, techniques_used, risk_flags if any) "
        "plus PSYCHOLOGY and NUTRITION_AND_ACTIVITY blocks. Produce three coordinated messages: "
        "patient_nudge: brief affirming wrap-up referencing progress or coping themes (no clinical jargon). "
        "caregiver_update: one short paragraph on how the family can support the patient this week "
        "(themes only — do not quote raw message excerpts or sensitive tokens). "
        "doctor_summary: concise clinical handoff (mental state trajectory, techniques, any risk_flags). "
        "Set should_dispatch=true so summaries are delivered to every linked recipient."
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
        f"NUTRITION_AND_ACTIVITY:\n{json.dumps(context.nutrition, indent=2)}\n\n"
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
