from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.medical_service import ClinicalSummary, get_clinical_summary

router = APIRouter()


@router.get("/patients/{patient_id}/clinical-summary", response_model=ClinicalSummary)
def clinical_summary(
    patient_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ClinicalSummary:
    return get_clinical_summary(db, patient_id, user)
