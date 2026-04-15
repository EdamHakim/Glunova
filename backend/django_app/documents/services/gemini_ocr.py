"""Gemini Flash vision: OCR + structured extraction (optional when API key set)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

OCR_EXTRACTION_PROMPT = """
You are a medical document OCR and extraction system.

1. Read the attached image or PDF and return the complete raw OCR text verbatim in raw_text.
2. Extract structured fields into extracted matching exactly this JSON shape:
   {
     "patient": { "name": null or string, "dob": "YYYY-MM-DD" or null, "id": null or string },
     "document_type": one of "prescription"|"lab_report"|"medical_report"|"unknown",
     "date": "YYYY-MM-DD" or null,
     "vitals": { "blood_pressure": null or string, "heart_rate": null or string },
     "labs": [{ "name": string, "value": string, "unit": null or string }],
     "medications": [{ "name": string, "dosage": null or string, "frequency": null or string, "duration": null or string, "route": null or string }],
     "notes": null or string
   }
3. field_evidence must map dot-path keys (e.g. "patient.name", "date", "notes") to an exact verbatim substring from raw_text that supports that field. If unsure, omit the key.
4. Return ONLY valid JSON with keys raw_text, extracted, field_evidence. No markdown fences, no preamble.
"""


def _strip_json_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def parse_gemini_json_response(text: str) -> dict[str, Any]:
    cleaned = _strip_json_fences(text)
    return json.loads(cleaned)


def run_gemini_ocr(file_bytes: bytes, mime_type: str) -> dict[str, Any]:
    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    api_key = api_key.strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")

    import google.generativeai as genai
    import os
    os.environ["GOOGLE_API_KEY"] = api_key

    genai.configure(api_key=api_key, transport="rest")
    model_name = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        [
            {"mime_type": mime_type, "data": file_bytes},
            OCR_EXTRACTION_PROMPT,
        ],
    )
    text = getattr(response, "text", None) or ""
    if not text.strip():
        raise RuntimeError("Empty Gemini response")
    max_chars = getattr(settings, "LLM_MAX_CHARS", 50000)
    if len(text) > max_chars:
        text = text[:max_chars]
    return parse_gemini_json_response(text)


def normalize_ocr_text(raw: str) -> str:
    if not raw:
        return ""
    t = raw.replace("\r\n", "\n")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()
