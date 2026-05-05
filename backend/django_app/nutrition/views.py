from __future__ import annotations

from datetime import date, timedelta

import httpx
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from carecircle.models import CarePlan
from documents.access import can_access_patient_documents, parse_patient_pk
from users.models import PatientCaregiverLink
from nutrition.models import ExerciseSession, Meal, NutritionGoal, RecoveryPlan, WeeklyWellnessPlan

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
        ids = list(
            PatientCaregiverLink.objects.filter(caregiver=user, status="accepted")
            .values_list("patient_id", flat=True)
            .distinct()
        )
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


# ── Weekly Wellness Plan helpers ───────────────────────────────────────────────

def _build_wellness_profile(patient, request_data: dict) -> dict:
    """Assemble the WeeklyWellnessPlanRequest payload from DB + request body."""
    from monitoring.models import PatientMedication

    meds = list(
        PatientMedication.objects.filter(patient=patient, verification_status="matched")
        .values_list("name_display", flat=True)
    )
    goal_obj   = NutritionGoal.objects.filter(patient=patient).order_by("-valid_from").first()
    week_start = date.today() - timedelta(days=date.today().weekday())
    p = getattr(patient, "patient_profile", None)

    carb_per_meal = 60
    if goal_obj and goal_obj.target_carbs_g:
        carb_per_meal = max(1, int(goal_obj.target_carbs_g // 3))

    return {
        "patient_id":            patient.id,
        "age":                   (p.age if p else None) or 30,
        "weight_kg":             float(p.weight_kg or 70) if p else 70.0,
        "height_cm":             float(p.height_cm or 170) if p else 170.0,
        "bmi":                   round(p.bmi or 25.0, 1) if p else 25.0,
        "diabetes_type":         p.diabetes_type if p else "Type 2",
        "hba1c":                 float(p.hba1c_level) if p and p.hba1c_level else None,
        "last_glucose":          float(p.blood_glucose_level) if p and p.blood_glucose_level else None,
        "medications":           meds,
        "allergies":             p.allergies if p else [],
        "hypertension":          bool(p.hypertension) if p else False,
        "heart_disease":         bool(p.heart_disease) if p else False,
        "cuisine":               request_data.get("cuisine", "mediterranean"),
        "carb_limit_per_meal_g": carb_per_meal,
        "target_calories_kcal":  float(goal_obj.target_calories_kcal) if goal_obj else None,
        "target_carbs_g":        float(goal_obj.target_carbs_g) if goal_obj else None,
        "target_protein_g":      float(goal_obj.target_protein_g) if goal_obj else None,
        "target_fat_g":          float(goal_obj.target_fat_g) if goal_obj else None,
        "fitness_level":         request_data.get("fitness_level", "beginner"),
        "goal":                  request_data.get("goal", "maintenance"),
        "sessions_per_week":     int(request_data.get("sessions_per_week", 3)),
        "minutes_per_session":   int(request_data.get("minutes_per_session", 30)),
        "available_equipment":   request_data.get("available_equipment", ["none"]),
        "injuries_or_limits":    request_data.get("injuries_or_limits", []),
        "week_start":            week_start.isoformat(),
    }


def _persist_wellness_plan(patient, plan_data: dict, profile: dict) -> WeeklyWellnessPlan:
    week_start = date.fromisoformat(profile["week_start"])
    plan, _ = WeeklyWellnessPlan.objects.update_or_create(
        patient=patient,
        week_start=week_start,
        defaults={
            "status":           WeeklyWellnessPlan.Status.READY,
            "fitness_level":    profile.get("fitness_level", ""),
            "goal":             profile.get("goal", ""),
            "cuisine":          profile.get("cuisine", ""),
            "generated_at":     timezone.now(),
            "clinical_snapshot": profile,
            "week_summary":     plan_data.get("week_summary", {}),
        },
    )

    days_in_payload = [day["day_index"] for day in plan_data.get("days", [])]

    # Wipe stale rows for every day we're about to write so re-generation is clean.
    Meal.objects.filter(wellness_plan=plan, day_index__in=days_in_payload).delete()
    ExerciseSession.objects.filter(wellness_plan=plan, day_index__in=days_in_payload).delete()

    meals_to_create:    list[Meal]            = []
    sessions_to_create: list[ExerciseSession] = []

    for day in plan_data.get("days", []):
        day_idx = day["day_index"]

        for m in day.get("meals", []):
            meals_to_create.append(Meal(
                wellness_plan=plan,
                day_index=day_idx,
                meal_type=m.get("meal_type", "snack"),
                name=m.get("name", ""),
                description=m.get("description", ""),
                ingredients=m.get("ingredients", []),
                preparation_time_minutes=m.get("preparation_time_minutes", 20),
                calories_kcal=m.get("calories_kcal", 0),
                carbs_g=m.get("carbs_g", 0),
                protein_g=m.get("protein_g", 0),
                fat_g=m.get("fat_g", 0),
                sugar_g=m.get("sugar_g", 0),
                glycemic_index=m.get("glycemic_index", "medium"),
                glycemic_load=m.get("glycemic_load", "medium"),
                diabetes_rationale=m.get("diabetes_rationale", ""),
            ))

        for s in day.get("exercise_sessions", []):
            sessions_to_create.append(ExerciseSession(
                patient=patient,
                wellness_plan=plan,
                day_index=day_idx,
                title=s.get("name", "Session")[:255],
                exercise_type=s.get("exercise_type", ""),
                description=s.get("description", ""),
                intensity=s.get("intensity", "moderate"),
                duration_minutes=s.get("duration_minutes", 30),
                sets=s.get("sets"),
                reps=s.get("reps"),
                equipment=s.get("equipment", []),
                pre_exercise_glucose_check=s.get("pre_exercise_glucose_check", False),
                post_exercise_snack_tip=s.get("post_exercise_snack_tip", ""),
                diabetes_rationale=s.get("diabetes_rationale", ""),
                scheduled_for=timezone.now(),
            ))

    Meal.objects.bulk_create(meals_to_create)
    ExerciseSession.objects.bulk_create(sessions_to_create)
    return plan


def _serialize_wellness_plan(plan: WeeklyWellnessPlan) -> dict:
    meals_qs    = Meal.objects.filter(wellness_plan=plan).order_by("day_index", "meal_type")
    sessions_qs = ExerciseSession.objects.filter(wellness_plan=plan).order_by("day_index", "title")

    day_meals:    dict[int, list] = {}
    day_sessions: dict[int, list] = {}

    for m in meals_qs:
        day_meals.setdefault(m.day_index, []).append({
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
            "diabetes_rationale":       m.diabetes_rationale,
        })

    for s in sessions_qs:
        day_sessions.setdefault(s.day_index, []).append({
            "id":                          s.id,
            "exercise_type":               s.exercise_type,
            "name":                        s.title,
            "description":                 s.description,
            "intensity":                   s.intensity,
            "duration_minutes":            s.duration_minutes,
            "sets":                        s.sets,
            "reps":                        s.reps,
            "equipment":                   s.equipment,
            "pre_exercise_glucose_check":  s.pre_exercise_glucose_check,
            "post_exercise_snack_tip":     s.post_exercise_snack_tip,
            "diabetes_rationale":          s.diabetes_rationale,
            "status":                      s.status,
        })

    return {
        "id":           plan.id,
        "week_start":   plan.week_start.isoformat(),
        "status":       plan.status,
        "fitness_level": plan.fitness_level,
        "goal":         plan.goal,
        "cuisine":      plan.cuisine,
        "generated_at": plan.generated_at.isoformat() if plan.generated_at else None,
        "week_summary": plan.week_summary,
        "days": [
            {
                "day_index":        i,
                "day_name":         _DAYS[i],
                "exercise_sessions": day_sessions.get(i, []),
                "meals":            day_meals.get(i, []),
            }
            for i in range(7)
        ],
    }


# ── Weekly Wellness Plan views ─────────────────────────────────────────────────

class WellnessPlanGenerateView(APIView):
    """POST /api/v1/nutrition/wellness-plan/generate"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if getattr(request.user, "role", None) != "patient":
            return Response({"detail": "Only patients can generate wellness plans."}, status=status.HTTP_403_FORBIDDEN)

        profile = _build_wellness_profile(request.user, request.data)
        try:
            resp = httpx.post(
                f"{FASTAPI_BASE}/wellness/weekly-plan/generate",
                json=profile,
                timeout=600,
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

        plan = _persist_wellness_plan(request.user, plan_data, profile)
        return Response(_serialize_wellness_plan(plan), status=status.HTTP_201_CREATED)


class WellnessPlanRegenerateDayView(APIView):
    """POST /api/v1/nutrition/wellness-plan/<pk>/regenerate-day"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            plan = WeeklyWellnessPlan.objects.get(pk=pk, patient=request.user)
        except WeeklyWellnessPlan.DoesNotExist:
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
                f"{FASTAPI_BASE}/wellness/weekly-plan/generate",
                json=profile,
                timeout=180,
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

        _persist_wellness_plan(request.user, plan_data, plan.clinical_snapshot)
        plan.refresh_from_db()
        return Response(_serialize_wellness_plan(plan))


class WellnessPlanCurrentView(APIView):
    """GET /api/v1/nutrition/wellness-plan/current"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"detail": "No patient scope."}, status=status.HTTP_404_NOT_FOUND)

        plan = (
            WeeklyWellnessPlan.objects.filter(
                patient_id__in=patient_ids, status=WeeklyWellnessPlan.Status.READY
            )
            .order_by("-week_start")
            .first()
        )
        if not plan:
            return Response({"detail": "No wellness plan found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_wellness_plan(plan))


class WellnessPlanDetailView(APIView):
    """GET /api/v1/nutrition/wellness-plan/<pk>"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        patient_ids, error = _resolve_patient_scope(request.user, None)
        if error is not None:
            return error
        try:
            plan = WeeklyWellnessPlan.objects.get(pk=pk, patient_id__in=patient_ids)
        except WeeklyWellnessPlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_wellness_plan(plan))
