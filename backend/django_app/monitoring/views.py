from __future__ import annotations

from datetime import datetime

import httpx
from django.conf import settings
from django.db.models import Avg, Count, Q, QuerySet
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.access import can_access_patient_documents, parse_patient_pk
from users.models import PatientCaregiverLink, User, UserRole
from users.doctor_scope import patient_ids_for_doctor
from monitoring.models import DiseaseProgression, HealthAlert, MonitoringLog, PatientLabResult, RiskAssessment, PatientMedication
from screening.models import ScreeningResult
from documents.services.storage import create_download_payload


def _health_alerts_for_viewer(user, patient_ids: list[int]) -> QuerySet[HealthAlert]:
    """Risk/clinical alerts for everyone; care-agent posts only for the intended role."""
    qs = HealthAlert.objects.filter(patient_id__in=patient_ids)
    role = getattr(user, "role", None)
    if role == "patient":
        return qs.filter(
            Q(agent_audience__isnull=True) | Q(agent_audience=HealthAlert.AgentAudience.PATIENT)
        )
    if role == "doctor":
        return qs.filter(
            Q(agent_audience__isnull=True) | Q(agent_audience=HealthAlert.AgentAudience.DOCTOR)
        )
    if role == "caregiver":
        return qs.filter(agent_audience__isnull=True)
    return qs.none()


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
        return patient_ids_for_doctor(user), None
    if role == "caregiver":
        ids = list(
            PatientCaregiverLink.objects.filter(caregiver=user, status="accepted")
            .values_list("patient_id", flat=True)
            .distinct()
        )
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
            _health_alerts_for_viewer(request.user, patient_ids)
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
                "is_agent": bool(alert.agent_audience),
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
        for alert in (
            _health_alerts_for_viewer(request.user, patient_ids)
            .select_related("patient")
            .order_by("-triggered_at")[:limit]
        ):
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
        for lab in (
            PatientLabResult.objects.filter(patient_id__in=patient_ids)
            .select_related("patient", "source_document")
            .order_by("-observed_at", "-updated_at", "-created_at")[:limit]
        ):
            entries.append(
                {
                    "type": "lab_result",
                    "timestamp": lab.observed_at or lab.created_at,
                    "patient_id": int(lab.patient_id),
                    "patient_username": lab.patient.username,
                    "title": "Lab Result Recorded",
                    "description": lab.test_name,
                    "value": f"{lab.value}{f' {lab.unit}' if lab.unit else ''}",
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
        tiers_order = ["low", "high", "critical"]
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

        patient_ids = patient_ids_for_doctor(request.user)
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

        alerts_count = _health_alerts_for_viewer(request.user, patient_ids).filter(
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


class DashboardMyPatientsView(APIView):
    """Linked patients for dashboard pickers: doctors (care team link) and caregivers (accepted link)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = getattr(request.user, "role", None)
        if role == UserRole.DOCTOR:
            patient_ids = patient_ids_for_doctor(request.user)
        elif role == UserRole.CAREGIVER:
            patient_ids = list(
                PatientCaregiverLink.objects.filter(caregiver=request.user, status="accepted")
                .values_list("patient_id", flat=True)
                .distinct()
            )
        else:
            return Response(
                {"detail": "Only doctors and caregivers can list linked patients."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not patient_ids:
            return Response({"items": []})

        patients_qs = User.objects.filter(id__in=patient_ids, role=UserRole.PATIENT).only(
            "id", "username", "first_name", "last_name"
        )
        items = [
            {
                "id": int(u.pk),
                "username": u.username,
                "display_name": (u.get_full_name() or "").strip() or u.username,
            }
            for u in patients_qs
        ]
        items.sort(key=lambda row: row["display_name"].lower())
        return Response({"items": items})


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
        
        # Resolve URLs (direct if remote, proxy if local)
        payload = []
        for med in items:
            try:
                storage_info = create_download_payload(med.source_document)
                if storage_info["type"] == "url":
                    doc_url = storage_info["url"]
                    preview_url = storage_info["url"]
                else:
                    doc_url = request.build_absolute_uri(reverse("documents-download", kwargs={"pk": med.source_document_id}))
                    preview_url = request.build_absolute_uri(reverse("documents-preview", kwargs={"pk": med.source_document_id}))
            except Exception:
                doc_url = None
                preview_url = None

            payload.append({
                "id": med.id,
                "patient_id": str(med.patient_id),
                "source_document_id": str(med.source_document_id),
                "source_document_filename": med.source_document.original_filename,
                "source_document_created_at": med.source_document.created_at.isoformat(),
                "source_document_mime_type": med.source_document.mime_type,
                "source_document_url": doc_url,
                "source_document_preview_url": preview_url,
                "source_document_count": 1,
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
            })
        return Response({"items": payload, "total": len(payload)})


class PatientLabResultsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"items": [], "total": 0})

        items = (
            PatientLabResult.objects.filter(patient_id__in=patient_ids)
            .select_related("source_document")
            .order_by("-observed_at", "-updated_at", "-created_at")
        )

        # Resolve URLs (direct if remote, proxy if local)
        payload = []
        for row in items:
            try:
                storage_info = create_download_payload(row.source_document)
                if storage_info["type"] == "url":
                    doc_url = storage_info["url"]
                    preview_url = storage_info["url"]
                else:
                    doc_url = request.build_absolute_uri(reverse("documents-download", kwargs={"pk": row.source_document_id}))
                    preview_url = request.build_absolute_uri(reverse("documents-preview", kwargs={"pk": row.source_document_id}))
            except Exception:
                doc_url = None
                preview_url = None

            payload.append({
                "id": row.id,
                "patient_id": str(row.patient_id),
                "source_document_id": str(row.source_document_id),
                "source_document_filename": row.source_document.original_filename,
                "source_document_created_at": row.source_document.created_at.isoformat(),
                "source_document_mime_type": row.source_document.mime_type,
                "source_document_url": doc_url,
                "source_document_preview_url": preview_url,
                "test_name": row.test_name,
                "normalized_name": row.normalized_name,
                "value": row.value,
                "numeric_value": row.numeric_value,
                "unit": row.unit,
                "reference_range": row.reference_range,
                "observed_at": row.observed_at.isoformat() if row.observed_at else None,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            })
        return Response({"items": payload, "total": len(payload)})


_TIER_RANK = {"low": 0, "high": 1, "critical": 2}
_MODALITY_LABELS = {
    "retinopathy": "Diabetic Retinopathy",
    "infrared": "Thermal Foot",
    "tongue": "Tongue",
    "foot_ulcer": "Foot Ulcer (DFU)",
    "cataract": "Cataract",
    "voice": "Voice",
    "fusion": "Fusion",
}


def _trend_label(current_score: float, previous_score: float | None, threshold: float = 0.10) -> str:
    """Symmetric numeric trend (used for Risk Stratification + most modalities)."""
    if previous_score is None:
        return "first"
    delta = current_score - previous_score
    if delta > threshold:
        return "worsening"
    if delta < -threshold:
        return "improving"
    return "stable"


class MonitoringRiskStratificationView(APIView):
    """Hero card data for the Monitoring page — current tier + trend vs previous."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"current": None, "previous": None})

        # Patient role: their own latest. Doctor/caregiver with no patient_id: latest assessed across scope.
        qs = (
            RiskAssessment.objects
            .filter(patient_id__in=patient_ids)
            .select_related("patient")
            .order_by("-assessed_at", "-created_at")
        )
        rows = list(qs[:2])
        if not rows:
            return Response({"current": None, "previous": None})

        current = rows[0]
        previous = rows[1] if len(rows) > 1 else None

        drivers = current.drivers if isinstance(current.drivers, dict) else {}
        recommendation = drivers.get("recommendation") or "No recommendation available."
        n_models_used = drivers.get("n_models_used", 0)
        reasons = drivers.get("reasons") or []
        if not isinstance(reasons, list):
            reasons = []
        override_reason = drivers.get("override_reason")

        trend = _trend_label(float(current.score), float(previous.score) if previous else None)
        delta_score = float(current.score) - float(previous.score) if previous else None

        return Response({
            "current": {
                "id": current.id,
                "patient_id": int(current.patient_id),
                "patient_username": current.patient.username,
                "tier": current.tier,
                "score": float(current.score),
                "confidence": float(current.confidence),
                "recommendation": recommendation,
                "reasons": [str(r) for r in reasons],
                "override_reason": override_reason,
                "n_models_used": int(n_models_used) if isinstance(n_models_used, int) else 0,
                "assessed_at": current.assessed_at.isoformat(),
                "relative_time": _format_relative_time(current.assessed_at),
            },
            "previous": {
                "tier": previous.tier,
                "score": float(previous.score),
                "assessed_at": previous.assessed_at.isoformat(),
            } if previous else None,
            "trend": trend,
            "delta_score": delta_score,
        })


class MonitoringScreeningHistoryView(APIView):
    """Longitudinal screening results grouped by modality, with AI-detected trend."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"modalities": [], "total_scans": 0})

        # Pull the last N scans per modality. We collect all then group in Python
        # to keep the SQL portable; bounded by limit so the payload stays small.
        per_modality_limit = 5
        rows = (
            ScreeningResult.objects
            .filter(patient_id__in=patient_ids)
            .order_by("-captured_at", "-created_at")
            .values("modality", "score", "risk_label", "model_version", "metadata", "captured_at")[:200]
        )

        grouped: dict[str, list[dict]] = {}
        for r in rows:
            modality = r["modality"]
            if modality not in grouped:
                grouped[modality] = []
            if len(grouped[modality]) < per_modality_limit:
                grouped[modality].append({
                    "score": float(r["score"]),
                    "risk_label": r["risk_label"],
                    "model_version": r["model_version"],
                    "metadata": r["metadata"] if isinstance(r["metadata"], dict) else {},
                    "captured_at": r["captured_at"].isoformat(),
                    "relative_time": _format_relative_time(r["captured_at"]),
                })

        modalities_payload = []
        for modality, scans in grouped.items():
            latest = scans[0]
            previous_score = float(scans[1]["score"]) if len(scans) > 1 else None
            trend = _trend_label(latest["score"], previous_score)
            delta = latest["score"] - previous_score if previous_score is not None else None

            # Sparkline = list of scores oldest→newest (reverse since we collected newest→oldest).
            sparkline = [s["score"] for s in reversed(scans)]

            modalities_payload.append({
                "modality": modality,
                "label": _MODALITY_LABELS.get(modality, modality.replace("_", " ").title()),
                "scans": scans,                       # newest first
                "latest": latest,
                "trend": trend,
                "delta_score": delta,
                "sparkline": sparkline,               # oldest first
                "scan_count": len(scans),
            })

        # Sort modalities by most recent activity.
        modalities_payload.sort(key=lambda m: m["latest"]["captured_at"], reverse=True)

        return Response({
            "modalities": modalities_payload,
            "total_scans": sum(m["scan_count"] for m in modalities_payload),
        })


class MonitoringDiseaseProgressionView(APIView):
    """Patient-level disease progression — risk score over time + summary trend."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"assessments": [], "trend": "first"})

        # Last N assessments, oldest -> newest for the chart.
        rows = list(
            RiskAssessment.objects
            .filter(patient_id__in=patient_ids)
            .order_by("-assessed_at", "-created_at")[:20]
        )
        rows.reverse()  # chronological order for the chart

        if not rows:
            return Response({"assessments": [], "trend": "first"})

        assessments = []
        for r in rows:
            drivers = r.drivers if isinstance(r.drivers, dict) else {}
            assessments.append({
                "id": r.id,
                "tier": r.tier,
                "score": float(r.score),
                "confidence": float(r.confidence),
                "n_models_used": int(drivers.get("n_models_used", 0)),
                "assessed_at": r.assessed_at.isoformat(),
                "relative_time": _format_relative_time(r.assessed_at),
            })

        first = assessments[0]
        last = assessments[-1]
        # delta_score / delta_confidence kept on first->last basis for KPI display
        # ("how far the patient has drifted since the very first assessment"), but
        # the trend label itself is computed on last vs PREVIOUS (clinical "right now").
        delta_score = last["score"] - first["score"]
        delta_confidence = last["confidence"] - first["confidence"]

        # Trend reflects the patient's CURRENT trajectory (clinical "how is the
        # patient doing now?"), not their full history. We compare the latest
        # assessment to the immediately previous one:
        #   - tier change always wins (a fresh escalation HIGH->CRITICAL is
        #     immediately flagged WORSENING regardless of score, a de-escalation
        #     CRITICAL->HIGH is IMPROVING even if score is still high)
        #   - same tier -> use score delta with a 10% threshold as tie-breaker
        # This keeps the label consistent with the Risk Stratification card and
        # avoids freezing a patient as "WORSENING" forever because of an old
        # escalation they have since recovered from.
        _TIER_ORDER = {"low": 0, "high": 1, "critical": 2}

        if len(assessments) < 2:
            trend = "first"
        else:
            previous = assessments[-2]
            prev_rank = _TIER_ORDER.get(previous["tier"], 0)
            last_rank = _TIER_ORDER.get(last["tier"], 0)
            recent_score_delta = last["score"] - previous["score"]

            if last_rank > prev_rank:
                trend = "worsening"
            elif last_rank < prev_rank:
                trend = "improving"
            elif recent_score_delta > 0.10:
                trend = "worsening"
            elif recent_score_delta < -0.10:
                trend = "improving"
            else:
                trend = "stable"

        # Tier journey = unique tiers in chronological order (e.g. low -> high -> critical).
        tier_journey: list[str] = []
        for a in assessments:
            if not tier_journey or tier_journey[-1] != a["tier"]:
                tier_journey.append(a["tier"])

        # Count only UPWARD tier transitions (low->high, high->critical, etc.).
        # A round-trip low->high->low has 1 escalation, not 2.
        tier_escalations = 0
        for prev_tier, curr_tier in zip(tier_journey, tier_journey[1:]):
            if _TIER_ORDER.get(curr_tier, 0) > _TIER_ORDER.get(prev_tier, 0):
                tier_escalations += 1

        # Period in days (rough)
        period_seconds = (rows[-1].assessed_at - rows[0].assessed_at).total_seconds()
        period_days = max(1, int(period_seconds // 86400))

        # Active alerts count for this patient scope
        active_alerts = _health_alerts_for_viewer(request.user, patient_ids).filter(
            status=HealthAlert.Status.ACTIVE,
        ).count()

        recent_score_delta = (
            last["score"] - assessments[-2]["score"] if len(assessments) >= 2 else None
        )

        return Response({
            "assessments": assessments,
            "trend": trend,
            "delta_score": delta_score,
            "recent_score_delta": recent_score_delta,
            "delta_confidence": delta_confidence,
            "tier_journey": tier_journey,
            "tier_escalations": tier_escalations,
            "n_assessments": len(assessments),
            "period_days": period_days,
            "modalities_evolution": {
                "first": first["n_models_used"],
                "last": last["n_models_used"],
            },
            "confidence_evolution": {
                "first": first["confidence"],
                "last": last["confidence"],
                "delta": delta_confidence,
            },
            "active_alerts_count": int(active_alerts),
        })


class RefreshRiskView(APIView):
    """Trigger a fresh fusion risk assessment for the authenticated patient."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if getattr(user, "role", None) != "patient":
            return Response(
                {"detail": "Only patients can refresh their own risk assessment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        patient_id = int(user.pk)
        ai_url = getattr(settings, "AI_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
        url = f"{ai_url}/monitoring/internal/refresh-tier/{patient_id}"

        try:
            resp = httpx.post(url, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            return Response(
                {"detail": f"Risk refresh failed: {exc.response.text}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            return Response(
                {"detail": f"Risk refresh unavailable: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({
            "tier": data.get("tier"),
            "score": data.get("score"),
            "health_alert_id": data.get("health_alert_id"),
        })
