from django.urls import path

from .views import PatientMedicationListView
from .views_clinical_support import (
    ClinicalImagingQueueView,
    ClinicalPreconsultationView,
    ClinicalPrioritiesView,
    ClinicalSummaryView,
)

urlpatterns = [
    path("medications", PatientMedicationListView.as_view(), name="medications-list"),
    path("clinical/summary", ClinicalSummaryView.as_view(), name="clinical-summary"),
    path("clinical/priorities", ClinicalPrioritiesView.as_view(), name="clinical-priorities"),
    path("clinical/imaging-queue", ClinicalImagingQueueView.as_view(), name="clinical-imaging-queue"),
    path("clinical/preconsultation", ClinicalPreconsultationView.as_view(), name="clinical-preconsultation"),
]
