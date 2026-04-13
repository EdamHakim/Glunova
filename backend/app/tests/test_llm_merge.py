from app.schemas.document_extraction import DocumentExtractionResult
from app.services.document_ocr.llm_refinement import _merge_llm_into_rules


def test_merge_adds_grounded_glucose() -> None:
    ocr = "Random text glucose value 142 mg/dL end"
    rules = DocumentExtractionResult()
    llm = {"glucose": 142, "glucose_unit": "mg/dL"}
    out = _merge_llm_into_rules(rules, llm, ocr)
    assert out.glucose == 142
    assert out.glucose_unit == "mg/dL"


def test_merge_rejects_ungrounded_value() -> None:
    ocr = "no numbers here except nine"
    rules = DocumentExtractionResult()
    llm = {"glucose": 999}
    out = _merge_llm_into_rules(rules, llm, ocr)
    assert out.glucose is None


def test_rule_value_kept_when_llm_differs() -> None:
    ocr = "glucose 100 mg/dl"
    rules = DocumentExtractionResult(glucose=100.0, glucose_unit="mg/dL")
    llm = {"glucose": 200}
    out = _merge_llm_into_rules(rules, llm, ocr)
    assert out.glucose == 100.0
