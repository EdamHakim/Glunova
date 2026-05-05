import uuid

from django.conf import settings
from django.db import models


class MedicalDocument(models.Model):
    class ProcessingStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class LlmRefinementStatus(models.TextChoices):
        OK = "ok", "Ok"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="medical_documents",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_medical_documents",
    )
    original_filename = models.CharField(max_length=512)
    mime_type = models.CharField(max_length=128)
    storage_path = models.CharField(max_length=1024)
    raw_ocr_text = models.TextField(blank=True)
    extracted_json = models.JSONField(default=dict)
    extracted_json_rules = models.JSONField(default=dict)
    llm_provider_used = models.CharField(max_length=64, null=True, blank=True)
    llm_refinement_status = models.CharField(
        max_length=16,
        choices=LlmRefinementStatus.choices,
        default=LlmRefinementStatus.SKIPPED,
    )
    document_type_detected = models.CharField(max_length=64, null=True, blank=True)
    processing_status = models.CharField(
        max_length=16,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.id})"
