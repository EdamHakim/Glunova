from __future__ import annotations

from django.contrib.auth import get_user_model

from clinical.models import CarePlan

from .models import PatientCaregiverLink

User = get_user_model()


def can_access_patient_documents(actor: User, patient_pk: int) -> bool:
    """Whether actor may list/upload/download documents for the given patient user id."""
    role = getattr(actor, "role", None)
    if role == "patient":
        return actor.pk == patient_pk
    if role == "doctor":
        return CarePlan.objects.filter(doctor=actor, patient_id=patient_pk).exists()
    if role == "caregiver":
        return PatientCaregiverLink.objects.filter(caregiver=actor, patient_id=patient_pk).exists()
    return False


def parse_patient_pk(raw_patient_pk: object) -> int | None:
    try:
        patient_pk = int(raw_patient_pk)
    except (TypeError, ValueError):
        return None
    return patient_pk if patient_pk > 0 else None


def patient_exists(patient_pk: int) -> bool:
    return User.objects.filter(pk=patient_pk).exists()
