"""Deterministic rule pass on raw OCR text (validator / grounding layer)."""

from __future__ import annotations

import re
from typing import Any

from dateutil import parser as date_parser


def _extract_bp(text: str) -> str | None:
    m = re.search(r"\b(\d{2,3})\s*/\s*(\d{2,3})\b", text)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def _extract_hr(text: str) -> str | None:
    m = re.search(r"\b(?:HR|heart\s*rate|pulse)\s*[:\-]?\s*(\d{2,3})\s*(?:bpm)?\b", text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{2,3})\s*bpm\b", text, re.I)
    if m:
        return m.group(1)
    return None


def _extract_dates(text: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(
        r"\b(20\d{2}|19\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b",
        text,
    ):
        try:
            dt = date_parser.parse(m.group(0), dayfirst=False, yearfirst=True)
            out.append(dt.date().isoformat())
        except (ValueError, OverflowError, TypeError):
            continue
    for m in re.finditer(
        r"\b(0?[1-9]|1[0-2])[/-](0?[1-9]|[12]\d|3[01])[/-](20\d{2}|19\d{2})\b",
        text,
    ):
        try:
            dt = date_parser.parse(m.group(0), dayfirst=False, yearfirst=False)
            out.append(dt.date().isoformat())
        except (ValueError, OverflowError, TypeError):
            continue
    return out


def _primary_date(text: str) -> str | None:
    dates = _extract_dates(text)
    return dates[0] if dates else None


def _extract_labs(text: str) -> list[dict[str, Any]]:
    labs: list[dict[str, Any]] = []
    tl = text.lower()

    def add(name: str, value: str, unit: str | None = None) -> None:
        labs.append({"name": name, "value": value, "unit": unit})

    m = re.search(
        r"(?:glucose|blood\s*glucose)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mg/dl|mmol/l)?",
        tl,
        re.I,
    )
    if m:
        add("Glucose", m.group(1), m.group(2))

    m = re.search(r"hba1c\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(%|mmol/mol)?", tl, re.I)
    if m:
        add("HbA1c", m.group(1), m.group(2))

    m = re.search(
        r"(?:total\s*cholesterol|cholesterol)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mg/dl)?",
        tl,
        re.I,
    )
    if m:
        add("Cholesterol", m.group(1), m.group(2) or "mg/dL")

    m = re.search(r"insulin\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:u|units)?", tl, re.I)
    if m:
        add("Insulin", m.group(1), "units")

    return labs


def _extract_meds(text: str) -> list[dict[str, Any]]:
    meds: list[dict[str, Any]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or len(s) < 3:
            continue
        if re.match(r"^(rx|℞|medication|drug)\b", s, re.I):
            s = re.sub(r"^(rx|℞|medication|drug)\s*[:\-]?\s*", "", s, flags=re.I).strip()
        if re.search(r"\d+\s*(mg|mcg|g|ml)\b", s, re.I):
            parts = re.split(r"\s{2,}|\t+", s)
            name = parts[0]
            dosage = None
            frequency = None
            if len(parts) > 1:
                dosage = parts[1]
            if len(parts) > 2:
                frequency = parts[2]
            mfreq = re.search(
                r"\b(once\s+daily|twice\s+daily|tid|bid|qd|prn|weekly)\b",
                s,
                re.I,
            )
            if mfreq and not frequency:
                frequency = mfreq.group(1)
            meds.append(
                {
                    "name": name[:200],
                    "dosage": dosage,
                    "frequency": frequency,
                    "duration": None,
                    "route": None,
                }
            )
    return meds[:50]


def _detect_doc_type(text: str) -> str:
    tl = text.lower()
    if any(k in tl for k in ("prescription", "rx ", "rx:", "dispense", "refill")):
        return "prescription"
    if any(
        k in tl
        for k in (
            "laboratory",
            "lab report",
            "reference range",
            "specimen",
            "hba1c",
            "glucose",
        )
    ):
        return "lab_report"
    if any(k in tl for k in ("progress note", "clinical summary", "assessment", "impression:")):
        return "medical_report"
    return "unknown"


def empty_schema() -> dict[str, Any]:
    return {
        "patient": {"name": None, "dob": None, "id": None},
        "document_type": "unknown",
        "date": None,
        "vitals": {"blood_pressure": None, "heart_rate": None},
        "labs": [],
        "medications": [],
        "notes": None,
    }


def run_rule_validation(raw_text: str) -> dict[str, Any]:
    text = raw_text or ""
    base = empty_schema()
    base["document_type"] = _detect_doc_type(text)
    base["date"] = _primary_date(text)
    base["vitals"]["blood_pressure"] = _extract_bp(text)
    base["vitals"]["heart_rate"] = _extract_hr(text)
    base["labs"] = _extract_labs(text)
    base["medications"] = _extract_meds(text)
    return base
