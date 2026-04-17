"""Medication verification via RxNorm first, Groq for ambiguous tie-breaks."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RxNormCandidate:
    rxcui: str
    score: int
    rank: int | None
    name: str | None = None


def _normalized_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _http_get_json(url: str, timeout: int) -> dict[str, Any]:
    with request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


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


def fetch_rxnorm_candidates(name: str) -> list[RxNormCandidate]:
    normalized = _normalized_name(name)
    if not normalized:
        return []

    timeout = int(getattr(settings, "MEDICATION_VERIFY_TIMEOUT_SECONDS", 5))
    base_url = getattr(settings, "RXNORM_BASE_URL", "https://rxnav.nlm.nih.gov/REST").rstrip("/")
    max_entries = int(getattr(settings, "MEDICATION_VERIFY_MAX_CANDIDATES", 5))
    query = parse.urlencode({"term": normalized, "maxEntries": str(max_entries)})
    payload = _http_get_json(f"{base_url}/approximateTerm.json?{query}", timeout=timeout)
    candidates = _extract_candidates(payload)

    resolved: list[RxNormCandidate] = []
    for candidate in candidates:
        display_name = None
        try:
            properties = _http_get_json(f"{base_url}/rxcui/{candidate.rxcui}/properties.json", timeout=timeout)
            properties_payload = properties.get("properties") or {}
            raw_name = properties_payload.get("name")
            display_name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else None
        except Exception:
            logger.warning("Failed to fetch RxNorm properties for %s", candidate.rxcui, exc_info=True)
        resolved.append(
            RxNormCandidate(
                rxcui=candidate.rxcui,
                score=candidate.score,
                rank=candidate.rank,
                name=display_name,
            )
        )
    return resolved


def groq_tiebreak_medication(
    *,
    medication_name: str,
    raw_ocr_text: str,
    candidates: list[RxNormCandidate],
) -> dict[str, Any]:
    api_key = getattr(settings, "GROQ_API_KEY", "").strip().strip("'\"")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured")

    try:
        from groq import Groq
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

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"),
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
        }
        for candidate in candidates
    ]


def verify_medication_entry(
    medication: dict[str, Any],
    *,
    raw_ocr_text: str,
    cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cache_key = _normalized_name(medication.get("name"))
    if not cache_key:
        verification = {
            "status": "failed",
            "rxcui": None,
            "name_display": None,
            "candidates": [],
            "note": "Medication name missing",
        }
        enriched = dict(medication)
        enriched["verification"] = verification
        return enriched

    if cache is not None and cache_key in cache:
        enriched = dict(medication)
        enriched["verification"] = dict(cache[cache_key])
        return enriched

    min_score = int(getattr(settings, "MEDICATION_VERIFY_MIN_SCORE", 60))
    ambiguity_gap = int(getattr(settings, "MEDICATION_VERIFY_AMBIGUITY_GAP", 5))
    verification: dict[str, Any]

    try:
        candidates = fetch_rxnorm_candidates(cache_key)
    except error.URLError as exc:
        verification = {
            "status": "failed",
            "rxcui": None,
            "name_display": None,
            "candidates": [],
            "note": f"RxNorm request failed: {exc.reason}",
        }
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
            top = candidates[0]
            second = candidates[1] if len(candidates) > 1 else None
            gap = top.score - second.score if second else None
            is_clear_match = top.score >= min_score and (gap is None or gap >= ambiguity_gap)
            if is_clear_match:
                verification = {
                    "status": "matched",
                    "rxcui": top.rxcui,
                    "name_display": top.name or cache_key,
                    "candidates": candidate_payload,
                    "note": "Matched via RxNorm",
                }
            else:
                try:
                    tie_break = groq_tiebreak_medication(
                        medication_name=cache_key,
                        raw_ocr_text=raw_ocr_text,
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

    enriched = dict(medication)
    enriched["verification"] = verification
    if cache is not None:
        cache[cache_key] = dict(verification)
    return enriched


def verify_and_enrich_medications(merged: dict[str, Any], raw_ocr_text: str) -> dict[str, Any]:
    doc_type = merged.get("document_type") or merged.get("document_type_detected")
    medications = merged.get("medications")
    if doc_type != "prescription" or not isinstance(medications, list):
        return merged

    cache: dict[str, dict[str, Any]] = {}
    enriched = dict(merged)
    enriched["medications"] = [
        verify_medication_entry(medication, raw_ocr_text=raw_ocr_text, cache=cache)
        if isinstance(medication, dict)
        else medication
        for medication in medications
    ]
    return enriched
