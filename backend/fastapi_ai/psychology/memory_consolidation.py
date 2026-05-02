"""Session-end consolidation: LLM extracts episodic chunks + semantic profile patch."""

from __future__ import annotations

import json
import logging
from typing import Any

from core.config import settings
from psychology.memory_scoring import merge_semantic_profile

logger = logging.getLogger(__name__)


def _shallow_existing(existing_semantic: dict[str, Any] | None) -> dict[str, Any]:
    return dict(existing_semantic) if isinstance(existing_semantic, dict) else {}


CONSOLIDATION_SYSTEM = """You are a clinical documentation assistant for diabetes-focused mental-health coaching (Sanadi).
Extract structured memory from ONE completed session summary. Output JSON ONLY.
Never invent clinical facts not supported by the input. Use concise clinical English for episodic texts (for retrieval).
Schema:
{
  "episodic_chunks": [
    {
      "text": "single retrievable clinical fact or event under 400 chars",
      "memory_type": "distress_event|breakthrough|coping_tool|relationship|sleep_energy|therapy_process|clinical_risk|other",
      "emotion_at_time": "string or omit",
      "distress_score": 0.0-1.0 or omit,
      "clinical_flag": true only for crisis,self-harm,suicidal ideation, severe disordered eating, abuse, refusal of care signals
    }
  ],
  "semantic_patch": {
    "primary_stressors": ["optional short strings"],
    "known_triggers": [],
    "coping_strengths": [],
    "communication_style": "direct|gentle|metaphor-based or omit",
    "therapy_language_note": "short or omit",
    "distress_trend_note": "short or omit from session cues only",
    "clinical_summary_note": "short or omit",
    "therapy_progress_note": "short or omit",
    "last_crisis_at": "ISO-8601 datetime only if crisis/clinical_flag in session",
    "contradictions_pending": [{"claim_a":"","claim_b":"","domain":"sleep|mood|coping|safety|other","session_anchor":""}],
    "updated_from_session_id": "passed in user message"
  },
  "requires_physician_review": false,
  "physician_review_reason": "short if true else omit"
}
Cap episodic_chunks at 12. Omit empty arrays."""


def run_session_consolidation(
    *,
    summary_dict: dict[str, Any],
    session_id: str,
    patient_id: int,
    preferred_language: str,
    avg_distress: float | None,
    existing_semantic: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, bool, str | None]:
    """
    Returns (episodic_chunk_dicts_for_qdrant, merged_semantic_dict_or_none, requires_review, review_reason).
    merged_semantic is None when consolidation is off or the LLM call failed (caller uses raw blob fallback).
    """
    if getattr(settings, "mem0_enabled", False):
        logger.info("mem0_enabled is set; native Groq consolidation remains the active path.")

    api_key = (settings.groq_api_key or "").strip().strip("'\"")
    if not api_key or not settings.psychology_consolidation_enabled:
        return [], None, False, None

    user_blob = json.dumps(summary_dict, ensure_ascii=False, indent=2)[:12000]
    user_prompt = (
        f"patient_id={patient_id}\nsession_id={session_id}\npreferred_language={preferred_language}\n"
        f"avg_distress_estimate={avg_distress}\n\nSESSION_SUMMARY_JSON:\n{user_blob}"
    )

    raw: dict[str, Any] | None = None
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        model = (settings.psychology_consolidation_model or settings.groq_model).strip()
        response = client.chat.completions.create(
            model=model,
            temperature=0.15,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": CONSOLIDATION_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
        )
        txt = (response.choices[0].message.content or "{}").strip()
        if "```" in txt:
            if "```json" in txt:
                txt = txt.split("```json", 1)[-1].split("```", 1)[0].strip()
            else:
                txt = txt.split("```", 1)[-1].split("```", 1)[0].strip()
        parsed = json.loads(txt)
        raw = parsed if isinstance(parsed, dict) else None
    except Exception as exc:
        logger.warning("memory consolidation LLM failed: %s", exc)
        return [], None, False, None

    if raw is None:
        return [], None, False, None

    merged_base = _shallow_existing(existing_semantic)
    patch_in = raw.get("semantic_patch")
    merged = merge_semantic_profile(
        merged_base,
        patch_in if isinstance(patch_in, dict) else {},
        contradictions_cap=int(settings.psychology_semantic_contradictions_cap),
    )
    merged["updated_from_session_id"] = session_id

    episodic: list[dict[str, Any]] = []
    chunks = raw.get("episodic_chunks")
    if isinstance(chunks, list):
        for item in chunks[:24]:
            if not isinstance(item, dict):
                continue
            txt = str(item.get("text", "")).strip()
            if not txt:
                continue
            episodic.append(
                {
                    "text": txt[:2400],
                    "memory_type": str(item.get("memory_type") or "other")[:64],
                    "emotion_at_time": str(item.get("emotion_at_time") or "")[:64] or None,
                    "distress_score": float(item["distress_score"])
                    if isinstance(item.get("distress_score"), (int, float))
                    else None,
                    "clinical_flag": bool(item.get("clinical_flag", False)),
                }
            )

    req = bool(raw.get("requires_physician_review"))
    reason_raw = raw.get("physician_review_reason")
    reason = str(reason_raw).strip() if isinstance(reason_raw, str) and reason_raw.strip() else None

    contradictions = merged.get("contradictions_pending")
    if isinstance(contradictions, list) and contradictions:
        for c in contradictions:
            if not isinstance(c, dict):
                continue
            domain = str(c.get("domain", "")).lower()
            if domain == "safety" or domain == "clinical":
                req = True
                reason = reason or "Semantic consolidation flagged contradiction in safety-sensitive domain."

    return episodic[:12], merged, req, reason
