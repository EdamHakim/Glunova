"""Doctor ↔ patient assignment used for scoped APIs (documents, monitoring, nutrition, etc.)."""


def patient_ids_for_doctor(doctor) -> list[int]:
    """Patients who linked this doctor (Care Circle → Manage My Care Team)."""
    from users.models import PatientDoctorLink

    return list(
        PatientDoctorLink.objects.filter(doctor=doctor).values_list("patient_id", flat=True).distinct()
    )
