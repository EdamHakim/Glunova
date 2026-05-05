from __future__ import annotations

from django.utils.timezone import now
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.access import can_access_patient_documents, parse_patient_pk
from users.models import PatientCaregiverLink, PatientDoctorLink, User, UserRole

from .models import Appointment, CarePlan, CareTask, FamilyUpdate, MedicationGuidance


# ── Shared helpers ────────────────────────────────────────────────────────────

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
        from_plans = set(CarePlan.objects.filter(doctor=user).values_list("patient_id", flat=True))
        from_links = set(PatientDoctorLink.objects.filter(doctor=user).values_list("patient_id", flat=True))
        return list(from_plans | from_links), None
    if role == UserRole.CAREGIVER:
        ids = list(
            PatientCaregiverLink.objects.filter(caregiver=user, status="accepted")
            .values_list("patient_id", flat=True)
            .distinct()
        )
        return ids, None
    return [], None


def _user_display(u: User | None) -> str:
    if u is None:
        return "Unknown"
    full = f"{u.first_name} {u.last_name}".strip()
    return full or u.username


def _require_role(user, role: str) -> Response | None:
    if getattr(user, "role", None) != role:
        return Response({"detail": f"Only {role}s can perform this action."}, status=status.HTTP_403_FORBIDDEN)
    return None


# ── Existing read-only views ──────────────────────────────────────────────────

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

        # Doctors: union of CarePlan links and PatientDoctorLink
        doctor_ids = (
            set(CarePlan.objects.filter(patient_id__in=patient_ids, doctor_id__isnull=False).values_list("doctor_id", flat=True))
            | set(PatientDoctorLink.objects.filter(patient_id__in=patient_ids).values_list("doctor_id", flat=True))
        )
        caregiver_ids = set(
            PatientCaregiverLink.objects.filter(patient_id__in=patient_ids, status="accepted")
            .values_list("caregiver_id", flat=True)
        )
        for doctor in User.objects.filter(pk__in=doctor_ids).select_related("doctor_profile"):
            profile = getattr(doctor, "doctor_profile", None)
            members.append(
                {
                    "id": int(doctor.pk),
                    "name": _user_display(doctor),
                    "username": doctor.username,
                    "role": "Doctor",
                    "status": "Available",
                    "specialization": profile.specialization if profile else "",
                    "hospital_affiliation": profile.hospital_affiliation if profile else "",
                }
            )
        for caregiver in User.objects.filter(pk__in=caregiver_ids).select_related("caregiver_profile"):
            profile = getattr(caregiver, "caregiver_profile", None)
            members.append(
                {
                    "id": int(caregiver.pk),
                    "name": _user_display(caregiver),
                    "username": caregiver.username,
                    "role": "Caregiver",
                    "status": "Active",
                    "relationship": profile.relationship if profile else "",
                    "is_professional": profile.is_professional if profile else False,
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
                "source": update.source,
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


# ── Available members to link ─────────────────────────────────────────────────

class AvailableDoctorsView(APIView):
    """Patient-only: list all doctors not yet linked."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        err = _require_role(request.user, "patient")
        if err:
            return err

        linked_ids = set(PatientDoctorLink.objects.filter(patient=request.user).values_list("doctor_id", flat=True))
        doctors = (
            User.objects.filter(role=UserRole.DOCTOR)
            .exclude(pk__in=linked_ids)
            .select_related("doctor_profile")
        )
        payload = []
        for d in doctors:
            profile = getattr(d, "doctor_profile", None)
            payload.append({
                "id": d.pk,
                "name": _user_display(d),
                "username": d.username,
                "specialization": profile.specialization if profile else "",
                "license_number": profile.license_number if profile else "",
                "hospital_affiliation": profile.hospital_affiliation if profile else "",
            })
        return Response({"items": payload, "total": len(payload)})


class AvailableCaregiversView(APIView):
    """Patient-only: list all caregivers not yet linked (any status)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        err = _require_role(request.user, "patient")
        if err:
            return err

        linked_ids = set(PatientCaregiverLink.objects.filter(patient=request.user).values_list("caregiver_id", flat=True))
        caregivers = (
            User.objects.filter(role=UserRole.CAREGIVER)
            .exclude(pk__in=linked_ids)
            .select_related("caregiver_profile")
        )
        payload = []
        for c in caregivers:
            profile = getattr(c, "caregiver_profile", None)
            payload.append({
                "id": c.pk,
                "name": _user_display(c),
                "username": c.username,
                "relationship": profile.relationship if profile else "",
                "is_professional": profile.is_professional if profile else False,
            })
        return Response({"items": payload, "total": len(payload)})


# ── Patient: manage doctor links ──────────────────────────────────────────────

class MyDoctorView(APIView):
    """Patient-only: list and create doctor links."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        err = _require_role(request.user, "patient")
        if err:
            return err

        links = PatientDoctorLink.objects.filter(patient=request.user).select_related("doctor__doctor_profile")
        payload = []
        for link in links:
            d = link.doctor
            profile = getattr(d, "doctor_profile", None)
            payload.append({
                "id": link.pk,
                "doctor_id": d.pk,
                "name": _user_display(d),
                "username": d.username,
                "specialization": profile.specialization if profile else "",
                "hospital_affiliation": profile.hospital_affiliation if profile else "",
                "linked_at": link.linked_at.isoformat(),
            })
        return Response({"items": payload, "total": len(payload)})

    def post(self, request):
        err = _require_role(request.user, "patient")
        if err:
            return err

        doctor_id = request.data.get("doctor_id")
        if not doctor_id:
            return Response({"detail": "doctor_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            doctor = User.objects.get(pk=doctor_id, role=UserRole.DOCTOR)
        except User.DoesNotExist:
            return Response({"detail": "Doctor not found."}, status=status.HTTP_404_NOT_FOUND)

        link, created = PatientDoctorLink.objects.get_or_create(patient=request.user, doctor=doctor)
        if not created:
            return Response({"detail": "Already linked to this doctor."}, status=status.HTTP_409_CONFLICT)

        profile = getattr(doctor, "doctor_profile", None)
        return Response(
            {
                "id": link.pk,
                "doctor_id": doctor.pk,
                "name": _user_display(doctor),
                "specialization": profile.specialization if profile else "",
                "hospital_affiliation": profile.hospital_affiliation if profile else "",
                "linked_at": link.linked_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class MyDoctorDetailView(APIView):
    """Patient-only: remove a doctor link."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        err = _require_role(request.user, "patient")
        if err:
            return err

        try:
            link = PatientDoctorLink.objects.get(pk=pk, patient=request.user)
        except PatientDoctorLink.DoesNotExist:
            return Response({"detail": "Link not found."}, status=status.HTTP_404_NOT_FOUND)

        link.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Patient: manage caregiver invitations ─────────────────────────────────────

class MyCaregiverView(APIView):
    """Patient-only: list caregiver links (all statuses) and send new invitations."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        err = _require_role(request.user, "patient")
        if err:
            return err

        links = PatientCaregiverLink.objects.filter(patient=request.user).select_related("caregiver__caregiver_profile")
        payload = []
        for link in links:
            c = link.caregiver
            profile = getattr(c, "caregiver_profile", None)
            payload.append({
                "id": link.pk,
                "caregiver_id": c.pk,
                "name": _user_display(c),
                "username": c.username,
                "relationship": profile.relationship if profile else "",
                "is_professional": profile.is_professional if profile else False,
                "status": link.status,
                "created_at": link.created_at.isoformat(),
                "responded_at": link.responded_at.isoformat() if link.responded_at else None,
            })
        return Response({"items": payload, "total": len(payload)})

    def post(self, request):
        err = _require_role(request.user, "patient")
        if err:
            return err

        caregiver_id = request.data.get("caregiver_id")
        if not caregiver_id:
            return Response({"detail": "caregiver_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            caregiver = User.objects.get(pk=caregiver_id, role=UserRole.CAREGIVER)
        except User.DoesNotExist:
            return Response({"detail": "Caregiver not found."}, status=status.HTTP_404_NOT_FOUND)

        if PatientCaregiverLink.objects.filter(patient=request.user, caregiver=caregiver).exists():
            return Response({"detail": "Invitation already sent or link already exists."}, status=status.HTTP_409_CONFLICT)

        link = PatientCaregiverLink.objects.create(
            patient=request.user,
            caregiver=caregiver,
            status="pending",
        )
        profile = getattr(caregiver, "caregiver_profile", None)
        return Response(
            {
                "id": link.pk,
                "caregiver_id": caregiver.pk,
                "name": _user_display(caregiver),
                "relationship": profile.relationship if profile else "",
                "is_professional": profile.is_professional if profile else False,
                "status": link.status,
                "created_at": link.created_at.isoformat(),
                "responded_at": None,
            },
            status=status.HTTP_201_CREATED,
        )


class MyCaregiverDetailView(APIView):
    """Patient-only: cancel / remove a caregiver link."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        err = _require_role(request.user, "patient")
        if err:
            return err

        try:
            link = PatientCaregiverLink.objects.get(pk=pk, patient=request.user)
        except PatientCaregiverLink.DoesNotExist:
            return Response({"detail": "Link not found."}, status=status.HTTP_404_NOT_FOUND)

        link.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Caregiver: invitation inbox ───────────────────────────────────────────────

class PendingInvitationsView(APIView):
    """Caregiver-only: list all pending invitations received."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        err = _require_role(request.user, "caregiver")
        if err:
            return err

        links = (
            PatientCaregiverLink.objects.filter(caregiver=request.user, status="pending")
            .select_related("patient")
            .order_by("-created_at")
        )
        payload = [
            {
                "id": link.pk,
                "patient_id": link.patient.pk,
                "name": _user_display(link.patient),
                "username": link.patient.username,
                "created_at": link.created_at.isoformat(),
            }
            for link in links
        ]
        return Response({"items": payload, "total": len(payload)})


class RespondInvitationView(APIView):
    """Caregiver-only: accept or reject a specific pending invitation."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        err = _require_role(request.user, "caregiver")
        if err:
            return err

        try:
            link = PatientCaregiverLink.objects.get(pk=pk, caregiver=request.user, status="pending")
        except PatientCaregiverLink.DoesNotExist:
            return Response({"detail": "Pending invitation not found."}, status=status.HTTP_404_NOT_FOUND)

        action = (request.data.get("action") or "").strip().lower()
        if action not in ("accept", "reject"):
            return Response({"detail": "action must be 'accept' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)

        link.status = "accepted" if action == "accept" else "rejected"
        link.responded_at = now()
        link.save(update_fields=["status", "responded_at"])

        return Response({
            "id": link.pk,
            "status": link.status,
            "responded_at": link.responded_at.isoformat(),
        })
