from pydantic import BaseModel, Field
from typing import Any, Optional

class ExtractionRequest(BaseModel):
    ocr_text: str

class ExtractionResponse(BaseModel):
    raw_ocr_text: str
    extracted_json: dict[str, Any]
    extracted_json_rules: dict[str, Any]
    field_evidence: dict[str, Any]
    status: str = "ok"
    review_required: bool = False
    confidence_score: Optional[float] = None

class HealthResponse(BaseModel):
    status: str
    azure_ready: bool = False
