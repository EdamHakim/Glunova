from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import UserRole
from app.models.monitoring import CarePlan, HealthAlert, ScreeningResult
from app.repositories import doctor_repo, monitoring_repo
from app.schemas.monitoring import (
    CarePlanCreate,
    CarePlanUpdate,
    HealthAlertCreate,
    HealthAlertPatch,
    ScreeningResultCreate,
)
from app.services import access


def add_screening(
    db: Session, patient_id: UUID, user, payload: ScreeningResultCreate
) -> ScreeningResult:
    if user.role not in (UserRole.DOCTOR, UserRole.PATIENT):
        raise ForbiddenError("Not allowed to add screening results")
    if user.role == UserRole.PATIENT and user.id != patient_id:
        raise ForbiddenError("Patients may only add results for themselves")
    if user.role == UserRole.DOCTOR and not doctor_repo.is_assigned(db, user.id, patient_id):
        raise ForbiddenError("Doctor not assigned to patient")
    row = ScreeningResult(
        patient_id=patient_id,
        type=payload.type,
        result_score=payload.result_score,
        risk_prediction=payload.risk_prediction,
        raw_data_reference=payload.raw_data_reference,
        extra=payload.extra,
    )
    return monitoring_repo.add_screening(db, row)


def add_alert(db: Session, patient_id: UUID, user, payload: HealthAlertCreate) -> HealthAlert:
    if user.role != UserRole.DOCTOR:
        raise ForbiddenError("Only clinicians may create alerts")
    if not doctor_repo.is_assigned(db, user.id, patient_id):
        raise ForbiddenError("Doctor not assigned to patient")
    row = HealthAlert(
        patient_id=patient_id,
        alert_type=payload.alert_type,
        severity=payload.severity,
        message=payload.message,
    )
    return monitoring_repo.add_alert(db, row)


def patch_alert(db: Session, alert_id: UUID, user, patch: HealthAlertPatch) -> HealthAlert:
    row = monitoring_repo.get_alert(db, alert_id)
    if not row:
        raise NotFoundError("Alert not found")
    if user.role == UserRole.DOCTOR:
        if not doctor_repo.is_assigned(db, user.id, row.patient_id):
            raise ForbiddenError("Doctor not assigned to patient")
    elif user.role == UserRole.PATIENT:
        if user.id != row.patient_id:
            raise ForbiddenError("Not your alert")
    else:
        raise ForbiddenError("Caregivers cannot resolve alerts")
    row.is_resolved = patch.is_resolved
    return monitoring_repo.save_alert(db, row)


def create_care_plan(db: Session, user, payload: CarePlanCreate) -> CarePlan:
    if user.role != UserRole.DOCTOR or user.id != payload.doctor_id:
        raise ForbiddenError("Only the authoring doctor can create this care plan")
    if not doctor_repo.is_assigned(db, user.id, payload.patient_id):
        raise ForbiddenError("Doctor not assigned to patient")
    row = CarePlan(
        patient_id=payload.patient_id,
        doctor_id=payload.doctor_id,
        plan_details=payload.plan_details,
    )
    return monitoring_repo.save_care_plan(db, row)


def update_care_plan(db: Session, plan_id: UUID, user, payload: CarePlanUpdate) -> CarePlan:
    row = monitoring_repo.get_care_plan(db, plan_id)
    if not row:
        raise NotFoundError("Care plan not found")
    if user.role != UserRole.DOCTOR or user.id != row.doctor_id:
        raise ForbiddenError("Only the authoring doctor may update this plan")
    row.plan_details = payload.plan_details
    return monitoring_repo.save_care_plan(db, row)


def assert_patient_readable(db: Session, user, patient_id: UUID) -> None:
    if not access.can_access_patient(user, patient_id, db):
        raise ForbiddenError("No access to this patient")
