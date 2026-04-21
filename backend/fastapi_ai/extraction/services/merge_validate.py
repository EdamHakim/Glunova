"""Conservative merge: rules win for clinical numerics; LLM text only if grounded in OCR."""

from __future__ import annotations

import copy
import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class LabRow(BaseModel):
    name: str
    value: str
    unit: str | None = None


class MedRow(BaseModel):
    name: str
    dosage: str | None = None
    frequency: str | None = None
    duration: str | None = None
    route: str | None = None


class ExtractedPayload(BaseModel):
    document_type: str = "unknown"
    medications: list[MedRow] = Field(default_factory=list)


def _norm(s: str) -> str:
    return " ".join(s.split())


def _evidence_ok(evidence: str | None, raw: str) -> bool:
    if not evidence or not raw:
        return False
    ev = evidence.strip()
    if len(ev) < 2:
        return False
    return ev in raw or ev.lower() in raw.lower()


def merge_and_validate(
    raw_ocr_text: str,
    rules: dict[str, Any],
    llm_extracted: dict[str, Any] | None,
    field_evidence: dict[str, str] | None,
) -> dict[str, Any]:
    final = copy.deepcopy(rules)
    raw = raw_ocr_text or ""
    if not llm_extracted:
        try:
            return ExtractedPayload.model_validate(final).model_dump(mode="json")
        except ValidationError:
            return final

    fe = field_evidence or {}

    # Document type / date: prefer LLM only if evidence or matches rule unknown
    dt = llm_extracted.get("document_type")
    if isinstance(dt, str) and dt in (
        "prescription",
        "lab_report",
        "medical_report",
        "unknown",
    ):
        if final.get("document_type") == "unknown" or _evidence_ok(fe.get("document_type"), raw):
            final["document_type"] = dt

    # Medications: Deduplicate based on fuzzy name + dosage
    g_meds = llm_extracted.get("medications")
    if isinstance(g_meds, list):
        import rapidfuzz
        
        final_meds = final.get("medications", [])
        
        for row in g_meds:
            if not isinstance(row, dict):
                continue
            name = row.get("name")
            if not isinstance(name, str) or len(name) < 2:
                continue
            
            # Grounding check: name must be in OCR
            if name.lower() not in raw.lower():
                continue
            
            dosage = _norm(str(row.get("dosage") or ""))
            
            # Check for existing similar medication
            is_duplicate = False
            for existing in final_meds:
                existing_name = existing.get("name", "")
                existing_dosage = _norm(str(existing.get("dosage") or ""))
                
                # If name is very similar AND dosage matches
                name_sim = rapidfuzz.fuzz.token_sort_ratio(name.lower(), existing_name.lower())
                if name_sim > 85 and (not dosage or not existing_dosage or dosage.lower() == existing_dosage.lower()):
                    is_duplicate = True
                    # Update existing with LLM info if missing (e.g. frequency normalization)
                    for key in ["frequency", "duration", "route", "dosage"]:
                        if not existing.get(key) and row.get(key):
                            existing[key] = row.get(key)
                    break
            
            if not is_duplicate:
                final_meds.append({
                    "name": name,
                    "dosage": row.get("dosage"),
                    "frequency": row.get("frequency"),
                    "duration": row.get("duration"),
                    "route": row.get("route"),
                })
        
        final["medications"] = final_meds

    try:
        return ExtractedPayload.model_validate(final).model_dump(mode="json")
    except ValidationError:
        return final
