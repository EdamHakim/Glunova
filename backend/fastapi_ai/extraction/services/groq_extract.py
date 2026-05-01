"""Groq text-only structured extraction for OCR output."""

from __future__ import annotations

import json
import logging
import base64
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)

GROQ_EXTRACTION_PROMPT = """
You are a high-precision medical document extraction system. 

INPUT:
- Raw OCR text or a visual representation of a medical document.

TASKS:
1. Extract structured data into the EXACT JSON schema provided below.
2. Ground all extractions in the text. Do not invent values.
3. For 'field_evidence', map dot-path keys to the verbatim text segment.

MEDICAL INSTRUCTIONS:
- Document Type: 
    - 'prescription': If the document lists medications, dosages, and instructions (e.g., Rx).
    - 'lab_report': If the document lists medical test results with values and units (e.g., Glucose, Calcium).
- Abbreviations: "b.i.d" -> "twice daily", "q.d" -> "once daily", "t.i.d" -> "three times daily", "p.r.n" -> "as needed".
- Medications: Identify brand names and generic names. Capture the full dosage string (e.g., "500mg").
- Labs: Extract test names, numerical values, and units. Identify if a value is flagged as out of range.

EXAMPLES:

Example 1 (Prescription):
Input: "Rx: Metf0rmin 500mg - 1 tab b.i.d. for 30 days. Pat: John Doe. Date: 12/04/2024"
Output:
{
  "extracted": {
    "document_type": "prescription",
    "document_date": "2024-04-12",
    "patient_name": "John Doe",
    "medications": [{
      "name": "Metformin",
      "dosage": "500mg",
      "frequency": "twice daily",
      "duration": "30 days"
    }],
    "labs": []
  },
  "field_evidence": {
    "patient_name": "John Doe",
    "medications.0.name": "Metf0rmin"
  }
}

Example 2 (Lab Report):
Input: "HEMOGLOBIN A1C ..... 7.2 % (Ref: 4.0-5.6). Date 2024-01-10"
Output:
{
  "extracted": {
    "document_type": "lab_report",
    "document_date": "2024-01-10",
    "labs": [{
      "name": "Hemoglobin A1c",
      "value": "7.2",
      "unit": "%",
      "reference_range": "4.0-5.6",
      "is_out_of_range": true
    }],
    "medications": []
  },
  "field_evidence": {
    "labs.0.value": "7.2"
  }
}

SCHEMA:
{
  "extracted": {
    "document_type": "prescription" | "lab_report" | "unknown",
    "document_date": "YYYY-MM-DD" or null,
    "patient_name": string or null,
    "provider_name": string or null,
    "medications": [
      {
        "name": string,
        "dosage": string or null,
        "frequency": string or null,
        "duration": string or null,
        "route": string or null,
        "instructions": string or null
      }
    ],
    "labs": [
      {
        "name": string,
        "value": string,
        "unit": string or null,
        "reference_range": string or null,
        "is_out_of_range": boolean or null
      }
    ]
  },
  "field_evidence": { "key_path": "verbatim_ocr_text" }
}

INSTRUCTIONS:
- Return ONLY the JSON object.
- If OCR is messy, use medical judgment for typos (e.g., "Metf0rmin" -> "Metformin") ONLY if certain.
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


def run_groq_vision_extract(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    """
    Perform multi-modal extraction directly from the image.
    Useful when OCR quality is low or layout is complex.
    """
    api_key = (settings.groq_api_key or "").strip().strip("'\"")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured")

    # Base64 encode the image
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    
    # Construct the data URI
    data_uri = f"data:{mime_type};base64,{base64_image}"

    model_name = settings.groq_vision_model
    
    # We use the same prompt, but adjusted for visual context
    vision_prompt = GROQ_EXTRACTION_PROMPT + "\n\nNOTE: You are looking at the ACTUAL IMAGE of the document. Use visual cues (stamps, signatures, handwriting) to improve accuracy."

    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError("groq package is not installed") from exc

    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model_name,
            temperature=0,
            messages=[
                {"role": "system", "content": "You are a medical vision extraction tool. Respond with valid JSON only."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri},
                        },
                    ],
                },
            ],
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.error("Groq Vision API call failed: %s", exc)
        return {"extracted": {}, "field_evidence": {}}

    content = response.choices[0].message.content or "{}"
    payload = _parse_json_response(content)
    
    return {
        "extracted": payload.get("extracted", {}),
        "field_evidence": payload.get("field_evidence", {}),
        "method": "vision"
    }
