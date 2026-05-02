from django.conf import settings
from django.db import models


class NutritionGoal(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="nutrition_goals")
    target_calories_kcal = models.FloatField()
    target_carbs_g = models.FloatField()
    target_protein_g = models.FloatField(default=0.0)
    target_fat_g = models.FloatField(default=0.0)
    target_sugar_g = models.FloatField(default=0.0)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    rationale = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-valid_from", "-created_at"]


class ExerciseSession(models.Model):
    class Intensity(models.TextChoices):
        LOW = "low", "Low"
        MODERATE = "moderate", "Moderate"
        HIGH = "high", "High"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        COMPLETED = "completed", "Completed"
        SKIPPED = "skipped", "Skipped"

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exercise_sessions")
    title = models.CharField(max_length=255)
    intensity = models.CharField(max_length=16, choices=Intensity.choices)
    duration_minutes = models.PositiveIntegerField()
    scheduled_for = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scheduled_for", "-created_at"]


class RecoveryPlan(models.Model):
    exercise_session = models.OneToOneField(
        "nutrition.ExerciseSession",
        on_delete=models.CASCADE,
        related_name="recovery_plan",
    )
    snack_suggestion = models.CharField(max_length=255, blank=True)
    hydration_ml = models.PositiveIntegerField(default=0)
    glucose_recheck_minutes = models.PositiveIntegerField(default=30)
    next_session_tip = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
