from pydantic import BaseModel, Field
from typing import Any, Optional, List, Dict
from datetime import date

# --- Medical Data Templates ---

class LabResult(BaseModel):
    name: str = Field(..., description="Name of the test (e.g., HbA1c, Glucose)")
    value: str = Field(..., description="The numerical or qualitative result")
    unit: Optional[str] = Field(None, description="Measurement unit (e.g., mg/dL, %)")
    reference_range: Optional[str] = Field(None, description="Normal range provided by the lab")
    is_out_of_range: Optional[bool] = Field(None, description="Flagged as abnormal by the lab")

class MedicationVerification(BaseModel):
    status: str = Field("unverified", description="matched, ambiguous, unverified, or failed")
    rxcui: Optional[str] = None
    name_display: Optional[str] = None
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    note: Optional[str] = None
    confidence: float = 0.0

class Medication(BaseModel):
    name: str = Field(..., description="Drug name (Brand or Generic)")
    dosage: Optional[str] = Field(None, description="Strength and form (e.g., 500mg tablet)")
    frequency: Optional[str] = Field(None, description="How often to take (e.g., twice daily)")
    duration: Optional[str] = Field(None, description="How long to take (e.g., 7 days)")
    route: Optional[str] = Field(None, description="Oral, IV, Topical, etc.")
    instructions: Optional[str] = Field(None, description="Specific instructions (e.g., before food)")
    verification: Optional[MedicationVerification] = None

class ExtractionResult(BaseModel):
    document_type: str = Field("unknown", description="prescription, lab_report, or unknown")
    document_date: Optional[date] = Field(None, description="Date of the document")
    patient_name: Optional[str] = None
    provider_name: Optional[str] = None
    labs: List[LabResult] = Field(default_factory=list)
    medications: List[Medication] = Field(default_factory=list)


class ExtractionRequest(BaseModel):
    ocr_text: str

class ExtractionResponse(BaseModel):
    raw_ocr_text: str
    extracted_json: ExtractionResult
    extracted_json_rules: Dict[str, Any]
    field_evidence: Dict[str, Any]
    status: str = "ok"
    review_required: bool = False
    confidence_score: Optional[float] = None

class HealthResponse(BaseModel):
    status: str
    azure_ready: bool = False

