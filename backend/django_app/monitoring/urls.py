from django.urls import path

from .views import (
    DashboardOverviewView,
    MonitoringAlertsView,
    MonitoringProgressionSummaryView,
    MonitoringTimelineView,
    PatientLabResultsView,
    PatientMedicationsView,
)

urlpatterns = [
    path("monitoring/alerts", MonitoringAlertsView.as_view(), name="monitoring-alerts"),
    path("monitoring/timeline", MonitoringTimelineView.as_view(), name="monitoring-timeline"),
    path("monitoring/progression", MonitoringProgressionSummaryView.as_view(), name="monitoring-progression"),
    path("lab-results", PatientLabResultsView.as_view(), name="monitoring-lab-results"),
    path("medications", PatientMedicationsView.as_view(), name="monitoring-medications"),
    path("dashboard/overview", DashboardOverviewView.as_view(), name="dashboard-overview"),
]
