"""Normalize patient-written memory blobs to English for Qdrant embedding (English corpus)."""

from __future__ import annotations

import logging
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You translate psychotherapy session memory excerpts into concise clinical English for vector search. "
    "Preserve factual content and emotional weight. Respond with the translation only — no preamble, quotes, "
    "or commentary."
)


def groq_translate_patient_text_to_english(text: str, source_language_hint: str) -> str | None:
    """Return English text or None if translation is unavailable."""
    trimmed = text.strip()
    if not trimmed:
        return trimmed
    api_key = (settings.groq_api_key or "").strip().strip("\"'")
    if not api_key:
        logger.debug("Memory translation skipped: GROQ_API_KEY missing")
        return None

    hint = source_language_hint.strip() or "unknown"
    user_block = (
        f"Recorded source language hint: {hint}\n\n"
        f"Patient-associated text:\n{trimmed}\n\n"
        "English:"
    )

    try:
        from groq import Groq
    except ImportError as exc:
        logger.warning("groq package missing for memory translation: %s", exc)
        return None

    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            temperature=0.15,
            max_tokens=384,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_block},
            ],
        )
    except Exception as exc:
        logger.warning("Groq memory translation failed: %s", exc)
        return None

    raw = (response.choices[0].message.content or "").strip()
    out = raw.strip('"').strip("'").strip()
    return out if out else None


def translate_summary_strings_for_embedding(
    summary_dict: dict[str, Any],
    *,
    hint: str,
) -> dict[str, Any]:
    """Copy summary and translate textual fields patient may have authored in FR/AR/darija/mixed."""
    out = dict(summary_dict)
    excerpt = str(out.get("last_patient_message_excerpt") or "").strip()
    if excerpt:
        translated = groq_translate_patient_text_to_english(excerpt, hint)
        if translated:
            out["last_patient_message_excerpt"] = translated[:200]

    for field in ("breakthroughs", "triggers"):
        val = out.get(field)
        if isinstance(val, list):
            rewritten: list[str] = []
            for item in val:
                if not isinstance(item, str) or not item.strip():
                    continue
                t = groq_translate_patient_text_to_english(item.strip(), hint)
                rewritten.append(t if t else item)
            out[field] = rewritten

    return out
