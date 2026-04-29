from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from typing import Any
import logging

from core.rbac import require_roles
from extraction.schemas import ExtractionResponse, HealthResponse
from extraction.services.orchestrator import extract_document_payload

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

    mime_type = file.content_type or ""
    payload = await extract_document_payload(content, mime_type, ocr_backend="auto")

    return ExtractionResponse(
        raw_ocr_text=payload["raw_ocr_text"],
        extracted_json=payload["extracted_json"],
        extracted_json_rules=payload["extracted_json_rules"],
        field_evidence=payload["field_evidence"],
        status=payload["status"],
        review_required=payload["review_required"],
        confidence_score=payload["confidence_score"],
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
