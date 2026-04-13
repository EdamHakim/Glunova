from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.associations import CaregiverPatientLink, DoctorPatientAssignment
from app.models.patient import Patient


def get_by_id(db: Session, patient_id: UUID) -> Patient | None:
    return db.get(Patient, patient_id)


def count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Patient)) or 0


def list_paginated(db: Session, offset: int, limit: int) -> tuple[list[Patient], int]:
    total = count(db)
    rows = db.scalars(select(Patient).offset(offset).limit(limit)).all()
    return list(rows), total


def list_for_doctor(
    db: Session, doctor_id: UUID, offset: int, limit: int
) -> tuple[list[Patient], int]:
    base = (
        select(Patient)
        .join(DoctorPatientAssignment)
        .where(DoctorPatientAssignment.doctor_id == doctor_id)
    )
    total = (
        db.scalar(
            select(func.count())
            .select_from(Patient)
            .join(DoctorPatientAssignment)
            .where(DoctorPatientAssignment.doctor_id == doctor_id)
        )
        or 0
    )
    rows = db.scalars(base.offset(offset).limit(limit)).all()
    return list(rows), total


def list_for_caregiver(
    db: Session, caregiver_id: UUID, offset: int, limit: int
) -> tuple[list[Patient], int]:
    base = (
        select(Patient)
        .join(CaregiverPatientLink)
        .where(CaregiverPatientLink.caregiver_id == caregiver_id)
    )
    total = (
        db.scalar(
            select(func.count())
            .select_from(Patient)
            .join(CaregiverPatientLink)
            .where(CaregiverPatientLink.caregiver_id == caregiver_id)
        )
        or 0
    )
    rows = db.scalars(base.offset(offset).limit(limit)).all()
    return list(rows), total


def save(db: Session, patient: Patient) -> Patient:
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient
