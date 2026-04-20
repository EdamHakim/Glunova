from django.urls import path

from .views import CareCircleAppointmentsView, CareCirclePlanView, CareCircleTeamView, CareCircleUpdatesView

urlpatterns = [
    path("care-circle/team", CareCircleTeamView.as_view(), name="care-circle-team"),
    path("care-circle/plan", CareCirclePlanView.as_view(), name="care-circle-plan"),
    path("care-circle/updates", CareCircleUpdatesView.as_view(), name="care-circle-updates"),
    path("care-circle/appointments", CareCircleAppointmentsView.as_view(), name="care-circle-appointments"),
]
