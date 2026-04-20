from django.conf import settings
from django.db import models


class ScreeningResult(models.Model):
    class Modality(models.TextChoices):
        VOICE = "voice", "Voice"
        TONGUE = "tongue", "Tongue"
        FUSION = "fusion", "Voice + Tongue Fusion"
        CATARACT = "cataract", "Cataract"
        RETINOPATHY = "retinopathy", "Retinopathy"
        FOOT_ULCER = "foot_ulcer", "Foot Ulcer"
        INFRARED = "infrared", "Infrared"

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="screening_results")
    modality = models.CharField(max_length=32, choices=Modality.choices)
    score = models.FloatField()
    risk_label = models.CharField(max_length=64)
    model_version = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    captured_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-captured_at", "-created_at"]


class AIExplanation(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_explanations")
    context_type = models.CharField(max_length=64)
    context_id = models.CharField(max_length=64)
    method = models.CharField(max_length=64, blank=True)
    technical_summary = models.TextField(blank=True)
    plain_language_summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
