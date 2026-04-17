from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from clinical.models import PatientMedication
from documents.models import MedicalDocument
from documents.services.pipeline import process_document_upload

User = get_user_model()


class PipelineMedicationPersistenceTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(username="patient1", password="test", role="patient")
        self.doc = MedicalDocument.objects.create(
            patient=self.patient,
            uploaded_by=self.patient,
            original_filename="prescription.png",
            mime_type="image/png",
            storage_path="patient_1/prescription.png",
            processing_status=MedicalDocument.ProcessingStatus.PENDING,
        )

    @patch("documents.services.pipeline.upload_medical_file")
    @patch("documents.services.pipeline.extract_local_ocr_text")
    @patch("documents.services.pipeline.run_groq_structured_extract")
    @patch("documents.services.pipeline.run_rule_validation")
    @patch("documents.services.pipeline.merge_and_validate")
    @patch("documents.services.pipeline.verify_and_enrich_medications")
    def test_reprocessing_replaces_document_medications(
        self,
        mock_verify_and_enrich_medications,
        mock_merge_and_validate,
        mock_run_rule_validation,
        mock_run_groq_structured_extract,
        mock_extract_local_ocr_text,
        mock_upload_medical_file,
    ):
        mock_upload_medical_file.return_value = None
        mock_extract_local_ocr_text.return_value = "Take amoxicillin twice daily"
        mock_run_groq_structured_extract.return_value = {"extracted": {}, "field_evidence": {}}
        mock_run_rule_validation.return_value = {"document_type": "prescription", "medications": []}
        mock_merge_and_validate.return_value = {"document_type": "prescription", "medications": []}
        mock_verify_and_enrich_medications.side_effect = [
            {
                "document_type": "prescription",
                "medications": [
                    {
                        "name": "amoxicillin",
                        "dosage": "500mg",
                        "frequency": "twice daily",
                        "verification": {
                            "status": "matched",
                            "rxcui": "723",
                            "name_display": "Amoxicillin 500 MG Oral Capsule",
                        },
                    }
                ],
            },
            {
                "document_type": "prescription",
                "medications": [
                    {
                        "name": "ibuprofen",
                        "dosage": "200mg",
                        "frequency": "nightly",
                        "verification": {
                            "status": "unverified",
                            "rxcui": None,
                            "name_display": None,
                        },
                    }
                ],
            },
        ]

        process_document_upload(self.doc, b"fake-image", "image/png")
        self.assertEqual(PatientMedication.objects.filter(source_document=self.doc).count(), 1)
        first = PatientMedication.objects.get(source_document=self.doc)
        self.assertEqual(first.name_raw, "amoxicillin")
        self.assertEqual(first.rxcui, "723")

        process_document_upload(self.doc, b"fake-image", "image/png")
        self.assertEqual(PatientMedication.objects.filter(source_document=self.doc).count(), 1)
        replacement = PatientMedication.objects.get(source_document=self.doc)
        self.assertEqual(replacement.name_raw, "ibuprofen")
        self.assertIsNone(replacement.rxcui)
        self.assertEqual(replacement.verification_status, "unverified")

    @patch("documents.services.pipeline.upload_medical_file")
    @patch("documents.services.pipeline.extract_local_ocr_text")
    @patch("documents.services.pipeline.run_groq_structured_extract")
    @patch("documents.services.pipeline.run_rule_validation")
    @patch("documents.services.pipeline.merge_and_validate")
    @patch("documents.services.pipeline.verify_and_enrich_medications")
    def test_duplicate_medication_rows_from_same_document_are_collapsed(
        self,
        mock_verify_and_enrich_medications,
        mock_merge_and_validate,
        mock_run_rule_validation,
        mock_run_groq_structured_extract,
        mock_extract_local_ocr_text,
        mock_upload_medical_file,
    ):
        mock_upload_medical_file.return_value = None
        mock_extract_local_ocr_text.return_value = "Take amoxicillin twice daily"
        mock_run_groq_structured_extract.return_value = {"extracted": {}, "field_evidence": {}}
        mock_run_rule_validation.return_value = {"document_type": "prescription", "medications": []}
        mock_merge_and_validate.return_value = {"document_type": "prescription", "medications": []}
        mock_verify_and_enrich_medications.return_value = {
            "document_type": "prescription",
            "medications": [
                {
                    "name": "amoxicillin",
                    "dosage": "500mg",
                    "frequency": "twice daily",
                    "route": "oral",
                    "verification": {
                        "status": "matched",
                        "rxcui": "723",
                        "name_display": "Amoxicillin 500 MG Oral Capsule",
                    },
                },
                {
                    "name": "amoxicillin",
                    "dosage": "500mg",
                    "frequency": "twice daily",
                    "route": "oral",
                    "verification": {
                        "status": "matched",
                        "rxcui": "723",
                        "name_display": "Amoxicillin 500 MG Oral Capsule",
                    },
                },
            ],
        }

        process_document_upload(self.doc, b"fake-image", "image/png")

        self.assertEqual(PatientMedication.objects.filter(source_document=self.doc).count(), 1)
