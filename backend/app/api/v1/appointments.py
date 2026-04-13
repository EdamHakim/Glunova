from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import appointment_repo
from app.schemas.appointment import AppointmentCreate, AppointmentRead, AppointmentUpdate
from app.services import appointment_service
from app.utils.pagination import PaginatedResponse, PaginationParams, offset_limit

router = APIRouter()


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def create_appointment(
    data: AppointmentCreate,
    user: Annotated[User, Depends(require_roles(UserRole.PATIENT, UserRole.DOCTOR))],
    db: Annotated[Session, Depends(get_db)],
) -> AppointmentRead:
    appt = appointment_service.create_appointment(db, user.id, user.role, data)
    return AppointmentRead.model_validate(appt)


@router.get("", response_model=PaginatedResponse[AppointmentRead])
def list_appointments(
    pagination: Annotated[PaginationParams, Depends()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PaginatedResponse[AppointmentRead]:
    off, lim = offset_limit(pagination.page, pagination.page_size)
    if user.role == UserRole.PATIENT:
        rows, total = appointment_repo.list_for_patient(db, user.id, off, lim)
    elif user.role == UserRole.DOCTOR:
        rows, total = appointment_repo.list_for_doctor(db, user.id, off, lim)
    elif user.role == UserRole.CAREGIVER:
        rows, total = appointment_repo.list_for_caregiver(db, user.id, off, lim)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")
    items = [AppointmentRead.model_validate(r) for r in rows]
    return PaginatedResponse.from_sequence(
        items, total=total, page=pagination.page, page_size=pagination.page_size
    )


@router.get("/{appointment_id}", response_model=AppointmentRead)
def get_appointment(
    appointment_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AppointmentRead:
    appt = appointment_service.get_appointment(db, appointment_id, user)
    return AppointmentRead.model_validate(appt)


@router.patch("/{appointment_id}", response_model=AppointmentRead)
def patch_appointment(
    appointment_id: UUID,
    data: AppointmentUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AppointmentRead:
    appt = appointment_service.update_appointment(db, appointment_id, user, data)
    return AppointmentRead.model_validate(appt)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_appointment(
    appointment_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    appointment_service.delete_appointment(db, appointment_id, user)
