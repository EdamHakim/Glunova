"""Groq text-only structured extraction for OCR output."""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings

GROQ_EXTRACTION_PROMPT = """
You are a medical document extraction system.

Input:
- raw OCR text from a medical image or PDF

Tasks:
1. Extract structured fields into exactly this JSON shape:
   {
     "patient": { "name": null or string, "dob": "YYYY-MM-DD" or null, "id": null or string },
     "document_type": one of "prescription"|"lab_report"|"medical_report"|"unknown",
     "date": "YYYY-MM-DD" or null,
     "vitals": { "blood_pressure": null or string, "heart_rate": null or string },
     "labs": [{ "name": string, "value": string, "unit": null or string }],
     "medications": [{ "name": string, "dosage": null or string, "frequency": null or string, "duration": null or string, "route": null or string }],
     "notes": null or string
   }
2. field_evidence must map dot-path keys (for example "patient.name", "date", "notes") to an exact verbatim substring from the OCR text supporting the field. If unsure, omit the key.
3. Return ONLY valid JSON with keys: extracted, field_evidence.
4. Never invent values that are not grounded in the OCR text.
""".strip()


def _parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


def run_groq_structured_extract(raw_ocr_text: str) -> dict[str, Any]:
    api_key = getattr(settings, "GROQ_API_KEY", "").strip().strip("'\"")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured")

    model_name = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
    prompt = f"{GROQ_EXTRACTION_PROMPT}\n\nOCR text:\n{raw_ocr_text}"

    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError("groq package is not installed") from exc

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model_name,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return only JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content or "{}"
    payload = _parse_json_response(content)
    extracted = payload.get("extracted")
    field_evidence = payload.get("field_evidence")
    return {
        "extracted": extracted if isinstance(extracted, dict) else {},
        "field_evidence": field_evidence if isinstance(field_evidence, dict) else {},
    }
