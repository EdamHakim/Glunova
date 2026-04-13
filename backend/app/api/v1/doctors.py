from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import doctor_repo, patient_repo
from app.schemas.doctor import AssignPatientIn, DoctorRead, DoctorUpdate
from app.schemas.patient import PatientRead
from app.services import doctor_service
from app.utils.pagination import PaginatedResponse, PaginationParams, offset_limit

router = APIRouter()


@router.get("/me", response_model=DoctorRead)
def read_doctor_me(
    user: Annotated[User, Depends(require_roles(UserRole.DOCTOR))],
    db: Annotated[Session, Depends(get_db)],
) -> DoctorRead:
    doc = doctor_repo.get_by_id(db, user.id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found")
    return DoctorRead.model_validate(doc)


@router.patch("/me", response_model=DoctorRead)
def update_doctor_me(
    data: DoctorUpdate,
    user: Annotated[User, Depends(require_roles(UserRole.DOCTOR))],
    db: Annotated[Session, Depends(get_db)],
) -> DoctorRead:
    doc = doctor_service.update_profile(db, user.id, data)
    return DoctorRead.model_validate(doc)


@router.post("/me/patients", status_code=status.HTTP_201_CREATED)
def assign_patient(
    body: AssignPatientIn,
    user: Annotated[User, Depends(require_roles(UserRole.DOCTOR))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    doctor_service.assign_patient_to_doctor(db, user.id, body.patient_id)
    return {"status": "assigned"}


@router.delete("/me/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_patient(
    patient_id: UUID,
    user: Annotated[User, Depends(require_roles(UserRole.DOCTOR))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    doctor_service.unassign_patient(db, user.id, patient_id)


@router.get("/me/patients", response_model=PaginatedResponse[PatientRead])
def list_my_patients(
    pagination: Annotated[PaginationParams, Depends()],
    user: Annotated[User, Depends(require_roles(UserRole.DOCTOR))],
    db: Annotated[Session, Depends(get_db)],
) -> PaginatedResponse[PatientRead]:
    off, lim = offset_limit(pagination.page, pagination.page_size)
    rows, total = patient_repo.list_for_doctor(db, user.id, off, lim)
    items = [PatientRead.model_validate(r) for r in rows]
    return PaginatedResponse.from_sequence(
        items, total=total, page=pagination.page, page_size=pagination.page_size
    )
