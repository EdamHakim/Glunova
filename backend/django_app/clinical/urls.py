from django.urls import path

from .views import PatientMedicationListView

urlpatterns = [
    path("medications", PatientMedicationListView.as_view(), name="medications-list"),
]
