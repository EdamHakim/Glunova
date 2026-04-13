from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocumentProcessingStatus, LLMRefinementStatus


class MedicalDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    uploaded_by_user_id: UUID | None
    original_filename: str
    mime_type: str
    storage_path: str
    raw_ocr_text: str | None = None
    extracted_json: dict[str, Any] | None = None
    extracted_json_rules: dict[str, Any] | None = None
    llm_provider_used: str | None = None
    llm_refinement_status: LLMRefinementStatus | None = None
    document_type_detected: str | None = None
    processing_status: DocumentProcessingStatus
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

