"""Pure helpers for episodic memory retrieval scoring (semantic + temporal decay + clinical boost)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class MemoryScoreParams:
    decay_half_life_days: float = 30.0
    decay_floor: float = 0.25
    clinical_boost: float = 1.45
    recency_weight: float = 0.15
    recency_scale_days: float = 14.0


def cosine_hit_score(hit: object) -> float:
    """Normalize Qdrant hit score to [0, 1]; cosine collections usually return similarity in [0,1]."""
    score = getattr(hit, "score", None)
    if score is None:
        return 0.0
    try:
        s = float(score)
    except (TypeError, ValueError):
        return 0.0
    if 0.0 <= s <= 1.0:
        return s
    if -1.0 <= s <= 1.0:
        return max(0.0, (s + 1.0) / 2.0)
    return max(0.0, min(1.0, s))


def payload_age_days(payload: dict, *, now_ts: float | None = None) -> float:
    """Approximate age in days from payload created_at unix or ISO session_ended_at."""
    now = now_ts if now_ts is not None else datetime.now(tz=timezone.utc).timestamp()
    raw_created = payload.get("created_at")
    if isinstance(raw_created, (int, float)):
        return max(0.0, (now - float(raw_created)) / 86400.0)
    iso = payload.get("session_ended_at")
    if isinstance(iso, str) and iso.strip():
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0.0, (now - dt.timestamp()) / 86400.0)
        except ValueError:
            pass
    return 0.0


def decay_multiplier(age_days: float, *, half_life_days: float, floor: float) -> float:
    if half_life_days <= 0:
        return floor
    import math

    mult = math.pow(0.5, age_days / half_life_days)
    return max(floor, float(mult))


def recency_bonus(age_days: float, *, scale_days: float, weight: float) -> float:
    if scale_days <= 0 or weight <= 0:
        return 0.0
    import math

    # Recent memories (small age_days) add up to ~weight.
    factor = math.exp(-age_days / scale_days)
    return weight * factor


def fuse_memory_scores(
    similarity: float,
    age_days: float,
    *,
    clinical_flag: bool,
    params: MemoryScoreParams,
    recency_boost_enabled: bool,
) -> float:
    decay = decay_multiplier(
        age_days, half_life_days=params.decay_half_life_days, floor=params.decay_floor
    )
    adj = similarity * decay
    if clinical_flag:
        adj *= params.clinical_boost
    if recency_boost_enabled:
        adj += recency_bonus(age_days, scale_days=params.recency_scale_days, weight=params.recency_weight)
    return adj


def merge_semantic_profile(existing: dict, patch: dict, *, contradictions_cap: int = 12) -> dict:
    """
    Merge LLM-produced patch into semantic_profile_json-shaped dict.
    Lists: capped union. Scalars under known keys: patch wins when present.
    """
    import copy

    base = copy.deepcopy(existing) if isinstance(existing, dict) else {}
    if not isinstance(patch, dict):
        return base

    list_fields = (
        "primary_stressors",
        "known_triggers",
        "coping_strengths",
        "current_medications_summary",
        "therapy_focus",
    )
    for key in list_fields:
        if key not in patch:
            continue
        cur = base.get(key)
        incoming = patch.get(key)
        if not isinstance(incoming, list):
            continue
        cur_list = cur if isinstance(cur, list) else []
        merged: list = []
        seen: set[str] = set()
        for item in list(cur_list) + list(incoming):
            s = str(item).strip()
            if s and s.lower() not in seen:
                seen.add(s.lower())
                merged.append(s[:280])
            if len(merged) >= 24:
                break
        base[key] = merged

    scalar_fields = (
        "diabetes_context_summary",
        "hba1c_trend",
        "therapy_progress_note",
        "communication_style",
        "therapy_language_note",
        "distress_trend_note",
        "clinical_summary_note",
        "updated_from_session_id",
    )
    for key in scalar_fields:
        if key in patch and patch[key] not in (None, ""):
            val = patch[key]
            base[key] = val if isinstance(val, str) else str(val)

    if "contradictions_pending" in patch and isinstance(patch["contradictions_pending"], list):
        cur_c = base.get("contradictions_pending")
        cur_list = cur_c if isinstance(cur_c, list) else []
        merged_c = list(cur_list) + patch["contradictions_pending"]
        trimmed = merged_c[-contradictions_cap:]
        base["contradictions_pending"] = trimmed

    if isinstance(patch.get("last_crisis_at"), str) and patch["last_crisis_at"].strip():
        base["last_crisis_at"] = patch["last_crisis_at"].strip()

    agg = patch.get("aggregates")
    if isinstance(agg, dict):
        base_agg = base.get("aggregates")
        ba = base_agg if isinstance(base_agg, dict) else {}
        for ak, av in agg.items():
            if av not in (None, ""):
                ba[str(ak)] = av
        base["aggregates"] = ba

    return base
