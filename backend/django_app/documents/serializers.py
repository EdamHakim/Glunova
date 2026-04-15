from __future__ import annotations

from rest_framework import serializers

from .models import MedicalDocument


class MedicalDocumentSerializer(serializers.ModelSerializer):
    patient_id = serializers.SerializerMethodField()
    raw_ocr_text = serializers.SerializerMethodField()

    class Meta:
        model = MedicalDocument
        fields = (
            "id",
            "patient_id",
            "original_filename",
            "mime_type",
            "document_type_detected",
            "processing_status",
            "llm_refinement_status",
            "extracted_json",
            "raw_ocr_text",
            "created_at",
        )
        read_only_fields = fields

    def get_patient_id(self, obj: MedicalDocument) -> str:
        return str(obj.patient_id)

    def get_raw_ocr_text(self, obj: MedicalDocument) -> str | None:
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if user and getattr(user, "role", None) == "caregiver":
            return None
        return obj.raw_ocr_text or None

class MedicalDocumentListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for document lists (excludes heavy OCR text and extraction).
    """
    patient_id = serializers.SerializerMethodField()

    class Meta:
        model = MedicalDocument
        fields = (
            "id",
            "patient_id",
            "original_filename",
            "mime_type",
            "document_type_detected",
            "processing_status",
            "llm_refinement_status",
            "created_at",
        )

    def get_patient_id(self, obj: MedicalDocument) -> str:
        return str(obj.patient_id)
