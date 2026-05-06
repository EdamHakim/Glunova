"""DispatchAgent — Groq LLM (llama-3.1-8b-instant) + MCP dispatch_update tool.

Receives a ReasoningOutput, decides which recipients to message,
then calls the dispatch_update MCP tool for each one via the shared
ClientSession owned by the Orchestrator.
"""

from __future__ import annotations

import json
import logging

from groq import Groq
from mcp import ClientSession

from agent.schemas import DispatchResult, ReasoningOutput
from core.config import settings

logger = logging.getLogger(__name__)

_DISPATCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "dispatch_update",
        "description": "Deliver a care-agent message: patient/doctor go to Monitoring alerts; caregiver to Care Circle.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id":     {"type": "integer", "description": "Patient user ID"},
                "recipient_type": {"type": "string",  "enum": ["patient", "caregiver", "doctor"]},
                "message":        {"type": "string",  "description": "The message to dispatch"},
                "recipient_id":   {"type": ["integer", "null"], "description": "Caregiver user ID when recipient_type is caregiver; null for patient and doctor"},
                "title":          {"type": "string",  "description": "Short alert title shown in the monitoring feed (max 80 chars). Make it specific to the reason, e.g. 'Nutrition Check-in', 'Activity Reminder', 'Health Alert', 'Crisis Support'."},
            },
            "required": ["patient_id", "recipient_type", "message", "title"],
        },
    },
}

_SYSTEM = """\
You are the dispatch coordinator for Glunova's proactive care agent.
You receive pre-drafted care messages and the patient's care team composition.
Your job is to call dispatch_update for each relevant recipient exactly once.

Rules:
- Always dispatch the patient_nudge to the patient (recipient_type="patient", recipient_id=null).
- If caregiver_update is provided AND caregivers list is non-empty, dispatch once per caregiver.
- If doctor_summary is provided AND a doctor is linked, dispatch for the doctor (recipient_type='doctor', recipient_id=null).
- Do not modify the messages — dispatch them verbatim.
- Choose a short, specific title that reflects the reason for the message:
    nutrition_skip context  → "Meal Check-in" or "Activity Check-in"
    therapy_session context → "Therapy Session Summary"
    crisis context          → "Crisis Support Alert"
    health alert context    → "Health Alert" or "Risk Update"
    routine check-in        → "Care Coordinator Update"
- Call dispatch_update for each recipient, then stop.
"""


async def run(
    reasoning: ReasoningOutput,
    care_team: dict,
    session: ClientSession,
) -> DispatchResult:
    doctor     = care_team.get("doctor")
    caregivers = care_team.get("caregivers", [])

    user_content = (
        f"Patient ID: {reasoning.patient_id}\n\n"
        f"Care team:\n"
        f"  Doctor: {json.dumps(doctor)}\n"
        f"  Caregivers: {json.dumps(caregivers)}\n\n"
        f"Messages to dispatch:\n"
        f"  patient_nudge: {reasoning.patient_nudge}\n"
        f"  caregiver_update: {reasoning.caregiver_update}\n"
        f"  doctor_summary: {reasoning.doctor_summary}\n\n"
        "Call dispatch_update for each applicable recipient."
    )

    client = Groq(api_key=(settings.groq_api_key or "").strip())
    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user",   "content": user_content},
    ]

    dispatched = 0
    recipients: list[str] = []
    # One logical recipient per run (LLM sometimes emits duplicate caregiver tool calls).
    seen_recipients: set[tuple[str, int | None]] = set()

    def _recipient_key(args: dict) -> tuple[str, int | None]:
        rt = (args.get("recipient_type") or "").strip().lower()
        rid = args.get("recipient_id")
        if rt in ("patient", "doctor"):
            return (rt, None)
        if rt == "caregiver" and rid is not None:
            try:
                return ("caregiver", int(rid))
            except (TypeError, ValueError):
                return ("caregiver", None)
        return (rt, rid if rid is None else rid)

    for _ in range(6):  # max rounds — one per recipient + one final
        response = client.chat.completions.create(
            model=settings.psychology_consolidation_model,  # llama-3.1-8b-instant
            messages=messages,
            tools=[_DISPATCH_TOOL_SCHEMA],
            tool_choice="auto",
            temperature=0.1,
            max_tokens=512,
        )
        msg = response.choices[0].message
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in (msg.tool_calls or [])
        ]})

        if not msg.tool_calls:
            break

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            rkey = _recipient_key(args)
            if rkey in seen_recipients:
                dup_payload = json.dumps(
                    {"ok": True, "deduped": True, "recipient_type": args.get("recipient_type")}
                )
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": dup_payload})
                logger.info(
                    "[DispatchAgent] skipped duplicate recipient patient=%s key=%s",
                    args.get("patient_id"),
                    rkey,
                )
                continue
            seen_recipients.add(rkey)

            mcp_result = await session.call_tool("dispatch_update", args)
            result_text = mcp_result.content[0].text if mcp_result.content else "{}"
            result_data = json.loads(result_text)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_text,
            })

            if result_data.get("ok"):
                dispatched += 1
                recipients.append(args.get("recipient_type", "unknown"))
                logger.info(
                    "[DispatchAgent] dispatched patient=%s recipient=%s family_update=%s health_alert=%s",
                    args.get("patient_id"),
                    args.get("recipient_type"),
                    result_data.get("family_update_id"),
                    result_data.get("health_alert_id"),
                )

    return DispatchResult(
        patient_id=reasoning.patient_id,
        messages_dispatched=dispatched,
        recipients=recipients,
    )
