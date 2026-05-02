"""Mental-state → Sanadi topic soft-routing helpers used in Qdrant reranking."""

from __future__ import annotations

from psychology.kb_retrieval import coerce_mental_state_for_kb, preferred_sanadi_topics_for_mental_state
from psychology.schemas import MentalState


def test_coerce_mental_state_accepts_enum_value_and_names() -> None:
    assert coerce_mental_state_for_kb(MentalState.anxious) == MentalState.anxious
    assert coerce_mental_state_for_kb("Anxious") == MentalState.anxious
    assert coerce_mental_state_for_kb("anxious") == MentalState.anxious


def test_preferred_topics_respect_buckets() -> None:
    anxious = preferred_sanadi_topics_for_mental_state(MentalState.anxious)
    assert "intervention" in anxious and "concept" in anxious
    neutral = preferred_sanadi_topics_for_mental_state(MentalState.neutral)
    assert neutral == frozenset()
    crisis = preferred_sanadi_topics_for_mental_state(MentalState.crisis)
    assert "referral" in crisis and "assistant_routing" in crisis
