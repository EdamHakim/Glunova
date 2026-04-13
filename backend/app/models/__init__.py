"""SQLAlchemy models — import order matters for mapper configuration."""

from app.models.appointment import Appointment
from app.models.associations import CaregiverPatientLink, DoctorPatientAssignment
from app.models.caregiver import Caregiver
from app.models.doctor import Doctor
from app.models.enums import (
    AlertSeverity,
    AppointmentStatus,
    DiabetesType,
    DocumentProcessingStatus,
    Gender,
    LLMRefinementStatus,
    MoodState,
    RiskLevel,
    TrendStatus,
    UserRole,
)
from app.models.monitoring import CarePlan, HealthAlert, ScreeningResult
from app.models.patient import Patient
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.medical_document import MedicalDocument

__all__ = [
    "AlertSeverity",
    "Appointment",
    "AppointmentStatus",
    "Caregiver",
    "CaregiverPatientLink",
    "CarePlan",
    "DiabetesType",
    "Doctor",
    "DoctorPatientAssignment",
    "Gender",
    "DocumentProcessingStatus",
    "HealthAlert",
    "LLMRefinementStatus",
    "MedicalDocument",
    "MoodState",
    "Patient",
    "RefreshToken",
    "RiskLevel",
    "ScreeningResult",
    "TrendStatus",
    "User",
    "UserRole",
]
