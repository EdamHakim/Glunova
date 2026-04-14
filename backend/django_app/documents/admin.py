from django.contrib import admin

from .models import MedicalDocument, PatientCaregiverLink


@admin.register(PatientCaregiverLink)
class PatientCaregiverLinkAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "caregiver", "created_at")
    search_fields = ("patient__username", "caregiver__username")


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
