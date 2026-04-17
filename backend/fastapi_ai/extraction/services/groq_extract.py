"""Groq text-only structured extraction for OCR output."""

from __future__ import annotations

import json
import logging
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)

GROQ_EXTRACTION_PROMPT = """
You are a high-precision medical document extraction system.

INPUT:
- Raw OCR text from a medical image (prescription, lab report, or clinical note).

TASKS:
1. Extract structured data into the EXACT JSON schema provided below.
2. Ground all extractions in the text. Do not invent values.
3. For 'field_evidence', map dot-path keys (e.g., "patient_name", "medications.0.dosage") to the verbatim text segment supporting that value.

SCHEMA:
{
  "extracted": {
    "document_type": "prescription" | "lab_report" | "medical_report" | "unknown",
    "document_date": "YYYY-MM-DD" or null,
    "patient_name": string or null,
    "provider_name": string or null,
    "vitals": {
       "blood_pressure": string or null (e.g. "120/80"),
       "heart_rate": string or null,
       "spo2": string or null,
       "weight": {"value": string, "unit": string} or null,
       "temperature": {"value": string, "unit": string} or null
    },
    "medications": [
      {
        "name": string,
        "dosage": string or null,
        "frequency": string or null,
        "duration": string or null,
        "route": string or null
      }
    ],
    "labs": [
      {
        "name": string,
        "value": string,
        "unit": string or null
      }
    ]
  },
  "field_evidence": {
    "key_path": "verbatim_ocr_text"
  }
}

INSTRUCTIONS:
- Return ONLY the JSON object. 
- If the OCR is messy, use your best medical judgment to resolve typos but ONLY if high confidence.
- OCR text often contains stray characters or headers; ignore them.
""".strip()


def _parse_json_response(text: str) -> dict[str, Any]:
    """Extract and parse JSON from the model response."""
    cleaned = text.strip()
    
    # Remove markdown code blocks if present
    if "```" in cleaned:
        # Try to find the first block
        try:
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            else:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
        except IndexError:
            # Fallback: remove all triple backticks
            cleaned = cleaned.replace("```", "").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
                
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM JSON response: %s\nContent: %s", exc, cleaned)
        return {"extracted": {}, "field_evidence": {}}


def run_groq_structured_extract(raw_ocr_text: str) -> dict[str, Any]:
    api_key = (settings.groq_api_key or "").strip().strip("'\"")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured")

    # Simple truncation to avoid context window issues (approx 10k chars)
    # Medical docs are rarely longer than this unless they are multiple pages.
    # If they are multiple pages, we prefer keeping the top (headers/patient info) 
    # and the bottom (signatures/notes).
    max_chars = 12000
    if len(raw_ocr_text) > max_chars:
        logger.warning("OCR text truncated from %d to %d chars", len(raw_ocr_text), max_chars)
        raw_ocr_text = raw_ocr_text[:8000] + "\n[... truncated ...]\n" + raw_ocr_text[-4000:]

    model_name = settings.groq_model
    prompt = f"{GROQ_EXTRACTION_PROMPT}\n\nOCR text:\n{raw_ocr_text}"

    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError("groq package is not installed") from exc

    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model_name,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a medical extraction tool. Respond with valid JSON only."},
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:
        logger.error("Groq API call failed: %s", exc)
        return {"extracted": {}, "field_evidence": {}}

    content = response.choices[0].message.content or "{}"
    payload = _parse_json_response(content)
    
    return {
        "extracted": payload.get("extracted", {}),
        "field_evidence": payload.get("field_evidence", {}),
    }
