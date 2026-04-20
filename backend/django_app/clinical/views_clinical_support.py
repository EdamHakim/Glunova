from __future__ import annotations

from django.db.models import Count
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from carecircle.models import CarePlan
from clinical.models import ClinicalCaseReview, CrisisEscalation, ImagingAnalysis
from monitoring.models import RiskAssessment


def _assigned_patient_ids(user) -> list[int]:
    return list(CarePlan.objects.filter(doctor=user).values_list("patient_id", flat=True).distinct())


class ClinicalSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids = _assigned_patient_ids(request.user)
        if not patient_ids:
            return Response({"critical_cases": 0, "high_risk": 0, "stable": 0, "pending_review": 0})

        latest_assessment_ids = (
            RiskAssessment.objects.filter(patient_id__in=patient_ids)
            .order_by("patient_id", "-assessed_at", "-created_at")
            .distinct("patient_id")
            .values_list("id", flat=True)
        )
        latest = RiskAssessment.objects.filter(id__in=latest_assessment_ids)
        tier_counts = {row["tier"]: row["count"] for row in latest.values("tier").annotate(count=Count("id"))}
        pending_review = ImagingAnalysis.objects.filter(patient_id__in=patient_ids).count()
        critical_cases = CrisisEscalation.objects.filter(patient_id__in=patient_ids, status__in=["open", "in_review"]).count()

        return Response(
            {
                "critical_cases": int(critical_cases),
                "high_risk": int(tier_counts.get("high", 0) + tier_counts.get("critical", 0)),
                "stable": int(tier_counts.get("low", 0)),
                "pending_review": int(pending_review),
            }
        )


class ClinicalPrioritiesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids = _assigned_patient_ids(request.user)
        if not patient_ids:
            return Response({"items": [], "total": 0})

        cases = (
            ClinicalCaseReview.objects.filter(patient_id__in=patient_ids)
            .select_related("patient")
            .order_by("-created_at")[:50]
        )
        payload = [
            {
                "id": item.id,
                "patient_id": int(item.patient_id),
                "patient_name": item.patient.username,
                "priority": item.priority,
                "summary": item.summary,
                "status": item.status,
                "created_at": item.created_at.isoformat(),
            }
            for item in cases
        ]
        return Response({"items": payload, "total": len(payload)})


class ClinicalImagingQueueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids = _assigned_patient_ids(request.user)
        if not patient_ids:
            return Response({"items": [], "total": 0})

        rows = (
            ImagingAnalysis.objects.filter(patient_id__in=patient_ids)
            .select_related("patient")
            .order_by("-captured_at", "-created_at")[:100]
        )
        payload = [
            {
                "id": row.id,
                "patient_id": int(row.patient_id),
                "patient_name": row.patient.username,
                "analysis_type": row.analysis_type,
                "severity_grade": int(row.severity_grade),
                "confidence": float(row.confidence),
                "captured_at": row.captured_at.isoformat(),
            }
            for row in rows
        ]
        return Response({"items": payload, "total": len(payload)})


class ClinicalPreconsultationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids = _assigned_patient_ids(request.user)
        if not patient_ids:
            return Response({"items": [], "total": 0})

        cases = (
            ClinicalCaseReview.objects.filter(patient_id__in=patient_ids)
            .select_related("patient")
            .order_by("-created_at")[:20]
        )
        payload = [
            {
                "id": item.id,
                "patient_id": int(item.patient_id),
                "patient_name": item.patient.username,
                "chief_complaint": item.summary,
                "recommendation": "Follow-up review recommended",
                "priority": item.priority,
                "created_at": item.created_at.isoformat(),
            }
            for item in cases
        ]
        return Response({"items": payload, "total": len(payload)})
