from __future__ import annotations

import json
import logging
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)

THERAPY_SYSTEM = """You are a licensed-style supportive mental-health coach for adults with diabetes-related stress.
Use short, warm, practical CBT-informed language. Never diagnose, never prescribe medication, and do not provide emergency instructions beyond escalation guidance.
You MUST use retrieved context only when relevant. If retrieved context is weak, ask one clarifying question and avoid fabricated facts.
Match the patient's language and tone. If the detected language is Tunisian Darija, reply in simple Tunisian Darija (Latin or Arabic script acceptable, avoid formal MSA).
If safety risk appears, output brief supportive text and recommendation=notify_clinician_immediately.
You MUST respond with a single JSON object only.
JSON schema:
{
  "reply": "string",
  "technique": "string",
  "recommendation": "string|null",
  "citations": ["chunk_id_or_source", "..."],
  "safety_mode": "normal|low_context|elevated_guard|crisis_guard"
}
"""


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    reply = payload.get("reply")
    technique = payload.get("technique")
    recommendation = payload.get("recommendation")
    if not isinstance(reply, str) or not reply.strip():
        return None
    if not isinstance(technique, str) or not technique.strip():
        return None
    if recommendation is not None and not isinstance(recommendation, str):
        return None
    citations = payload.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    citations = [str(c).strip() for c in citations if str(c).strip()]
    safety_mode = str(payload.get("safety_mode") or "normal").strip().lower()
    if safety_mode not in {"normal", "low_context", "elevated_guard", "crisis_guard"}:
        safety_mode = "normal"
    return {
        "reply": reply.strip(),
        "technique": technique.strip(),
        "recommendation": recommendation.strip() if isinstance(recommendation, str) and recommendation.strip() else None,
        "citations": citations[:5],
        "safety_mode": safety_mode,
    }


def run_therapy_llm(
    user_text: str,
    mental_state: str,
    detected_language: str,
    kb_snippets: list[dict[str, str]],
    memory_items: list[str],
    health_context: dict[str, Any],
    fusion_summary: str,
) -> dict[str, Any] | None:
    api_key = (settings.groq_api_key or "").strip().strip("'\"")
    if not api_key:
        return None

    kb_block = "\n".join(
        f"- [{item.get('chunk_id') or item.get('source','unknown')}] {item.get('text', '')[:240]}"
        for item in kb_snippets[:4]
    )
    mem_block = "\n".join(f"- {m[:220]}" for m in memory_items[:5])
    sem_compact = ""
    hc_dump = health_context or {}
    if isinstance(hc_dump, dict):
        sem_compact = str(hc_dump.get("semantic_profile_compact") or "").strip()
        hc_dump = {k: v for k, v in hc_dump.items() if k not in ("semantic_profile_compact", "semantic_profile_json")}
    health_block = json.dumps(hc_dump, ensure_ascii=False)[:1200]
    semantic_section = ""
    if sem_compact:
        semantic_section = f"Semantic patient profile (distilled):\n{sem_compact[:900]}\n"

    user_prompt = f"""Patient message: {user_text}
Detected language: {detected_language}
Detected mental_state: {mental_state}
Fusion summary: {fusion_summary}
Health / profile context (JSON): {health_block}
{semantic_section}Relevant episodic memory (retrieved by current message):
{mem_block or '- (none)'}
CBT knowledge snippets:
{kb_block or '- (none)'}
Return JSON following the schema exactly."""

    try:
        from groq import Groq
    except ImportError as exc:
        logger.warning("groq not installed: %s", exc)
        return None

    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": THERAPY_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        logger.error("Groq therapy call failed: %s", exc)
        return None

    raw = (response.choices[0].message.content or "{}").strip()
    try:
        if "```" in raw:
            raw = raw.split("```json", 1)[-1].split("```", 1)[0].strip() if "```json" in raw else raw.split("```", 1)[1].split("```", 1)[0].strip()
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        return _validate_payload(parsed)
    except json.JSONDecodeError:
        logger.error("Therapy JSON parse failed: %s", raw[:500])
        return None
