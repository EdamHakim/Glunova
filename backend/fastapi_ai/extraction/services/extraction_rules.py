"""Deterministic rule pass on raw OCR text (validator / grounding layer)."""

from __future__ import annotations

import re
from typing import Any
from dateutil import parser as date_parser


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
        (r"(?:cortisol[eé]mie|cortisol\s+s[eé]rique)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(ng/ml|nmol/l)", "Cortisol"),
        (r"(?:premi[eè]re\s+heure)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mm)?", "ESR 1h"),
        (r"(?:deuxi[eè]me\s+heure)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(mm)?", "ESR 2h"),
    ]

    for pattern, name in patterns:
        _add_matches(pattern, name)

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    def _looks_like_value(line: str) -> bool:
        return bool(re.fullmatch(r"-?\d+(?:[.,]\d+)?", line))

    def _looks_like_unit(line: str) -> bool:
        if len(line) > 32 or line.startswith("("):
            return False
        if _looks_like_value(line):
            return False
        if not re.fullmatch(r"[%/A-Za-zµμ0-9,.\-\s²³]+", line):
            return False
        return any(ch.isalpha() for ch in line) or "%" in line or "/" in line or "²" in line or "³" in line

    def _norm_unit(line: str) -> str:
        return re.sub(r"\s+", "", line.strip().lower().replace("μ", "µ"))

    def _collect_line_pairs(index: int, allowed_units: set[str]) -> list[tuple[str, str]]:
        def _scan(start: int, stop: int) -> list[tuple[int, str, str]]:
            found: list[tuple[int, str, str]] = []
            for j in range(start, stop):
                if j == index or j + 1 == index:
                    continue
                first = lines[j]
                second = lines[j + 1]
                distance = min(abs(index - j), abs(index - (j + 1)))

                if _looks_like_unit(first) and _looks_like_value(second):
                    found.append((distance, second.replace(",", "."), first))
            return found

        prev_candidates = _scan(max(0, index - 6), index - 1)
        next_candidates = _scan(index + 1, min(len(lines) - 1, index + 6))

        if allowed_units:
            prev_preferred = [row for row in prev_candidates if _norm_unit(row[2]) in allowed_units]
            next_preferred = [row for row in next_candidates if _norm_unit(row[2]) in allowed_units]
            if prev_preferred:
                candidates = prev_preferred
            elif next_preferred:
                candidates = next_preferred
            else:
                candidates = prev_candidates or next_candidates
        else:
            candidates = prev_candidates or next_candidates

        deduped: list[tuple[str, str]] = []
        seen_pairs: set[tuple[str, str]] = set()
        for _distance, value, unit in sorted(candidates, key=lambda item: item[0]):
            key = (value.lower(), _norm_unit(unit))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            deduped.append((value, unit))
        return deduped[:1]

    alias_map: dict[str, tuple[list[str], set[str]]] = {
        "Glucose": ([r"glyc[eé]mie", r"glucose"], {"mmol/l", "mg/dl", "g/l"}),
        "HbA1c": ([r"hba1c", r"h[eé]moglobine\s+glyqu[eé]e"], {"%", "mmol/mol"}),
        "Creatinine": ([r"cr[eé]atinine", r"creatinine"], {"µmol/l", "umol/l", "mg/l", "mg/dl"}),
        "Calcium": ([r"calcium"], {"mmol/l", "mg/l"}),
        "CRP": ([r"prot[eé]ine\s*c\s*r[eé]active", r"\bcrp\b"], {"mg/l"}),
        "Sodium": ([r"sodium"], {"mmol/l", "meq/l"}),
        "Potassium": ([r"potassium"], {"mmol/l", "meq/l"}),
        "Chloride": ([r"chlorures?"], {"mmol/l"}),
        "Bicarbonate": ([r"r[eé]serve\s+alcaline"], {"mmol/l"}),
        "Total Protein": ([r"protides?\s+totaux"], {"g/l"}),
        "Serum Folate": ([r"folates?\s+s[eé]riques"], {"nmol/l", "ng/ml"}),
        "FT4": ([r"\bft4\b"], {"pmol/l"}),
        "TSH": ([r"\btsh\b"], {"µui/ml", "mui/l", "iu/ml"}),
        "Ferritin": ([r"ferritin[eé]mie", r"ferritine"], {"ng/ml"}),
        "Vitamin B12": ([r"vitamine\s*b\s*12", r"vitamin\s*b\s*12"], {"pg/ml"}),
        "CPK": ([r"c\.?p\.?k\.?"], {"ui/l", "u/l"}),
        "FT3": ([r"\bft3\b"], {"pmol/l"}),
        "Vitamin D": ([r"vitamine\s*d"], {"ng/ml"}),
        "Cortisol": ([r"cortisol[eé]mie", r"cortisol\s+s[eé]rique"], {"ng/ml", "nmol/l"}),
        "ESR 1h": ([r"premi[eè]re\s+heure"], {"mm"}),
        "ESR 2h": ([r"deuxi[eè]me\s+heure"], {"mm"}),
    }

    for idx, line in enumerate(lines):
        for name, (aliases, allowed_units) in alias_map.items():
            if any(re.search(alias, line, re.I) for alias in aliases):
                for value, unit in _collect_line_pairs(idx, allowed_units):
                    add(name, value, unit)

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
    return "unknown"


def empty_schema() -> dict[str, Any]:
    return {
        "document_type": "unknown",
        "date": None,
        "patient_name": None,
        "labs": [],
        "medications": [],
    }


def run_rule_validation(raw_text: str) -> dict[str, Any]:
    text = raw_text or ""
    base = empty_schema()
    
    base["document_type"] = _detect_doc_type(text)
    base["date"] = (_extract_dates(text) or [None])[0]
    base["labs"] = _extract_labs(text)
    base["medications"] = _extract_meds(text)
    
    return base
