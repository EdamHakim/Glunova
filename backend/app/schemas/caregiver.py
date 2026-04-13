from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaregiverUpdate(BaseModel):
    default_relationship_label: str | None = Field(default=None, max_length=120)


class CaregiverRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    default_relationship_label: str | None
    created_at: datetime
    updated_at: datetime


class CaregiverLinkCreate(BaseModel):
    patient_id: UUID
    relationship_to_patient: str = Field(default="caregiver", max_length=120)
