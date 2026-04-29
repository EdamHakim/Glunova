from __future__ import annotations

import logging
from typing import Any

from extraction.services.extraction_rules import run_rule_validation
from extraction.services.groq_extract import run_groq_structured_extract, run_groq_vision_extract
from extraction.services.local_ocr import extract_local_ocr_payload
from extraction.services.medication_verify import verify_and_enrich_medications
from extraction.services.merge_validate import merge_and_validate
from extraction.services.preprocessing import optimize_image_for_ocr

logger = logging.getLogger(__name__)


async def extract_document_payload(
    file_bytes: bytes,
    mime_type: str,
    *,
    ocr_backend: str = "auto",
) -> dict[str, Any]:
    optimized_content = optimize_image_for_ocr(file_bytes, mime_type)

    if ocr_backend not in {"auto", "azure", "local"}:
        raise ValueError("ocr_backend must be one of: auto, azure, local")

    if ocr_backend == "local":
        ocr_payload = extract_local_ocr_payload(optimized_content, mime_type)
    else:
        try:
            from extraction.services.azure_ocr import extract_azure_ocr_payload
        except Exception:
            logger.warning("Azure OCR client unavailable; falling back to local OCR")
            extract_azure_ocr_payload = None

        if extract_azure_ocr_payload is None:
            ocr_payload = extract_local_ocr_payload(optimized_content, mime_type)
            ocr_payload["meta"]["fallback_from"] = "azure_import_error"
        else:
            ocr_payload = await extract_azure_ocr_payload(optimized_content, mime_type)
        if ocr_backend == "auto" and not ocr_payload.get("text"):
            logger.info("Azure OCR returned no text; falling back to local OCR")
            local_payload = extract_local_ocr_payload(optimized_content, mime_type)
            local_payload["meta"]["fallback_from"] = "azure"
            ocr_payload = local_payload

    raw_ocr = ocr_payload["text"]
    ocr_meta = ocr_payload["meta"]

    llm_extracted: dict[str, Any] = {}
    field_evidence: dict[str, Any] = {}

    is_image = "image" in mime_type.lower()
    use_vision = is_image and (ocr_meta.get("low_quality") or not raw_ocr)

    try:
        if use_vision:
            logger.info("Triggering Vision-based extraction due to low OCR quality or no text")
            payload = run_groq_vision_extract(optimized_content, mime_type)
        else:
            payload = run_groq_structured_extract(raw_ocr)

        llm_extracted = payload.get("extracted", {})
        field_evidence = payload.get("field_evidence", {})
    except Exception as exc:
        logger.error("LLM extraction failed: %s", exc, exc_info=True)

    rules_snapshot = run_rule_validation(raw_ocr)
    rules_snapshot["_ocr_meta"] = ocr_meta

    if ocr_meta.get("low_quality"):
        logger.warning("Low OCR quality detected", extra={"ocr_meta": ocr_meta})

    merged = merge_and_validate(raw_ocr, rules_snapshot, llm_extracted, field_evidence)
    final = await verify_and_enrich_medications(merged, raw_ocr)

    ocr_conf = ocr_meta.get("average_confidence")
    if ocr_conf is None:
        ocr_conf = 0.0

    has_interactions = len(final.get("drug_interactions", [])) > 0
    has_unverified_meds = False
    meds = final.get("medications", [])
    if isinstance(meds, list):
        for medication in meds:
            status = medication.get("verification", {}).get("status")
            if status in {"unverified", "ambiguous", "failed"}:
                has_unverified_meds = True
                break

    review_required = (
        ocr_conf < 70.0
        or ocr_meta.get("low_quality")
        or has_interactions
        or has_unverified_meds
        or not raw_ocr
    )

    return {
        "raw_ocr_text": raw_ocr,
        "extracted_json": final,
        "extracted_json_rules": rules_snapshot,
        "field_evidence": field_evidence,
        "status": "low_ocr_quality" if ocr_meta.get("low_quality") else "ok",
        "review_required": review_required,
        "confidence_score": ocr_conf if ocr_conf > 0 else None,
    }
