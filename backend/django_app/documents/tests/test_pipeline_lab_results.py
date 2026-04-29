from __future__ import annotations

from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from documents.models import MedicalDocument
from documents.services.pipeline import process_document_upload
from monitoring.models import PatientLabResult

User = get_user_model()


class PipelineLabResultPersistenceTests(TestCase):
    def setUp(self) -> None:
        self.patient = User.objects.create_user(username="patient-labs", password="test", role="patient")
        self.doc = MedicalDocument.objects.create(
            patient=self.patient,
            uploaded_by=self.patient,
            original_filename="lab-report.pdf",
            mime_type="application/pdf",
            storage_path="patient_1/lab-report.pdf",
            processing_status=MedicalDocument.ProcessingStatus.PENDING,
        )

    @patch("documents.services.pipeline.upload_medical_file")
    @patch("documents.services.pipeline.httpx.Client")
    def test_pipeline_persists_lab_results_for_monitoring(
        self,
        mock_client_class: Mock,
        mock_upload_medical_file: Mock,
    ) -> None:
        mock_upload_medical_file.return_value = None

        mock_response = Mock()
        mock_response.json.return_value = {
            "raw_ocr_text": "GLYCEMIE 5.83 mmol/L\nHEMOGLOBINE GLYQUEE 5.52 %",
            "extracted_json": {
                "document_type": "lab_report",
                "date": "2026-03-31",
                "labs": [
                    {"name": "Glucose", "value": "5.83", "unit": "mmol/L"},
                    {"name": "HbA1c", "value": "5.52", "unit": "%"},
                    {"name": "HbA1c", "value": "5.52", "unit": "%"},
                ],
            },
            "extracted_json_rules": {"document_type": "lab_report"},
            "field_evidence": {},
            "status": "ok",
        }
        mock_response.raise_for_status.return_value = None

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        process_document_upload(self.doc, b"%PDF", "application/pdf")

        self.doc.refresh_from_db()
        self.assertEqual(self.doc.processing_status, MedicalDocument.ProcessingStatus.COMPLETED)
        self.assertEqual(PatientLabResult.objects.filter(source_document=self.doc).count(), 2)

        glucose = PatientLabResult.objects.get(source_document=self.doc, normalized_name="glucose")
        self.assertEqual(glucose.value, "5.83")
        self.assertEqual(glucose.unit, "mmol/L")
        self.assertEqual(glucose.numeric_value, 5.83)
        self.assertIsNotNone(glucose.observed_at)

    @patch("documents.services.pipeline.upload_medical_file")
    @patch("documents.services.pipeline.httpx.Client")
    def test_reprocessing_replaces_document_lab_results(
        self,
        mock_client_class: Mock,
        mock_upload_medical_file: Mock,
    ) -> None:
        mock_upload_medical_file.return_value = None

        first_response = Mock()
        first_response.json.return_value = {
            "raw_ocr_text": "CREATININE 71.6 µmol/L",
            "extracted_json": {
                "document_type": "lab_report",
                "date": "2026-03-31",
                "labs": [{"name": "Creatinine", "value": "71.6", "unit": "µmol/L"}],
            },
            "extracted_json_rules": {"document_type": "lab_report"},
            "field_evidence": {},
            "status": "ok",
        }
        first_response.raise_for_status.return_value = None

        second_response = Mock()
        second_response.json.return_value = {
            "raw_ocr_text": "CREATININE 8.1 mg/L",
            "extracted_json": {
                "document_type": "lab_report",
                "date": "2026-03-31",
                "labs": [{"name": "Creatinine", "value": "8.1", "unit": "mg/L"}],
            },
            "extracted_json_rules": {"document_type": "lab_report"},
            "field_evidence": {},
            "status": "ok",
        }
        second_response.raise_for_status.return_value = None

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.post.side_effect = [first_response, second_response]
        mock_client_class.return_value = mock_client

        process_document_upload(self.doc, b"%PDF", "application/pdf")
        process_document_upload(self.doc, b"%PDF", "application/pdf")

        rows = list(PatientLabResult.objects.filter(source_document=self.doc))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].value, "8.1")
        self.assertEqual(rows[0].unit, "mg/L")
