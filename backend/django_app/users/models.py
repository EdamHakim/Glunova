from __future__ import annotations

from datetime import date

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.timezone import now


class UserRole(models.TextChoices):
    PATIENT   = "patient",   "Patient"
    DOCTOR    = "doctor",    "Doctor"
    CAREGIVER = "caregiver", "Caregiver"


class GenderChoices(models.TextChoices):
    MALE   = "Male",   "Male"
    FEMALE = "Female", "Female"


class SmokingStatusChoices(models.TextChoices):
    # Strings match the Kaggle diabetes_prediction_dataset label-encoder vocab.
    NEVER       = "never",       "Never"
    FORMER      = "former",      "Former"
    CURRENT     = "current",     "Current"
    EVER        = "ever",        "Ever"
    NOT_CURRENT = "not current", "Not current"
    NO_INFO     = "No Info",     "No info"


class DiabetesTypeChoices(models.TextChoices):
    TYPE_1      = "Type 1",      "Type 1"
    TYPE_2      = "Type 2",      "Type 2"
    GESTATIONAL = "Gestational", "Gestational"
    PREDIABETES = "Prediabetes", "Prediabetes"


class User(AbstractUser):
    role            = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.PATIENT)
    profile_picture = models.ImageField(upload_to="profile_pictures/", null=True, blank=True)


class PatientProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="patient_profile"
    )

    # Demographics
    date_of_birth  = models.DateField(null=True, blank=True)
    gender         = models.CharField(max_length=10, choices=GenderChoices.choices, null=True, blank=True)
    height_cm      = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    weight_kg      = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    # Comorbidities
    hypertension   = models.BooleanField(null=True, blank=True)
    heart_disease  = models.BooleanField(null=True, blank=True)
    smoking_status = models.CharField(max_length=20, choices=SmokingStatusChoices.choices, null=True, blank=True)

    # Diabetes-specific
    diabetes_type       = models.CharField(
        max_length=20, choices=DiabetesTypeChoices.choices, default=DiabetesTypeChoices.TYPE_2
    )
    hba1c_level         = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    blood_glucose_level = models.IntegerField(null=True, blank=True)
    allergies           = models.JSONField(default=list)

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
        h = float(self.height_cm) / 100.0
        return round(float(self.weight_kg) / (h * h), 2)

    def __str__(self):
        return f"PatientProfile(user={self.user_id})"


class DoctorProfile(models.Model):
    user                 = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="doctor_profile"
    )
    specialization       = models.CharField(max_length=100, blank=True)
    license_number       = models.CharField(max_length=64, blank=True)
    hospital_affiliation = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"DoctorProfile(user={self.user_id})"


class CaregiverProfile(models.Model):
    user            = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="caregiver_profile"
    )
    relationship    = models.CharField(max_length=50, blank=True)  # e.g. "spouse", "parent"
    is_professional = models.BooleanField(default=False)

    def __str__(self):
        return f"CaregiverProfile(user={self.user_id})"
