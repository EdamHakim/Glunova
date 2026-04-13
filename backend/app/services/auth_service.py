import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.exceptions import ConflictError, UnauthorizedError
from app.models.caregiver import Caregiver
from app.models.doctor import Doctor
from app.models.enums import UserRole
from app.models.patient import Patient
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories import user_repo
from app.schemas.auth import (
    LoginRequest,
    RegisterCaregiverRequest,
    RegisterDoctorRequest,
    RegisterPatientRequest,
    TokenPair,
)

logger = logging.getLogger(__name__)


def _hash_refresh(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _store_refresh_token(db: Session, user_id: UUID, raw_token: str, user_agent: str | None) -> None:
    payload = security.decode_token(raw_token)
    security.verify_token_type(payload, "refresh")
    exp = payload.get("exp")
    if not exp:
        raise UnauthorizedError("Invalid refresh token")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    row = RefreshToken(
        user_id=user_id,
        token_hash=_hash_refresh(raw_token),
        expires_at=expires_at,
        user_agent=user_agent,
    )
    db.add(row)
    db.commit()


def register_patient(db: Session, data: RegisterPatientRequest) -> User:
    email = data.email.lower()
    if user_repo.get_by_email(db, email):
        raise ConflictError("Email already registered")
    user = User(
        full_name=data.full_name,
        email=email,
        password_hash=security.hash_password(data.password),
        role=UserRole.PATIENT,
        phone_number=data.phone_number,
    )
    db.add(user)
    db.flush()
    db.add(Patient(id=user.id))
    db.commit()
    db.refresh(user)
    logger.info("Registered patient user_id=%s", user.id)
    return user


def register_doctor(db: Session, data: RegisterDoctorRequest) -> User:
    email = data.email.lower()
    if user_repo.get_by_email(db, email):
        raise ConflictError("Email already registered")
    user = User(
        full_name=data.full_name,
        email=email,
        password_hash=security.hash_password(data.password),
        role=UserRole.DOCTOR,
        phone_number=data.phone_number,
    )
    db.add(user)
    db.flush()
    db.add(
        Doctor(
            id=user.id,
            specialization=data.specialization,
            years_of_experience=data.years_of_experience,
            license_number=data.license_number,
        )
    )
    db.commit()
    db.refresh(user)
    logger.info("Registered doctor user_id=%s", user.id)
    return user


def register_caregiver(db: Session, data: RegisterCaregiverRequest) -> User:
    email = data.email.lower()
    if user_repo.get_by_email(db, email):
        raise ConflictError("Email already registered")
    user = User(
        full_name=data.full_name,
        email=email,
        password_hash=security.hash_password(data.password),
        role=UserRole.CAREGIVER,
        phone_number=data.phone_number,
    )
    db.add(user)
    db.flush()
    db.add(
        Caregiver(
            id=user.id,
            default_relationship_label=data.default_relationship_label,
        )
    )
    db.commit()
    db.refresh(user)
    logger.info("Registered caregiver user_id=%s", user.id)
    return user


def login(db: Session, data: LoginRequest, user_agent: str | None = None) -> TokenPair:
    user = user_repo.get_by_email(db, data.email.lower())
    if not user or not user.is_active:
        raise UnauthorizedError("Invalid credentials")
    if not security.verify_password(data.password, user.password_hash):
        raise UnauthorizedError("Invalid credentials")
    access = security.create_access_token(
        user.id, extra_claims={"role": user.role.value}
    )
    refresh = security.create_refresh_token(user.id)
    _store_refresh_token(db, user.id, refresh, user_agent)
    return TokenPair(access_token=access, refresh_token=refresh)


def refresh_tokens(db: Session, refresh_token: str, user_agent: str | None = None) -> TokenPair:
    try:
        payload = security.decode_token(refresh_token)
        security.verify_token_type(payload, "refresh")
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise UnauthorizedError("Invalid refresh token") from None

    th = _hash_refresh(refresh_token)
    q = select(RefreshToken).where(
        RefreshToken.token_hash == th,
        RefreshToken.revoked.is_(False),
    )
    row = db.scalars(q).first()
    if not row or row.user_id != user_id:
        raise UnauthorizedError("Invalid refresh token")
    if row.expires_at < datetime.now(timezone.utc):
        raise UnauthorizedError("Refresh token expired")

    row.revoked = True
    db.add(row)
    db.commit()

    user = user_repo.get_by_id(db, user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("User inactive")

    access = security.create_access_token(user.id, extra_claims={"role": user.role.value})
    new_refresh = security.create_refresh_token(user.id)
    _store_refresh_token(db, user.id, new_refresh, user_agent)
    return TokenPair(access_token=access, refresh_token=new_refresh)


def logout(db: Session, refresh_token: str) -> None:
    try:
        payload = security.decode_token(refresh_token)
        security.verify_token_type(payload, "refresh")
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return
    th = _hash_refresh(refresh_token)
    q = select(RefreshToken).where(
        RefreshToken.token_hash == th,
        RefreshToken.user_id == user_id,
    )
    row = db.scalars(q).first()
    if row:
        row.revoked = True
        db.add(row)
        db.commit()
