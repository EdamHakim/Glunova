"""Ingest → storage → local OCR → Groq extraction (optional) → rules → merge."""

from __future__ import annotations

import logging
import os
import re

from django.conf import settings

from documents.models import MedicalDocument

from .extraction_rules import run_rule_validation
from .groq_extract import run_groq_structured_extract
from .local_ocr import extract_local_ocr_text
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


def normalize_ocr_text(raw: str) -> str:
    if not raw:
        return ""
    t = raw.replace("\r\n", "\n")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


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
    llm_extracted: dict | None = None
    field_evidence: dict | None = None
    llm_status = MedicalDocument.LlmRefinementStatus.SKIPPED
    llm_provider = None

    raw_ocr = normalize_ocr_text(
        extract_local_ocr_text(file_bytes, mime_type, getattr(settings, "OCR_LANGUAGE", "eng"))
    )

    api_key = (getattr(settings, "GROQ_API_KEY", "") or "").strip()
    if raw_ocr and api_key:
        try:
            payload = run_groq_structured_extract(raw_ocr)
            extracted = payload.get("extracted")
            llm_extracted = extracted if isinstance(extracted, dict) else None
            fe = payload.get("field_evidence")
            field_evidence = fe if isinstance(fe, dict) else None
            llm_status = MedicalDocument.LlmRefinementStatus.OK
            llm_provider = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
        except Exception as exc:
            logger.warning("Groq extraction failed (fallback to rules): %s", exc, exc_info=True)
            llm_status = MedicalDocument.LlmRefinementStatus.FAILED
    else:
        llm_status = MedicalDocument.LlmRefinementStatus.SKIPPED

    rules_snapshot = run_rule_validation(raw_ocr)
    merged = merge_and_validate(raw_ocr, rules_snapshot, llm_extracted, field_evidence)

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
