"""Heuristics for psychology KB retrieval depth (RAG `k`)."""

from __future__ import annotations

from core.config import settings
from psychology.schemas import MentalState


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
