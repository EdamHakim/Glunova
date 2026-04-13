from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DiabetesType, Gender, MoodState, RiskLevel, TrendStatus


class PatientBase(BaseModel):
    date_of_birth: date | None = None
    gender: Gender | None = None
    weight_kg: Decimal | None = Field(default=None, ge=0)
    height_cm: Decimal | None = Field(default=None, ge=0)
    blood_type: str | None = Field(default=None, max_length=8)
    smoker: bool = False
    alcohol_use: bool = False
    resting_heart_rate: int | None = Field(default=None, ge=0, le=300)
    blood_pressure_systolic: int | None = Field(default=None, ge=0, le=300)
    blood_pressure_diastolic: int | None = Field(default=None, ge=0, le=200)
    oxygen_saturation: Decimal | None = Field(default=None, ge=0, le=100)
    body_temperature: Decimal | None = None
    diabetes_type: DiabetesType | None = None
    diagnosis_date: date | None = None
    hba1c: Decimal | None = None
    fasting_glucose: Decimal | None = None
    postprandial_glucose: Decimal | None = None
    risk_level: RiskLevel | None = None
    last_screening_result: str | None = None
    trend_status: TrendStatus | None = None
    allergies: list | dict | None = None
    chronic_conditions: list | dict | None = None
    medications: list | dict | None = None
    past_surgeries: list | dict | None = None
    stress_level: int | None = Field(default=None, ge=0, le=10)
    sleep_hours_avg: Decimal | None = Field(default=None, ge=0, le=24)
    mood_state: MoodState | None = None


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    date_of_birth: date | None = None
    gender: Gender | None = None
    weight_kg: Decimal | None = Field(default=None, ge=0)
    height_cm: Decimal | None = Field(default=None, ge=0)
    blood_type: str | None = Field(default=None, max_length=8)
    smoker: bool | None = None
    alcohol_use: bool | None = None
    resting_heart_rate: int | None = Field(default=None, ge=0, le=300)
    blood_pressure_systolic: int | None = Field(default=None, ge=0, le=300)
    blood_pressure_diastolic: int | None = Field(default=None, ge=0, le=200)
    oxygen_saturation: Decimal | None = Field(default=None, ge=0, le=100)
    body_temperature: Decimal | None = None
    diabetes_type: DiabetesType | None = None
    diagnosis_date: date | None = None
    hba1c: Decimal | None = None
    fasting_glucose: Decimal | None = None
    postprandial_glucose: Decimal | None = None
    risk_level: RiskLevel | None = None
    last_screening_result: str | None = None
    trend_status: TrendStatus | None = None
    allergies: list | dict | None = None
    chronic_conditions: list | dict | None = None
    medications: list | dict | None = None
    past_surgeries: list | dict | None = None
    stress_level: int | None = Field(default=None, ge=0, le=10)
    sleep_hours_avg: Decimal | None = Field(default=None, ge=0, le=24)
    mood_state: MoodState | None = None


class PatientRead(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bmi: Decimal | None
    created_at: datetime
    updated_at: datetime


class PatientPublicSummary(BaseModel):
    """Restricted view for caregivers (no full clinical JSON blobs by default)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    risk_level: RiskLevel | None
    trend_status: TrendStatus | None
    last_screening_result: str | None
