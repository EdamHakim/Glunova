from django.urls import path

from .views import (
    AvailableCaregiversView,
    AvailableDoctorsView,
    BookingDoctorsForPatientView,
    BookAppointmentView,
    BookableSlotsView,
    CancelAppointmentView,
    CareCircleAppointmentsView,
    CareCircleUpdatesView,
    MyAppointmentSlotDetailView,
    MyAppointmentSlotsBulkView,
    MyAppointmentSlotsView,
    MyCaregiverDetailView,
    MyCaregiverView,
    MyDoctorDetailView,
    MyDoctorView,
    PendingInvitationsView,
    RespondInvitationView,
)

urlpatterns = [
    # ── Existing read-only views ──────────────────────────────────────────────
    path("care-circle/updates", CareCircleUpdatesView.as_view(), name="care-circle-updates"),
    path("care-circle/appointments", CareCircleAppointmentsView.as_view(), name="care-circle-appointments"),
    path("care-circle/appointments/<int:pk>/cancel", CancelAppointmentView.as_view(), name="care-circle-appointment-cancel"),

    path("care-circle/my-appointment-slots", MyAppointmentSlotsView.as_view(), name="care-circle-my-appointment-slots"),
    path("care-circle/my-appointment-slots/bulk", MyAppointmentSlotsBulkView.as_view(), name="care-circle-my-appointment-slots-bulk"),
    path("care-circle/my-appointment-slots/<int:pk>", MyAppointmentSlotDetailView.as_view(), name="care-circle-my-appointment-slot-detail"),
    path("care-circle/bookable-slots", BookableSlotsView.as_view(), name="care-circle-bookable-slots"),
    path("care-circle/book-appointment", BookAppointmentView.as_view(), name="care-circle-book-appointment"),
    path("care-circle/booking/doctors", BookingDoctorsForPatientView.as_view(), name="care-circle-booking-doctors"),

    # ── Discovery: who can be linked ─────────────────────────────────────────
    path("care-circle/available-doctors", AvailableDoctorsView.as_view(), name="care-circle-available-doctors"),
    path("care-circle/available-caregivers", AvailableCaregiversView.as_view(), name="care-circle-available-caregivers"),

    # ── Patient: doctor links ─────────────────────────────────────────────────
    path("care-circle/my-doctor", MyDoctorView.as_view(), name="care-circle-my-doctor"),
    path("care-circle/my-doctor/<int:pk>", MyDoctorDetailView.as_view(), name="care-circle-my-doctor-detail"),

    # ── Patient: caregiver invitations ───────────────────────────────────────
    path("care-circle/my-caregiver", MyCaregiverView.as_view(), name="care-circle-my-caregiver"),
    path("care-circle/my-caregiver/<int:pk>", MyCaregiverDetailView.as_view(), name="care-circle-my-caregiver-detail"),

    # ── Caregiver: invitation inbox ───────────────────────────────────────────
    path("care-circle/pending-invitations", PendingInvitationsView.as_view(), name="care-circle-pending-invitations"),
    path("care-circle/pending-invitations/<int:pk>/respond", RespondInvitationView.as_view(), name="care-circle-respond-invitation"),
]
