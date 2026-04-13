"""LLM refinement via Groq (OpenAI-compatible) or Ollama."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import settings
from app.models.enums import LLMRefinementStatus
from app.schemas.document_extraction import DocumentExtractionResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a medical document information extractor. You receive OCR text (may have errors) and a draft JSON from rules.
Return ONLY a single JSON object with the same keys as the draft. You may fill null fields ONLY if the value appears explicitly in the OCR text (or obvious OCR typo of the same token). Do not invent patient data or lab values not present in OCR.
If unsure, keep null. For document_type use one of: lab_report, prescription, medical_report, unknown.
medications must be an array of objects with keys name, dosage, frequency, duration, route (strings or null)."""


def _truncate_ocr(text: str) -> str:
    max_c = settings.LLM_MAX_OCR_CHARS
    if len(text) <= max_c:
        return text
    return text[:max_c] + "\n...[truncated]"


def _strip_json_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _value_grounded_in_ocr(value: Any, ocr_lower: str) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return True
    if isinstance(value, int | float):
        s = str(value)
        if s in ocr_lower or s.replace(".0", "") in ocr_lower:
            return True
        if isinstance(value, float):
            alt = f"{value:.1f}".rstrip("0").rstrip(".")
            return alt in ocr_lower
        return False
    if isinstance(value, str):
        v = value.strip().lower()
        if len(v) < 2:
            return False
        return v in ocr_lower
    return False


def _merge_llm_into_rules(
    rules: DocumentExtractionResult,
    llm_raw: dict[str, Any],
    ocr_text: str,
) -> DocumentExtractionResult:
    ocr_lower = ocr_text.lower()
    base = rules.model_dump()
    for key, lv in llm_raw.items():
        if key == "medications" and isinstance(lv, list):
            merged_meds: list[dict[str, Any]] = []
            for item in lv:
                if not isinstance(item, dict):
                    continue
                med = {k: item.get(k) for k in ("name", "dosage", "frequency", "duration", "route")}
                name = med.get("name")
                if name and _value_grounded_in_ocr(str(name), ocr_lower):
                    merged_meds.append(med)
            if merged_meds:
                existing = base.get("medications") or []
                if not existing:
                    base["medications"] = merged_meds
        elif key in base and base.get(key) in (None, "", []):
            if lv in (None, "", []):
                continue
            if key in (
                "glucose",
                "hba1c",
                "cholesterol",
                "insulin",
                "blood_pressure_systolic",
                "blood_pressure_diastolic",
                "age",
            ):
                if _value_grounded_in_ocr(lv, ocr_lower):
                    base[key] = lv
            elif key in ("patient_name", "doctor_name", "lab_name", "diagnosis", "instructions", "date"):
                if isinstance(lv, str) and _value_grounded_in_ocr(lv, ocr_lower):
                    base[key] = lv
            elif key == "gender" and lv in ("male", "female", "unknown"):
                if lv == "unknown" or _value_grounded_in_ocr(lv, ocr_lower):
                    base[key] = lv
            elif key == "document_type" and isinstance(lv, str):
                if lv in ("lab_report", "prescription", "medical_report", "unknown"):
                    base[key] = lv
            elif key.endswith("_unit") and isinstance(lv, str):
                if _value_grounded_in_ocr(lv, ocr_lower) or lv in ("%", "mg/dL", "mmol/L", "units"):
                    base[key] = lv
    return DocumentExtractionResult.model_validate(base)


def _refine_sync_blocking(
    ocr_text: str,
    rules_result: DocumentExtractionResult,
) -> tuple[DocumentExtractionResult, LLMRefinementStatus, str | None]:
    provider = settings.LLM_PROVIDER
    ocr_use = _truncate_ocr(ocr_text)
    user_content = json.dumps(
        {"ocr_text": ocr_use, "draft_json": rules_result.model_dump(mode="json")},
        ensure_ascii=False,
    )
    if provider == "groq" and settings.GROQ_API_KEY:
        url = f"{settings.GROQ_BASE_URL.rstrip('/')}/chat/completions"
        body = {
            "model": settings.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        try:
            with httpx.Client(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                r = client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                r.raise_for_status()
                data = r.json()
            content = data["choices"][0]["message"]["content"]
            raw = json.loads(_strip_json_fence(content))
            return _merge_llm_into_rules(rules_result, raw, ocr_text), LLMRefinementStatus.OK, "groq"
        except Exception as e:
            logger.exception("Groq refinement failed: %s", e)
            return rules_result, LLMRefinementStatus.FAILED, None
    if provider == "ollama":
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        body = {
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        try:
            with httpx.Client(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                r = client.post(url, json=body)
                r.raise_for_status()
                data = r.json()
            content = data.get("message", {}).get("content", "")
            raw = json.loads(_strip_json_fence(content))
            return _merge_llm_into_rules(rules_result, raw, ocr_text), LLMRefinementStatus.OK, "ollama"
        except Exception as e:
            logger.exception("Ollama refinement failed: %s", e)
            return rules_result, LLMRefinementStatus.FAILED, None
    if provider == "groq" and not settings.GROQ_API_KEY:
        return rules_result, LLMRefinementStatus.SKIPPED, None
    return rules_result, LLMRefinementStatus.SKIPPED, None
