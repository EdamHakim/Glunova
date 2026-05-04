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


class WeeklyWellnessPlan(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        READY   = "ready",   "Ready"
        FAILED  = "failed",  "Failed"

    patient            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wellness_plans"
    )
    week_start         = models.DateField()
    status             = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    fitness_level      = models.CharField(max_length=20, blank=True)
    goal               = models.CharField(max_length=30, blank=True)
    cuisine            = models.CharField(max_length=30, blank=True)
    generated_at       = models.DateTimeField(null=True, blank=True)
    clinical_snapshot  = models.JSONField(default=dict)
    week_summary       = models.JSONField(default=dict)

    class Meta:
        ordering = ["-week_start"]
        unique_together = [("patient", "week_start")]

    def __str__(self):
        return f"WellnessPlan({self.patient_id}, week={self.week_start})"


class ExerciseSession(models.Model):
    class Intensity(models.TextChoices):
        LOW = "low", "Low"
        MODERATE = "moderate", "Moderate"
        HIGH = "high", "High"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        COMPLETED = "completed", "Completed"
        SKIPPED = "skipped", "Skipped"

    patient          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exercise_sessions")
    wellness_plan    = models.ForeignKey(WeeklyWellnessPlan, on_delete=models.CASCADE, related_name="exercise_sessions", null=True, blank=True)
    day_index        = models.PositiveSmallIntegerField(null=True, blank=True)  # 0-6
    exercise_type    = models.CharField(max_length=30, blank=True)  # cardio / strength / flexibility / HIIT / mobility
    title            = models.CharField(max_length=255)
    description      = models.TextField(blank=True)
    intensity        = models.CharField(max_length=16, choices=Intensity.choices)
    duration_minutes = models.PositiveIntegerField()
    sets             = models.PositiveSmallIntegerField(null=True, blank=True)
    reps             = models.PositiveSmallIntegerField(null=True, blank=True)
    equipment        = models.JSONField(default=list)
    pre_exercise_glucose_check = models.BooleanField(default=False)
    post_exercise_snack_tip    = models.TextField(blank=True)
    diabetes_rationale         = models.TextField(blank=True)
    scheduled_for    = models.DateTimeField()
    status           = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    notes            = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

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


class Meal(models.Model):
    class MealType(models.TextChoices):
        BREAKFAST           = "breakfast",           "Breakfast"
        LUNCH               = "lunch",               "Lunch"
        DINNER              = "dinner",              "Dinner"
        SNACK               = "snack",               "Snack"
        PRE_WORKOUT_SNACK   = "pre_workout_snack",   "Pre-Workout Snack"
        POST_WORKOUT_SNACK  = "post_workout_snack",  "Post-Workout Snack"

    class GILevel(models.TextChoices):
        LOW    = "low",    "Low"
        MEDIUM = "medium", "Medium"
        HIGH   = "high",   "High"

    wellness_plan            = models.ForeignKey(
        WeeklyWellnessPlan, on_delete=models.CASCADE, related_name="meals", null=True, blank=True
    )
    day_index                = models.PositiveSmallIntegerField()
    meal_type                = models.CharField(max_length=20, choices=MealType.choices)
    name                     = models.CharField(max_length=200)
    description              = models.TextField()
    ingredients              = models.JSONField(default=list)
    preparation_time_minutes = models.PositiveSmallIntegerField(default=20)
    calories_kcal            = models.FloatField()
    carbs_g                  = models.FloatField()
    protein_g                = models.FloatField()
    fat_g                    = models.FloatField()
    sugar_g                  = models.FloatField()
    glycemic_index           = models.CharField(max_length=10, choices=GILevel.choices)
    glycemic_load            = models.CharField(max_length=10, choices=GILevel.choices)
    diabetes_rationale       = models.TextField()

    class Meta:
        ordering = ["day_index", "meal_type"]
        unique_together = [("wellness_plan", "day_index", "meal_type")]

    def __str__(self):
        return f"{self.meal_type} day{self.day_index} — {self.name}"
