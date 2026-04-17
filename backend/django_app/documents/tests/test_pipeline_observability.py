from __future__ import annotations

from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from documents.models import MedicalDocument
from documents.services.pipeline import process_document_upload

User = get_user_model()


class PipelineObservabilityTests(TestCase):
    def setUp(self) -> None:
        self.patient = User.objects.create_user(username="patient-ocr", password="test", role="patient")
        self.doc = MedicalDocument.objects.create(
            patient=self.patient,
            uploaded_by=self.patient,
            original_filename="scan.pdf",
            mime_type="application/pdf",
            storage_path="patient_1/scan.pdf",
            processing_status=MedicalDocument.ProcessingStatus.PENDING,
        )

    @patch("documents.services.pipeline.upload_medical_file")
    @patch("documents.services.pipeline.httpx.Client")
    def test_pipeline_persists_top_level_raw_ocr_and_ocr_meta(
        self,
        mock_client_class: Mock,
        mock_upload_medical_file: Mock,
    ) -> None:
        mock_upload_medical_file.return_value = None

        mock_response = Mock()
        mock_response.json.return_value = {
            "raw_ocr_text": "[page 1]\nscanned text",
            "extracted_json": {"document_type": "unknown"},
            "extracted_json_rules": {
                "_ocr_meta": {
                    "source": "pdf_raster",
                    "used_raster_fallback": True,
                    "low_quality": False,
                }
            },
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
        self.assertEqual(self.doc.raw_ocr_text, "[page 1]\nscanned text")
        self.assertEqual(self.doc.extracted_json_rules["_ocr_meta"]["source"], "pdf_raster")
        self.assertEqual(self.doc.processing_status, MedicalDocument.ProcessingStatus.COMPLETED)
