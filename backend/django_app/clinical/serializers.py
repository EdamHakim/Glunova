from __future__ import annotations

from django.urls import reverse
from rest_framework import serializers

from .models import PatientMedication


class PatientMedicationSerializer(serializers.ModelSerializer):
    patient_id = serializers.SerializerMethodField()
    source_document_id = serializers.SerializerMethodField()
    source_document_filename = serializers.SerializerMethodField()
    source_document_created_at = serializers.SerializerMethodField()
    source_document_mime_type = serializers.SerializerMethodField()
    source_document_preview_url = serializers.SerializerMethodField()
    source_document_count = serializers.SerializerMethodField()

    class Meta:
        model = PatientMedication
        fields = (
            "id",
            "patient_id",
            "source_document_id",
            "source_document_filename",
            "source_document_created_at",
            "source_document_mime_type",
            "source_document_preview_url",
            "source_document_count",
            "name_raw",
            "name_display",
            "rxcui",
            "dosage",
            "frequency",
            "duration",
            "route",
            "verification_status",
            "verification_detail",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_patient_id(self, obj: PatientMedication) -> str:
        return str(obj.patient_id)

    def get_source_document_id(self, obj: PatientMedication) -> str:
        return str(obj.source_document_id)

    def get_source_document_filename(self, obj: PatientMedication) -> str:
        return obj.source_document.original_filename

    def get_source_document_created_at(self, obj: PatientMedication) -> str:
        return obj.source_document.created_at.isoformat()

    def get_source_document_mime_type(self, obj: PatientMedication) -> str:
        return obj.source_document.mime_type

    def get_source_document_preview_url(self, obj: PatientMedication) -> str | None:
        if not obj.source_document.mime_type.startswith("image/"):
            return None
        request = self.context.get("request")
        path = reverse("documents-preview", kwargs={"pk": obj.source_document_id})
        return request.build_absolute_uri(path) if request else path

    def get_source_document_count(self, obj: PatientMedication) -> int:
        return int(getattr(obj, "source_document_count", 1))
