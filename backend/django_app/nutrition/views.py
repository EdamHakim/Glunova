from __future__ import annotations

from django.db.models import Avg, Sum
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from carecircle.models import CarePlan
from documents.access import can_access_patient_documents, parse_patient_pk
from documents.models import PatientCaregiverLink
from nutrition.models import ExerciseSession, FoodSubstitution, MealLog, NutritionGoal, RecoveryPlan


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


class NutritionSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"detail": {"totals": {}, "goal": None, "averages": {}, "substitutions_count": 0}})

        meals = MealLog.objects.filter(patient_id__in=patient_ids)
        latest_goal = NutritionGoal.objects.filter(patient_id__in=patient_ids).order_by("-valid_from", "-created_at").first()
        totals = meals.aggregate(
            calories_kcal=Sum("calories_kcal"),
            carbs_g=Sum("carbs_g"),
            sugar_g=Sum("sugar_g"),
        )
        averages = meals.aggregate(
            gi=Avg("gi"),
            gl=Avg("gl"),
        )
        substitutions_count = FoodSubstitution.objects.filter(patient_id__in=patient_ids).count()

        goal_payload = None
        if latest_goal:
            goal_payload = {
                "target_calories_kcal": latest_goal.target_calories_kcal,
                "target_carbs_g": latest_goal.target_carbs_g,
                "target_protein_g": latest_goal.target_protein_g,
                "target_fat_g": latest_goal.target_fat_g,
                "target_sugar_g": latest_goal.target_sugar_g,
                "valid_from": latest_goal.valid_from.isoformat(),
                "valid_to": latest_goal.valid_to.isoformat() if latest_goal.valid_to else None,
            }

        return Response(
            {
                "totals": {key: float(value or 0) for key, value in totals.items()},
                "goal": goal_payload,
                "averages": {key: float(value or 0) for key, value in averages.items()},
                "substitutions_count": int(substitutions_count),
            }
        )


class MealLogListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"items": [], "total": 0})

        limit = min(max(int(request.query_params.get("limit", "20")), 1), 200)
        meals = MealLog.objects.filter(patient_id__in=patient_ids).select_related("patient").order_by("-logged_at", "-created_at")[:limit]
        payload = [
            {
                "id": meal.id,
                "patient_id": int(meal.patient_id),
                "patient_username": meal.patient.username,
                "input_type": meal.input_type,
                "description": meal.description,
                "carbs_g": meal.carbs_g,
                "calories_kcal": meal.calories_kcal,
                "sugar_g": meal.sugar_g,
                "gi": meal.gi,
                "gl": meal.gl,
                "logged_at": meal.logged_at.isoformat(),
            }
            for meal in meals
        ]
        return Response({"items": payload, "total": len(payload)})

    def post(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.data.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"detail": "Patient context required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Take the first patient_id from the scope (usually the current patient)
        patient_id = patient_ids[0]
        
        data = request.data
        try:
            meal = MealLog.objects.create(
                patient_id=patient_id,
                input_type=data.get("input_type", "photo"),
                description=data.get("description", ""),
                carbs_g=float(data.get("carbs_g", 0)),
                calories_kcal=float(data.get("calories_kcal", 0)),
                sugar_g=float(data.get("sugar_g", 0)),
                gi=float(data.get("gi", 0)),
                gl=float(data.get("gl", 0)),
            )
            return Response({"id": meal.id, "status": "logged"}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


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
