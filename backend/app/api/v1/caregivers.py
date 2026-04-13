from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import caregiver_repo
from app.schemas.caregiver import CaregiverLinkCreate, CaregiverRead, CaregiverUpdate
from app.services import caregiver_service

router = APIRouter()


@router.get("/me", response_model=CaregiverRead)
def read_caregiver_me(
    user: Annotated[User, Depends(require_roles(UserRole.CAREGIVER))],
    db: Annotated[Session, Depends(get_db)],
) -> CaregiverRead:
    cg = caregiver_repo.get_by_id(db, user.id)
    if not cg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Caregiver profile not found")
    return CaregiverRead.model_validate(cg)


@router.patch("/me", response_model=CaregiverRead)
def update_caregiver_me(
    data: CaregiverUpdate,
    user: Annotated[User, Depends(require_roles(UserRole.CAREGIVER))],
    db: Annotated[Session, Depends(get_db)],
) -> CaregiverRead:
    cg = caregiver_service.update_profile(db, user.id, data)
    return CaregiverRead.model_validate(cg)


@router.post("/me/patient-links", status_code=status.HTTP_201_CREATED)
def link_patient(
    body: CaregiverLinkCreate,
    user: Annotated[User, Depends(require_roles(UserRole.CAREGIVER))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    caregiver_service.link_patient(
        db, user.id, body.patient_id, body.relationship_to_patient
    )
    return {"status": "linked"}


@router.delete("/me/patient-links/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_patient(
    patient_id: UUID,
    user: Annotated[User, Depends(require_roles(UserRole.CAREGIVER))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    caregiver_service.unlink_patient(db, user.id, patient_id)
