from django.conf import settings
from django.db import models


class MonitoringLog(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="monitoring_logs")
    source = models.CharField(max_length=50)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class RiskAssessment(models.Model):
    class Tier(models.TextChoices):
        # Glunova fusion v11 outputs only 3 tiers: LOW / HIGH / CRITICAL.
        # MODERATE was removed because the late_fusion_robust predictor never
        # emits it (cf. TIER_RANK in glunova_predictor.py) and clinical guidelines
        # (ADA 2024) align on a 3-level decision: monitor / refer / urgent.
        LOW = "low", "Low"
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

    class AgentAudience(models.TextChoices):
        PATIENT = "patient", "Patient"
        DOCTOR = "doctor", "Doctor"

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
    # Care-agent dispatch audience; null for clinical / risk-generated alerts.
    agent_audience = models.CharField(
        max_length=16,
        choices=AgentAudience.choices,
        null=True,
        blank=True,
    )

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
    instructions = models.TextField(null=True, blank=True)
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


class PatientLabResult(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="patient_lab_results")
    source_document = models.ForeignKey(
        "documents.MedicalDocument",
        on_delete=models.CASCADE,
        related_name="patient_lab_results",
    )
    test_name = models.CharField(max_length=255)
    normalized_name = models.CharField(max_length=255, blank=True)
    value = models.CharField(max_length=64)
    numeric_value = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=64, null=True, blank=True)
    reference_range = models.CharField(max_length=255, null=True, blank=True)
    is_out_of_range = models.BooleanField(null=True, blank=True)
    observed_at = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-observed_at", "-updated_at", "-created_at", "id"]

    def __str__(self) -> str:
        return f"{self.test_name}: {self.value}{f' {self.unit}' if self.unit else ''}"
