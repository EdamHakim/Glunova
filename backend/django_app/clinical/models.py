from django.conf import settings
from django.db import models


class CarePlan(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="care_plans")
    doctor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="assigned_care_plans")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MonitoringLog(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="monitoring_logs")
    source = models.CharField(max_length=50)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
