from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.associations import CaregiverPatientLink
from app.models.caregiver import Caregiver


def get_by_id(db: Session, caregiver_id: UUID) -> Caregiver | None:
    return db.get(Caregiver, caregiver_id)


def is_linked(db: Session, caregiver_id: UUID, patient_id: UUID) -> bool:
    q = select(CaregiverPatientLink).where(
        CaregiverPatientLink.caregiver_id == caregiver_id,
        CaregiverPatientLink.patient_id == patient_id,
    )
    return db.scalars(q).first() is not None


def link_patient(
    db: Session,
    caregiver_id: UUID,
    patient_id: UUID,
    relationship: str,
) -> CaregiverPatientLink:
    row = CaregiverPatientLink(
        caregiver_id=caregiver_id,
        patient_id=patient_id,
        relationship_to_patient=relationship,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def unlink_patient(db: Session, caregiver_id: UUID, patient_id: UUID) -> bool:
    stmt = select(CaregiverPatientLink).where(
        CaregiverPatientLink.caregiver_id == caregiver_id,
        CaregiverPatientLink.patient_id == patient_id,
    )
    row = db.scalars(stmt).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def list_linked_patient_ids(db: Session, caregiver_id: UUID) -> list[UUID]:
    q = select(CaregiverPatientLink.patient_id).where(
        CaregiverPatientLink.caregiver_id == caregiver_id
    )
    return list(db.scalars(q).all())
