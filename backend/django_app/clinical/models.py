from django.conf import settings
from django.db import models


class CrisisEscalation(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_REVIEW = "in_review", "In Review"
        CLOSED = "closed", "Closed"

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="crisis_escalations",
    )
    emotion_assessment = models.ForeignKey(
        "psychology.EmotionAssessment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalations",
    )
    physician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_crisis_escalations",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class ClinicalCaseReview(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_REVIEW = "in_review", "In Review"
        CLOSED = "closed", "Closed"

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clinical_case_reviews",
    )
    priority = models.CharField(max_length=16, choices=Priority.choices)
    summary = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ImagingAnalysis(models.Model):
    class AnalysisType(models.TextChoices):
        CATARACT = "cataract", "Cataract"
        RETINOPATHY = "retinopathy", "Retinopathy"
        FOOT_ULCER = "foot_ulcer", "Foot Ulcer"
        INFRARED = "infrared", "Infrared"

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="imaging_analyses")
    analysis_type = models.CharField(max_length=32, choices=AnalysisType.choices)
    severity_grade = models.PositiveSmallIntegerField(default=0)
    confidence = models.FloatField(default=0.0)
    findings = models.JSONField(default=dict, blank=True)
    captured_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-captured_at", "-created_at"]
