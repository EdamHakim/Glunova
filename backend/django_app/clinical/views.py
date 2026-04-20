from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.access import can_access_patient_documents, parse_patient_pk, patient_exists
from monitoring.models import PatientMedication

from .serializers import PatientMedicationSerializer


def _medication_group_key(item: PatientMedication) -> tuple[str, str, str, str, str]:
    canonical_name = (item.name_display or item.name_raw or "").strip().lower()
    return (
        (item.rxcui or "").strip().lower(),
        canonical_name,
        (item.dosage or "").strip().lower(),
        (item.frequency or "").strip().lower(),
        (item.route or "").strip().lower(),
    )


def _source_priority(item: PatientMedication) -> tuple[int, object, object]:
    return (
        1 if item.source_document.mime_type.startswith("image/") else 0,
        item.updated_at,
        item.created_at,
    )


class PatientMedicationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        raw_patient_id = request.query_params.get("patient_id")
        if not raw_patient_id:
            return Response({"detail": "patient_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        patient_id = parse_patient_pk(raw_patient_id)
        if patient_id is None:
            return Response({"detail": "patient_id must be a positive integer"}, status=status.HTTP_400_BAD_REQUEST)
        if not patient_exists(patient_id):
            return Response({"detail": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)
        if not can_access_patient_documents(request.user, patient_id):
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        items = list(
            PatientMedication.objects.filter(patient_id=patient_id)
            .select_related("source_document")
            .order_by("-updated_at", "-created_at", "id")
        )
        deduped: list[PatientMedication] = []
        seen: dict[tuple[str, str, str, str, str], PatientMedication] = {}
        source_counts: dict[tuple[str, str, str, str, str], int] = {}
        for item in items:
            key = _medication_group_key(item)
            source_counts[key] = source_counts.get(key, 0) + 1
            existing = seen.get(key)
            if existing is None:
                seen[key] = item
                deduped.append(item)
                continue
            if _source_priority(item) > _source_priority(existing):
                seen[key] = item
                deduped[deduped.index(existing)] = item

        for item in deduped:
            item.source_document_count = source_counts[_medication_group_key(item)]

        serializer = PatientMedicationSerializer(deduped, many=True, context={"request": request})
        return Response({"items": serializer.data, "total": len(deduped)})
