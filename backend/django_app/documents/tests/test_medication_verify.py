from __future__ import annotations

import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from documents.services.medication_verify import (
    RxNormCandidate,
    _cached_rxnorm_approximate_candidates,
    _cached_rxnorm_display_name,
    fetch_rxnorm_candidates_with_variants,
    fetch_rxnorm_candidates,
    _select_medication_context_window,
    verify_and_enrich_medications,
    verify_medication_entry,
)


class FetchRxNormCandidatesTests(SimpleTestCase):
    def test_select_medication_context_window_prefers_best_matching_line_and_neighbors(self):
        raw_ocr = "\n".join(
            [
                "Header line",
                "Am0xicillin 500 mg oral capsule twice daily",
                "for 7 days",
                "Ibuprofen 200 mg tablet prn",
            ]
        )

        context = _select_medication_context_window(
            {"name": "amoxicillin", "dosage": "500 mg", "route": "oral", "frequency": "twice daily"},
            raw_ocr,
        )

        self.assertIn("Am0xicillin 500 mg oral capsule twice daily", context)
        self.assertIn("for 7 days", context)
        self.assertNotIn("Ibuprofen 200 mg tablet prn", context)

    @override_settings(RXNORM_BASE_URL="https://rxnav.example/REST", MEDICATION_VERIFY_TIMEOUT_SECONDS=7)
    @patch("documents.services.medication_verify.request.urlopen")
    def test_fetch_rxnorm_candidates_parses_candidates_and_names(self, mock_urlopen: Mock):
        _cached_rxnorm_approximate_candidates.cache_clear()
        _cached_rxnorm_display_name.cache_clear()
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

    @override_settings(
        RXNORM_BASE_URL="https://rxnav.example/REST",
        MEDICATION_VERIFY_TIMEOUT_SECONDS=7,
        MEDICATION_VERIFY_PROPERTY_LOOKUP_LIMIT=1,
    )
    @patch("documents.services.medication_verify.request.urlopen")
    def test_fetch_rxnorm_candidates_uses_cache_and_limits_property_lookups(self, mock_urlopen: Mock):
        _cached_rxnorm_approximate_candidates.cache_clear()
        _cached_rxnorm_display_name.cache_clear()

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

        mock_urlopen.side_effect = [approx_response, properties_one]

        first = fetch_rxnorm_candidates("amox")
        second = fetch_rxnorm_candidates("amox")

        self.assertEqual(first, second)
        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertEqual(first[0].name, "Amoxicillin 500 MG Oral Capsule")
        self.assertIsNone(first[1].name)

    @patch("documents.services.medication_verify.fetch_rxnorm_candidates")
    def test_fetch_rxnorm_candidates_with_variants_reranks_by_ocr_similarity(self, mock_fetch_rxnorm_candidates: Mock):
        mock_fetch_rxnorm_candidates.side_effect = [
            [],
            [RxNormCandidate(rxcui="111", score=82, rank=1, name="Ampicillin 500 MG Oral Capsule")],
            [RxNormCandidate(rxcui="222", score=79, rank=1, name="Amoxicillin 500 MG Oral Capsule")],
        ]

        candidates = fetch_rxnorm_candidates_with_variants("am0xicillin caps")

        self.assertEqual(candidates[0].rxcui, "222")
        self.assertGreater(candidates[0].match_score or 0, candidates[1].match_score or 0)

    @patch("documents.services.medication_verify.fetch_rxnorm_candidates")
    def test_fetch_rxnorm_candidates_with_variants_prefers_strength_and_form_context(
        self,
        mock_fetch_rxnorm_candidates: Mock,
    ):
        mock_fetch_rxnorm_candidates.return_value = [
            RxNormCandidate(rxcui="111", score=91, rank=1, name="Metformin 500 MG Oral Tablet"),
            RxNormCandidate(rxcui="222", score=93, rank=2, name="Metformin 850 MG Oral Tablet"),
            RxNormCandidate(rxcui="333", score=92, rank=3, name="Metformin 500 MG Oral Capsule"),
        ]

        candidates = fetch_rxnorm_candidates_with_variants(
            "metforrnin",
            medication={"name": "metforrnin", "dosage": "500 mg", "route": "oral"},
            raw_ocr_text="Rx line: metforrnin 500 mg oral tablet twice daily",
        )

        self.assertEqual(candidates[0].rxcui, "111")
        self.assertGreater(candidates[0].context_score or 0, candidates[1].context_score or 0)
        self.assertGreater(candidates[0].context_score or 0, candidates[2].context_score or 0)


class VerifyMedicationEntryTests(SimpleTestCase):
    @patch("documents.services.medication_verify.fetch_rxnorm_candidates_with_variants")
    def test_verify_medication_entry_marks_clear_rxnorm_match(self, mock_fetch_rxnorm_candidates_with_variants: Mock):
        mock_fetch_rxnorm_candidates_with_variants.return_value = [
            RxNormCandidate(
                rxcui="123",
                score=95,
                rank=1,
                name="Paracetamol 500 MG Oral Tablet",
                match_score=97,
                context_score=55,
            ),
            RxNormCandidate(
                rxcui="456",
                score=80,
                rank=2,
                name="Paramax 500 MG Oral Tablet",
                match_score=74,
                context_score=20,
            ),
        ]

        result = verify_medication_entry({"name": "paracetamol", "dosage": "500mg"}, raw_ocr_text="paracetamol 500mg")

        self.assertEqual(result["verification"]["status"], "matched")
        self.assertEqual(result["verification"]["rxcui"], "123")
        self.assertEqual(result["verification"]["name_display"], "Paracetamol 500 MG Oral Tablet")

    @patch("documents.services.medication_verify.groq_suggest_ocr_corrections")
    @patch("documents.services.medication_verify.groq_tiebreak_medication")
    @patch("documents.services.medication_verify.fetch_rxnorm_candidates_with_variants")
    def test_verify_medication_entry_skips_groq_for_fast_path_match(
        self,
        mock_fetch_rxnorm_candidates_with_variants: Mock,
        mock_groq_tiebreak_medication: Mock,
        mock_groq_suggest_ocr_corrections: Mock,
    ):
        mock_fetch_rxnorm_candidates_with_variants.return_value = [
            RxNormCandidate(
                rxcui="123",
                score=76,
                rank=1,
                name="Amoxicillin 500 MG Oral Capsule",
                match_score=94,
                context_score=34,
            ),
            RxNormCandidate(
                rxcui="456",
                score=75,
                rank=2,
                name="Ampicillin 500 MG Oral Capsule",
                match_score=88,
                context_score=28,
            ),
        ]
        mock_groq_suggest_ocr_corrections.return_value = {"suggestions": []}

        result = verify_medication_entry(
            {"name": "am0xicillin", "dosage": "500mg", "route": "oral"},
            raw_ocr_text="Rx: am0xicillin 500mg oral capsule",
        )

        self.assertEqual(result["verification"]["status"], "matched")
        self.assertEqual(result["verification"]["rxcui"], "123")
        self.assertEqual(result["verification"]["note"], "Matched via RxNorm fast-path")
        mock_groq_tiebreak_medication.assert_not_called()

    @patch("documents.services.medication_verify.groq_suggest_ocr_corrections")
    @patch("documents.services.medication_verify.groq_tiebreak_medication")
    @patch("documents.services.medication_verify.fetch_rxnorm_candidates_with_variants")
    def test_verify_medication_entry_uses_groq_for_ambiguous_match(
        self,
        mock_fetch_rxnorm_candidates_with_variants: Mock,
        mock_groq_tiebreak_medication: Mock,
        mock_groq_suggest_ocr_corrections: Mock,
    ):
        mock_fetch_rxnorm_candidates_with_variants.return_value = [
            RxNormCandidate(
                rxcui="123",
                score=88,
                rank=1,
                name="Amoxicillin 500 MG Oral Capsule",
                match_score=91,
                context_score=22,
            ),
            RxNormCandidate(
                rxcui="456",
                score=85,
                rank=2,
                name="Amoxicillin/Clavulanate 500 MG Oral Tablet",
                match_score=90,
                context_score=20,
            ),
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
    @patch("documents.services.medication_verify.fetch_rxnorm_candidates_with_variants")
    def test_verify_medication_entry_uses_llm_ocr_rescue_for_unverified_name(
        self,
        mock_fetch_rxnorm_candidates_with_variants: Mock,
        mock_groq_suggest_ocr_corrections: Mock,
    ):
        mock_fetch_rxnorm_candidates_with_variants.side_effect = [
            [],
            [
                RxNormCandidate(
                    rxcui="999",
                    score=93,
                    rank=1,
                    name="Paracetamol 500 MG Oral Tablet",
                    match_score=96,
                    context_score=30,
                )
            ],
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
    @patch("documents.services.medication_verify.fetch_rxnorm_candidates_with_variants")
    def test_verify_medication_entry_keeps_ambiguous_status_when_llm_rescue_still_unclear(
        self,
        mock_fetch_rxnorm_candidates_with_variants: Mock,
        mock_groq_tiebreak_medication: Mock,
        mock_groq_suggest_ocr_corrections: Mock,
    ):
        mock_fetch_rxnorm_candidates_with_variants.side_effect = [
            [
                RxNormCandidate(rxcui="123", score=88, rank=1, name="Amoxil", match_score=89, context_score=5),
                RxNormCandidate(rxcui="456", score=87, rank=2, name="Amoxicillin", match_score=88, context_score=4),
            ],
            [
                RxNormCandidate(
                    rxcui="777",
                    score=84,
                    rank=1,
                    name="Amoxicillin 250 MG",
                    match_score=70,
                    context_score=2,
                ),
                RxNormCandidate(
                    rxcui="888",
                    score=82,
                    rank=2,
                    name="Ampicillin 250 MG",
                    match_score=68,
                    context_score=1,
                ),
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

    @patch("documents.services.medication_verify.fetch_rxnorm_candidates_with_variants")
    def test_verify_medication_entry_prefers_context_aligned_candidate(
        self,
        mock_fetch_rxnorm_candidates_with_variants: Mock,
    ):
        mock_fetch_rxnorm_candidates_with_variants.return_value = [
            RxNormCandidate(
                rxcui="123",
                score=95,
                rank=1,
                name="Prednisone 20 MG Oral Tablet",
                match_score=86,
                context_score=55,
            ),
            RxNormCandidate(
                rxcui="456",
                score=97,
                rank=2,
                name="Prednisone 10 MG Oral Tablet",
                match_score=87,
                context_score=10,
            ),
        ]

        result = verify_medication_entry(
            {"name": "prednisone", "dosage": "20 mg", "route": "oral"},
            raw_ocr_text="Vitamin D 1000 IU\nTake prednisone 20 mg oral tablet once daily\nIbuprofen 400 mg",
        )

        self.assertEqual(result["verification"]["status"], "matched")
        self.assertEqual(result["verification"]["rxcui"], "123")
        self.assertIn("prednisone 20 mg oral tablet once daily", result["verification"]["ocr_context_window"].lower())
        self.assertNotIn("Vitamin D 1000 IU", result["verification"]["ocr_context_window"])

    @patch("documents.services.medication_verify.fetch_rxnorm_candidates_with_variants")
    def test_verify_and_enrich_medications_skips_non_prescriptions(
        self,
        mock_fetch_rxnorm_candidates_with_variants: Mock,
    ):
        merged = {
            "document_type": "lab_report",
            "medications": [{"name": "ibuprofen"}],
        }

        result = verify_and_enrich_medications(merged, "ibuprofen")

        self.assertEqual(result, merged)
        mock_fetch_rxnorm_candidates_with_variants.assert_not_called()
