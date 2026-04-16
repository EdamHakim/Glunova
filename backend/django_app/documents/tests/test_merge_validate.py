from django.test import SimpleTestCase

from documents.services.extraction_rules import run_rule_validation
from documents.services.merge_validate import merge_and_validate


class MergeValidateTests(SimpleTestCase):
    def test_rules_win_bp_when_llm_ungrounded(self):
        raw = "Blood pressure 120/80 today."
        rules = run_rule_validation(raw)
        llm = {
            "patient": {"name": None, "dob": None, "id": None},
            "document_type": "unknown",
            "date": None,
            "vitals": {"blood_pressure": "999/999", "heart_rate": None},
            "labs": [],
            "medications": [],
            "notes": None,
        }
        fe = {}
        merged = merge_and_validate(raw, rules, llm, fe)
        self.assertEqual(merged["vitals"]["blood_pressure"], "120/80")

    def test_llm_name_with_evidence(self):
        raw = "Patient name: Jane Doe presented for follow-up."
        rules = run_rule_validation(raw)
        llm = {
            "patient": {"name": "Jane Doe", "dob": None, "id": None},
            "document_type": "unknown",
            "date": None,
            "vitals": {"blood_pressure": None, "heart_rate": None},
            "labs": [],
            "medications": [],
            "notes": None,
        }
        fe = {"patient.name": "Jane Doe"}
        merged = merge_and_validate(raw, rules, llm, fe)
        self.assertEqual(merged["patient"]["name"], "Jane Doe")
