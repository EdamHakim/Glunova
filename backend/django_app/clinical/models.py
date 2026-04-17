from django.conf import settings
from django.db import models


class CarePlan(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="care_plans")
    doctor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="assigned_care_plans")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MonitoringLog(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="monitoring_logs")
    source = models.CharField(max_length=50)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class PatientMedication(models.Model):
    class VerificationStatus(models.TextChoices):
        MATCHED = "matched", "Matched"
        AMBIGUOUS = "ambiguous", "Ambiguous"
        UNVERIFIED = "unverified", "Unverified"
        FAILED = "failed", "Failed"

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_medications",
    )
    source_document = models.ForeignKey(
        "documents.MedicalDocument",
        on_delete=models.CASCADE,
        related_name="patient_medications",
    )
    name_raw = models.CharField(max_length=255)
    name_display = models.CharField(max_length=255, null=True, blank=True)
    rxcui = models.CharField(max_length=32, null=True, blank=True)
    dosage = models.CharField(max_length=255, null=True, blank=True)
    frequency = models.CharField(max_length=255, null=True, blank=True)
    duration = models.CharField(max_length=255, null=True, blank=True)
    route = models.CharField(max_length=255, null=True, blank=True)
    verification_status = models.CharField(
        max_length=16,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
    )
    verification_detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at", "id"]

    def __str__(self) -> str:
        return f"{self.name_display or self.name_raw} for patient {self.patient_id}"
