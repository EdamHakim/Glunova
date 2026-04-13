from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.appointment import Appointment
from app.models.enums import UserRole
from app.repositories import appointment_repo, doctor_repo, user_repo
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.services import access


def create_appointment(db: Session, actor_id: UUID, actor_role: UserRole, data: AppointmentCreate) -> Appointment:
    """Patient or doctor may create; doctor must be assigned to patient."""
    patient = user_repo.get_by_id(db, data.patient_id)
    doctor = user_repo.get_by_id(db, data.doctor_id)
    if not patient or patient.role != UserRole.PATIENT:
        raise NotFoundError("Patient not found")
    if not doctor or doctor.role != UserRole.DOCTOR:
        raise NotFoundError("Doctor not found")

    if actor_role == UserRole.PATIENT:
        if actor_id != data.patient_id:
            raise ForbiddenError("Patients may only book for themselves")
    elif actor_role == UserRole.DOCTOR:
        if actor_id != data.doctor_id:
            raise ForbiddenError("Doctors may only create appointments for themselves")
        if not doctor_repo.is_assigned(db, data.doctor_id, data.patient_id):
            raise ForbiddenError("Doctor is not assigned to this patient")
    else:
        raise ForbiddenError("Only patients or doctors can create appointments")

    appt = Appointment(
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        scheduled_at=data.scheduled_at,
        notes=data.notes,
    )
    return appointment_repo.save(db, appt)


def get_appointment(db: Session, appt_id: UUID, user) -> Appointment:
    appt = appointment_repo.get_by_id(db, appt_id)
    if not appt:
        raise NotFoundError("Appointment not found")
    if not access.can_access_patient(user, appt.patient_id, db):
        raise ForbiddenError("No access to this appointment")
    if user.role == UserRole.DOCTOR and user.id != appt.doctor_id:
        raise ForbiddenError("Appointment is for another doctor")
    return appt


def update_appointment(
    db: Session, appt_id: UUID, user, data: AppointmentUpdate
) -> Appointment:
    appt = get_appointment(db, appt_id, user)
    updates = data.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(appt, k, v)
    return appointment_repo.save(db, appt)


def delete_appointment(db: Session, appt_id: UUID, user) -> None:
    appt = get_appointment(db, appt_id, user)
    if user.role == UserRole.CAREGIVER:
        raise ForbiddenError("Caregivers cannot delete appointments")
    appointment_repo.delete(db, appt)
