"""Tests for episodic retrieval scoring + semantic merge (Sanadi memory layers)."""

from __future__ import annotations

import math

import pytest

from psychology.memory_scoring import (
    MemoryScoreParams,
    cosine_hit_score,
    decay_multiplier,
    fuse_memory_scores,
    merge_semantic_profile,
    payload_age_days,
)


class DummyHit:
    def __init__(self, score: float):
        self.score = score
        self.payload = {}


def test_payload_age_days_from_created_at() -> None:
    now = 10_000_000.0
    age = payload_age_days({"created_at": now - 2 * 86400}, now_ts=now)
    assert abs(age - 2.0) < 1e-6


def test_decay_monotone() -> None:
    a = decay_multiplier(1.0, half_life_days=30.0, floor=0.25)
    b = decay_multiplier(60.0, half_life_days=30.0, floor=0.25)
    assert a > b


def test_clinical_boost() -> None:
    p = MemoryScoreParams()
    s0 = fuse_memory_scores(0.8, age_days=5.0, clinical_flag=False, params=p, recency_boost_enabled=False)
    s1 = fuse_memory_scores(0.8, age_days=5.0, clinical_flag=True, params=p, recency_boost_enabled=False)
    assert s1 > s0


def test_cosine_hit_score() -> None:
    assert cosine_hit_score(DummyHit(0.9)) == pytest.approx(0.9)
    assert 0.0 <= cosine_hit_score(DummyHit(-0.5)) <= 1.0


def test_merge_semantic_contradiction_cap() -> None:
    long_list = [{"claim_a": str(i), "claim_b": "b", "domain": "sleep"} for i in range(20)]
    merged = merge_semantic_profile({}, {"contradictions_pending": long_list}, contradictions_cap=12)
    assert len(merged["contradictions_pending"]) <= 12


def test_decay_half_life_midpoint() -> None:
    floor = 0.1
    h = decay_multiplier(30.0, half_life_days=30.0, floor=floor)
    assert math.isclose(h, max(floor, 0.5), rel_tol=0.02)
