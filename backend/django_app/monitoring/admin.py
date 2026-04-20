from django.contrib import admin

from .models import DiseaseProgression, HealthAlert, MonitoringLog, PatientMedication, RiskAssessment


@admin.register(MonitoringLog)
class MonitoringLogAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "source", "created_at")
    search_fields = ("patient__username", "source")


@admin.register(PatientMedication)
class PatientMedicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "name_raw",
        "name_display",
        "rxcui",
        "verification_status",
        "source_document",
        "updated_at",
    )
    list_filter = ("verification_status",)
    search_fields = (
        "patient__username",
        "name_raw",
        "name_display",
        "rxcui",
        "source_document__original_filename",
    )
    readonly_fields = ("created_at", "updated_at")


admin.site.register(RiskAssessment)
admin.site.register(HealthAlert)
admin.site.register(DiseaseProgression)
