from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.patient import Patient
from app.repositories import patient_repo
from app.schemas.patient import PatientUpdate
from app.utils.bmi import calculate_bmi


def get_patient_or_404(db: Session, patient_id: UUID) -> Patient:
    p = patient_repo.get_by_id(db, patient_id)
    if not p:
        raise NotFoundError("Patient not found")
    return p


def update_patient(db: Session, patient_id: UUID, data: PatientUpdate) -> Patient:
    patient = get_patient_or_404(db, patient_id)
    update = data.model_dump(exclude_unset=True)
    for k, v in update.items():
        setattr(patient, k, v)
    if "weight_kg" in update or "height_cm" in update:
        patient.bmi = calculate_bmi(patient.weight_kg, patient.height_cm)
    return patient_repo.save(db, patient)
