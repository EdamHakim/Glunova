from __future__ import annotations

from datetime import datetime

from django.db.models import Avg, Count, QuerySet
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.access import can_access_patient_documents, parse_patient_pk
from documents.models import PatientCaregiverLink
from carecircle.models import CarePlan
from monitoring.models import DiseaseProgression, HealthAlert, MonitoringLog, RiskAssessment, PatientMedication
from screening.models import ScreeningResult
from users.models import UserRole


def _resolve_patient_scope(user, raw_patient_id: str | None) -> tuple[list[int] | None, Response | None]:
    role = getattr(user, "role", None)
    if raw_patient_id:
        patient_id = parse_patient_pk(raw_patient_id)
        if patient_id is None:
            return None, Response({"detail": "patient_id must be a positive integer"}, status=status.HTTP_400_BAD_REQUEST)
        if not can_access_patient_documents(user, patient_id):
            return None, Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        return [patient_id], None

    if role == "patient":
        return [int(user.pk)], None
    if role == "doctor":
        ids = list(CarePlan.objects.filter(doctor=user).values_list("patient_id", flat=True).distinct())
        return ids, None
    if role == "caregiver":
        ids = list(PatientCaregiverLink.objects.filter(caregiver=user).values_list("patient_id", flat=True).distinct())
        return ids, None
    return [], None


def _format_relative_time(ts: datetime) -> str:
    now = timezone.now()
    delta = now - ts
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} min ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = seconds // 86400
    return f"{days} day{'s' if days != 1 else ''} ago"


class MonitoringAlertsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"items": [], "total": 0})

        items = (
            HealthAlert.objects.filter(patient_id__in=patient_ids)
            .select_related("patient")
            .order_by("-triggered_at", "-created_at")[:100]
        )
        payload = [
            {
                "id": alert.id,
                "patient_id": int(alert.patient_id),
                "patient_username": alert.patient.username,
                "severity": alert.severity,
                "title": alert.title,
                "message": alert.message,
                "status": alert.status,
                "triggered_at": alert.triggered_at.isoformat(),
                "relative_time": _format_relative_time(alert.triggered_at),
            }
            for alert in items
        ]
        return Response({"items": payload, "total": len(payload)})


class MonitoringTimelineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"items": [], "total": 0})

        limit = int(request.query_params.get("limit", "50"))
        limit = min(max(limit, 1), 200)

        entries: list[dict] = []
        for result in ScreeningResult.objects.filter(patient_id__in=patient_ids).select_related("patient").order_by("-captured_at")[:limit]:
            entries.append(
                {
                    "type": "screening",
                    "timestamp": result.captured_at,
                    "patient_id": int(result.patient_id),
                    "patient_username": result.patient.username,
                    "title": "Screening Completed",
                    "description": f"{result.modality} -> {result.risk_label}",
                    "value": f"Score: {result.score:.2f}",
                }
            )
        for progression in (
            DiseaseProgression.objects.filter(patient_id__in=patient_ids).select_related("patient").order_by("-recorded_at")[:limit]
        ):
            entries.append(
                {
                    "type": "progression",
                    "timestamp": progression.recorded_at,
                    "patient_id": int(progression.patient_id),
                    "patient_username": progression.patient.username,
                    "title": "Progression Update",
                    "description": progression.indicator.replace("_", " ").title(),
                    "value": f"{progression.trend} ({progression.value:.2f})",
                }
            )
        for alert in HealthAlert.objects.filter(patient_id__in=patient_ids).select_related("patient").order_by("-triggered_at")[:limit]:
            entries.append(
                {
                    "type": "alert",
                    "timestamp": alert.triggered_at,
                    "patient_id": int(alert.patient_id),
                    "patient_username": alert.patient.username,
                    "title": alert.title,
                    "description": alert.message,
                    "value": alert.severity,
                }
            )
        for log in MonitoringLog.objects.filter(patient_id__in=patient_ids).select_related("patient").order_by("-created_at")[:limit]:
            entries.append(
                {
                    "type": "log",
                    "timestamp": log.created_at,
                    "patient_id": int(log.patient_id),
                    "patient_username": log.patient.username,
                    "title": "Monitoring Log",
                    "description": log.source,
                    "value": str(log.payload.get("risk_score", "")),
                }
            )

        entries.sort(key=lambda item: item["timestamp"], reverse=True)
        entries = entries[:limit]
        payload = [
            {
                **item,
                "timestamp": item["timestamp"].isoformat(),
                "relative_time": _format_relative_time(item["timestamp"]),
            }
            for item in entries
        ]
        return Response({"items": payload, "total": len(payload)})


class MonitoringProgressionSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"tiers": [], "total_patients": 0})

        latest_ids = (
            RiskAssessment.objects.filter(patient_id__in=patient_ids)
            .order_by("patient_id", "-assessed_at", "-created_at")
            .distinct("patient_id")
            .values_list("id", flat=True)
        )
        latest_qs: QuerySet[RiskAssessment] = RiskAssessment.objects.filter(id__in=latest_ids)

        counts = {row["tier"]: row["count"] for row in latest_qs.values("tier").annotate(count=Count("id"))}
        avg_scores = {row["tier"]: row["avg"] for row in latest_qs.values("tier").annotate(avg=Avg("score"))}
        total = len(patient_ids)
        tiers_order = ["low", "moderate", "high", "critical"]
        tiers = [
            {
                "tier": tier,
                "count": int(counts.get(tier, 0)),
                "avg_score": float(avg_scores.get(tier) or 0),
                "percentage": float((counts.get(tier, 0) / total) * 100 if total else 0),
            }
            for tier in tiers_order
        ]
        return Response({"tiers": tiers, "total_patients": total})


class DashboardOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "role", None) != UserRole.DOCTOR:
            return Response({"detail": "Doctor access required"}, status=status.HTTP_403_FORBIDDEN)

        patient_ids = list(CarePlan.objects.filter(doctor=request.user).values_list("patient_id", flat=True).distinct())
        if not patient_ids:
            return Response({"stats": {}, "trend": [], "recent_patients": []})

        latest_ids = (
            RiskAssessment.objects.filter(patient_id__in=patient_ids)
            .order_by("patient_id", "-assessed_at", "-created_at")
            .distinct("patient_id")
            .values_list("id", flat=True)
        )
        latest_assessments = list(
            RiskAssessment.objects.filter(id__in=latest_ids).select_related("patient").order_by("-assessed_at")
        )

        alerts_count = HealthAlert.objects.filter(
            patient_id__in=patient_ids,
            status=HealthAlert.Status.ACTIVE,
        ).count()
        pending_screenings = max(0, len(patient_ids) - ScreeningResult.objects.filter(patient_id__in=patient_ids).values("patient_id").distinct().count())
        avg_risk_score = (
            sum(item.score for item in latest_assessments) / len(latest_assessments)
            if latest_assessments
            else 0.0
        )

        recent_rows = (
            RiskAssessment.objects.filter(patient_id__in=patient_ids)
            .select_related("patient")
            .order_by("-assessed_at", "-created_at")[:7]
        )
        trend = [
            {
                "date": row.assessed_at.strftime("%b %d"),
                "risk_score": float(row.score),
                "confidence": float(row.confidence),
            }
            for row in reversed(list(recent_rows))
        ]

        def _tier_label(score: float) -> str:
            if score >= 0.75:
                return "Critical"
            if score >= 0.55:
                return "High"
            if score >= 0.35:
                return "Moderate"
            return "Low"

        recent_patients = [
            {
                "id": int(item.patient_id),
                "name": item.patient.username,
                "risk_level": _tier_label(item.score),
                "last_assessment": item.assessed_at.isoformat(),
                "status": "Requires Follow-up" if item.score >= 0.55 else "Monitoring",
            }
            for item in latest_assessments[:5]
        ]

        return Response(
            {
                "stats": {
                    "active_patients": len(patient_ids),
                    "pending_screenings": int(pending_screenings),
                    "alerts": int(alerts_count),
                    "avg_risk_score": round(float(avg_risk_score) * 100, 1),
                },
                "trend": trend,
                "recent_patients": recent_patients,
            }
        )


class PatientMedicationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"items": [], "total": 0})

        items = (
            PatientMedication.objects.filter(patient_id__in=patient_ids)
            .select_related("source_document")
            .order_by("-updated_at", "-created_at")
        )
        
        payload = [
            {
                "id": med.id,
                "patient_id": str(med.patient_id),
                "source_document_id": str(med.source_document_id),
                "source_document_filename": med.source_document.original_filename,
                "source_document_created_at": med.source_document.created_at.isoformat(),
                "source_document_mime_type": med.source_document.mime_type,
                "source_document_preview_url": None, # Should be generated if needed
                "source_document_count": 1, # TODO: implement aggregation if needed
                "name_raw": med.name_raw,
                "name_display": med.name_display,
                "rxcui": med.rxcui,
                "dosage": med.dosage,
                "frequency": med.frequency,
                "duration": med.duration,
                "route": med.route,
                "verification_status": med.verification_status,
                "verification_detail": med.verification_detail,
                "created_at": med.created_at.isoformat(),
                "updated_at": med.updated_at.isoformat(),
            }
            for med in items
        ]
        return Response({"items": payload, "total": len(payload)})
