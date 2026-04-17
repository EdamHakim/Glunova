from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from typing import Any
import logging

from core.rbac import require_roles
from extraction.schemas import ExtractionResponse, HealthResponse
from extraction.services.local_ocr import extract_local_ocr_payload
from extraction.services.groq_extract import run_groq_structured_extract
from extraction.services.extraction_rules import run_rule_validation
from extraction.services.merge_validate import merge_and_validate
from extraction.services.medication_verify import verify_and_enrich_medications

router = APIRouter(prefix="/extraction", tags=["extraction"])
logger = logging.getLogger(__name__)

@router.post(
    "/extract",
    response_model=ExtractionResponse,
    summary="Extract structured data from medical document",
)
async def extract_medical_data(
    file: UploadFile = File(...),
    claims: dict = Depends(require_roles("patient", "doctor")),
) -> ExtractionResponse:
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    # 1. OCR
    ocr_payload = extract_local_ocr_payload(content, file.content_type or "")
    raw_ocr = ocr_payload["text"]
    ocr_meta = ocr_payload["meta"]
    if not raw_ocr:
        logger.warning("No OCR text extracted", extra={"ocr_meta": ocr_meta})
        return ExtractionResponse(
            raw_ocr_text="",
            extracted_json={},
            extracted_json_rules={"_ocr_meta": ocr_meta},
            field_evidence={},
            status="low_ocr_quality" if ocr_meta.get("low_quality") else "no_text_found",
        )

    # 2. LLM Extraction (Optional fallback)
    llm_extracted = {}
    field_evidence = {}
    try:
        payload = run_groq_structured_extract(raw_ocr)
        llm_extracted = payload.get("extracted", {})
        field_evidence = payload.get("field_evidence", {})
    except Exception as exc:
        # Log error in real implementation
        pass

    # 3. Rule Validation
    rules_snapshot = run_rule_validation(raw_ocr)
    rules_snapshot["_ocr_meta"] = ocr_meta

    if ocr_meta.get("low_quality"):
        logger.warning("Low OCR quality detected", extra={"ocr_meta": ocr_meta})

    # 4. Merge
    merged = merge_and_validate(raw_ocr, rules_snapshot, llm_extracted, field_evidence)

    # 5. Enrichment
    final = verify_and_enrich_medications(merged, raw_ocr)

    return ExtractionResponse(
        raw_ocr_text=raw_ocr,
        extracted_json=final,
        extracted_json_rules=rules_snapshot,
        field_evidence=field_evidence,
        status="low_ocr_quality" if ocr_meta.get("low_quality") else "ok"
    )

@router.get("/health", response_model=HealthResponse)
def extraction_health() -> HealthResponse:
    import pytesseract
    try:
        version = pytesseract.get_tesseract_version()
    except Exception:
        version = "unknown"
    return HealthResponse(status="ok", tesseract_version=str(version))
