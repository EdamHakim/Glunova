from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class WeeklyWellnessPlanRequest(BaseModel):
    patient_id: int

    # ── Clinical context ──────────────────────────────────────────────────────
    age:                int
    weight_kg:          float
    height_cm:          float
    bmi:                float
    diabetes_type:      str
    hba1c:              Optional[float] = None
    last_glucose:       Optional[float] = None
    medications:        List[str] = []
    allergies:          List[str] = []
    hypertension:       bool = False
    heart_disease:      bool = False

    # ── Nutrition preferences ─────────────────────────────────────────────────
    cuisine:               str   = "mediterranean"
    carb_limit_per_meal_g: int   = 60
    target_calories_kcal:  Optional[float] = None
    target_carbs_g:        Optional[float] = None
    target_protein_g:      Optional[float] = None
    target_fat_g:          Optional[float] = None

    # ── Fitness preferences ───────────────────────────────────────────────────
    fitness_level:      Literal["beginner", "intermediate", "advanced"] = "beginner"
    goal:               Literal["weight_loss", "muscle_gain", "endurance", "flexibility", "maintenance"] = "maintenance"
    sessions_per_week:  int = Field(default=3, ge=1, le=7)
    minutes_per_session: int = Field(default=30, ge=10, le=120)
    available_equipment: List[str] = ["none"]
    injuries_or_limits:  List[str] = []

    # ── Week range ────────────────────────────────────────────────────────────
    week_start: str              # ISO date e.g. "2026-05-05"
    day_index:  Optional[int] = None  # None = full week, 0–6 = single-day regen
