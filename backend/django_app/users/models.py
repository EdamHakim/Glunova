from datetime import date

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.timezone import now


class UserRole(models.TextChoices):
    PATIENT = "patient", "Patient"
    DOCTOR = "doctor", "Doctor"
    CAREGIVER = "caregiver", "Caregiver"


class GenderChoices(models.TextChoices):
    MALE = "Male", "Male"
    FEMALE = "Female", "Female"


class SmokingStatusChoices(models.TextChoices):
    # Strings match the Kaggle diabetes_prediction_dataset label-encoder vocab.
    NEVER = "never", "Never"
    FORMER = "former", "Former"
    CURRENT = "current", "Current"
    EVER = "ever", "Ever"
    NOT_CURRENT = "not current", "Not current"
    NO_INFO = "No Info", "No info"


class User(AbstractUser):
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.PATIENT)

    # ─── Patient health profile (nullable; empty for non-patient roles) ──────
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GenderChoices.choices, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    hypertension = models.BooleanField(null=True, blank=True)
    heart_disease = models.BooleanField(null=True, blank=True)
    smoking_status = models.CharField(max_length=20, choices=SmokingStatusChoices.choices, null=True, blank=True)
    hba1c_level = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    blood_glucose_level = models.IntegerField(null=True, blank=True)

    @property
    def age(self) -> int | None:
        if not self.date_of_birth:
            return None
        today: date = now().date()
        return (
            today.year - self.date_of_birth.year
            - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        )

    @property
    def bmi(self) -> float | None:
        if not self.height_cm or not self.weight_kg or float(self.height_cm) <= 0:
            return None
        height_m = float(self.height_cm) / 100.0
        return round(float(self.weight_kg) / (height_m * height_m), 2)
