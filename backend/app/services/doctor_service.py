from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import UserRole
from app.repositories import doctor_repo, patient_repo, user_repo
from app.schemas.doctor import DoctorUpdate


def assign_patient_to_doctor(db: Session, doctor_user_id: UUID, patient_id: UUID) -> None:
    doctor_user = user_repo.get_by_id(db, doctor_user_id)
    if not doctor_user or doctor_user.role != UserRole.DOCTOR:
        raise NotFoundError("Doctor not found")
    patient_user = user_repo.get_by_id(db, patient_id)
    if not patient_user or patient_user.role != UserRole.PATIENT:
        raise NotFoundError("Patient not found")
    if not patient_repo.get_by_id(db, patient_id):
        raise NotFoundError("Patient profile missing")
    if doctor_repo.is_assigned(db, doctor_user_id, patient_id):
        raise ConflictError("Already assigned")
    doctor_repo.assign_patient(db, doctor_user_id, patient_id)


def unassign_patient(db: Session, doctor_user_id: UUID, patient_id: UUID) -> None:
    if not doctor_repo.unassign_patient(db, doctor_user_id, patient_id):
        raise NotFoundError("Assignment not found")


def update_profile(db: Session, doctor_user_id: UUID, data: DoctorUpdate):
    doctor = doctor_repo.get_by_id(db, doctor_user_id)
    if not doctor:
        raise NotFoundError("Doctor profile not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(doctor, k, v)
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor
