from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AlertSeverity, RiskLevel


class ScreeningResultCreate(BaseModel):
    type: str = Field(max_length=64)
    result_score: float | None = None
    risk_prediction: RiskLevel | None = None
    raw_data_reference: str | None = Field(default=None, max_length=512)
    extra: dict | list | None = None


class ScreeningResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    type: str
    result_score: float | None
    risk_prediction: RiskLevel | None
    raw_data_reference: str | None
    extra: dict | list | None
    created_at: datetime


class HealthAlertCreate(BaseModel):
    alert_type: str = Field(max_length=64)
    severity: AlertSeverity
    message: str


class HealthAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    alert_type: str
    severity: AlertSeverity
    message: str
    is_resolved: bool
    created_at: datetime


class HealthAlertPatch(BaseModel):
    is_resolved: bool


class CarePlanCreate(BaseModel):
    patient_id: UUID
    doctor_id: UUID
    plan_details: dict | list


class CarePlanUpdate(BaseModel):
    plan_details: dict | list


class CarePlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    doctor_id: UUID
    plan_details: dict | list
    updated_at: datetime
