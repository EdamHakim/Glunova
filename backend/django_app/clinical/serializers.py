from __future__ import annotations

from rest_framework import serializers

from .models import PatientMedication


class PatientMedicationSerializer(serializers.ModelSerializer):
    patient_id = serializers.SerializerMethodField()
    source_document_id = serializers.SerializerMethodField()
    source_document_filename = serializers.SerializerMethodField()
    source_document_created_at = serializers.SerializerMethodField()

    class Meta:
        model = PatientMedication
        fields = (
            "id",
            "patient_id",
            "source_document_id",
            "source_document_filename",
            "source_document_created_at",
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
