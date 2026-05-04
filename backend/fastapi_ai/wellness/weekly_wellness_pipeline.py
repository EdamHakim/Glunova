"""
Weekly Wellness Plan pipeline — two-stage LLM via api.navy (OpenAI-compatible).

Stage 1: generate the exercise schedule for the week.
Stage 2: generate meals informed by each day's exercise load.
Both stages share the same patient clinical context.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from openai import OpenAI

from .weekly_wellness_schema import WeeklyWellnessPlanRequest

log = logging.getLogger(__name__)

NAVY_BASE_URL = "https://api.navy/v1"
NAVY_MODEL    = os.environ.get("OPENAI_MODEL", "gpt-4o")

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

CUISINE_DESCRIPTIONS: dict[str, str] = {
    "mediterranean": "Mediterranean diet (olive oil, fish, legumes, whole grains, vegetables)",
    "maghreb":        "Maghreb/North African cuisine (couscous, tagines, legumes, lamb, harissa)",
    "middle_eastern": "Middle Eastern cuisine (bulgur, hummus, falafel, grilled meats, za'atar)",
    "western":        "Western cuisine (balanced plates, lean proteins, low-GI carbs, salads)",
}


def _get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key, base_url=NAVY_BASE_URL)


def _extract_json(raw: str) -> dict:
    """Extract JSON object from LLM output that may contain preamble/postamble text."""
    # Strip markdown fences first
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    raw = raw.strip()
    # Find the outermost JSON object
    start = raw.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in LLM response. Raw (first 300): {raw[:300]}")
    # Find matching closing brace
    depth = 0
    end = -1
    for i, ch in enumerate(raw[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        raise ValueError(f"Unbalanced braces in LLM response. Raw (first 300): {raw[:300]}")
    return json.loads(raw[start : end + 1])


def _call(client: OpenAI, prompt: str, *, max_tokens: int = 4000) -> dict:
    try:
        resp = client.chat.completions.create(
            model=NAVY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        log.exception("OpenAI API call failed")
        raise RuntimeError(f"LLM API error: {exc}") from exc

    raw = resp.choices[0].message.content or ""
    log.debug("LLM raw response (first 500 chars): %s", raw[:500])
    try:
        return _extract_json(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        log.error("JSON extraction failed. Raw response:\n%s", raw[:2000])
        raise RuntimeError(f"JSON parse error: {exc}") from exc


def _bmi_label(bmi: float) -> str:
    if bmi < 18.5: return "Underweight"
    if bmi < 25:   return "Normal"
    if bmi < 30:   return "Overweight"
    return "Obese"


def _hba1c_label(v: float | None) -> str:
    if v is None:  return "unknown"
    if v < 5.7:    return "Normal"
    if v < 6.5:    return "Prediabetic range"
    if v < 8.0:    return "Controlled"
    return "Poorly controlled — HIGH RISK"


def _clinical_block(req: WeeklyWellnessPlanRequest) -> str:
    cardiac_flag = "⚠️ CARDIAC RISK — avoid high-intensity exercise" if req.heart_disease else "No cardiac contraindication"
    hyp_flag     = "⚠️ Hypertension — monitor BP during exercise" if req.hypertension else "No hypertension"
    carb_guidance = "45–60 g per meal" if (req.hba1c or 0) < 8 else "30–45 g per meal (strict — high HbA1c)"
    return f"""PATIENT CLINICAL PROFILE:
- Age: {req.age} yrs | BMI: {req.bmi:.1f} ({_bmi_label(req.bmi)})
- Diabetes: {req.diabetes_type} | HbA1c: {req.hba1c}% — {_hba1c_label(req.hba1c)}
- Last fasting glucose: {req.last_glucose} mg/dL
- Medications: {', '.join(req.medications) if req.medications else 'None'}
- Allergies: {', '.join(req.allergies) if req.allergies else 'None'}
- Cardiac: {cardiac_flag}
- {hyp_flag}
- Per-meal carb limit: {req.carb_limit_per_meal_g} g ({carb_guidance})
- Daily calorie target: {req.target_calories_kcal or 'not set'} kcal"""


# ── Stage 1: Exercise schedule ─────────────────────────────────────────────────

def _exercise_prompt(req: WeeklyWellnessPlanRequest, target_days: list[int]) -> str:
    day_names = [DAYS[i] for i in target_days]
    return f"""You are a certified clinical exercise physiologist specialising in diabetes management.

{_clinical_block(req)}

FITNESS PROFILE:
- Level: {req.fitness_level} | Goal: {req.goal}
- Sessions per week: {req.sessions_per_week} (spread rest days evenly)
- Duration per session: {req.minutes_per_session} min
- Available equipment: {', '.join(req.available_equipment)}
- Injuries / limits: {', '.join(req.injuries_or_limits) if req.injuries_or_limits else 'None'}

ADA EXERCISE GUIDELINES TO APPLY:
- Minimum 150 min/week moderate aerobic activity for Type 2 diabetes
- No more than 2 consecutive days without exercise
- Pre-exercise glucose check mandatory if last_glucose < 100 or > 250 mg/dL
- High-intensity HIIT is CONTRAINDICATED when heart_disease=True
- Always include diabetes_rationale explaining glucose impact of each session
- Include intensity_score (0–10) and exercise_load_minutes per day

Generate schedule ONLY for: {', '.join(day_names)}

Return ONLY valid JSON — no markdown fences:
{{
  "exercise_week_summary": {{
    "total_active_days": <int>,
    "total_load_minutes": <int>,
    "avg_intensity_score": <float>,
    "fitness_philosophy": "<1-2 sentences>"
  }},
  "days": [
    {{
      "day_index": <0–6>,
      "day_name": "<Monday…Sunday>",
      "is_rest_day": <bool>,
      "intensity_score": <0–10>,
      "exercise_load_minutes": <int>,
      "sessions": [
        {{
          "session_order": 1,
          "exercise_type": "cardio|strength|flexibility|HIIT|mobility",
          "name": "<session name>",
          "description": "<1-sentence description>",
          "duration_minutes": <int>,
          "intensity": "low|moderate|high",
          "sets": <int|null>,
          "reps": <int|null>,
          "equipment": ["<item>"],
          "pre_exercise_glucose_check": <bool>,
          "post_exercise_snack_tip": "<tip>",
          "diabetes_rationale": "<why this is safe/beneficial>"
        }}
      ]
    }}
  ]
}}"""


# ── Stage 2: Meal plan informed by exercise schedule ───────────────────────────

def _meal_prompt(req: WeeklyWellnessPlanRequest, exercise_days: list[dict], target_days: list[int]) -> str:
    cuisine_desc = CUISINE_DESCRIPTIONS.get(req.cuisine, req.cuisine)

    # Build a compact exercise context string for each day
    exercise_ctx_lines = []
    day_map = {d["day_index"]: d for d in exercise_days}
    for i in target_days:
        d = day_map.get(i, {})
        if d.get("is_rest_day"):
            exercise_ctx_lines.append(f"  Day {i} ({DAYS[i]}): REST DAY — reduce calories ~10-15%, no workout snacks")
        else:
            load = d.get("exercise_load_minutes", 0)
            intensity = d.get("intensity_score", 5)
            exercise_ctx_lines.append(
                f"  Day {i} ({DAYS[i]}): ACTIVE — {load} min, intensity {intensity}/10 "
                f"→ add pre_workout_snack + post_workout_snack meal types"
            )
    exercise_ctx = "\n".join(exercise_ctx_lines)

    return f"""You are a certified clinical dietitian specialising in diabetes nutrition management.

{_clinical_block(req)}

CUISINE STYLE: {cuisine_desc}
Protein target: {req.target_protein_g or 'not set'} g | Fat target: {req.target_fat_g or 'not set'} g

EXERCISE SCHEDULE CONTEXT (adjust meals accordingly):
{exercise_ctx}

ADA/EASD NUTRITION GUIDELINES:
- Carbohydrates: prioritise GI < 55 sources; respect per-meal carb limit above
- Pre-workout snack (active days only): 15–25 g fast carbs, 30–45 min before session
- Post-workout snack (active days only): protein + moderate carb within 30 min after
- Rest days: omit workout snacks, reduce total daily intake by ~10-15%
- High HbA1c (≥8%): strict 30–45 g carbs/meal, low-GI only
- Metformin users: include B12-rich foods daily
- NO allergens: {', '.join(req.allergies) if req.allergies else 'none'}

Generate meals ONLY for day indices: {target_days}

Return ONLY valid JSON — no markdown fences:
{{
  "meal_week_summary": {{
    "avg_daily_calories": <number>,
    "avg_daily_carbs_g": <number>,
    "avg_daily_protein_g": <number>,
    "avg_daily_fat_g": <number>,
    "dietary_philosophy": "<1-2 sentences>"
  }},
  "days": [
    {{
      "day_index": <0–6>,
      "day_name": "<Monday…Sunday>",
      "total_calories_kcal": <number>,
      "total_carbs_g": <number>,
      "glucose_check_reminders": ["<reminder>"],
      "meals": [
        {{
          "meal_type": "breakfast|lunch|dinner|snack|pre_workout_snack|post_workout_snack",
          "name": "<meal name>",
          "description": "<brief, one sentence>",
          "ingredients": ["<qty> <unit> <item>"],
          "preparation_time_minutes": <int>,
          "calories_kcal": <number>,
          "carbs_g": <number>,
          "protein_g": <number>,
          "fat_g": <number>,
          "sugar_g": <number>,
          "glycemic_index": "low|medium|high",
          "glycemic_load": "low|medium|high",
          "diabetes_rationale": "<why appropriate for this patient>"
        }}
      ]
    }}
  ]
}}"""


# ── Merge + public entry point ─────────────────────────────────────────────────

def _merge(exercise_data: dict, meal_data: dict) -> dict:
    ex_days  = {d["day_index"]: d for d in exercise_data.get("days", [])}
    meal_days = {d["day_index"]: d for d in meal_data.get("days", [])}

    merged_days: list[dict[str, Any]] = []
    for i in sorted(set(list(ex_days) + list(meal_days))):
        ex  = ex_days.get(i, {})
        mel = meal_days.get(i, {})
        merged_days.append({
            "day_index":              i,
            "day_name":               ex.get("day_name") or mel.get("day_name") or DAYS[i],
            "is_rest_day":            ex.get("is_rest_day", True),
            "intensity_score":        ex.get("intensity_score", 0),
            "exercise_load_minutes":  ex.get("exercise_load_minutes", 0),
            "exercise_sessions":      ex.get("sessions", []),
            "meals":                  mel.get("meals", []),
            "day_summary": {
                "total_calories_kcal":    mel.get("total_calories_kcal"),
                "total_carbs_g":          mel.get("total_carbs_g"),
                "exercise_load_minutes":  ex.get("exercise_load_minutes", 0),
                "glucose_check_reminders": mel.get("glucose_check_reminders", []),
            },
        })

    return {
        "week_summary": {
            **exercise_data.get("exercise_week_summary", {}),
            **meal_data.get("meal_week_summary", {}),
        },
        "days": merged_days,
    }


def _merge_meal_chunks(chunks: list[dict]) -> dict:
    """Merge multiple partial meal_data dicts (each covering a subset of days)."""
    merged_days: list[dict] = []
    avg_fields = ["avg_daily_calories", "avg_daily_carbs_g", "avg_daily_protein_g", "avg_daily_fat_g"]
    summary: dict = {}

    for chunk in chunks:
        merged_days.extend(chunk.get("days", []))
        for field in avg_fields:
            summary.setdefault(field, [])
            val = chunk.get("meal_week_summary", {}).get(field)
            if val is not None:
                summary[field].append(val)

    # Average the numeric summary fields across chunks
    averaged: dict = {k: round(sum(v) / len(v), 1) for k, v in summary.items() if v}
    # Take dietary_philosophy from the first chunk that has it
    for chunk in chunks:
        phil = chunk.get("meal_week_summary", {}).get("dietary_philosophy")
        if phil:
            averaged["dietary_philosophy"] = phil
            break

    return {"meal_week_summary": averaged, "days": merged_days}


def generate_weekly_wellness_plan(req: WeeklyWellnessPlanRequest) -> dict:
    client      = _get_client()
    target_days = [req.day_index] if req.day_index is not None else list(range(7))

    # Stage 1 — exercise schedule (full week or single day)
    exercise_data = _call(client, _exercise_prompt(req, target_days), max_tokens=4000)

    # Stage 2 — meals split into chunks of ≤4 days to stay within token limits
    chunk_size  = 4
    ex_days     = exercise_data.get("days", [])
    meal_chunks = []
    for i in range(0, len(target_days), chunk_size):
        chunk_days = target_days[i : i + chunk_size]
        chunk_data = _call(
            client,
            _meal_prompt(req, ex_days, chunk_days),
            max_tokens=5000,
        )
        meal_chunks.append(chunk_data)

    meal_data = _merge_meal_chunks(meal_chunks) if len(meal_chunks) > 1 else (meal_chunks[0] if meal_chunks else {})

    return _merge(exercise_data, meal_data)
