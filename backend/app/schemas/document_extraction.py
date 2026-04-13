"""Structured extraction schema for medical documents (Care Circle OCR)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MedicationItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    duration: str | None = None
    route: str | None = None


class DocumentExtractionResult(BaseModel):
    """Final merged output; all optional fields use null when unknown."""

    model_config = ConfigDict(extra="ignore")

    patient_name: str | None = None
    age: int | None = None
    gender: str | None = Field(default=None, description='one of "male", "female", "unknown"')

    glucose: float | None = None
    glucose_unit: str | None = None
    hba1c: float | None = None
    hba1c_unit: str | None = None
    blood_pressure_systolic: int | None = None
    blood_pressure_diastolic: int | None = None
    cholesterol: float | None = None
    cholesterol_unit: str | None = None
    insulin: float | None = None
    insulin_unit: str | None = None

    medications: list[MedicationItem] = Field(default_factory=list)
    diagnosis: str | None = None
    instructions: str | None = None

    document_type: str | None = Field(
        default=None,
        description='lab_report | prescription | medical_report | unknown',
    )
    lab_name: str | None = None
    doctor_name: str | None = None
    date: str | None = Field(default=None, description="ISO YYYY-MM-DD")

    def model_dump_json_safe(self) -> dict[str, Any]:
        d = self.model_dump(mode="json")
        d["medications"] = [m for m in d["medications"] if any(m.values())] or []
        return d
