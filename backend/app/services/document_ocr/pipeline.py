"""End-to-end: validate file, store, OCR, rules, LLM merge."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import ValidationAppError
from app.models.enums import DocumentProcessingStatus, LLMRefinementStatus
from app.schemas.document_extraction import DocumentExtractionResult
from app.services.document_ocr.extraction_rules import extract_from_ocr_text, result_to_dict
from app.services.document_ocr.llm_refinement import _refine_sync_blocking
from app.services.document_ocr.ocr_engine import ALLOWED_MIME, run_ocr
from app.services.document_ocr.storage import save_upload
from app.services.document_ocr.text_normalize import normalize_ocr_text

logger = logging.getLogger(__name__)


def process_uploaded_file(
    patient_id: UUID,
    file_bytes: bytes,
    original_filename: str,
    mime_type: str,
) -> dict[str, Any]:
    if mime_type not in ALLOWED_MIME:
        raise ValidationAppError(f"Unsupported file type: {mime_type}")
    max_b = settings.UPLOAD_MAX_MB * 1024 * 1024
    if len(file_bytes) > max_b:
        raise ValidationAppError(f"File too large (max {settings.UPLOAD_MAX_MB} MB)")

    storage_path = save_upload(patient_id, file_bytes, original_filename)

    try:
        raw_ocr = run_ocr(file_bytes, mime_type)
    except Exception as e:
        logger.exception("OCR failed")
        raise ValidationAppError(f"OCR failed: {e!s}") from e

    normalized = normalize_ocr_text(raw_ocr)
    rules_result = extract_from_ocr_text(normalized)
    rules_dict = result_to_dict(rules_result)

    merged, llm_status, provider = _refine_sync_blocking(normalized, rules_result)
    final_dict = merged.model_dump(mode="json")

    return {
        "storage_path": storage_path,
        "raw_ocr_text": normalized,
        "extracted_json_rules": rules_dict,
        "extracted_json": final_dict,
        "document_type_detected": final_dict.get("document_type"),
        "llm_refinement_status": llm_status,
        "llm_provider_used": provider,
        "processing_status": DocumentProcessingStatus.COMPLETED,
        "error_message": None,
    }
