"""Ingest → storage → Gemini (optional) → rules → merge → persist fields on MedicalDocument."""

from __future__ import annotations

import logging
import os
import re

from django.conf import settings

from documents.models import MedicalDocument

from .extraction_rules import run_rule_validation
from .gemini_ocr import GeminiQuotaExceeded, normalize_ocr_text, run_gemini_ocr
from .merge_validate import merge_and_validate
from .storage import upload_medical_file

logger = logging.getLogger(__name__)

_ALLOWED_MIMES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
    }
)


def safe_filename(name: str) -> str:
    base = os.path.basename(name).replace("\\", "/")
    base = re.sub(r"[^a-zA-Z0-9._-]+", "_", base).strip("._") or "upload.bin"
    return base[:255]


def process_document_upload(doc: MedicalDocument, file_bytes: bytes, mime_type: str) -> None:
    if mime_type not in _ALLOWED_MIMES:
        raise ValueError(f"Unsupported MIME type: {mime_type}")

    max_mb = int(getattr(settings, "UPLOAD_MAX_MB", 10))
    if len(file_bytes) > max_mb * 1024 * 1024:
        raise ValueError(f"File exceeds maximum size of {max_mb} MB")

    upload_medical_file(doc.storage_path, file_bytes, mime_type)

    raw_ocr = ""
    gemini_extracted: dict | None = None
    field_evidence: dict | None = None
    llm_status = MedicalDocument.LlmRefinementStatus.SKIPPED
    llm_provider = None

    api_key = (getattr(settings, "GEMINI_API_KEY", "") or "").strip()
    if api_key:
        try:
            payload = run_gemini_ocr(file_bytes, mime_type)
            raw_ocr = normalize_ocr_text(str(payload.get("raw_text", "")))
            gem = payload.get("extracted")
            gemini_extracted = gem if isinstance(gem, dict) else None
            fe = payload.get("field_evidence")
            field_evidence = fe if isinstance(fe, dict) else None
            llm_status = MedicalDocument.LlmRefinementStatus.OK
            llm_provider = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
        except GeminiQuotaExceeded as exc:
            logger.info("Gemini OCR quota limited (fallback to rules): %s", exc)
            llm_status = MedicalDocument.LlmRefinementStatus.SKIPPED
        except Exception as exc:
            logger.warning("Gemini OCR failed (fallback to rules): %s", exc, exc_info=True)
            llm_status = MedicalDocument.LlmRefinementStatus.FAILED
    else:
        llm_status = MedicalDocument.LlmRefinementStatus.SKIPPED

    rules_snapshot = run_rule_validation(raw_ocr)
    merged = merge_and_validate(raw_ocr, rules_snapshot, gemini_extracted, field_evidence)

    doc_type = merged.get("document_type") or rules_snapshot.get("document_type")

    doc.raw_ocr_text = raw_ocr
    doc.extracted_json = merged
    doc.extracted_json_rules = rules_snapshot
    doc.llm_refinement_status = llm_status
    doc.llm_provider_used = llm_provider
    doc.document_type_detected = doc_type if isinstance(doc_type, str) else None
    doc.processing_status = MedicalDocument.ProcessingStatus.COMPLETED
    doc.error_message = ""
    doc.save(
        update_fields=[
            "raw_ocr_text",
            "extracted_json",
            "extracted_json_rules",
            "llm_refinement_status",
            "llm_provider_used",
            "document_type_detected",
            "processing_status",
            "error_message",
            "updated_at",
        ]
    )
