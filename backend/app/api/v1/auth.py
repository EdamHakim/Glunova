from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterCaregiverRequest,
    RegisterDoctorRequest,
    RegisterPatientRequest,
    TokenPair,
)
from app.schemas.user import UserRead
from app.services import auth_service

router = APIRouter()


@router.post("/register/patient", response_model=UserRead)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def register_patient(
    request: Request,
    data: RegisterPatientRequest,
    db: Session = Depends(get_db),
) -> UserRead:
    user = auth_service.register_patient(db, data)
    return UserRead.model_validate(user)


@router.post("/register/doctor", response_model=UserRead)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def register_doctor(
    request: Request,
    data: RegisterDoctorRequest,
    db: Session = Depends(get_db),
) -> UserRead:
    user = auth_service.register_doctor(db, data)
    return UserRead.model_validate(user)


@router.post("/register/caregiver", response_model=UserRead)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def register_caregiver(
    request: Request,
    data: RegisterCaregiverRequest,
    db: Session = Depends(get_db),
) -> UserRead:
    user = auth_service.register_caregiver(db, data)
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenPair)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login(
    request: Request,
    data: LoginRequest,
    db: Session = Depends(get_db),
    user_agent: str | None = Header(default=None, alias="User-Agent"),
) -> TokenPair:
    return auth_service.login(db, data, user_agent=user_agent)


@router.post("/refresh", response_model=TokenPair)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def refresh(
    request: Request,
    data: RefreshRequest,
    db: Session = Depends(get_db),
    user_agent: str | None = Header(default=None, alias="User-Agent"),
) -> TokenPair:
    return auth_service.refresh_tokens(db, data.refresh_token, user_agent=user_agent)


@router.post("/logout", status_code=204)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def logout(
    request: Request,
    data: RefreshRequest,
    db: Session = Depends(get_db),
) -> None:
    auth_service.logout(db, data.refresh_token)
