from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import User
from app.repositories import caregiver_repo, doctor_repo


def can_access_patient(user: User, patient_id: UUID, db: Session) -> bool:
    if user.role == UserRole.PATIENT:
        return user.id == patient_id
    if user.role == UserRole.DOCTOR:
        return doctor_repo.is_assigned(db, user.id, patient_id)
    if user.role == UserRole.CAREGIVER:
        return caregiver_repo.is_linked(db, user.id, patient_id)
    return False


def can_doctor_manage_patient(doctor_id: UUID, patient_id: UUID, db: Session) -> bool:
    return doctor_repo.is_assigned(db, doctor_id, patient_id)
