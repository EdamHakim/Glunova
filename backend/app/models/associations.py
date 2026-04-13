from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DoctorPatientAssignment(Base):
    """Doctor ↔ patient assignment (many-to-many with metadata)."""

    __tablename__ = "doctor_patient_assignments"

    doctor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    patient_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="patient_assignments")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="doctor_assignments")


class CaregiverPatientLink(Base):
    """Caregiver ↔ patient link with relationship label."""

    __tablename__ = "caregiver_patient_links"

    caregiver_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("caregivers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    patient_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relationship_to_patient: Mapped[str] = mapped_column(String(120), default="caregiver")
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    caregiver: Mapped["Caregiver"] = relationship("Caregiver", back_populates="patient_links")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="caregiver_links")
