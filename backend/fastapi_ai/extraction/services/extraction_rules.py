"""Deterministic rule pass on raw OCR text (validator / grounding layer)."""

from __future__ import annotations

import re
from typing import Any
from dateutil import parser as date_parser


def _extract_vitals(text: str) -> dict[str, Any]:
    vitals = {}
    
    # Blood Pressure: 120/80
    m = re.search(r"\b(\d{2,3})\s*/\s*(\d{2,3})\b", text)
    if m:
        vitals["blood_pressure"] = f"{m.group(1)}/{m.group(2)}"
        
    # Heart Rate: 72 bpm
    m = re.search(r"\b(?:HR|heart\s*rate|pulse)\s*[:\-]?\s*(\d{2,3})\s*(?:bpm)?\b", text, re.I)
    if not m:
        m = re.search(r"\b(\d{2,3})\s*bpm\b", text, re.I)
    if m:
        vitals["heart_rate"] = m.group(1)
        
    # SpO2: 98%
    m = re.search(r"\b(?:SpO2|Oxygen\s*Saturation)\s*[:\-]?\s*(\d{2,3})\s*%\b", text, re.I)
    if m:
        vitals["spo2"] = m.group(1)
        
    # Weight: 70 kg, 154 lbs
    m = re.search(r"\b(?:Weight|Wt)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(kg|lbs?)\b", text, re.I)
    if m:
        vitals["weight"] = {"value": m.group(1), "unit": m.group(2).lower()}
        
    # BMI: 24.5
    m = re.search(r"\bBMI\s*[:\-]?\s*(\d+(?:\.\d+)?)\b", text, re.I)
    if m:
        vitals["bmi"] = m.group(1)
        
    # Temperature: 37.0 C, 98.6 F
    m = re.search(r"\b(?:Temp|Temperature)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:°|deg)?\s*([CF])\b", text, re.I)
    if m:
        vitals["temperature"] = {"value": m.group(1), "unit": m.group(2).upper()}
        
    return vitals


def _extract_dates(text: str) -> list[str]:
    """Extract dates in various formats and return as ISO strings."""
    out: list[str] = []
    
    # Common numeric patterns: 2024-01-15, 15/01/2024, 01-15-2024
    patterns = [
        r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b",        # YYYY-MM-DD
        r"\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b",        # DD/MM/YYYY or MM/DD/YYYY
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b", # Jan 15, 2024
    ]
    
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.I):
            try:
                # Use fuzzy parsing but avoid being too aggressive
                dt = date_parser.parse(m.group(0), dayfirst=True) # Prefer European for numeric if ambiguous
                out.append(dt.date().isoformat())
            except (ValueError, OverflowError, TypeError):
                continue
    return sorted(list(set(out)), reverse=True)


def _extract_labs(text: str) -> list[dict[str, Any]]:
    labs: list[dict[str, Any]] = []
    tl = text.lower()

    def add(name: str, value: str, unit: str | None = None) -> None:
        labs.append({"name": name, "value": value, "unit": unit})

    patterns = [
        (r"(?:glucose|blood\s*glucose)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mg/dl|mmol/l)?", "Glucose"),
        (r"hba1c\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(%|mmol/mol)?", "HbA1c"),
        (r"(?:total\s*cholesterol|cholesterol)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mg/dl|mmol/l)?", "Cholesterol"),
        (r"creatinine\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mg/dl|umol/l)?", "Creatinine"),
        (r"alt\s*[:\-]?\s*(\d+)\s*(u/l)?", "ALT"),
        (r"ast\s*[:\-]?\s*(\d+)\s*(u/l)?", "AST"),
        (r"potassium|k\+\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mmol/l|meq/l)?", "Potassium"),
        (r"sodium|na\+\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mmol/l|meq/l)?", "Sodium"),
        (r"insulin\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:u|units)?", "Insulin"),
    ]

    for pattern, name in patterns:
        m = re.search(pattern, tl, re.I)
        if m:
            unit = m.group(2) if len(m.groups()) > 1 else None
            add(name, m.group(1), unit)

    return labs


def _extract_meds(text: str) -> list[dict[str, Any]]:
    meds: list[dict[str, Any]] = []
    
    # Match lines that look like medications: "DrugName 10mg once daily"
    # or "Medication: DrugName 10mg"
    for line in text.splitlines():
        s = line.strip()
        if not s or len(s) < 5:
            continue
            
        # Strip common prefixes
        s = re.sub(r"^(rx|℞|medication|drug|taking|ordered|name)\s*[:\-]?\s*", "", s, flags=re.I).strip()
        
        # Look for a dosage pattern as a split point
        # e.g. "Metformin 500mg BID"
        m_dosage = re.search(r"(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?))\b", s, re.I)
        if m_dosage:
            name_part = s[:m_dosage.start()].strip()
            rest_part = s[m_dosage.start():].strip()
            
            # Clean name from start-of-line noise like list numbers "1. Metformin"
            name = re.sub(r"^\d+[\.\)]\s*", "", name_part).strip()
            
            if len(name) < 2:
                continue
                
            dosage = m_dosage.group(1)
            
            # Looking for frequency in the rest of the line
            mfreq = re.search(
                r"\b(once\s+daily|twice\s+daily|three\s+times\s+daily|daily|nightly|morning|evening|bid|tid|qid|qd|prn|weekly|stat)\b",
                rest_part,
                re.I,
            )
            frequency = mfreq.group(1) if mfreq else None
            
            # Also look for duration: "for 7 days"
            mdur = re.search(r"\b(?:for|duration)\s*[:\-]?\s*(\d+\s*(?:days?|weeks?|months?))\b", rest_part, re.I)
            duration = mdur.group(1) if mdur else None

            meds.append({
                "name": name[:150],
                "dosage": dosage,
                "frequency": frequency,
                "duration": duration,
                "route": None,
            })
            
    return meds[:50]


def _detect_doc_type(text: str) -> str:
    tl = text.lower()
    if any(k in tl for k in ("prescription", "rx ", "rx:", "dispense", "refill", "take 1", "take one")):
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
            "creatinine",
            "bilirubin",
        )
    ):
        return "lab_report"
    if any(k in tl for k in ("progress note", "clinical summary", "assessment", "impression:", "diagnosis:", "history of")):
        return "medical_report"
    return "unknown"


def empty_schema() -> dict[str, Any]:
    return {
        "document_type": "unknown",
        "date": None,
        "patient_name": None,
        "vitals": {},
        "labs": [],
        "medications": [],
    }


def run_rule_validation(raw_text: str) -> dict[str, Any]:
    text = raw_text or ""
    base = empty_schema()
    
    base["document_type"] = _detect_doc_type(text)
    base["date"] = (_extract_dates(text) or [None])[0]
    base["vitals"] = _extract_vitals(text)
    base["labs"] = _extract_labs(text)
    base["medications"] = _extract_meds(text)
    
    return base
