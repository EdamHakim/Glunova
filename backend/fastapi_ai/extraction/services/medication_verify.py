"""Medication verification via RxNorm first, then Groq-assisted rescue/tie-breaks."""

from __future__ import annotations

import difflib
import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib import error, parse, request

import rapidfuzz
from core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RxNormCandidate:
    rxcui: str
    score: int
    rank: int | None
    name: str | None = None
    match_score: int | None = None
    context_score: int | None = None


def _normalized_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def _canonicalize_name(value: str) -> str:
    cleaned = _normalized_name(value).lower()
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", cleaned)
    return " ".join(cleaned.split())


def _ocr_normalized_name(value: str) -> str:
    cleaned = _canonicalize_name(value)
    if not cleaned:
        return ""
    substitutions = (
        ("0", "o"),
        ("1", "l"),
        ("5", "s"),
        ("8", "b"),
        ("vv", "w"),
        ("rn", "m"),
        ("cl", "d"),
    )
    for source, target in substitutions:
        cleaned = cleaned.replace(source, target)
    return " ".join(cleaned.split())


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


async def _http_get_json_async(url: str, timeout: int) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


@lru_cache(maxsize=512)
async def _cached_rxnorm_approximate_candidates(
    base_url: str,
    timeout: int,
    normalized_name: str,
    max_entries: int,
) -> tuple[RxNormCandidate, ...]:
    query = parse.urlencode({"term": normalized_name, "maxEntries": str(max_entries)})
    payload = await _http_get_json_async(f"{base_url}/approximateTerm.json?{query}", timeout=timeout)
    return tuple(_extract_candidates(payload))


async def _cached_rxnorm_display_name(base_url: str, timeout: int, rxcui: str) -> str | None:
    try:
        properties = await _http_get_json_async(f"{base_url}/rxcui/{rxcui}/properties.json", timeout=timeout)
        properties_payload = properties.get("properties") or {}
        raw_name = properties_payload.get("name")
        return raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else None
    except Exception:
        logger.warning("Failed to fetch RxNorm properties for %s", rxcui, exc_info=True)
        return None


def _token_set(value: str) -> set[str]:
    return {token for token in _ocr_normalized_name(value).split() if token}


def _extract_strength_tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?)\b", value.lower())
    }


def _extract_form_tokens(value: str) -> set[str]:
    forms = {
        "tablet",
        "tablets",
        "tab",
        "tabs",
        "capsule",
        "capsules",
        "cap",
        "caps",
        "syrup",
        "solution",
        "suspension",
        "cream",
        "ointment",
        "gel",
        "spray",
        "drop",
        "drops",
        "patch",
        "injection",
        "injectable",
    }
    return {token for token in _token_set(value) if token in forms}


def _extract_route_tokens(value: str) -> set[str]:
    routes = {
        "oral",
        "topical",
        "intravenous",
        "iv",
        "intramuscular",
        "im",
        "subcutaneous",
        "sc",
        "ophthalmic",
        "otic",
        "nasal",
        "inhalation",
        "rectal",
    }
    return {token for token in _token_set(value) if token in routes}


def _extract_frequency_tokens(value: str) -> set[str]:
    frequency_patterns = (
        r"\bonce daily\b",
        r"\btwice daily\b",
        r"\bthree times daily\b",
        r"\bfour times daily\b",
        r"\bdaily\b",
        r"\bnightly\b",
        r"\bbid\b",
        r"\btid\b",
        r"\bqid\b",
        r"\bprn\b",
        r"\bevery \d+ hours\b",
    )
    lowered = value.lower()
    return {match.group(0) for pattern in frequency_patterns for match in re.finditer(pattern, lowered)}


def _select_medication_context_window(medication: dict[str, Any], raw_ocr_text: str) -> str:
    raw = raw_ocr_text or ""
    if not raw.strip():
        return ""

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return ""

    name = _normalized_name(medication.get("name"))
    dosage = _normalized_name(medication.get("dosage"))
    frequency = _normalized_name(medication.get("frequency"))
    duration = _normalized_name(medication.get("duration"))
    route = _normalized_name(medication.get("route"))

    def line_score(line: str) -> float:
        normalized_line = _ocr_normalized_name(line)
        score = 0.0
        if name:
            score += difflib.SequenceMatcher(None, _ocr_normalized_name(name), normalized_line).ratio() * 100
            if _ocr_normalized_name(name) in normalized_line:
                score += 40
        if dosage and dosage.lower() in line.lower():
            score += 25
        if route and route.lower() in line.lower():
            score += 15
        if frequency and frequency.lower() in line.lower():
            score += 15
        if duration and duration.lower() in line.lower():
            score += 10
        return score

    def is_supporting_neighbor(line: str) -> bool:
        lowered = line.lower()
        if dosage and dosage.lower() in lowered:
            return True
        if route and route.lower() in lowered:
            return True
        if frequency and frequency.lower() in lowered:
            return True
        if duration and duration.lower() in lowered:
            return True
        if _extract_strength_tokens(line):
            return True
        if _extract_form_tokens(line):
            return True
        if _extract_route_tokens(line):
            return True
        if _extract_frequency_tokens(line):
            return True
        if re.search(r"\bfor \d+ (day|days|week|weeks|month|months)\b", lowered):
            return True
        return False

    best_index = max(range(len(lines)), key=lambda index: line_score(lines[index]))
    best_score = line_score(lines[best_index])
    if best_score <= 0:
        return raw.strip()

    selected = [lines[best_index]]
    if best_index > 0 and is_supporting_neighbor(lines[best_index - 1]):
        selected.insert(0, lines[best_index - 1])
    if best_index + 1 < len(lines) and is_supporting_neighbor(lines[best_index + 1]):
        selected.append(lines[best_index + 1])
    return "\n".join(selected).strip()


def _medication_context_blob(medication: dict[str, Any], raw_ocr_text: str) -> str:
    context_window = _select_medication_context_window(medication, raw_ocr_text)
    parts = [
        _normalized_name(medication.get("name")),
        _normalized_name(medication.get("dosage")),
        _normalized_name(medication.get("frequency")),
        _normalized_name(medication.get("duration")),
        _normalized_name(medication.get("route")),
    ]
    parts = [part for part in parts if part]
    if context_window:
        parts.append(context_window)
    return " ".join(parts)


def _extract_candidates(payload: dict[str, Any]) -> list[RxNormCandidate]:
    group = payload.get("approximateGroup") or payload.get("approxGroup") or {}
    raw_candidates = group.get("candidate") or []
    if isinstance(raw_candidates, dict):
        raw_candidates = [raw_candidates]

    candidates: list[RxNormCandidate] = []
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            continue
        rxcui = str(raw.get("rxcui") or "").strip()
        if not rxcui:
            continue
        candidates.append(
            RxNormCandidate(
                rxcui=rxcui,
                score=_to_int(raw.get("score")),
                rank=_to_int(raw.get("rank")) or None,
            )
        )
    return candidates


async def fetch_rxnorm_candidates(name: str) -> list[RxNormCandidate]:
    normalized = _normalized_name(name)
    if not normalized:
        return []

    timeout = 10
    base_url = "https://rxnav.nlm.nih.gov/REST"
    max_entries = 5
    property_lookup_limit = 3
    candidates = list(await _cached_rxnorm_approximate_candidates(base_url, timeout, normalized, max_entries))

    resolved: list[RxNormCandidate] = []
    
    # We can parallelize the display name lookups too
    async def resolve_one(candidate, index):
        display_name = None
        if index < property_lookup_limit:
            display_name = await _cached_rxnorm_display_name(base_url, timeout, candidate.rxcui)
        return RxNormCandidate(
            rxcui=candidate.rxcui,
            score=candidate.score,
            rank=candidate.rank,
            name=display_name,
        )

    tasks = [resolve_one(candidate, i) for i, candidate in enumerate(candidates)]
    resolved = await asyncio.gather(*tasks)
    return list(resolved)


def _generate_query_variants(name: str) -> list[str]:
    variants: list[str] = []
    raw = _normalized_name(name)
    canonical = _canonicalize_name(name)
    ocr = _ocr_normalized_name(name)
    for variant in (raw, canonical, ocr):
        if variant and variant not in variants:
            variants.append(variant)

    stripped = re.sub(r"\b(tab|tabs|tablet|tablets|cap|caps|capsule|capsules|syrup|inj|injection)\b", "", ocr)
    stripped = " ".join(stripped.split())
    if stripped and stripped not in variants:
        variants.append(stripped)
    return variants


def _candidate_similarity(query: str, candidate_name: str | None) -> int:
    if not candidate_name:
        return 0
    left = _ocr_normalized_name(query)
    right = _ocr_normalized_name(candidate_name)
    if not left or not right:
        return 0

    ratio = rapidfuzz.fuzz.token_sort_ratio(left, right) / 100.0
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens), 1)
    prefix_bonus = 0.1 if right.startswith(left[: min(len(left), 5)]) else 0.0
    return int(round((ratio * 0.7 + overlap * 0.2 + prefix_bonus) * 100))


def _candidate_context_score(candidate_name: str | None, context_blob: str) -> int:
    if not candidate_name:
        return 0
    if not context_blob:
        return 0

    candidate_blob = candidate_name.lower()
    context_blob = context_blob.lower()
    score = 0

    strength_tokens = _extract_strength_tokens(context_blob)
    candidate_strength = _extract_strength_tokens(candidate_blob)
    if strength_tokens and candidate_strength:
        score += 35 * len(strength_tokens & candidate_strength)

    form_tokens = _extract_form_tokens(context_blob)
    candidate_forms = _extract_form_tokens(candidate_blob)
    if form_tokens and candidate_forms:
        score += 20 * len(form_tokens & candidate_forms)

    route_tokens = _extract_route_tokens(context_blob)
    candidate_routes = _extract_route_tokens(candidate_blob)
    if route_tokens and candidate_routes:
        score += 15 * len(route_tokens & candidate_routes)

    frequency_tokens = _extract_frequency_tokens(context_blob)
    if frequency_tokens:
        score += 8 * sum(1 for token in frequency_tokens if token in context_blob)

    return score


def _rerank_candidates(query: str, medication: dict[str, Any], raw_ocr_text: str, candidates: list[RxNormCandidate]) -> list[RxNormCandidate]:
    context_blob = _medication_context_blob(medication, raw_ocr_text)
    scored = [
        RxNormCandidate(
            rxcui=candidate.rxcui,
            score=candidate.score,
            rank=candidate.rank,
            name=candidate.name,
            match_score=_candidate_similarity(query, candidate.name),
            context_score=_candidate_context_score(candidate.name, context_blob),
        )
        for candidate in candidates
    ]
    scored.sort(
        key=lambda candidate: (
            candidate.context_score if candidate.context_score is not None else -1,
            candidate.match_score if candidate.match_score is not None else -1,
            candidate.score,
            -(candidate.rank or 9999),
        ),
        reverse=True,
    )
    return scored


def _merge_candidate_lists(
    query: str,
    medication: dict[str, Any],
    raw_ocr_text: str,
    candidate_lists: list[list[RxNormCandidate]],
) -> list[RxNormCandidate]:
    merged: dict[str, RxNormCandidate] = {}
    for candidates in candidate_lists:
        for candidate in _rerank_candidates(query, medication, raw_ocr_text, candidates):
            existing = merged.get(candidate.rxcui)
            if existing is None:
                merged[candidate.rxcui] = candidate
                continue
            existing_match = existing.match_score if existing.match_score is not None else -1
            current_match = candidate.match_score if candidate.match_score is not None else -1
            existing_context = existing.context_score if existing.context_score is not None else -1
            current_context = candidate.context_score if candidate.context_score is not None else -1
            if (current_context, current_match, candidate.score) > (existing_context, existing_match, existing.score):
                merged[candidate.rxcui] = candidate
    return sorted(
        merged.values(),
        key=lambda candidate: (
            candidate.context_score if candidate.context_score is not None else -1,
            candidate.match_score if candidate.match_score is not None else -1,
            candidate.score,
            -(candidate.rank or 9999),
        ),
        reverse=True,
    )


async def fetch_rxnorm_candidates_with_variants(
    name: str,
    *,
    medication: dict[str, Any] | None = None,
    raw_ocr_text: str = "",
) -> list[RxNormCandidate]:
    variants = _generate_query_variants(name)
    
    async def get_variant(variant):
        try:
            return await fetch_rxnorm_candidates(variant)
        except Exception:
            if variant == _normalized_name(name):
                raise
            logger.warning("Variant RxNorm lookup failed for %s", variant, exc_info=True)
            return []

    candidate_lists = await asyncio.gather(*(get_variant(v) for v in variants))
    return _merge_candidate_lists(name, medication or {"name": name}, raw_ocr_text, list(candidate_lists))


async def groq_tiebreak_medication(
    *,
    medication_name: str,
    raw_ocr_text: str,
    candidates: list[RxNormCandidate],
) -> dict[str, Any]:
    api_key = (settings.groq_api_key or "").strip().strip("'\"")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured")

    try:
        from groq import AsyncGroq
    except ImportError as exc:
        raise RuntimeError("groq package is not installed") from exc

    candidate_lines = [
        f'- rxcui: "{candidate.rxcui}", name: "{candidate.name or ""}", score: {candidate.score}'
        for candidate in candidates
    ]
    prompt = (
        "You are resolving an OCR-extracted prescription medication against RxNorm candidates.\n"
        "Pick the single best candidate only when the OCR context clearly supports it.\n"
        'Return JSON only with keys: {"rxcui": string|null, "reason": string}.\n'
        "If none is clearly correct, return null for rxcui.\n\n"
        f"OCR medication name: {medication_name}\n"
        f"OCR text:\n{raw_ocr_text[:4000]}\n\n"
        "Candidates:\n"
        + "\n".join(candidate_lines)
    )

    client = AsyncGroq(api_key=api_key)
    response = await client.chat.completions.create(
        model=settings.groq_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return only JSON."},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


async def groq_suggest_ocr_corrections(
    *,
    medication_name: str,
    raw_ocr_text: str,
) -> dict[str, Any]:
    api_key = (settings.groq_api_key or "").strip().strip("'\"")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured")

    try:
        from groq import AsyncGroq
    except ImportError as exc:
        raise RuntimeError("groq package is not installed") from exc

    prompt = (
        "You are reviewing an OCR-extracted medication name that may contain spelling mistakes.\n"
        "Suggest likely corrected medication names only when the OCR text supports them.\n"
        'Return JSON only with keys: {"suggestions": [{"name": string, "reason": string}]}.'
        " Return at most 3 suggestions. Use an empty list if unsure.\n\n"
        f"OCR medication name: {medication_name}\n"
        f"OCR text:\n{raw_ocr_text[:4000]}\n"
    )

    client = AsyncGroq(api_key=api_key)
    response = await client.chat.completions.create(
        model=settings.groq_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return only JSON."},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def _build_candidate_payload(candidates: list[RxNormCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "rxcui": candidate.rxcui,
            "name_display": candidate.name,
            "score": candidate.score,
            "rank": candidate.rank,
            "match_score": candidate.match_score,
            "context_score": candidate.context_score,
        }
        for candidate in candidates
    ]


def _best_clear_match(candidates: list[RxNormCandidate]) -> RxNormCandidate | None:
    if not candidates:
        return None
    min_score = 60
    ambiguity_gap = 5
    min_match_score = 72
    min_context_score = 0
    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    gap = top.score - second.score if second else None
    match_score = top.match_score if top.match_score is not None else _candidate_similarity(top.name or "", top.name)
    context_score = top.context_score if top.context_score is not None else 0
    second_match = second.match_score if second and second.match_score is not None else -1
    second_context = second.context_score if second and second.context_score is not None else -1
    if (
        top.score >= min_score
        and match_score >= min_match_score
        and context_score >= min_context_score
        and (
            gap is None
            or gap >= ambiguity_gap
            or match_score - second_match >= ambiguity_gap
            or context_score - second_context >= ambiguity_gap
        )
    ):
        return top
    return None


def _best_non_llm_match(candidates: list[RxNormCandidate]) -> tuple[RxNormCandidate | None, str | None]:
    strict_match = _best_clear_match(candidates)
    if strict_match is not None:
        return strict_match, "Matched via RxNorm"

    if not candidates:
        return None, None

    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    min_score = 60
    fast_min_match_score = 90
    fast_min_context_score = 25
    fast_min_combined_lead = 10

    top_match = top.match_score or 0
    top_context = top.context_score or 0
    top_combined = top_match + top_context
    second_combined = (second.match_score or 0) + (second.context_score or 0) if second else -1

    if (
        top.score >= min_score
        and top_match >= fast_min_match_score
        and top_context >= fast_min_context_score
        and (second is None or top_combined - second_combined >= fast_min_combined_lead)
    ):
        return top, "Matched via RxNorm fast-path"

    return None, None


async def _llm_rescue_medication_name(
    *,
    medication: dict[str, Any],
    medication_name: str,
    raw_ocr_text: str,
) -> dict[str, Any] | None:
    suggestions_payload = await groq_suggest_ocr_corrections(
        medication_name=medication_name,
        raw_ocr_text=raw_ocr_text,
    )
    raw_suggestions = suggestions_payload.get("suggestions")
    if not isinstance(raw_suggestions, list):
        return None

    attempted: list[dict[str, Any]] = []
    for suggestion in raw_suggestions[:3]:
        if not isinstance(suggestion, dict):
            continue
        suggested_name = _normalized_name(suggestion.get("name"))
        if not suggested_name or suggested_name.lower() == medication_name.lower():
            continue
        candidates = await fetch_rxnorm_candidates_with_variants(
            suggested_name,
            medication=medication,
            raw_ocr_text=raw_ocr_text,
        )
        attempted.append(
            {
                "name": suggested_name,
                "reason": suggestion.get("reason"),
                "candidates": _build_candidate_payload(candidates),
            }
        )
        chosen = _best_clear_match(candidates)
        if chosen:
            return {
                "status": "matched",
                "rxcui": chosen.rxcui,
                "name_display": chosen.name or suggested_name,
                "candidates": _build_candidate_payload(candidates),
                "note": suggestion.get("reason") or "Matched after LLM OCR correction",
                "corrected_name": suggested_name,
                "ocr_correction_attempts": attempted,
            }
    return {
        "attempts": attempted,
        "note": "LLM OCR correction did not produce a clear RxNorm match",
    }


async def verify_medication_entry(
    medication: dict[str, Any],
    *,
    raw_ocr_text: str,
    cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cache_key = _normalized_name(medication.get("name"))
    context_window = _select_medication_context_window(medication, raw_ocr_text)
    if not cache_key:
        verification = {
            "status": "failed",
            "rxcui": None,
            "name_display": None,
            "candidates": [],
            "note": "Medication name missing",
            "ocr_context_window": context_window or None,
        }
        enriched = dict(medication)
        enriched["verification"] = verification
        return enriched

    if cache is not None and cache_key in cache:
        enriched = dict(medication)
        enriched["verification"] = dict(cache[cache_key])
        return enriched

    verification: dict[str, Any]

    try:
        candidates = await fetch_rxnorm_candidates_with_variants(
            cache_key,
            medication=medication,
            raw_ocr_text=context_window or raw_ocr_text,
        )
    except Exception as exc:
        verification = {
            "status": "failed",
            "rxcui": None,
            "name_display": None,
            "candidates": [],
            "note": f"RxNorm processing failed: {exc}",
        }
    else:
        candidate_payload = _build_candidate_payload(candidates)
        if not candidates:
            verification = {
                "status": "unverified",
                "rxcui": None,
                "name_display": None,
                "candidates": [],
                "note": "No RxNorm match found",
            }
        else:
            top, top_note = _best_non_llm_match(candidates)
            if top:
                verification = {
                    "status": "matched",
                    "rxcui": top.rxcui,
                    "name_display": top.name or cache_key,
                    "candidates": candidate_payload,
                    "note": top_note or "Matched via RxNorm",
                }
            else:
                try:
                    tie_break = await groq_tiebreak_medication(
                        medication_name=cache_key,
                        raw_ocr_text=context_window or raw_ocr_text,
                        candidates=candidates[:3],
                    )
                except Exception as exc:
                    verification = {
                        "status": "ambiguous",
                        "rxcui": None,
                        "name_display": None,
                        "candidates": candidate_payload,
                        "note": f"Ambiguous RxNorm match and Groq tie-break failed: {exc}",
                    }
                else:
                    chosen_rxcui = str(tie_break.get("rxcui") or "").strip()
                    chosen = next((candidate for candidate in candidates if candidate.rxcui == chosen_rxcui), None)
                    reason = tie_break.get("reason")
                    if chosen:
                        verification = {
                            "status": "matched",
                            "rxcui": chosen.rxcui,
                            "name_display": chosen.name or cache_key,
                            "candidates": candidate_payload,
                            "note": reason or "Matched after Groq tie-break",
                        }
                    else:
                        verification = {
                            "status": "ambiguous",
                            "rxcui": None,
                            "name_display": None,
                            "candidates": candidate_payload,
                            "note": reason or "Ambiguous RxNorm candidates",
                        }

        if verification["status"] in {"ambiguous", "unverified"}:
            try:
                rescue = await _llm_rescue_medication_name(
                    medication=medication,
                    medication_name=cache_key,
                    raw_ocr_text=context_window or raw_ocr_text,
                )
            except Exception as exc:
                verification["note"] = f'{verification.get("note")}; LLM OCR rescue failed: {exc}'
            else:
                if rescue and rescue.get("status") == "matched":
                    rescue["note"] = rescue.get("note") or verification.get("note")
                    verification = rescue
                elif rescue:
                    verification["ocr_correction_attempts"] = rescue.get("attempts", [])
                    if rescue.get("note"):
                        verification["note"] = f'{verification.get("note")}; {rescue["note"]}'

    enriched = dict(medication)
    verification["ocr_context_window"] = context_window or None
    enriched["verification"] = verification
    if cache is not None:
        cache[cache_key] = dict(verification)
    return enriched


async def check_drug_drug_interactions(rxcuis: list[str]) -> list[dict[str, Any]]:
    """Check for interactions between a list of RxCUIs using the RxNorm Interaction API."""
    if len(rxcuis) < 2:
        return []

    base_url = "https://rxnav.nlm.nih.gov/REST"
    rxcuis_str = "+".join(rxcuis)
    try:
        url = f"{base_url}/interaction/list.json?rxcuis={rxcuis_str}"
        payload = await _http_get_json_async(url, timeout=10)
        
        interactions = []
        full_interaction_type_group = payload.get("fullInteractionTypeGroup") or []
        for group in full_interaction_type_group:
            full_interaction_types = group.get("fullInteractionType") or []
            for interaction_type in full_interaction_types:
                # Extract details
                comment = interaction_type.get("comment")
                interaction_pair = interaction_type.get("interactionPair", [{}])[0]
                description = interaction_pair.get("description")
                severity = interaction_pair.get("severity", "N/A")
                
                interactions.append({
                    "description": description,
                    "severity": severity,
                    "comment": comment
                })
        return interactions
    except Exception as exc:
        logger.warning(f"Failed to check interactions: {exc}")
        return []


async def verify_and_enrich_medications(merged: dict[str, Any], raw_ocr_text: str) -> dict[str, Any]:
    doc_type = merged.get("document_type") or merged.get("document_type_detected")
    medications = merged.get("medications")
    if doc_type != "prescription" or not isinstance(medications, list):
        return merged

    cache: dict[str, dict[str, Any]] = {}
    enriched = dict(merged)
    
    # 1. Individual Verification (Parallelized!)
    tasks = []
    for medication in medications:
        if isinstance(medication, dict):
            tasks.append(verify_medication_entry(medication, raw_ocr_text=raw_ocr_text, cache=cache))
        else:
            tasks.append(asyncio.sleep(0, result=medication)) # Handle non-dict edge case
    
    verified_meds = await asyncio.gather(*tasks)
    
    # 2. Extract verified RxCUIs for interaction check
    rxcuis = [
        med["verification"]["rxcui"] 
        for med in verified_meds 
        if isinstance(med, dict) and med.get("verification", {}).get("rxcui")
    ]
    
    # 3. Check Interactions
    interactions = []
    if len(rxcuis) >= 2:
        interactions = await check_drug_drug_interactions(rxcuis)
    
    enriched["medications"] = verified_meds
    enriched["drug_interactions"] = interactions
    
    return enriched
