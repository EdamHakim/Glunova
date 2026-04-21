from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from typing import Any
import logging

from core.rbac import require_roles
from extraction.schemas import ExtractionResponse, HealthResponse
from extraction.services.preprocessing import optimize_image_for_ocr
from extraction.services.azure_ocr import extract_azure_ocr_payload
from extraction.services.groq_extract import run_groq_structured_extract, run_groq_vision_extract
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

    # 0. Preprocessing (Optimize image for OCR)
    mime_type = file.content_type or ""
    optimized_content = optimize_image_for_ocr(content, mime_type)

    # 1. OCR (Azure only)
    ocr_payload = await extract_azure_ocr_payload(optimized_content, mime_type)
    
    raw_ocr = ocr_payload["text"]
    ocr_meta = ocr_payload["meta"]
    
    # 2. LLM Extraction (with Vision fallback)
    llm_extracted = {}
    field_evidence = {}
    
    # Decide whether to use Vision (for images with low OCR quality)
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
        logger.error(f"LLM extraction failed: {exc}", exc_info=True)

    # 3. Rule Validation
    rules_snapshot = run_rule_validation(raw_ocr)
    rules_snapshot["_ocr_meta"] = ocr_meta

    if ocr_meta.get("low_quality"):
        logger.warning("Low OCR quality detected", extra={"ocr_meta": ocr_meta})

    # 4. Merge
    merged = merge_and_validate(raw_ocr, rules_snapshot, llm_extracted, field_evidence)

    # 5. Enrichment
    final = await verify_and_enrich_medications(merged, raw_ocr)

    # 6. Reliability & HITL Logic
    azure_conf = ocr_meta.get("average_confidence")
    if azure_conf is None:
        azure_conf = 0.0
    
    has_interactions = len(final.get("drug_interactions", [])) > 0
    
    # Check for unverified medications
    has_unverified_meds = False
    meds = final.get("medications", [])
    if isinstance(meds, list):
        for m in meds:
            v_status = m.get("verification", {}).get("status")
            if v_status in ["unverified", "ambiguous", "failed"]:
                has_unverified_meds = True
                break

    # Determine if review is required
    review_required = (
        azure_conf < 70.0 or 
        ocr_meta.get("low_quality") or 
        has_interactions or 
        has_unverified_meds or
        not raw_ocr
    )

    return ExtractionResponse(
        raw_ocr_text=raw_ocr,
        extracted_json=final,
        extracted_json_rules=rules_snapshot,
        field_evidence=field_evidence,
        status="low_ocr_quality" if ocr_meta.get("low_quality") else "ok",
        review_required=review_required,
        confidence_score=azure_conf if azure_conf > 0 else None
    )

@router.get("/health", response_model=HealthResponse)
def extraction_health() -> HealthResponse:
    from core.config import settings
    
    azure_configured = bool(settings.azure_document_intelligence_endpoint and 
                           settings.azure_document_intelligence_key and 
                           "your_azure_key_here" not in settings.azure_document_intelligence_key)
    
    return HealthResponse(
        status="ok",
        azure_ready=azure_configured
    )
