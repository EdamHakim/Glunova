"""Heuristics for psychology KB retrieval depth (RAG `k`)."""

from __future__ import annotations

from typing import Any

from core.config import settings
from psychology.schemas import MentalState

# Soft topic preferences for reranking (sanadi_topic from `chunking.sanadi_section_topic`).
_MENTAL_STATE_PREFERRED_TOPICS: dict[MentalState, frozenset[str]] = {
    MentalState.neutral: frozenset(),
    MentalState.anxious: frozenset({"intervention", "lifestyle_communication", "concept"}),
    MentalState.distressed: frozenset({"intervention", "assessment", "referral"}),
    MentalState.depressed: frozenset({"intervention", "lifestyle_communication", "referral"}),
    MentalState.crisis: frozenset({"referral", "assistant_routing", "intervention"}),
}


def coerce_mental_state_for_kb(value: Any) -> MentalState | None:
    """Normalize router/service inputs for KB reranking."""
    if value is None:
        return None
    if isinstance(value, MentalState):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        for member in MentalState:
            if member.value == raw or member.name.lower() == raw.lower():
                return member
    return None


def preferred_sanadi_topics_for_mental_state(state: MentalState | None) -> frozenset[str]:
    if state is None:
        return frozenset()
    return _MENTAL_STATE_PREFERRED_TOPICS.get(state, frozenset())


def resolve_kb_retrieval_limit(text: str, mental_state: MentalState) -> int:
    """
    Choose final `k` from query length and fused mental-state severity.

    Short clarifying messages pull fewer chunks; complex narratives and higher
    distress states request more (bounded by env-configured min/max).
    """
    raw = (text or "").strip()
    words = len(raw.split()) if raw else 0

    base = settings.psychology_kb_default_limit
    if mental_state in (MentalState.distressed, MentalState.depressed):
        base += 2
    elif mental_state == MentalState.anxious:
        base += 1

    if words <= 8:
        base -= 2
    elif words >= 55:
        base += 2
    elif words >= 28:
        base += 1

    lo = settings.psychology_kb_limit_min
    hi = settings.psychology_kb_limit_max
    return max(lo, min(hi, base))
