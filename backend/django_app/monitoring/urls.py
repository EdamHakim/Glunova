from django.urls import path

from .views import DashboardOverviewView, MonitoringAlertsView, MonitoringProgressionSummaryView, MonitoringTimelineView

urlpatterns = [
    path("monitoring/alerts", MonitoringAlertsView.as_view(), name="monitoring-alerts"),
    path("monitoring/timeline", MonitoringTimelineView.as_view(), name="monitoring-timeline"),
    path("monitoring/progression", MonitoringProgressionSummaryView.as_view(), name="monitoring-progression"),
    path("dashboard/overview", DashboardOverviewView.as_view(), name="dashboard-overview"),
]
