from django.test import SimpleTestCase

from documents.services.extraction_rules import run_rule_validation


class RuleExtractionTests(SimpleTestCase):
    def test_blood_pressure(self):
        text = "Patient vitals: BP 128/82 noted in clinic."
        out = run_rule_validation(text)
        self.assertEqual(out["vitals"]["blood_pressure"], "128/82")

    def test_glucose_lab(self):
        text = "Glucose: 104 mg/dl after fasting."
        out = run_rule_validation(text)
        names = [lab["name"] for lab in out["labs"]]
        self.assertIn("Glucose", names)

    def test_document_type_lab(self):
        text = "Laboratory report — reference range for HbA1c."
        out = run_rule_validation(text)
        self.assertEqual(out["document_type"], "lab_report")
