from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.monitoring import CarePlan, HealthAlert, ScreeningResult


def add_screening(db: Session, row: ScreeningResult) -> ScreeningResult:
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_screenings(
    db: Session, patient_id: UUID, offset: int, limit: int
) -> tuple[list[ScreeningResult], int]:
    total = (
        db.scalar(
            select(func.count()).select_from(ScreeningResult).where(
                ScreeningResult.patient_id == patient_id
            )
        )
        or 0
    )
    q = (
        select(ScreeningResult)
        .where(ScreeningResult.patient_id == patient_id)
        .order_by(ScreeningResult.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(q).all()), total


def add_alert(db: Session, row: HealthAlert) -> HealthAlert:
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_alerts(
    db: Session, patient_id: UUID, offset: int, limit: int, unresolved_only: bool = False
) -> tuple[list[HealthAlert], int]:
    cond = [HealthAlert.patient_id == patient_id]
    if unresolved_only:
        cond.append(HealthAlert.is_resolved.is_(False))

    filt = and_(*cond)
    total = (
        db.scalar(select(func.count()).select_from(HealthAlert).where(filt)) or 0
    )
    q = (
        select(HealthAlert)
        .where(filt)
        .order_by(HealthAlert.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(q).all()), total


def get_alert(db: Session, alert_id: UUID) -> HealthAlert | None:
    return db.get(HealthAlert, alert_id)


def save_alert(db: Session, row: HealthAlert) -> HealthAlert:
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_care_plan(db: Session, plan_id: UUID) -> CarePlan | None:
    return db.get(CarePlan, plan_id)


def list_care_plans(
    db: Session, patient_id: UUID, offset: int, limit: int
) -> tuple[list[CarePlan], int]:
    total = (
        db.scalar(
            select(func.count()).select_from(CarePlan).where(CarePlan.patient_id == patient_id)
        )
        or 0
    )
    q = (
        select(CarePlan)
        .where(CarePlan.patient_id == patient_id)
        .order_by(CarePlan.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(q).all()), total


def save_care_plan(db: Session, row: CarePlan) -> CarePlan:
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
