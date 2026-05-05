from django.urls import path

from .views import (
    DashboardOverviewView,
    MonitoringAlertsView,
    MonitoringDiseaseProgressionView,
    MonitoringProgressionSummaryView,
    MonitoringRiskStratificationView,
    MonitoringScreeningHistoryView,
    MonitoringTimelineView,
    PatientLabResultsView,
    PatientMedicationsView,
    RefreshRiskView,
    TriggerAgentView,
)

urlpatterns = [
    path("monitoring/alerts", MonitoringAlertsView.as_view(), name="monitoring-alerts"),
    path("monitoring/refresh-risk", RefreshRiskView.as_view(), name="monitoring-refresh-risk"),
    path("monitoring/trigger-agent", TriggerAgentView.as_view(), name="monitoring-trigger-agent"),
    path("monitoring/timeline", MonitoringTimelineView.as_view(), name="monitoring-timeline"),
    path("monitoring/progression", MonitoringProgressionSummaryView.as_view(), name="monitoring-progression"),
    path("monitoring/risk-stratification", MonitoringRiskStratificationView.as_view(), name="monitoring-risk-stratification"),
    path("monitoring/screening-history", MonitoringScreeningHistoryView.as_view(), name="monitoring-screening-history"),
    path("monitoring/disease-progression", MonitoringDiseaseProgressionView.as_view(), name="monitoring-disease-progression"),
    path("lab-results", PatientLabResultsView.as_view(), name="monitoring-lab-results"),
    path("medications", PatientMedicationsView.as_view(), name="monitoring-medications"),
    path("dashboard/overview", DashboardOverviewView.as_view(), name="dashboard-overview"),
]
