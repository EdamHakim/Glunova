from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import UserRole
from app.repositories import caregiver_repo, patient_repo, user_repo
from app.schemas.caregiver import CaregiverUpdate


def link_patient(
    db: Session, caregiver_user_id: UUID, patient_id: UUID, relationship: str
) -> None:
    cg_user = user_repo.get_by_id(db, caregiver_user_id)
    if not cg_user or cg_user.role != UserRole.CAREGIVER:
        raise NotFoundError("Caregiver not found")
    pt_user = user_repo.get_by_id(db, patient_id)
    if not pt_user or pt_user.role != UserRole.PATIENT:
        raise NotFoundError("Patient not found")
    if not patient_repo.get_by_id(db, patient_id):
        raise NotFoundError("Patient profile missing")
    if caregiver_repo.is_linked(db, caregiver_user_id, patient_id):
        raise ConflictError("Already linked")
    caregiver_repo.link_patient(db, caregiver_user_id, patient_id, relationship)


def unlink_patient(db: Session, caregiver_user_id: UUID, patient_id: UUID) -> None:
    if not caregiver_repo.unlink_patient(db, caregiver_user_id, patient_id):
        raise NotFoundError("Link not found")


def update_profile(db: Session, caregiver_user_id: UUID, data: CaregiverUpdate):
    cg = caregiver_repo.get_by_id(db, caregiver_user_id)
    if not cg:
        raise NotFoundError("Caregiver profile not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(cg, k, v)
    db.add(cg)
    db.commit()
    db.refresh(cg)
    return cg
