from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clinical.models import PatientMedication
from clinical.views import PatientMedicationListView
from documents.models import MedicalDocument

User = get_user_model()


class PatientMedicationApiTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.patient = User.objects.create_user(username="patient-api", password="test", role="patient")
        self.image_doc = MedicalDocument.objects.create(
            patient=self.patient,
            uploaded_by=self.patient,
            original_filename="prescription-image.png",
            mime_type="image/png",
            storage_path="patient_1/prescription-image.png",
            processing_status=MedicalDocument.ProcessingStatus.COMPLETED,
        )
        self.pdf_doc = MedicalDocument.objects.create(
            patient=self.patient,
            uploaded_by=self.patient,
            original_filename="prescription-copy.pdf",
            mime_type="application/pdf",
            storage_path="patient_1/prescription-copy.pdf",
            processing_status=MedicalDocument.ProcessingStatus.COMPLETED,
        )

    def test_medications_api_dedupes_same_medication_across_documents_and_exposes_preview(self):
        PatientMedication.objects.create(
            patient=self.patient,
            source_document=self.image_doc,
            name_raw="amoxicillin",
            name_display="Amoxicillin 500 MG Oral Capsule",
            rxcui="723",
            dosage="500mg",
            frequency="twice daily",
            route="oral",
            verification_status="matched",
        )
        PatientMedication.objects.create(
            patient=self.patient,
            source_document=self.pdf_doc,
            name_raw="amoxicillin",
            name_display="Amoxicillin 500 MG Oral Capsule",
            rxcui="723",
            dosage="500mg",
            frequency="twice daily",
            route="oral",
            verification_status="matched",
        )

        request = self.factory.get(f"/api/v1/medications?patient_id={self.patient.pk}")
        force_authenticate(request, user=self.patient)
        response = PatientMedicationListView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        item = response.data["items"][0]
        self.assertEqual(item["source_document_id"], str(self.image_doc.id))
        self.assertEqual(item["source_document_count"], 2)
        self.assertEqual(item["source_document_mime_type"], "image/png")
        self.assertTrue(item["source_document_preview_url"].endswith(f"/api/v1/documents/{self.image_doc.id}/preview"))
