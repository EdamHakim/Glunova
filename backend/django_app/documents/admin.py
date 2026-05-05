from django.contrib import admin

from users.models import PatientCaregiverLink

from .models import MedicalDocument


@admin.register(PatientCaregiverLink)
class PatientCaregiverLinkAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "caregiver", "status", "created_at", "responded_at")
    search_fields = ("patient__username", "caregiver__username")
    list_filter = ("status",)


@admin.register(MedicalDocument)
class MedicalDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "original_filename",
        "patient",
        "processing_status",
        "llm_refinement_status",
        "created_at",
    )
    list_filter = ("processing_status", "llm_refinement_status")
    readonly_fields = ("id", "created_at", "updated_at")
