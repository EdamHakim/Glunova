from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# ── API request / response ────────────────────────────────────────────────────

class CoordinateRequest(BaseModel):
    patient_id: int
    trigger: Literal["alert", "cron", "manual", "nutrition_skip", "crisis"] = "manual"


class CoordinateResponse(BaseModel):
    status: str
    patient_id: int
    messages_dispatched: int
    trigger: str
    risk_tier: str | None = None
    skipped_reason: str | None = None


class CoordinateAllRequest(BaseModel):
    trigger: Literal["cron", "manual"] = "cron"


class CoordinateAllResponse(BaseModel):
    patients_processed: int
    messages_dispatched: int
    errors: list[str]


# ── A2A inter-agent contracts ─────────────────────────────────────────────────

class CareTeamMember(BaseModel):
    id: int
    name: str
    role: str  # "doctor" | "caregiver"
    specialization: str | None = None
    relationship: str | None = None


class PatientContext(BaseModel):
    """Output of ContextAgent — input to RiskReasonerAgent."""
    patient_id: int
    monitoring: dict
    nutrition: dict
    psychology: dict
    care_team: dict  # {doctor: CareTeamMember|None, caregivers: list[CareTeamMember]}


class ReasoningOutput(BaseModel):
    """Output of RiskReasonerAgent — input to DispatchAgent."""
    patient_id: int
    risk_tier: Literal["LOW", "HIGH", "CRITICAL"]
    priority_level: Literal["low", "medium", "high", "urgent"]
    key_signals: list[str]
    should_dispatch: bool
    # Pre-generated messages; DispatchAgent personalises and dispatches them.
    patient_nudge: str
    caregiver_update: str | None  # None when no caregivers linked
    doctor_summary: str | None    # None when no doctor linked


class DispatchResult(BaseModel):
    """Output of DispatchAgent."""
    patient_id: int
    messages_dispatched: int
    recipients: list[str]
