from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import patient_repo
from app.schemas.patient import PatientPublicSummary, PatientRead, PatientUpdate
from app.services import access, patient_service
from app.utils.pagination import PaginatedResponse, PaginationParams, offset_limit

router = APIRouter()


@router.get("/me", response_model=PatientRead)
def read_my_patient_profile(
    user: Annotated[User, Depends(require_roles(UserRole.PATIENT))],
    db: Annotated[Session, Depends(get_db)],
) -> PatientRead:
    p = patient_service.get_patient_or_404(db, user.id)
    return PatientRead.model_validate(p)


@router.patch("/me", response_model=PatientRead)
def update_my_patient_profile(
    data: PatientUpdate,
    user: Annotated[User, Depends(require_roles(UserRole.PATIENT))],
    db: Annotated[Session, Depends(get_db)],
) -> PatientRead:
    p = patient_service.update_patient(db, user.id, data)
    return PatientRead.model_validate(p)


@router.get("", response_model=PaginatedResponse[PatientRead])
def list_patients(
    pagination: Annotated[PaginationParams, Depends()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PaginatedResponse[PatientRead]:
    off, lim = offset_limit(pagination.page, pagination.page_size)
    if user.role == UserRole.DOCTOR:
        rows, total = patient_repo.list_for_doctor(db, user.id, off, lim)
    elif user.role == UserRole.CAREGIVER:
        rows, total = patient_repo.list_for_caregiver(db, user.id, off, lim)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors and caregivers can list linked patients",
        )
    items = [PatientRead.model_validate(r) for r in rows]
    return PaginatedResponse.from_sequence(
        items, total=total, page=pagination.page, page_size=pagination.page_size
    )


@router.get("/{patient_id}", response_model=PatientRead | PatientPublicSummary)
def read_patient(
    patient_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PatientRead | PatientPublicSummary:
    if not access.can_access_patient(user, patient_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this patient")
    p = patient_service.get_patient_or_404(db, patient_id)
    if user.role == UserRole.CAREGIVER:
        return PatientPublicSummary.model_validate(p)
    return PatientRead.model_validate(p)


@router.patch("/{patient_id}", response_model=PatientRead)
def update_patient_by_clinician(
    patient_id: UUID,
    data: PatientUpdate,
    user: Annotated[User, Depends(require_roles(UserRole.DOCTOR))],
    db: Annotated[Session, Depends(get_db)],
) -> PatientRead:
    if not access.can_access_patient(user, patient_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this patient")
    p = patient_service.update_patient(db, patient_id, data)
    return PatientRead.model_validate(p)
