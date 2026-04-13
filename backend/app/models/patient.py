from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    DiabetesType,
    Gender,
    MoodState,
    RiskLevel,
    TrendStatus,
)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(
        SQLEnum(Gender, name="gender", native_enum=False), nullable=True
    )
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    bmi: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    blood_type: Mapped[str | None] = mapped_column(String(8), nullable=True)
    smoker: Mapped[bool] = mapped_column(Boolean, default=False)
    alcohol_use: Mapped[bool] = mapped_column(Boolean, default=False)

    resting_heart_rate: Mapped[int | None] = mapped_column(nullable=True)
    blood_pressure_systolic: Mapped[int | None] = mapped_column(nullable=True)
    blood_pressure_diastolic: Mapped[int | None] = mapped_column(nullable=True)
    oxygen_saturation: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    body_temperature: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)

    diabetes_type: Mapped[DiabetesType | None] = mapped_column(
        SQLEnum(DiabetesType, name="diabetes_type", native_enum=False), nullable=True
    )
    diagnosis_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    hba1c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    fasting_glucose: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    postprandial_glucose: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    risk_level: Mapped[RiskLevel | None] = mapped_column(
        SQLEnum(RiskLevel, name="risk_level", native_enum=False), nullable=True
    )
    last_screening_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    trend_status: Mapped[TrendStatus | None] = mapped_column(
        SQLEnum(TrendStatus, name="trend_status", native_enum=False), nullable=True
    )

    allergies: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    chronic_conditions: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    medications: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    past_surgeries: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)

    stress_level: Mapped[int | None] = mapped_column(nullable=True)
    sleep_hours_avg: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    mood_state: Mapped[MoodState | None] = mapped_column(
        SQLEnum(MoodState, name="mood_state", native_enum=False), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="patient_profile")
    doctor_assignments: Mapped[list["DoctorPatientAssignment"]] = relationship(
        "DoctorPatientAssignment", back_populates="patient"
    )
    caregiver_links: Mapped[list["CaregiverPatientLink"]] = relationship(
        "CaregiverPatientLink", back_populates="patient"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="patient"
    )
    screening_results: Mapped[list["ScreeningResult"]] = relationship(
        "ScreeningResult", back_populates="patient"
    )
    health_alerts: Mapped[list["HealthAlert"]] = relationship(
        "HealthAlert", back_populates="patient"
    )
    care_plans: Mapped[list["CarePlan"]] = relationship("CarePlan", back_populates="patient")
    medical_documents: Mapped[list["MedicalDocument"]] = relationship(
        "MedicalDocument", back_populates="patient"
    )
