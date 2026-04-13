from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssignPatientIn(BaseModel):
    patient_id: UUID


class DoctorBase(BaseModel):
    specialization: str | None = Field(default=None, max_length=255)
    years_of_experience: int | None = Field(default=None, ge=0, le=80)
    license_number: str | None = Field(default=None, max_length=128)
    availability_schedule: dict | list | None = None


class DoctorUpdate(DoctorBase):
    pass


class DoctorRead(DoctorBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
