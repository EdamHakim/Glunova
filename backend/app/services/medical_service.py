from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError
from app.models.enums import UserRole
from app.models.monitoring import CarePlan, HealthAlert, ScreeningResult
from app.repositories import doctor_repo


class ClinicalSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: UUID
    open_alerts: int
    screening_count: int
    latest_care_plan_id: UUID | None


def get_clinical_summary(db: Session, patient_id: UUID, user) -> ClinicalSummary:
    if user.role not in (UserRole.DOCTOR, UserRole.PATIENT):
        raise ForbiddenError("Clinical summary restricted to patient and assigned doctor")
    if user.role == UserRole.DOCTOR and not doctor_repo.is_assigned(db, user.id, patient_id):
        raise ForbiddenError("Doctor not assigned to patient")
    if user.role == UserRole.PATIENT and user.id != patient_id:
        raise ForbiddenError("Patients may only view their own summary")

    open_alerts = (
        db.scalar(
            select(func.count())
            .select_from(HealthAlert)
            .where(
                HealthAlert.patient_id == patient_id,
                HealthAlert.is_resolved.is_(False),
            )
        )
        or 0
    )
    screening_count = (
        db.scalar(
            select(func.count())
            .select_from(ScreeningResult)
            .where(ScreeningResult.patient_id == patient_id)
        )
        or 0
    )
    latest = db.scalars(
        select(CarePlan)
        .where(CarePlan.patient_id == patient_id)
        .order_by(CarePlan.updated_at.desc())
        .limit(1)
    ).first()

    return ClinicalSummary(
        patient_id=patient_id,
        open_alerts=open_alerts,
        screening_count=screening_count,
        latest_care_plan_id=latest.id if latest else None,
    )
