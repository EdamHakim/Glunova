from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories import monitoring_repo
from app.schemas.monitoring import (
    CarePlanCreate,
    CarePlanRead,
    CarePlanUpdate,
    HealthAlertCreate,
    HealthAlertPatch,
    HealthAlertRead,
    ScreeningResultCreate,
    ScreeningResultRead,
)
from app.services import monitoring_service
from app.utils.pagination import PaginatedResponse, PaginationParams, offset_limit

router = APIRouter()


@router.post(
    "/patients/{patient_id}/screenings",
    response_model=ScreeningResultRead,
    status_code=201,
)
def create_screening(
    patient_id: UUID,
    payload: ScreeningResultCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ScreeningResultRead:
    row = monitoring_service.add_screening(db, patient_id, user, payload)
    return ScreeningResultRead.model_validate(row)


@router.get(
    "/patients/{patient_id}/screenings",
    response_model=PaginatedResponse[ScreeningResultRead],
)
def list_screenings(
    patient_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PaginatedResponse[ScreeningResultRead]:
    monitoring_service.assert_patient_readable(db, user, patient_id)
    off, lim = offset_limit(pagination.page, pagination.page_size)
    rows, total = monitoring_repo.list_screenings(db, patient_id, off, lim)
    items = [ScreeningResultRead.model_validate(r) for r in rows]
    return PaginatedResponse.from_sequence(
        items, total=total, page=pagination.page, page_size=pagination.page_size
    )


@router.post(
    "/patients/{patient_id}/alerts",
    response_model=HealthAlertRead,
    status_code=201,
)
def create_alert(
    patient_id: UUID,
    payload: HealthAlertCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> HealthAlertRead:
    row = monitoring_service.add_alert(db, patient_id, user, payload)
    return HealthAlertRead.model_validate(row)


@router.get(
    "/patients/{patient_id}/alerts",
    response_model=PaginatedResponse[HealthAlertRead],
)
def list_alerts(
    patient_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    unresolved_only: bool = Query(default=False),
) -> PaginatedResponse[HealthAlertRead]:
    monitoring_service.assert_patient_readable(db, user, patient_id)
    off, lim = offset_limit(pagination.page, pagination.page_size)
    rows, total = monitoring_repo.list_alerts(db, patient_id, off, lim, unresolved_only)
    items = [HealthAlertRead.model_validate(r) for r in rows]
    return PaginatedResponse.from_sequence(
        items, total=total, page=pagination.page, page_size=pagination.page_size
    )


@router.patch("/alerts/{alert_id}", response_model=HealthAlertRead)
def patch_alert(
    alert_id: UUID,
    patch: HealthAlertPatch,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> HealthAlertRead:
    row = monitoring_service.patch_alert(db, alert_id, user, patch)
    return HealthAlertRead.model_validate(row)


@router.post("/care-plans", response_model=CarePlanRead, status_code=201)
def create_care_plan(
    payload: CarePlanCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CarePlanRead:
    row = monitoring_service.create_care_plan(db, user, payload)
    return CarePlanRead.model_validate(row)


@router.patch("/care-plans/{plan_id}", response_model=CarePlanRead)
def update_care_plan(
    plan_id: UUID,
    payload: CarePlanUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CarePlanRead:
    row = monitoring_service.update_care_plan(db, plan_id, user, payload)
    return CarePlanRead.model_validate(row)


@router.get(
    "/patients/{patient_id}/care-plans",
    response_model=PaginatedResponse[CarePlanRead],
)
def list_care_plans(
    patient_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PaginatedResponse[CarePlanRead]:
    monitoring_service.assert_patient_readable(db, user, patient_id)
    off, lim = offset_limit(pagination.page, pagination.page_size)
    rows, total = monitoring_repo.list_care_plans(db, patient_id, off, lim)
    items = [CarePlanRead.model_validate(r) for r in rows]
    return PaginatedResponse.from_sequence(
        items, total=total, page=pagination.page, page_size=pagination.page_size
    )
