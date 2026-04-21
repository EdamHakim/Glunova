"""Ingest → storage → Delegate extraction to FastAPI AI service."""

from __future__ import annotations

import logging
import os
import re
import httpx
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db import transaction
from jose import jwt

from documents.models import MedicalDocument
from monitoring.models import PatientMedication

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


def _persist_patient_medications(doc: MedicalDocument, extracted_json: dict) -> None:
    # 1. Clear medications previously associated WITH THIS DOCUMENT
    # (This ensures re-processing the same doc doesn't duplicate)
    PatientMedication.objects.filter(source_document=doc).delete()

    medications = extracted_json.get("medications")
    if extracted_json.get("document_type") != "prescription" or not isinstance(medications, list):
        return

    # 2. Fetch existing medications for THIS PATIENT (from other documents)
    # to avoid cross-document duplicates.
    existing_meds = PatientMedication.objects.filter(patient=doc.patient)
    existing_keys: set[tuple[str, str, str]] = set()
    for em in existing_meds:
        # We deduplicate based on (rxcui, normalized_name, dosage)
        key = (
            str(em.rxcui or "").strip().lower(),
            str(em.name_raw or "").strip().lower(),
            str(em.dosage or "").strip().lower()
        )
        existing_keys.add(key)

    rows: list[PatientMedication] = []
    # seen_in_current_batch to handle duplicates within the SAME document
    seen_in_current_batch: set[tuple[str, str, str]] = set()

    for medication in medications:
        if not isinstance(medication, dict):
            continue
        raw_name = medication.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue
        
        verification = medication.get("verification") if isinstance(medication.get("verification"), dict) else {}
        rxcui = str(verification.get("rxcui") or "").strip().lower()
        dosage = str(medication.get("dosage") or "").strip().lower()
        name_key = raw_name.strip().lower()

        dedupe_key = (rxcui, name_key, dosage)

        if dedupe_key in existing_keys or dedupe_key in seen_in_current_batch:
            # Skip if patient already has this medication from another document
            # or if we've already processed it in this batch.
            continue
        
        seen_in_current_batch.add(dedupe_key)
        rows.append(
            PatientMedication(
                patient=doc.patient,
                source_document=doc,
                name_raw=raw_name.strip(),
                name_display=verification.get("name_display") if isinstance(verification.get("name_display"), str) else None,
                rxcui=verification.get("rxcui") if isinstance(verification.get("rxcui"), str) else None,
                dosage=medication.get("dosage") if isinstance(medication.get("dosage"), str) else None,
                frequency=medication.get("frequency") if isinstance(medication.get("frequency"), str) else None,
                duration=medication.get("duration") if isinstance(medication.get("duration"), str) else None,
                route=medication.get("route") if isinstance(medication.get("route"), str) else None,
                verification_status=verification.get("status")
                if verification.get("status") in dict(PatientMedication.VerificationStatus.choices)
                else PatientMedication.VerificationStatus.UNVERIFIED,
                verification_detail=verification if verification else {},
            )
        )
    if rows:
        PatientMedication.objects.bulk_create(rows)


def _get_service_token(user_id: int) -> str:
    """Generate a short-lived JWT for service-to-service communication."""
    secret = getattr(settings, "JWT_SHARED_SECRET", settings.SECRET_KEY)
    payload = {
        "user_id": user_id,
        "role": "patient", # Elevation for processing
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def process_document_upload(doc: MedicalDocument, file_bytes: bytes, mime_type: str) -> None:
    if mime_type not in _ALLOWED_MIMES:
        raise ValueError(f"Unsupported MIME type: {mime_type}")

    max_mb = int(getattr(settings, "UPLOAD_MAX_MB", 10))
    if len(file_bytes) > max_mb * 1024 * 1024:
        raise ValueError(f"File exceeds maximum size of {max_mb} MB")

    upload_medical_file(doc.storage_path, file_bytes, mime_type)

    # Delegate to FastAPI AI Engine
    ai_service_url = os.getenv("AI_SERVICE_URL", "http://localhost:8001").rstrip("/")
    extraction_url = f"{ai_service_url}/extraction/extract"
    token = _get_service_token(doc.patient.id)

    llm_status = MedicalDocument.LlmRefinementStatus.SKIPPED
    llm_provider = None
    merged = {}
    rules_snapshot = {}
    field_evidence = {}
    raw_ocr = ""

    try:
        with httpx.Client(timeout=120.0) as client:
            files = {"file": (safe_filename(doc.original_filename), file_bytes, mime_type)}
            response = client.post(
                extraction_url,
                files=files,
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            data = response.json()
            
            merged = data.get("extracted_json", {})
            rules_snapshot = data.get("extracted_json_rules", {})
            field_evidence = data.get("field_evidence", {})
            raw_ocr = data.get("raw_ocr_text", "")
            
            llm_status = MedicalDocument.LlmRefinementStatus.OK
            llm_provider = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
            
    except Exception as exc:
        logger.error("FastAPI extraction failed: %s", exc, exc_info=True)
        llm_status = MedicalDocument.LlmRefinementStatus.FAILED
        doc.error_message = f"AI extraction failed: {str(exc)}"
        doc.processing_status = MedicalDocument.ProcessingStatus.FAILED
        doc.save(update_fields=["processing_status", "error_message", "updated_at"])
        return

    doc_type = merged.get("document_type") or rules_snapshot.get("document_type")

    with transaction.atomic():
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
        _persist_patient_medications(doc, merged)
