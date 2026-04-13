from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.associations import DoctorPatientAssignment
from app.models.doctor import Doctor


def get_by_id(db: Session, doctor_id: UUID) -> Doctor | None:
    return db.get(Doctor, doctor_id)


def is_assigned(db: Session, doctor_id: UUID, patient_id: UUID) -> bool:
    q = select(DoctorPatientAssignment).where(
        DoctorPatientAssignment.doctor_id == doctor_id,
        DoctorPatientAssignment.patient_id == patient_id,
    )
    return db.scalars(q).first() is not None


def assign_patient(db: Session, doctor_id: UUID, patient_id: UUID) -> DoctorPatientAssignment:
    row = DoctorPatientAssignment(doctor_id=doctor_id, patient_id=patient_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def unassign_patient(db: Session, doctor_id: UUID, patient_id: UUID) -> bool:
    stmt = select(DoctorPatientAssignment).where(
        DoctorPatientAssignment.doctor_id == doctor_id,
        DoctorPatientAssignment.patient_id == patient_id,
    )
    row = db.scalars(stmt).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def list_assigned_patient_ids(db: Session, doctor_id: UUID) -> list[UUID]:
    q = select(DoctorPatientAssignment.patient_id).where(
        DoctorPatientAssignment.doctor_id == doctor_id
    )
    return list(db.scalars(q).all())
