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

class HealthResponse(BaseModel):
    status: str
    tesseract_version: Optional[str] = None
    azure_ready: bool = False
