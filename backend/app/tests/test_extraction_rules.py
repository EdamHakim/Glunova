from app.services.document_ocr.extraction_rules import extract_from_ocr_text


def test_glucose_and_hba1c_lab() -> None:
    text = """
    Lab Report - City Lab
    Date: 2026-03-15
    Glucose: 110 mg/dL
    HbA1c: 6.2 %
    Blood pressure 128/82
    """
    r = extract_from_ocr_text(text)
    assert r.glucose == 110.0
    assert r.glucose_unit == "mg/dL"
    assert r.hba1c == 6.2
    assert r.blood_pressure_systolic == 128
    assert r.blood_pressure_diastolic == 82
    assert r.document_type == "lab_report"
    assert r.date == "2026-03-15"


def test_prescription_rx_block() -> None:
    text = """
    Dr. Smith
    Prescription
    Rx
    Metformin 500 mg    twice daily
    """
    r = extract_from_ocr_text(text)
    assert r.doctor_name is not None
    assert "smith" in (r.doctor_name or "").lower()
    assert r.document_type == "prescription"
    assert len(r.medications) >= 1
    assert "metformin" in (r.medications[0].name or "").lower()


def test_empty_text() -> None:
    r = extract_from_ocr_text("")
    assert r.document_type == "unknown"
    assert r.glucose is None
