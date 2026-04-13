from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.associations import CaregiverPatientLink


def get_by_id(db: Session, appt_id: UUID) -> Appointment | None:
    return db.get(Appointment, appt_id)


def list_for_patient(db: Session, patient_id: UUID, offset: int, limit: int) -> tuple[list[Appointment], int]:
    base = select(Appointment).where(Appointment.patient_id == patient_id)
    total = db.scalar(
        select(func.count()).select_from(Appointment).where(Appointment.patient_id == patient_id)
    ) or 0
    rows = db.scalars(base.order_by(Appointment.scheduled_at.desc()).offset(offset).limit(limit)).all()
    return list(rows), total


def list_for_doctor(db: Session, doctor_id: UUID, offset: int, limit: int) -> tuple[list[Appointment], int]:
    base = select(Appointment).where(Appointment.doctor_id == doctor_id)
    total = db.scalar(
        select(func.count()).select_from(Appointment).where(Appointment.doctor_id == doctor_id)
    ) or 0
    rows = db.scalars(base.order_by(Appointment.scheduled_at.desc()).offset(offset).limit(limit)).all()
    return list(rows), total


def list_for_caregiver(
    db: Session, caregiver_id: UUID, offset: int, limit: int
) -> tuple[list[Appointment], int]:
    base = (
        select(Appointment)
        .join(
            CaregiverPatientLink,
            CaregiverPatientLink.patient_id == Appointment.patient_id,
        )
        .where(CaregiverPatientLink.caregiver_id == caregiver_id)
    )
    total = (
        db.scalar(
            select(func.count())
            .select_from(Appointment)
            .join(
                CaregiverPatientLink,
                CaregiverPatientLink.patient_id == Appointment.patient_id,
            )
            .where(CaregiverPatientLink.caregiver_id == caregiver_id)
        )
        or 0
    )
    rows = db.scalars(base.order_by(Appointment.scheduled_at.desc()).offset(offset).limit(limit)).all()
    return list(rows), total


def save(db: Session, appt: Appointment) -> Appointment:
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return appt


def delete(db: Session, appt: Appointment) -> None:
    db.delete(appt)
    db.commit()
