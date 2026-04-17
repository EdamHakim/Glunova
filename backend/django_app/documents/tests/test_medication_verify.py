from __future__ import annotations

import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from documents.services.medication_verify import (
    RxNormCandidate,
    fetch_rxnorm_candidates,
    verify_and_enrich_medications,
    verify_medication_entry,
)


class FetchRxNormCandidatesTests(SimpleTestCase):
    @override_settings(RXNORM_BASE_URL="https://rxnav.example/REST", MEDICATION_VERIFY_TIMEOUT_SECONDS=7)
    @patch("documents.services.medication_verify.request.urlopen")
    def test_fetch_rxnorm_candidates_parses_candidates_and_names(self, mock_urlopen: Mock):
        approx_response = Mock()
        approx_response.read.return_value = json.dumps(
            {
                "approximateGroup": {
                    "candidate": [
                        {"rxcui": "123", "score": "92", "rank": "1"},
                        {"rxcui": "456", "score": "89", "rank": "2"},
                    ]
                }
            }
        ).encode("utf-8")
        approx_response.__enter__ = Mock(return_value=approx_response)
        approx_response.__exit__ = Mock(return_value=None)

        properties_one = Mock()
        properties_one.read.return_value = json.dumps({"properties": {"name": "Amoxicillin 500 MG Oral Capsule"}}).encode(
            "utf-8"
        )
        properties_one.__enter__ = Mock(return_value=properties_one)
        properties_one.__exit__ = Mock(return_value=None)

        properties_two = Mock()
        properties_two.read.return_value = json.dumps({"properties": {"name": "Ampicillin 500 MG Oral Capsule"}}).encode(
            "utf-8"
        )
        properties_two.__enter__ = Mock(return_value=properties_two)
        properties_two.__exit__ = Mock(return_value=None)

        mock_urlopen.side_effect = [approx_response, properties_one, properties_two]

        candidates = fetch_rxnorm_candidates("amox")

        self.assertEqual(
            candidates,
            [
                RxNormCandidate(rxcui="123", score=92, rank=1, name="Amoxicillin 500 MG Oral Capsule"),
                RxNormCandidate(rxcui="456", score=89, rank=2, name="Ampicillin 500 MG Oral Capsule"),
            ],
        )
        self.assertEqual(mock_urlopen.call_count, 3)


class VerifyMedicationEntryTests(SimpleTestCase):
    @patch("documents.services.medication_verify.fetch_rxnorm_candidates")
    def test_verify_medication_entry_marks_clear_rxnorm_match(self, mock_fetch_rxnorm_candidates: Mock):
        mock_fetch_rxnorm_candidates.return_value = [
            RxNormCandidate(rxcui="123", score=95, rank=1, name="Paracetamol 500 MG Oral Tablet"),
            RxNormCandidate(rxcui="456", score=80, rank=2, name="Paramax 500 MG Oral Tablet"),
        ]

        result = verify_medication_entry({"name": "paracetamol", "dosage": "500mg"}, raw_ocr_text="paracetamol 500mg")

        self.assertEqual(result["verification"]["status"], "matched")
        self.assertEqual(result["verification"]["rxcui"], "123")
        self.assertEqual(result["verification"]["name_display"], "Paracetamol 500 MG Oral Tablet")

    @patch("documents.services.medication_verify.groq_suggest_ocr_corrections")
    @patch("documents.services.medication_verify.groq_tiebreak_medication")
    @patch("documents.services.medication_verify.fetch_rxnorm_candidates")
    def test_verify_medication_entry_uses_groq_for_ambiguous_match(
        self,
        mock_fetch_rxnorm_candidates: Mock,
        mock_groq_tiebreak_medication: Mock,
        mock_groq_suggest_ocr_corrections: Mock,
    ):
        mock_fetch_rxnorm_candidates.return_value = [
            RxNormCandidate(rxcui="123", score=88, rank=1, name="Amoxicillin 500 MG Oral Capsule"),
            RxNormCandidate(rxcui="456", score=85, rank=2, name="Amoxicillin/Clavulanate 500 MG Oral Tablet"),
        ]
        mock_groq_tiebreak_medication.return_value = {"rxcui": "456", "reason": "OCR mentions clavulanate"}
        mock_groq_suggest_ocr_corrections.return_value = {"suggestions": []}

        result = verify_medication_entry(
            {"name": "amoxicillin clavulanate", "dosage": "500mg"},
            raw_ocr_text="Rx: amoxicillin clavulanate 500mg",
        )

        self.assertEqual(result["verification"]["status"], "matched")
        self.assertEqual(result["verification"]["rxcui"], "456")
        self.assertEqual(result["verification"]["note"], "OCR mentions clavulanate")

    @patch("documents.services.medication_verify.groq_suggest_ocr_corrections")
    @patch("documents.services.medication_verify.fetch_rxnorm_candidates")
    def test_verify_medication_entry_uses_llm_ocr_rescue_for_unverified_name(
        self,
        mock_fetch_rxnorm_candidates: Mock,
        mock_groq_suggest_ocr_corrections: Mock,
    ):
        mock_fetch_rxnorm_candidates.side_effect = [
            [],
            [RxNormCandidate(rxcui="999", score=93, rank=1, name="Paracetamol 500 MG Oral Tablet")],
        ]
        mock_groq_suggest_ocr_corrections.return_value = {
            "suggestions": [{"name": "paracetamol", "reason": "Likely OCR swap between c and e"}]
        }

        result = verify_medication_entry(
            {"name": "parecetamol", "dosage": "500mg"},
            raw_ocr_text="Rx: parecetamol 500mg tablets",
        )

        self.assertEqual(result["verification"]["status"], "matched")
        self.assertEqual(result["verification"]["rxcui"], "999")
        self.assertEqual(result["verification"]["corrected_name"], "paracetamol")
        self.assertEqual(result["verification"]["note"], "Likely OCR swap between c and e")

    @patch("documents.services.medication_verify.groq_suggest_ocr_corrections")
    @patch("documents.services.medication_verify.groq_tiebreak_medication")
    @patch("documents.services.medication_verify.fetch_rxnorm_candidates")
    def test_verify_medication_entry_keeps_ambiguous_status_when_llm_rescue_still_unclear(
        self,
        mock_fetch_rxnorm_candidates: Mock,
        mock_groq_tiebreak_medication: Mock,
        mock_groq_suggest_ocr_corrections: Mock,
    ):
        mock_fetch_rxnorm_candidates.side_effect = [
            [
                RxNormCandidate(rxcui="123", score=88, rank=1, name="Amoxil"),
                RxNormCandidate(rxcui="456", score=87, rank=2, name="Amoxicillin"),
            ],
            [
                RxNormCandidate(rxcui="777", score=84, rank=1, name="Amoxicillin 250 MG"),
                RxNormCandidate(rxcui="888", score=82, rank=2, name="Ampicillin 250 MG"),
            ],
        ]
        mock_groq_tiebreak_medication.return_value = {"rxcui": None, "reason": "OCR context is insufficient"}
        mock_groq_suggest_ocr_corrections.return_value = {
            "suggestions": [{"name": "amoxicillin", "reason": "Closest likely medication spelling"}]
        }

        result = verify_medication_entry(
            {"name": "amoxcillin", "dosage": "250mg"},
            raw_ocr_text="Rx: amoxcillin 250mg",
        )

        self.assertEqual(result["verification"]["status"], "ambiguous")
        self.assertIn("ocr_correction_attempts", result["verification"])
        self.assertIn("LLM OCR correction did not produce a clear RxNorm match", result["verification"]["note"])

    @patch("documents.services.medication_verify.fetch_rxnorm_candidates")
    def test_verify_and_enrich_medications_skips_non_prescriptions(self, mock_fetch_rxnorm_candidates: Mock):
        merged = {
            "document_type": "lab_report",
            "medications": [{"name": "ibuprofen"}],
        }

        result = verify_and_enrich_medications(merged, "ibuprofen")

        self.assertEqual(result, merged)
        mock_fetch_rxnorm_candidates.assert_not_called()
