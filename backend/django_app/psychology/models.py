from django.conf import settings
from django.db import models


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
