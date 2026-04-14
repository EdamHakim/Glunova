from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    PATIENT = "patient", "Patient"
    DOCTOR = "doctor", "Doctor"
    CAREGIVER = "caregiver", "Caregiver"


class User(AbstractUser):
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.PATIENT)

