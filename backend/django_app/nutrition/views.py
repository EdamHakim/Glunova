from __future__ import annotations

from datetime import date, timedelta

import httpx
from django.conf import settings
from django.db.models import Avg, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from carecircle.models import CarePlan
from documents.access import can_access_patient_documents, parse_patient_pk
from documents.models import PatientCaregiverLink
from nutrition.models import ExerciseSession, Meal, NutritionGoal, RecoveryPlan, WeeklyMealPlan

FASTAPI_BASE = getattr(settings, "AI_SERVICE_URL", "http://localhost:8001")

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


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


# ── Meal Plan helpers ─────────────────────────────────────────────────────────

def _build_clinical_profile(patient, cuisine: str) -> dict:
    """Assemble the MealPlanRequest payload from a patient's DB records."""
    from monitoring.models import PatientMedication

    meds = list(
        PatientMedication.objects.filter(patient=patient, verification_status="matched")
        .values_list("name_display", flat=True)
    )
    goal = NutritionGoal.objects.filter(patient=patient).order_by("-valid_from").first()
    week_start = date.today() - timedelta(days=date.today().weekday())

    carb_per_meal = 60
    if goal and goal.target_carbs_g:
        carb_per_meal = max(1, int(goal.target_carbs_g // 3))

    return {
        "patient_id":            patient.id,
        "age":                   patient.age or 30,
        "weight_kg":             float(patient.weight_kg or 70),
        "height_cm":             float(patient.height_cm or 170),
        "bmi":                   round(patient.bmi or 25.0, 1),
        "diabetes_type":         "Type 2",
        "hba1c":                 float(patient.hba1c_level) if patient.hba1c_level else None,
        "last_glucose":          float(patient.blood_glucose_level) if patient.blood_glucose_level else None,
        "medications":           meds,
        "allergies":             [],
        "carb_limit_per_meal_g": carb_per_meal,
        "target_calories_kcal":  float(goal.target_calories_kcal) if goal else None,
        "target_carbs_g":        float(goal.target_carbs_g) if goal else None,
        "target_protein_g":      float(goal.target_protein_g) if goal else None,
        "target_fat_g":          float(goal.target_fat_g) if goal else None,
        "cuisine":               cuisine,
        "week_start":            week_start.isoformat(),
    }


def _persist_plan(patient, plan_data: dict, profile: dict, cuisine: str) -> WeeklyMealPlan:
    week_start = date.fromisoformat(profile["week_start"])
    plan, _ = WeeklyMealPlan.objects.update_or_create(
        patient=patient,
        week_start=week_start,
        defaults={
            "status":            WeeklyMealPlan.Status.READY,
            "cuisine":           cuisine,
            "generated_at":      timezone.now(),
            "clinical_snapshot": profile,
            "week_summary":      plan_data.get("week_summary", {}),
        },
    )
    for day in plan_data.get("days", []):
        for m in day.get("meals", []):
            Meal.objects.update_or_create(
                meal_plan=plan,
                day_index=day["day_index"],
                meal_type=m["meal_type"],
                defaults={
                    "name":                     m["name"],
                    "description":              m["description"],
                    "ingredients":              m["ingredients"],
                    "preparation_time_minutes": m.get("preparation_time_minutes", 20),
                    "calories_kcal":            m["calories_kcal"],
                    "carbs_g":                  m["carbs_g"],
                    "protein_g":                m["protein_g"],
                    "fat_g":                    m["fat_g"],
                    "sugar_g":                  m["sugar_g"],
                    "glycemic_index":           m["glycemic_index"],
                    "glycemic_load":            m["glycemic_load"],
                    "nutritional_source":       m.get("nutritional_source", Meal.NutritionalSource.LLM_ESTIMATED),
                    "usda_breakdown":           m.get("usda_breakdown", []),
                    "diabetes_rationale":       m["diabetes_rationale"],
                },
            )
    return plan


def _serialize_plan(plan: WeeklyMealPlan) -> dict:
    meals_qs = Meal.objects.filter(meal_plan=plan).order_by("day_index", "meal_type")
    days: dict[int, list] = {}
    for m in meals_qs:
        days.setdefault(m.day_index, []).append({
            "meal_type":                m.meal_type,
            "name":                     m.name,
            "description":              m.description,
            "ingredients":              m.ingredients,
            "preparation_time_minutes": m.preparation_time_minutes,
            "calories_kcal":            m.calories_kcal,
            "carbs_g":                  m.carbs_g,
            "protein_g":                m.protein_g,
            "fat_g":                    m.fat_g,
            "sugar_g":                  m.sugar_g,
            "glycemic_index":           m.glycemic_index,
            "glycemic_load":            m.glycemic_load,
            "nutritional_source":       m.nutritional_source,
            "usda_breakdown":           m.usda_breakdown,
            "diabetes_rationale":       m.diabetes_rationale,
        })
    return {
        "id":           plan.id,
        "week_start":   plan.week_start.isoformat(),
        "status":       plan.status,
        "cuisine":      plan.cuisine,
        "generated_at": plan.generated_at.isoformat() if plan.generated_at else None,
        "week_summary": plan.week_summary,
        "days": [
            {"day_index": i, "day_name": _DAYS[i], "meals": days.get(i, [])}
            for i in range(7)
        ],
    }


# ── Meal Plan views ───────────────────────────────────────────────────────────

class MealPlanGenerateView(APIView):
    """POST /api/v1/nutrition/meal-plan/generate"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if getattr(request.user, "role", None) != "patient":
            return Response({"detail": "Only patients can generate meal plans."}, status=status.HTTP_403_FORBIDDEN)

        cuisine = request.data.get("cuisine", "mediterranean")
        profile = _build_clinical_profile(request.user, cuisine)

        try:
            resp = httpx.post(
                f"{FASTAPI_BASE}/nutrition/meal-plan/generate",
                json=profile,
                timeout=360,  # Groq (~20s) + USDA validation (~50 unique ingredients × 2s)
            )
            resp.raise_for_status()
            plan_data = resp.json()
        except httpx.HTTPStatusError as exc:
            return Response(
                {"detail": f"AI generation failed: {exc.response.status_code} — {exc.response.text[:300]}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            return Response({"detail": f"AI generation failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        plan = _persist_plan(request.user, plan_data, profile, cuisine)
        return Response(_serialize_plan(plan), status=status.HTTP_201_CREATED)


class MealPlanRegenerateDayView(APIView):
    """POST /api/v1/nutrition/meal-plan/<pk>/regenerate-day"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            plan = WeeklyMealPlan.objects.get(pk=pk, patient=request.user)
        except WeeklyMealPlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        raw_day = request.data.get("day_index")
        if raw_day is None:
            return Response({"detail": "day_index is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            day_index = int(raw_day)
            assert 0 <= day_index <= 6
        except (ValueError, AssertionError):
            return Response({"detail": "day_index must be 0–6."}, status=status.HTTP_400_BAD_REQUEST)

        profile = {**plan.clinical_snapshot, "day_index": day_index}
        try:
            resp = httpx.post(
                f"{FASTAPI_BASE}/nutrition/meal-plan/generate",
                json=profile,
                timeout=120,  # single day: Groq (~20s) + USDA (~4 meals × ~5 ingredients × 2s)
            )
            resp.raise_for_status()
            plan_data = resp.json()
        except httpx.HTTPStatusError as exc:
            return Response(
                {"detail": f"AI generation failed: {exc.response.status_code} — {exc.response.text[:300]}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            return Response({"detail": f"AI generation failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        _persist_plan(request.user, plan_data, plan.clinical_snapshot, plan.cuisine)
        plan.refresh_from_db()
        return Response(_serialize_plan(plan))


class MealPlanCurrentView(APIView):
    """GET /api/v1/nutrition/meal-plan/current"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"detail": "No patient scope."}, status=status.HTTP_404_NOT_FOUND)

        plan = (
            WeeklyMealPlan.objects.filter(
                patient_id__in=patient_ids, status=WeeklyMealPlan.Status.READY
            )
            .order_by("-week_start")
            .first()
        )
        if not plan:
            return Response({"detail": "No meal plan found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_plan(plan))


class MealPlanDetailView(APIView):
    """GET /api/v1/nutrition/meal-plan/<pk>"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        patient_ids, error = _resolve_patient_scope(request.user, None)
        if error is not None:
            return error
        try:
            plan = WeeklyMealPlan.objects.get(pk=pk, patient_id__in=patient_ids)
        except WeeklyMealPlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_plan(plan))
