from django.conf import settings
from django.db import models


class MonitoringLog(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="monitoring_logs")
    source = models.CharField(max_length=50)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class RiskAssessment(models.Model):
    class Tier(models.TextChoices):
        LOW = "low", "Low"
        MODERATE = "moderate", "Moderate"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="risk_assessments")
    tier = models.CharField(max_length=16, choices=Tier.choices)
    score = models.FloatField()
    confidence = models.FloatField(default=0.0)
    drivers = models.JSONField(default=list, blank=True)
    assessed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assessed_at", "-created_at"]


class HealthAlert(models.Model):
    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="health_alerts")
    risk_assessment = models.ForeignKey(
        "monitoring.RiskAssessment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    severity = models.CharField(max_length=16, choices=Severity.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    triggered_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-triggered_at", "-created_at"]


class DiseaseProgression(models.Model):
    class Trend(models.TextChoices):
        WORSENING = "worsening", "Worsening"
        STABLE = "stable", "Stable"
        IMPROVING = "improving", "Improving"

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="disease_progressions")
    indicator = models.CharField(max_length=128)
    value = models.FloatField()
    trend = models.CharField(max_length=16, choices=Trend.choices)
    recorded_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at", "-created_at"]


class PatientMedication(models.Model):
    class VerificationStatus(models.TextChoices):
        MATCHED = "matched", "Matched"
        AMBIGUOUS = "ambiguous", "Ambiguous"
        UNVERIFIED = "unverified", "Unverified"
        FAILED = "failed", "Failed"

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="patient_medications")
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
