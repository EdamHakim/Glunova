"""Conservative merge: rules win for clinical numerics; Gemini text only if grounded in OCR."""

from __future__ import annotations

import copy
import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class LabRow(BaseModel):
    name: str
    value: str
    unit: str | None = None


class MedRow(BaseModel):
    name: str
    dosage: str | None = None
    frequency: str | None = None
    duration: str | None = None
    route: str | None = None


class ExtractedPayload(BaseModel):
    patient: dict[str, Any] = Field(default_factory=dict)
    document_type: str = "unknown"
    date: str | None = None
    vitals: dict[str, Any] = Field(default_factory=dict)
    labs: list[LabRow] = Field(default_factory=list)
    medications: list[MedRow] = Field(default_factory=list)
    notes: str | None = None


def _norm(s: str) -> str:
    return " ".join(s.split())


def _evidence_ok(evidence: str | None, raw: str) -> bool:
    if not evidence or not raw:
        return False
    ev = evidence.strip()
    if len(ev) < 2:
        return False
    return ev in raw or ev.lower() in raw.lower()


def merge_and_validate(
    raw_ocr_text: str,
    rules: dict[str, Any],
    gemini_extracted: dict[str, Any] | None,
    field_evidence: dict[str, str] | None,
) -> dict[str, Any]:
    final = copy.deepcopy(rules)
    raw = raw_ocr_text or ""
    if not gemini_extracted:
        try:
            return ExtractedPayload.model_validate(final).model_dump(mode="json")
        except ValidationError:
            return final

    fe = field_evidence or {}

    # Document type / date: prefer Gemini only if evidence or matches rule unknown
    dt = gemini_extracted.get("document_type")
    if isinstance(dt, str) and dt in (
        "prescription",
        "lab_report",
        "medical_report",
        "unknown",
    ):
        if final.get("document_type") == "unknown" or _evidence_ok(fe.get("document_type"), raw):
            final["document_type"] = dt

    gd = gemini_extracted.get("date")
    if isinstance(gd, str) and _evidence_ok(fe.get("date"), raw):
        final["date"] = gd
    elif isinstance(gd, str) and gd in raw:
        final["date"] = gd

    # Patient block (text only with evidence)
    gp = gemini_extracted.get("patient") if isinstance(gemini_extracted.get("patient"), dict) else {}
    fp = final.setdefault("patient", {"name": None, "dob": None, "id": None})
    for key in ("name", "dob", "id"):
        val = gp.get(key) if isinstance(gp, dict) else None
        if isinstance(val, str) and val.strip():
            path = f"patient.{key}"
            if _evidence_ok(fe.get(path), raw) or val in raw or val.lower() in raw.lower():
                fp[key] = val.strip()

    # Vitals: keep rules BP/HR; allow Gemini only if substring in raw
    gv = gemini_extracted.get("vitals") if isinstance(gemini_extracted.get("vitals"), dict) else {}
    fv = final.setdefault("vitals", {"blood_pressure": None, "heart_rate": None})
    for key in ("blood_pressure", "heart_rate"):
        rv = fv.get(key)
        gv_val = gv.get(key) if isinstance(gv, dict) else None
        if isinstance(gv_val, str) and gv_val.strip():
            if (rv is None or rv == gv_val) and (gv_val in raw or gv_val.replace(" ", "") in raw.replace(" ", "")):
                fv[key] = gv_val.strip()
        # numerics from rules already in fv from rules snapshot

    # Labs: append Gemini rows whose name appears in raw
    g_labs = gemini_extracted.get("labs")
    if isinstance(g_labs, list):
        existing = {(l.get("name"), l.get("value")) for l in final.get("labs", []) if isinstance(l, dict)}
        for row in g_labs:
            if not isinstance(row, dict):
                continue
            name = row.get("name")
            if not isinstance(name, str) or name not in raw and name.lower() not in raw.lower():
                continue
            tup = (name, str(row.get("value", "")))
            if tup not in existing:
                final.setdefault("labs", []).append(
                    {
                        "name": name,
                        "value": str(row.get("value", "")),
                        "unit": row.get("unit"),
                    }
                )
                existing.add(tup)

    # Medications: Gemini name must appear in raw
    g_meds = gemini_extracted.get("medications")
    if isinstance(g_meds, list):
        seen = {json.dumps(m, sort_keys=True) for m in final.get("medications", [])}
        for row in g_meds:
            if not isinstance(row, dict):
                continue
            name = row.get("name")
            if not isinstance(name, str) or len(name) < 2:
                continue
            if name not in raw and name.lower() not in raw.lower():
                continue
            if name.lower() not in raw.lower():
                continue
            entry = {
                "name": name,
                "dosage": row.get("dosage"),
                "frequency": row.get("frequency"),
                "duration": row.get("duration"),
                "route": row.get("route"),
            }
            key = json.dumps(entry, sort_keys=True)
            if key not in seen:
                final.setdefault("medications", []).append(entry)
                seen.add(key)

    notes = gemini_extracted.get("notes")
    if isinstance(notes, str) and notes.strip() and _evidence_ok(fe.get("notes"), raw):
        final["notes"] = notes.strip()

    try:
        return ExtractedPayload.model_validate(final).model_dump(mode="json")
    except ValidationError:
        return final
