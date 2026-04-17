from django.test import SimpleTestCase

from documents.services.extraction_rules import run_rule_validation


class RuleExtractionTests(SimpleTestCase):
    def test_document_type_lab(self):
        text = "Laboratory report — reference range for HbA1c."
        out = run_rule_validation(text)
        self.assertEqual(out["document_type"], "lab_report")
