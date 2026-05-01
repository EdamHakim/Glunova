"""Ingest → storage → Delegate extraction to FastAPI AI service."""

from __future__ import annotations

import logging
import os
import re
import httpx
from datetime import datetime, time, timedelta, timezone

from django.conf import settings
from django.db import transaction
from django.utils import timezone as django_timezone
from django.utils.dateparse import parse_date
from jose import jwt

from documents.models import MedicalDocument
from monitoring.models import PatientLabResult, PatientMedication

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
    medications = extracted_json.get("medications")
    if extracted_json.get("document_type") != "prescription" or not isinstance(medications, list):
        return

    # 1. Fetch existing medications for THIS PATIENT
    # We map them by (rxcui, normalized_name, dosage) for quick lookup
    existing_meds = PatientMedication.objects.filter(patient=doc.patient)
    med_map: dict[tuple[str, str, str], PatientMedication] = {}
    for em in existing_meds:
        key = (
            str(em.rxcui or "").strip().lower(),
            str(em.name_raw or "").strip().lower(),
            str(em.dosage or "").strip().lower()
        )
        med_map[key] = em

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
        if dedupe_key in seen_in_current_batch:
            continue
        seen_in_current_batch.add(dedupe_key)

        # Update existing or create new
        med_obj = med_map.get(dedupe_key)
        if med_obj:
            # Update fields only if they are present in the new extraction
            med_obj.source_document = doc
            if medication.get("frequency"): med_obj.frequency = medication["frequency"]
            if medication.get("duration"): med_obj.duration = medication["duration"]
            if medication.get("route"): med_obj.route = medication["route"]
            if medication.get("instructions"): med_obj.instructions = medication["instructions"]
            med_obj.verification_status = verification.get("status", med_obj.verification_status)
            med_obj.verification_detail = verification or med_obj.verification_detail
            med_obj.save()
        else:
            PatientMedication.objects.create(
                patient=doc.patient,
                source_document=doc,
                name_raw=raw_name.strip(),
                name_display=verification.get("name_display"),
                rxcui=verification.get("rxcui"),
                dosage=medication.get("dosage"),
                frequency=medication.get("frequency"),
                duration=medication.get("duration"),
                route=medication.get("route"),
                instructions=medication.get("instructions"),
                verification_status=verification.get("status", "unverified"),
                verification_detail=verification or {},
            )


def _normalize_lab_name(value: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", lowered)


def _coerce_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = value.strip().replace(",", ".")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _resolve_observed_at(doc: MedicalDocument, extracted_json: dict) -> datetime:
    raw_date = extracted_json.get("date") or extracted_json.get("document_date")
    if isinstance(raw_date, str):
        parsed = parse_date(raw_date.strip())
        if parsed is not None:
            return django_timezone.make_aware(datetime.combine(parsed, time.min), django_timezone.get_current_timezone())
    return doc.created_at


def _persist_patient_lab_results(doc: MedicalDocument, extracted_json: dict) -> None:
    labs = extracted_json.get("labs")
    if extracted_json.get("document_type") != "lab_report" or not isinstance(labs, list):
        return

    observed_at = _resolve_observed_at(doc, extracted_json)
    
    # 2. Fetch existing labs for this patient to update vs create
    existing_labs = PatientLabResult.objects.filter(patient=doc.patient)
    lab_map: dict[tuple[str, str, str], PatientLabResult] = {}
    for el in existing_labs:
        # Key by name, date (as date string), and unit
        obs_date = el.observed_at.date().isoformat() if el.observed_at else "no-date"
        key = (el.normalized_name, obs_date, (el.unit or "").lower())
        lab_map[key] = el

    seen_in_current_batch: set[tuple[str, str, str]] = set()

    for lab in labs:
        if not isinstance(lab, dict):
            continue
        test_name = lab.get("name")
        value = lab.get("value")
        if not isinstance(test_name, str) or not isinstance(value, str):
            continue
        test_name = test_name.strip()
        value = value.strip()
        if not test_name or not value:
            continue

        unit = lab.get("unit") if isinstance(lab.get("unit"), str) and lab.get("unit").strip() else None
        normalized_name = _normalize_lab_name(test_name)
        obs_date_str = observed_at.date().isoformat()
        dedupe_key = (normalized_name, obs_date_str, (unit or "").lower())
        
        if dedupe_key in seen_in_current_batch:
            continue
        seen_in_current_batch.add(dedupe_key)

        lab_obj = lab_map.get(dedupe_key)
        if lab_obj:
            # Update existing
            lab_obj.source_document = doc
            lab_obj.value = value
            lab_obj.numeric_value = _coerce_float(value)
            if lab.get("reference_range"):
                lab_obj.reference_range = lab["reference_range"]
            lab_obj.is_out_of_range = lab.get("is_out_of_range")
            lab_obj.raw_payload = lab
            lab_obj.save()
        else:
            PatientLabResult.objects.create(
                patient=doc.patient,
                source_document=doc,
                test_name=test_name,
                normalized_name=normalized_name,
                value=value,
                numeric_value=_coerce_float(value),
                unit=unit.strip() if unit else None,
                reference_range=lab.get("reference_range"),
                is_out_of_range=lab.get("is_out_of_range"),
                observed_at=observed_at,
                raw_payload=lab,
            )


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
        _persist_patient_lab_results(doc, merged)
