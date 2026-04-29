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
    seen: set[tuple[str, str, str]] = set()

    def add(name: str, value: str, unit: str | None = None) -> None:
        clean_value = value.strip()
        clean_unit = (unit or "").strip()
        key = (name.lower(), clean_value.lower(), clean_unit.lower())
        if key in seen:
            return
        seen.add(key)
        labs.append({"name": name, "value": clean_value, "unit": clean_unit or None})

    def _add_matches(pattern: str, name: str, unit_group: int | None = 2, value_group: int = 1) -> None:
        for match in re.finditer(pattern, text, re.I | re.S):
            value = match.group(value_group)
            unit = match.group(unit_group) if unit_group is not None and match.lastindex and match.lastindex >= unit_group else None
            if value:
                add(name, value, unit)

    patterns = [
        (r"(?:glucose|blood\s*glucose|glyc[eé]mie)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mg/dl|mmol/l|g/l)?", "Glucose"),
        (r"(\d+(?:\.\d+)?)\s*(mg/dl|mmol/l|g/l)\s*(?:glucose|blood\s*glucose|glyc[eé]mie)", "Glucose"),
        (r"(?:hba1c|h[eé]moglobine\s+glyqu[eé]e)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(%|mmol/mol)?", "HbA1c"),
        (r"(\d+(?:\.\d+)?)\s*(%|mmol/mol)\s*(?:hba1c|h[eé]moglobine\s+glyqu[eé]e|r[eé]sultat)", "HbA1c"),
        (r"(?:total\s*cholesterol|cholesterol)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mg/dl|mmol/l)?", "Cholesterol"),
        (r"(?:creatinine|cr[eé]atinine)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mg/dl|umol/l|µmol/l|mg/l)?", "Creatinine"),
        (r"(\d+(?:\.\d+)?)\s*(mg/dl|umol/l|µmol/l|mg/l)\s*(?:creatinine|cr[eé]atinine)", "Creatinine"),
        (r"(?:alt)\s*[:\-]?\s*(\d+)\s*(u/l|ui/l)?", "ALT"),
        (r"(?:ast)\s*[:\-]?\s*(\d+)\s*(u/l|ui/l)?", "AST"),
        (r"(?:potassium|k\+)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mmol/l|meq/l)?", "Potassium"),
        (r"(\d+(?:\.\d+)?)\s*(mmol/l|meq/l)\s*(?:potassium|k\+)", "Potassium"),
        (r"(?:sodium|na\+)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mmol/l|meq/l)?", "Sodium"),
        (r"(\d+(?:\.\d+)?)\s*(mmol/l|meq/l)\s*(?:sodium|na\+)", "Sodium"),
        (r"(?:insulin)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(u|units)?", "Insulin"),
        (r"(?:calcium)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mmol/l|mg/l)?", "Calcium"),
        (r"(\d+(?:\.\d+)?)\s*(mmol/l|mg/l)\s*(?:calcium)", "Calcium"),
        (r"(?:prot[eé]ine\s*c\s*r[eé]active|crp)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mg/l)?", "CRP"),
        (r"(\d+(?:\.\d+)?)\s*(mg/l)\s*(?:prot[eé]ine\s*c\s*r[eé]active|crp)", "CRP"),
        (r"(?:chlorures?)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mmol/l)?", "Chloride"),
        (r"(?:r[eé]serve\s+alcaline)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mmol/l)?", "Bicarbonate"),
        (r"(?:protides?\s+totaux)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(g/l)?", "Total Protein"),
        (r"(?:folates?\s+s[eé]riques)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(nmol/l|ng/ml)?", "Serum Folate"),
        (r"(?:ft4)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(pmol/l)?", "FT4"),
        (r"(?:tsh)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(µui/ml|mui/l|iu/ml)?", "TSH"),
        (r"(?:ferritin[eé]mie|ferritine)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(ng/ml)?", "Ferritin"),
        (r"(?:vitamine\s*b\s*12|vitamin\s*b\s*12)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(pg/ml)?", "Vitamin B12"),
        (r"(?:c\.?p\.?k\.?)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(ui/l|u/l)?", "CPK"),
        (r"(?:ft3)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(pmol/l)?", "FT3"),
        (r"(?:vitamine\s*d(?:\s*\(25\s*hydroxy\))?)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(ng/ml)?", "Vitamin D"),
        (r"(?:cortisol[eé]mie|cortisol\s+s[eé]rique)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(ng/ml|nmol/l)?", "Cortisol"),
        (r"(?:premi[eè]re\s+heure)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mm)?", "ESR 1h"),
        (r"(?:deuxi[eè]me\s+heure)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mm)?", "ESR 2h"),
    ]

    for pattern, name in patterns:
        _add_matches(pattern, name)

    return labs[:100]


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
