from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.access import can_access_patient_documents, parse_patient_pk, patient_exists

from .models import PatientMedication
from .serializers import PatientMedicationSerializer


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

        items = (
            PatientMedication.objects.filter(patient_id=patient_id)
            .select_related("source_document")
            .order_by("-updated_at", "-created_at", "id")
        )
        serializer = PatientMedicationSerializer(items, many=True)
        return Response({"items": serializer.data, "total": items.count()})
