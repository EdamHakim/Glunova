from __future__ import annotations

from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.access import can_access_patient_documents, parse_patient_pk
from users.models import PatientCaregiverLink, PatientDoctorLink, User, UserRole

from .models import Appointment, AppointmentSlot, FamilyUpdate


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
        ids = set(PatientDoctorLink.objects.filter(doctor=user).values_list("patient_id", flat=True))
        return list(ids), None
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


def _parse_iso_datetime(raw, field_label: str) -> tuple:
    """Return (datetime | None, error Response | None)."""
    if raw is None or raw == "":
        return None, Response({"detail": f"{field_label} is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(raw, str):
        return None, Response({"detail": f"{field_label} must be a string."}, status=status.HTTP_400_BAD_REQUEST)
    dt = parse_datetime(raw.replace("Z", "+00:00"))
    if dt is None:
        return None, Response({"detail": f"Invalid ISO datetime for {field_label}."}, status=status.HTTP_400_BAD_REQUEST)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt, None


def _doctor_slot_overlaps(doctor_id: int, starts_at, ends_at, exclude_pk: int | None = None) -> bool:
    q = AppointmentSlot.objects.filter(
        doctor_id=doctor_id,
        starts_at__lt=ends_at,
        ends_at__gt=starts_at,
    )
    if exclude_pk is not None:
        q = q.exclude(pk=exclude_pk)
    return q.exists()


def _appointment_api_dict(appt: Appointment) -> dict:
    return {
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
        "booking_slot_id": appt.booking_slot_id,
    }


def _doctor_link_rows_for_patient(patient: User) -> list[dict]:
    rows: list[dict] = []
    links = PatientDoctorLink.objects.filter(patient=patient).select_related("doctor__doctor_profile")
    for link in links:
        d = link.doctor
        profile = getattr(d, "doctor_profile", None)
        rows.append({
            "id": link.pk,
            "doctor_id": d.pk,
            "name": _user_display(d),
            "username": d.username,
            "specialization": profile.specialization if profile else "",
            "hospital_affiliation": profile.hospital_affiliation if profile else "",
            "linked_at": link.linked_at.isoformat(),
        })
    return rows


def _coerce_optional_patient_id_raw(raw) -> str | None:
    if raw is None or raw == "":
        return None
    return str(raw).strip() or None


def _resolve_booking_target_patient(request, raw_patient_id: str | None) -> tuple[User | None, Response | None]:
    """Which patient the appointment is for (patient self-booking or caregiver acting for a linked patient)."""
    role = getattr(request.user, "role", None)
    if role == UserRole.PATIENT:
        if raw_patient_id is not None:
            pid = parse_patient_pk(raw_patient_id)
            if pid is None or pid != int(request.user.pk):
                return None, Response({"detail": "Patients may only book for themselves."}, status=status.HTTP_403_FORBIDDEN)
        return request.user, None

    if role == UserRole.CAREGIVER:
        if raw_patient_id is None:
            return None, Response({"detail": "patient_id is required for caregivers."}, status=status.HTTP_400_BAD_REQUEST)
        pid = parse_patient_pk(raw_patient_id)
        if pid is None:
            return None, Response({"detail": "patient_id must be a positive integer."}, status=status.HTTP_400_BAD_REQUEST)
        if not can_access_patient_documents(request.user, pid):
            return None, Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        patient = User.objects.filter(pk=pid, role=UserRole.PATIENT).first()
        if patient is None:
            return None, Response({"detail": "Patient not found."}, status=status.HTTP_404_NOT_FOUND)
        return patient, None

    return None, Response({"detail": "Only patients and caregivers may book appointments."}, status=status.HTTP_403_FORBIDDEN)


# ── Existing read-only views ──────────────────────────────────────────────────

class CareCircleUpdatesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "role", None) == UserRole.DOCTOR:
            return Response({"detail": "Care Circle is only available to patients and caregivers."}, status=status.HTTP_403_FORBIDDEN)
        patient_ids, error = _resolve_patient_scope(request.user, request.query_params.get("patient_id"))
        if error is not None:
            return error
        if not patient_ids:
            return Response({"items": [], "total": 0})

        updates_qs = FamilyUpdate.objects.filter(patient_id__in=patient_ids).select_related("patient", "caregiver")
        viewer_role = getattr(request.user, "role", None)
        if viewer_role == UserRole.PATIENT:
            updates_qs = updates_qs.filter(
                Q(source=FamilyUpdate.Source.HUMAN)
                | (Q(source=FamilyUpdate.Source.AGENT) & Q(caregiver_id__isnull=True))
            )
        elif viewer_role == UserRole.CAREGIVER:
            updates_qs = updates_qs.filter(
                Q(source=FamilyUpdate.Source.HUMAN)
                | (Q(source=FamilyUpdate.Source.AGENT) & Q(caregiver_id=request.user.pk))
            )
        updates = updates_qs.order_by("-created_at")[:100]
        payload = [
            {
                "id": update.id,
                "patient_id": int(update.patient_id),
                "patient_name": _user_display(update.patient),
                "from_name": (
                    "Care agent"
                    if update.source == FamilyUpdate.Source.AGENT
                    else (_user_display(update.caregiver) if update.caregiver else "System")
                ),
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
        if getattr(request.user, "role", None) == UserRole.DOCTOR:
            return Response({"detail": "Care Circle is only available to patients and caregivers."}, status=status.HTTP_403_FORBIDDEN)
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
        payload = [_appointment_api_dict(appt) for appt in appointments]
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

        payload = _doctor_link_rows_for_patient(request.user)
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


class BookingDoctorsForPatientView(APIView):
    """Patient or caregiver: list a patient's linked doctors (for booking flows)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = getattr(request.user, "role", None)
        raw_pid = request.query_params.get("patient_id")

        if role == UserRole.PATIENT:
            patient = request.user
            if raw_pid is not None and raw_pid != "":
                pid = parse_patient_pk(raw_pid)
                if pid is None or pid != int(patient.pk):
                    return Response({"detail": "Invalid patient context."}, status=status.HTTP_403_FORBIDDEN)
        elif role == UserRole.CAREGIVER:
            pid = parse_patient_pk(raw_pid or "")
            if pid is None:
                return Response({"detail": "patient_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            if not can_access_patient_documents(request.user, pid):
                return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
            patient = User.objects.filter(pk=pid, role=UserRole.PATIENT).first()
            if patient is None:
                return Response({"detail": "Patient not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({"detail": "Only patients and caregivers may use this endpoint."}, status=status.HTTP_403_FORBIDDEN)

        payload = _doctor_link_rows_for_patient(patient)
        return Response({"items": payload, "total": len(payload)})


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


# ── Doctor: appointment slots ─────────────────────────────────────────────────

class MyAppointmentSlotsView(APIView):
    """Doctor-only: list and create availability slots."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        err = _require_role(request.user, "doctor")
        if err:
            return err

        slots_qs = (
            AppointmentSlot.objects.filter(doctor=request.user)
            .annotate(is_booked=Exists(Appointment.objects.filter(booking_slot_id=OuterRef("pk"))))
            .order_by("starts_at")
        )
        payload = [
            {
                "id": slot.id,
                "doctor_id": int(slot.doctor_id),
                "starts_at": slot.starts_at.isoformat(),
                "ends_at": slot.ends_at.isoformat(),
                "is_booked": slot.is_booked,
                "created_at": slot.created_at.isoformat(),
            }
            for slot in slots_qs
        ]
        return Response({"items": payload, "total": len(payload)})

    def post(self, request):
        err = _require_role(request.user, "doctor")
        if err:
            return err

        starts_raw = request.data.get("starts_at")
        ends_raw = request.data.get("ends_at")
        starts_at, e1 = _parse_iso_datetime(starts_raw, "starts_at")
        if e1 is not None:
            return e1
        ends_at, e2 = _parse_iso_datetime(ends_raw, "ends_at")
        if e2 is not None:
            return e2
        if starts_at is None or ends_at is None:
            return Response({"detail": "Invalid datetime values."}, status=status.HTTP_400_BAD_REQUEST)
        if ends_at <= starts_at:
            return Response({"detail": "ends_at must be after starts_at."}, status=status.HTTP_400_BAD_REQUEST)

        if _doctor_slot_overlaps(int(request.user.pk), starts_at, ends_at):
            return Response({"detail": "Overlaps another slot you already published."}, status=status.HTTP_409_CONFLICT)

        slot = AppointmentSlot.objects.create(doctor=request.user, starts_at=starts_at, ends_at=ends_at)
        return Response(
            {
                "id": slot.id,
                "doctor_id": int(slot.doctor_id),
                "starts_at": slot.starts_at.isoformat(),
                "ends_at": slot.ends_at.isoformat(),
                "is_booked": False,
                "created_at": slot.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class MyAppointmentSlotDetailView(APIView):
    """Doctor-only: delete an unbooked slot."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        err = _require_role(request.user, "doctor")
        if err:
            return err

        try:
            slot = AppointmentSlot.objects.get(pk=pk, doctor=request.user)
        except AppointmentSlot.DoesNotExist:
            return Response({"detail": "Slot not found."}, status=status.HTTP_404_NOT_FOUND)

        if Appointment.objects.filter(booking_slot=slot).exists():
            return Response({"detail": "Cannot delete a slot that already has a booking."}, status=status.HTTP_409_CONFLICT)

        slot.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BookableSlotsView(APIView):
    """Patient or caregiver: list upcoming unbooked slots for a doctor linked to the booking patient."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        raw_doctor_id = request.query_params.get("doctor_id")
        if raw_doctor_id is None:
            return Response({"detail": "doctor_id query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            doctor_id = int(raw_doctor_id)
        except (TypeError, ValueError):
            return Response({"detail": "doctor_id must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        booking_patient, perr = _resolve_booking_target_patient(request, _coerce_optional_patient_id_raw(request.query_params.get("patient_id")))
        if perr is not None:
            return perr
        if booking_patient is None:
            return Response({"detail": "Booking patient could not be resolved."}, status=status.HTTP_400_BAD_REQUEST)

        linked = PatientDoctorLink.objects.filter(patient=booking_patient, doctor_id=doctor_id).exists()
        if not linked:
            return Response({"detail": "That patient is not linked to this doctor."}, status=status.HTTP_403_FORBIDDEN)

        t = timezone.now()
        slots = (
            AppointmentSlot.objects.filter(
                doctor_id=doctor_id,
                starts_at__gte=t,
            )
            .annotate(is_booked=Exists(Appointment.objects.filter(booking_slot_id=OuterRef("pk"))))
            .filter(is_booked=False)
            .order_by("starts_at")
        )
        payload = [
            {
                "id": slot.id,
                "doctor_id": int(slot.doctor_id),
                "starts_at": slot.starts_at.isoformat(),
                "ends_at": slot.ends_at.isoformat(),
            }
            for slot in slots
        ]
        return Response({"items": payload, "total": len(payload)})


class BookAppointmentView(APIView):
    """Patient or caregiver: book an open slot for a patient (creates Appointment)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        slot_id = request.data.get("slot_id")
        if slot_id is None:
            return Response({"detail": "slot_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        title = (request.data.get("title") or "").strip() or "Consultation"

        try:
            slot_pk = int(slot_id)
        except (TypeError, ValueError):
            return Response({"detail": "slot_id must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        booking_patient, perr = _resolve_booking_target_patient(request, _coerce_optional_patient_id_raw(request.data.get("patient_id")))
        if perr is not None:
            return perr
        if booking_patient is None:
            return Response({"detail": "Booking patient could not be resolved."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                slot = AppointmentSlot.objects.select_for_update().select_related("doctor").get(pk=slot_pk)
            except AppointmentSlot.DoesNotExist:
                return Response({"detail": "Slot not found."}, status=status.HTTP_404_NOT_FOUND)

            if not PatientDoctorLink.objects.filter(patient=booking_patient, doctor_id=slot.doctor_id).exists():
                return Response({"detail": "That patient is not linked to this doctor."}, status=status.HTTP_403_FORBIDDEN)

            if slot.starts_at < timezone.now():
                return Response({"detail": "That slot has already passed."}, status=status.HTTP_409_CONFLICT)

            if Appointment.objects.filter(booking_slot=slot).exists():
                return Response({"detail": "That slot was just booked."}, status=status.HTTP_409_CONFLICT)

            appt = Appointment.objects.create(
                patient=booking_patient,
                doctor=slot.doctor,
                title=title[:255],
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                booking_slot=slot,
                status=Appointment.Status.SCHEDULED,
            )

        appt_full = Appointment.objects.select_related("patient", "doctor", "caregiver").get(pk=appt.pk)
        return Response(_appointment_api_dict(appt_full), status=status.HTTP_201_CREATED)


class CancelAppointmentView(APIView):
    """Patient or caregiver: cancel a scheduled appointment and free the booking slot."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        role = getattr(request.user, "role", None)
        if role not in (UserRole.PATIENT, UserRole.CAREGIVER):
            return Response({"detail": "Only patients and caregivers may cancel visits."}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            try:
                appt = Appointment.objects.select_for_update().get(pk=pk)
            except Appointment.DoesNotExist:
                return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)

            if role == UserRole.PATIENT:
                if appt.patient_id != request.user.pk:
                    return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)
            elif not can_access_patient_documents(request.user, int(appt.patient_id)):
                return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

            if appt.status != Appointment.Status.SCHEDULED:
                return Response({"detail": "Only scheduled appointments can be cancelled."}, status=status.HTTP_400_BAD_REQUEST)

            appt.status = Appointment.Status.CANCELLED
            appt.booking_slot = None
            appt.save(update_fields=["status", "booking_slot"])

        appt_refresh = Appointment.objects.select_related("patient", "doctor", "caregiver").get(pk=appt.pk)
        return Response(_appointment_api_dict(appt_refresh))


# ── Doctor: bulk slot creation ────────────────────────────────────────────────

class MyAppointmentSlotsBulkView(APIView):
    """Doctor-only: create many slots in one request; overlapping ones are silently skipped."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        err = _require_role(request.user, "doctor")
        if err:
            return err

        raw_slots = request.data.get("slots")
        if not isinstance(raw_slots, list):
            return Response({"detail": "slots must be an array."}, status=status.HTTP_400_BAD_REQUEST)
        if len(raw_slots) == 0:
            return Response({"detail": "slots must not be empty."}, status=status.HTTP_400_BAD_REQUEST)
        if len(raw_slots) > 500:
            return Response({"detail": "Cannot create more than 500 slots at once."}, status=status.HTTP_400_BAD_REQUEST)

        parsed: list[tuple] = []
        for i, item in enumerate(raw_slots):
            if not isinstance(item, dict):
                return Response({"detail": f"slots[{i}] must be an object."}, status=status.HTTP_400_BAD_REQUEST)
            starts_at, e1 = _parse_iso_datetime(item.get("starts_at"), f"slots[{i}].starts_at")
            if e1 is not None:
                return e1
            ends_at, e2 = _parse_iso_datetime(item.get("ends_at"), f"slots[{i}].ends_at")
            if e2 is not None:
                return e2
            if ends_at <= starts_at:
                return Response(
                    {"detail": f"slots[{i}]: ends_at must be after starts_at."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            parsed.append((starts_at, ends_at))

        created_items = []
        skipped = 0

        with transaction.atomic():
            for starts_at, ends_at in parsed:
                if _doctor_slot_overlaps(int(request.user.pk), starts_at, ends_at):
                    skipped += 1
                    continue
                slot = AppointmentSlot.objects.create(
                    doctor=request.user,
                    starts_at=starts_at,
                    ends_at=ends_at,
                )
                created_items.append({
                    "id": slot.id,
                    "doctor_id": int(slot.doctor_id),
                    "starts_at": slot.starts_at.isoformat(),
                    "ends_at": slot.ends_at.isoformat(),
                    "is_booked": False,
                    "created_at": slot.created_at.isoformat(),
                })

        return Response(
            {"created": len(created_items), "skipped": skipped, "items": created_items},
            status=status.HTTP_201_CREATED,
        )
