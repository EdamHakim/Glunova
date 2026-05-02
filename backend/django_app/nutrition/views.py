from __future__ import annotations

from django.db.models import Avg, Sum
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from carecircle.models import CarePlan
from documents.access import can_access_patient_documents, parse_patient_pk
from documents.models import PatientCaregiverLink
from nutrition.models import ExerciseSession, NutritionGoal, RecoveryPlan


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



class ExercisePlanListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"items": [], "total": 0})

        limit = min(max(int(request.query_params.get("limit", "20")), 1), 200)
        sessions = (
            ExerciseSession.objects.filter(patient_id__in=patient_ids)
            .select_related("patient")
            .prefetch_related("recovery_plan")
            .order_by("-scheduled_for", "-created_at")[:limit]
        )
        recovery_by_session = {plan.exercise_session_id: plan for plan in RecoveryPlan.objects.filter(exercise_session__in=sessions)}
        payload = []
        for session in sessions:
            recovery = recovery_by_session.get(session.id)
            payload.append(
                {
                    "id": session.id,
                    "patient_id": int(session.patient_id),
                    "patient_username": session.patient.username,
                    "title": session.title,
                    "intensity": session.intensity,
                    "duration_minutes": session.duration_minutes,
                    "scheduled_for": session.scheduled_for.isoformat(),
                    "status": session.status,
                    "notes": session.notes,
                    "recovery_plan": (
                        {
                            "snack_suggestion": recovery.snack_suggestion,
                            "hydration_ml": recovery.hydration_ml,
                            "glucose_recheck_minutes": recovery.glucose_recheck_minutes,
                            "next_session_tip": recovery.next_session_tip,
                        }
                        if recovery
                        else None
                    ),
                }
            )
        return Response({"items": payload, "total": len(payload)})
