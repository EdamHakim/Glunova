import uuid

from django.conf import settings
from django.db import models


class PsychologyProfile(models.Model):
    """Per-patient psychology context, safety gates, and health hints for AI assembly."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="psychology_profile",
    )
    health_context_json = models.JSONField(default=dict, blank=True)
    personality_notes = models.TextField(blank=True)
    preferred_language = models.CharField(max_length=16, default="en")
    physician_review_required = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Psychology profile"
        verbose_name_plural = "Psychology profiles"


class PsychologySession(models.Model):
    """FastAPI-tracked therapy session (UUID session_id). Distinct from legacy TherapySession."""

    session_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True, editable=False)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="psychology_ai_sessions",
    )
    preferred_language = models.CharField(max_length=16, default="en")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    last_state = models.CharField(max_length=32, blank=True)
    crisis_score_history_json = models.JSONField(default=list, blank=True)
    session_summary_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at", "-created_at"]


class PsychologyMessage(models.Model):
    session = models.ForeignKey(
        PsychologySession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16)
    content = models.TextField()
    created_at = models.DateTimeField()
    fusion_metadata = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]


class PsychologyCrisisEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="psychology_crisis_events",
    )
    session = models.ForeignKey(
        PsychologySession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crisis_events",
    )
    probability = models.FloatField()
    action_taken = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class PsychologyEmotionLog(models.Model):
    """Time-series distress points (PostgreSQL; optional Timescale hypertable in ops)."""

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="psychology_emotion_logs",
    )
    logged_at = models.DateTimeField(db_index=True)
    distress_score = models.FloatField()
    mental_state = models.CharField(max_length=32)

    class Meta:
        ordering = ["-logged_at"]
        indexes = [
            models.Index(fields=["patient", "logged_at"]),
        ]


class EmotionAssessment(models.Model):
    class DistressLevel(models.TextChoices):
        LOW = "low", "Low"
        MODERATE = "moderate", "Moderate"
        HIGH = "high", "High"
        CRISIS = "crisis", "Crisis"

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="emotion_assessments")
    dominant_emotion = models.CharField(max_length=64)
    text_score = models.FloatField(default=0.0)
    speech_score = models.FloatField(default=0.0)
    facial_score = models.FloatField(default=0.0)
    distress_level = models.CharField(max_length=16, choices=DistressLevel.choices)
    summary = models.TextField(blank=True)
    assessed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assessed_at", "-created_at"]


class TherapySession(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="therapy_sessions")
    mode = models.CharField(max_length=64, default="sanadi")
    mood_before = models.CharField(max_length=64, blank=True)
    mood_after = models.CharField(max_length=64, blank=True)
    summary = models.TextField(blank=True)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at", "-created_at"]
