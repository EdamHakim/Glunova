from django.conf import settings
from django.db import models


class MealLog(models.Model):
    class InputType(models.TextChoices):
        TEXT = "text", "Text"
        BARCODE = "barcode", "Barcode"
        VOICE = "voice", "Voice"
        PHOTO = "photo", "Photo"

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="meal_logs")
    input_type = models.CharField(max_length=16, choices=InputType.choices)
    description = models.CharField(max_length=255)
    carbs_g = models.FloatField(default=0.0)
    calories_kcal = models.FloatField(default=0.0)
    sugar_g = models.FloatField(default=0.0)
    gi = models.FloatField(default=0.0)
    gl = models.FloatField(default=0.0)
    metadata = models.JSONField(default=dict, blank=True)
    logged_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-logged_at", "-created_at"]


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


class FoodSubstitution(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="food_substitutions")
    meal_log = models.ForeignKey(
        "nutrition.MealLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="substitutions",
    )
    original_food = models.CharField(max_length=255)
    suggested_food = models.CharField(max_length=255)
    reason = models.TextField(blank=True)
    expected_gi_delta = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


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
