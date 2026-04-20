from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.access import can_access_patient_documents, parse_patient_pk
from documents.models import PatientCaregiverLink
from users.models import User, UserRole

from .models import Appointment, CarePlan, CareTask, FamilyUpdate, MedicationGuidance


def _resolve_patient_scope(user, raw_patient_id: str | None) -> tuple[list[int] | None, Response | None]:
    role = getattr(user, "role", None)
    if raw_patient_id:
        patient_id = parse_patient_pk(raw_patient_id)
        if patient_id is None:
            return None, Response({"detail": "patient_id must be a positive integer"}, status=status.HTTP_400_BAD_REQUEST)
        if not can_access_patient_documents(user, patient_id):
            return None, Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        return [patient_id], None

    if role == UserRole.PATIENT:
        return [int(user.pk)], None
    if role == UserRole.DOCTOR:
        ids = list(CarePlan.objects.filter(doctor=user).values_list("patient_id", flat=True).distinct())
        return ids, None
    if role == UserRole.CAREGIVER:
        ids = list(PatientCaregiverLink.objects.filter(caregiver=user).values_list("patient_id", flat=True).distinct())
        return ids, None
    return [], None


def _user_display(u: User | None) -> str:
    if u is None:
        return "Unknown"
    full = f"{u.first_name} {u.last_name}".strip()
    return full or u.username


class CareCircleTeamView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"items": [], "total": 0})

        members: list[dict] = []
        patients = User.objects.filter(pk__in=patient_ids)
        for patient in patients:
            members.append(
                {
                    "id": int(patient.pk),
                    "name": _user_display(patient),
                    "username": patient.username,
                    "role": "Patient",
                    "status": "Active",
                }
            )

        doctor_ids = set(CarePlan.objects.filter(patient_id__in=patient_ids, doctor_id__isnull=False).values_list("doctor_id", flat=True))
        caregiver_ids = set(PatientCaregiverLink.objects.filter(patient_id__in=patient_ids).values_list("caregiver_id", flat=True))
        for doctor in User.objects.filter(pk__in=doctor_ids):
            members.append(
                {
                    "id": int(doctor.pk),
                    "name": _user_display(doctor),
                    "username": doctor.username,
                    "role": "Doctor",
                    "status": "Available",
                }
            )
        for caregiver in User.objects.filter(pk__in=caregiver_ids):
            members.append(
                {
                    "id": int(caregiver.pk),
                    "name": _user_display(caregiver),
                    "username": caregiver.username,
                    "role": "Caregiver",
                    "status": "Active",
                }
            )
        return Response({"items": members, "total": len(members)})


class CareCirclePlanView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"care_plans": [], "tasks": [], "medication_guidance": []})

        plans = (
            CarePlan.objects.filter(patient_id__in=patient_ids)
            .select_related("patient", "doctor")
            .order_by("-created_at")
        )
        plan_payload = [
            {
                "id": plan.id,
                "patient_id": int(plan.patient_id),
                "patient_name": _user_display(plan.patient),
                "doctor_name": _user_display(plan.doctor),
                "notes": plan.notes,
                "created_at": plan.created_at.isoformat(),
            }
            for plan in plans
        ]

        tasks = (
            CareTask.objects.filter(care_plan__patient_id__in=patient_ids)
            .select_related("care_plan__patient", "assignee")
            .order_by("-created_at")[:100]
        )
        task_payload = [
            {
                "id": task.id,
                "patient_id": int(task.care_plan.patient_id),
                "patient_name": _user_display(task.care_plan.patient),
                "title": task.title,
                "status": task.status,
                "assignee_name": _user_display(task.assignee),
                "due_at": task.due_at.isoformat() if task.due_at else None,
                "created_at": task.created_at.isoformat(),
            }
            for task in tasks
        ]

        guidance = MedicationGuidance.objects.filter(patient_id__in=patient_ids).select_related("patient").order_by("-created_at")[:100]
        guidance_payload = [
            {
                "id": row.id,
                "patient_id": int(row.patient_id),
                "patient_name": _user_display(row.patient),
                "medication_name": row.medication_name,
                "guidance": row.guidance,
                "doctor_validated": row.doctor_validated,
                "created_at": row.created_at.isoformat(),
            }
            for row in guidance
        ]
        return Response({"care_plans": plan_payload, "tasks": task_payload, "medication_guidance": guidance_payload})


class CareCircleUpdatesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"items": [], "total": 0})

        updates = FamilyUpdate.objects.filter(patient_id__in=patient_ids).select_related("patient", "caregiver").order_by("-created_at")[:100]
        payload = [
            {
                "id": update.id,
                "patient_id": int(update.patient_id),
                "patient_name": _user_display(update.patient),
                "from_name": _user_display(update.caregiver) if update.caregiver else "System",
                "summary": update.summary,
                "created_at": update.created_at.isoformat(),
            }
            for update in updates
        ]
        return Response({"items": payload, "total": len(payload)})


class CareCircleAppointmentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"items": [], "total": 0})

        appointments = (
            Appointment.objects.filter(patient_id__in=patient_ids)
            .select_related("patient", "doctor", "caregiver")
            .order_by("-starts_at")[:100]
        )
        payload = [
            {
                "id": appt.id,
                "patient_id": int(appt.patient_id),
                "patient_name": _user_display(appt.patient),
                "doctor_name": _user_display(appt.doctor),
                "caregiver_name": _user_display(appt.caregiver),
                "title": appt.title,
                "starts_at": appt.starts_at.isoformat(),
                "ends_at": appt.ends_at.isoformat(),
                "status": appt.status,
                "reminder_sent": appt.reminder_sent,
            }
            for appt in appointments
        ]
        return Response({"items": payload, "total": len(payload)})
