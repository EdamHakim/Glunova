"""Deterministic extraction from OCR plain text."""

from __future__ import annotations

import re
from typing import Any

from dateutil import parser as date_parser

from app.schemas.document_extraction import DocumentExtractionResult, MedicationItem


def _first_float(s: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)", s.replace(",", "."))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _parse_iso_date(text: str) -> str | None:
    for m in re.finditer(
        r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b",
        text,
    ):
        try:
            dt = date_parser.parse(m.group(1), dayfirst=False, yearfirst=True)
            return dt.date().isoformat()
        except (ValueError, TypeError, OverflowError):
            continue
    return None


def _extract_doctor(text: str) -> str | None:
    for pat in (
        r"(?:dr\.?|doctor)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})",
        r"(?:dr\.?|doctor)\s*([a-z]+(?:\s+[a-z]+){0,3})",
    ):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if len(name) > 2:
                return name.title()
    return None


def _extract_patient_name(text: str) -> str | None:
    m = re.search(
        r"(?:patient|name|nom)\s*[:\s]+\s*([A-Za-z][A-Za-z\s'.-]{2,60})",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip().title()
    return None


def _extract_age(text: str) -> int | None:
    m = re.search(r"(?:age|âge)\s*[:\s]*(\d{1,3})\s*(?:y|yr|years|ans)?", text, re.IGNORECASE)
    if m:
        try:
            a = int(m.group(1))
            return a if 0 < a < 130 else None
        except ValueError:
            pass
    return None


def _extract_gender(text: str) -> str | None:
    if re.search(r"\bmale\b|\bhomme\b|\bmasculin\b", text, re.IGNORECASE):
        if not re.search(r"\bfemale\b|\bfemme\b", text, re.IGNORECASE):
            return "male"
    if re.search(r"\bfemale\b|\bfemme\b|\bféminin\b", text, re.IGNORECASE):
        return "female"
    return None


def _extract_bp(text: str) -> tuple[int | None, int | None]:
    m = re.search(r"\b(\d{2,3})\s*/\s*(\d{2,3})\b", text)
    if m:
        try:
            return int(m.group(1)), int(m.group(2))
        except ValueError:
            pass
    m = re.search(r"bp\s*[:\s]*(\d{2,3})\s*[/\s]\s*(\d{2,3})", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1)), int(m.group(2))
        except ValueError:
            pass
    return None, None


def _near_label(text: str, label_pattern: str) -> str | None:
    m = re.search(
        rf"{label_pattern}\s*[:\s]{{0,3}}([^\n]{{0,80}})",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    g = m.group(1)
    if g is None:
        return None
    s = g.strip()
    return s if s else None


def extract_from_ocr_text(text: str) -> DocumentExtractionResult:
    t = text or ""
    low = t.lower()

    glucose = None
    glucose_unit = None
    gm = re.search(
        r"(?:glucose|blood\s+sugar|glycemia)\s*[: ]\s*([^\n]+)",
        low,
        re.IGNORECASE,
    )
    chunk = (gm.group(1).strip() if gm and gm.group(1) else None) or _near_label(
        low, r"glucose|blood sugar|glycemia|glycemie"
    )
    if chunk:
        glucose = _first_float(chunk)
        if "mmol" in chunk:
            glucose_unit = "mmol/L"
        elif "mg" in chunk or "dl" in chunk:
            glucose_unit = "mg/dL"

    hba1c = None
    hba1c_unit = None
    hm = re.search(
        r"(?:hba1c|hemoglobin\s*a1c|glycated\s*hemoglobin)\s*[: ]\s*([^\n]+)",
        low,
        re.IGNORECASE,
    )
    chunk = (hm.group(1).strip() if hm and hm.group(1) else None) or _near_label(
        low, r"hba1c|hemoglobin a1c|glycated hemoglobin|a1c"
    )
    if chunk:
        hba1c = _first_float(chunk)
        if hba1c is not None and "%" in chunk:
            hba1c_unit = "%"

    cholesterol = None
    cholesterol_unit = None
    chunk = _near_label(low, r"cholesterol|cholestérol|ldl|hdl|total chol")
    if chunk:
        cholesterol = _first_float(chunk)
        if "mg/dl" in chunk or "mg / dl" in chunk:
            cholesterol_unit = "mg/dL"
        elif "mmol" in chunk:
            cholesterol_unit = "mmol/L"

    insulin = None
    insulin_unit = None
    chunk = _near_label(low, r"insulin|insuline")
    if chunk:
        insulin = _first_float(chunk)
        if "unit" in chunk:
            insulin_unit = "units"

    sys_d, dia_d = _extract_bp(t)

    medications: list[MedicationItem] = []
    in_rx = False
    for raw_line in t.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        llow = line.lower()
        if re.match(r"^rx\b|^r/x\b|prescription|ordonnance", llow):
            in_rx = True
            continue
        if in_rx or re.search(
            r"\b(mg|mcg|g)\b.*\b(bid|tid|qid|daily|once|twice|od|hs)\b",
            llow,
        ):
            parts = re.split(r"\s{2,}|\t", line)
            if len(parts) >= 1 and len(line) > 3:
                med = MedicationItem(
                    name=parts[0][:200] or None,
                    dosage=parts[1][:120] if len(parts) > 1 else None,
                    frequency=parts[2][:120] if len(parts) > 2 else None,
                    duration=parts[3][:120] if len(parts) > 3 else None,
                    route=parts[4][:80] if len(parts) > 4 else None,
                )
                if med.name:
                    medications.append(med)

    diagnosis = None
    dm = re.search(
        r"(?:diagnosis|diagnostic|dx)\s*[:\s]+([^\n]{5,200})",
        t,
        re.IGNORECASE,
    )
    if dm:
        diagnosis = dm.group(1).strip()

    instructions = None
    im = re.search(
        r"(?:instructions?|directions?)\s*[:\s]+([^\n]{5,500})",
        t,
        re.IGNORECASE,
    )
    if im:
        instructions = im.group(1).strip()

    lab_name = None
    lm = re.search(
        r"(?i)(?:laboratory|lab\s+name|clinical\s+laboratory|laboratoire)\s*[:\s]+\s*([A-Za-z0-9\s&'.-]{2,80})",
        t,
    )
    if lm:
        lab_name = lm.group(1).strip()

    doc_type = "unknown"
    has_lab = any(
        x is not None for x in (glucose, hba1c, cholesterol, sys_d, dia_d)
    )
    has_rx = len(medications) > 0 or bool(re.search(r"\brx\b|mg\b.*daily|tablet|capsule", low))
    if has_rx and (medications or re.search(r"\d+\s*mg", low)):
        doc_type = "prescription"
    elif has_lab:
        doc_type = "lab_report"
    elif len(t) > 200 and not has_rx:
        doc_type = "medical_report"

    return DocumentExtractionResult(
        patient_name=_extract_patient_name(t),
        age=_extract_age(t),
        gender=_extract_gender(t),
        glucose=glucose,
        glucose_unit=glucose_unit,
        hba1c=hba1c,
        hba1c_unit=hba1c_unit,
        blood_pressure_systolic=sys_d,
        blood_pressure_diastolic=dia_d,
        cholesterol=cholesterol,
        cholesterol_unit=cholesterol_unit,
        insulin=insulin,
        insulin_unit=insulin_unit,
        medications=medications,
        diagnosis=diagnosis,
        instructions=instructions,
        document_type=doc_type,
        lab_name=lab_name,
        doctor_name=_extract_doctor(t),
        date=_parse_iso_date(t),
    )


def result_to_dict(r: DocumentExtractionResult) -> dict[str, Any]:
    d = r.model_dump(mode="json")
    return d
