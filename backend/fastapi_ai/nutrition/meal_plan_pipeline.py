"""
Two-stage Weekly Meal Plan pipeline.

Stage 1 — LLM (Groq llama-3.3-70b-versatile)
  Generates 7-day plan structure: meal names, descriptions, ingredients
  with quantities, GI/GL assessment, diabetes rationale, and
  LLM-estimated macros (kept as fallback).

Stage 2 — USDA FoodData Central validation
  For each meal, queries USDA per ingredient, scales by parsed quantity,
  sums to validated macros.  LLM values replaced when USDA succeeds;
  tagged "llm_estimated" otherwise so the UI can surface the difference.
"""
import json
import os
import re
import requests
from typing import Optional

from .meal_plan_schema import MealPlanRequest
from .pipeline_nutrition import call_with_retry   # reuse existing retry helper
from .usda_client import validate_meal_macros

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

CUISINE_DESCRIPTIONS: dict[str, str] = {
    "mediterranean": "Mediterranean diet (olive oil, fish, legumes, whole grains, vegetables)",
    "maghreb":        "Maghreb/North African cuisine (couscous, tagines, legumes, lamb, harissa)",
    "middle_eastern": "Middle Eastern cuisine (bulgur, hummus, falafel, grilled meats, za'atar)",
    "western":        "Western cuisine (balanced plates, lean proteins, low-GI carbs, salads)",
}


def _bmi_category(bmi: float) -> str:
    if bmi < 18.5: return "Underweight"
    if bmi < 25:   return "Normal"
    if bmi < 30:   return "Overweight"
    return "Obese"


def _hba1c_label(val: Optional[float]) -> str:
    if val is None: return "unknown"
    if val < 5.7:   return "Normal"
    if val < 6.5:   return "Prediabetic range"
    if val < 8.0:   return "Controlled"
    return "Poorly controlled — HIGH RISK"


def _build_prompt(req: MealPlanRequest, target_days: list[int]) -> str:
    days_to_generate = [DAYS[i] for i in target_days]
    cuisine_desc     = CUISINE_DESCRIPTIONS.get(req.cuisine, req.cuisine)
    carb_guidance    = (
        "45–60 g per meal" if (req.hba1c or 0) < 8 else "30–45 g per meal (strict — high HbA1c)"
    )

    return f"""You are a certified clinical dietitian specialising in diabetes nutrition management.

PATIENT CLINICAL PROFILE:
- Age: {req.age} yrs | BMI: {req.bmi:.1f} ({_bmi_category(req.bmi)})
- Diabetes type: {req.diabetes_type}
- HbA1c: {req.hba1c}% — {_hba1c_label(req.hba1c)}
- Last fasting glucose: {req.last_glucose} mg/dL
- Medications: {', '.join(req.medications) if req.medications else 'None reported'}
- Allergies / intolerances: {', '.join(req.allergies) if req.allergies else 'None'}
- Daily calorie target: {req.target_calories_kcal or 'not set'} kcal
- Per-meal carb limit: {req.carb_limit_per_meal_g} g | Daily carb: {req.target_carbs_g or 'not set'} g
- Protein target: {req.target_protein_g or 'not set'} g | Fat target: {req.target_fat_g or 'not set'} g

CUISINE STYLE: {cuisine_desc}

ADA/EASD GUIDELINES TO APPLY:
- Carbohydrates: {carb_guidance}; prioritise GI < 55 (low-GI) sources
- Protein: lean sources at every meal (fish, legumes, chicken, low-fat dairy)
- Fats: unsaturated preferred; limit saturated and trans fats
- Fibre: ≥ 25 g/day from vegetables, whole grains, legumes
- Snack: 15–20 g carbs paired with a protein source to blunt glucose spikes
- Avoid: added sugars, white bread, white rice, sugary drinks, high-GI starches
- Metformin users: include B12-rich foods (eggs, dairy, fish) daily
- Insulin users: keep carb amounts consistent across the same meal slot each day

Generate the plan ONLY for: {', '.join(days_to_generate)}

Return ONLY valid JSON — no text before or after, no markdown fences:
{{
  "week_summary": {{
    "avg_daily_calories": <number>,
    "avg_daily_carbs_g":  <number>,
    "avg_daily_protein_g": <number>,
    "avg_daily_fat_g":    <number>,
    "dietary_philosophy": "<1-2 sentence summary of the nutritional approach>"
  }},
  "days": [
    {{
      "day_index": <0–6>,
      "day_name":  "<Monday … Sunday>",
      "meals": [
        {{
          "meal_type":               "breakfast|lunch|dinner|snack",
          "name":                    "<meal name>",
          "description":             "<one-sentence description>",
          "ingredients":             ["<qty> <unit> <item>", ...],
          "preparation_time_minutes": <integer>,
          "calories_kcal":           <number>,
          "carbs_g":                 <number>,
          "protein_g":               <number>,
          "fat_g":                   <number>,
          "sugar_g":                 <number>,
          "glycemic_index":          "low|medium|high",
          "glycemic_load":           "low|medium|high",
          "diabetes_rationale":      "<why this meal is appropriate for this patient's glucose control>"
        }}
      ]
    }}
  ]
}}"""


def _call_groq(prompt: str) -> dict:
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        raise EnvironmentError("GROQ_API_KEY not set")

    def _api_call():
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       "llama-3.3-70b-versatile",
                "messages":    [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens":  6000,
            },
            timeout=90,
        )
        r.raise_for_status()
        return r.json()

    resp = call_with_retry(_api_call)
    raw  = resp["choices"][0]["message"]["content"].strip()
    raw  = re.sub(r"```json\s*|```\s*", "", raw).strip()
    return json.loads(raw)


def _enrich_with_usda(plan_data: dict) -> dict:
    """
    Stage 2: For every meal run USDA lookup.
    - Replaces LLM macro values with USDA-validated ones when found.
    - Preserves LLM estimates under llm_estimated_* keys for transparency.
    - Tags each meal with nutritional_source and stores per-ingredient breakdown.
    """
    for day in plan_data.get("days", []):
        for meal in day.get("meals", []):
            usda = validate_meal_macros(meal.get("ingredients", []))

            # Keep LLM numbers for auditability
            meal["llm_estimated_calories"] = meal.get("calories_kcal")
            meal["llm_estimated_carbs"]    = meal.get("carbs_g")
            meal["llm_estimated_protein"]  = meal.get("protein_g")
            meal["llm_estimated_fat"]      = meal.get("fat_g")
            meal["llm_estimated_sugar"]    = meal.get("sugar_g")

            if usda["source"] == "usda_validated":
                meal["calories_kcal"] = usda["calories_kcal"]
                meal["carbs_g"]       = usda["carbs_g"]
                meal["protein_g"]     = usda["protein_g"]
                meal["fat_g"]         = usda["fat_g"]
                meal["sugar_g"]       = usda["sugar_g"]

            meal["nutritional_source"] = usda["source"]
            meal["usda_breakdown"]     = usda["breakdown"]

    return plan_data


def generate_meal_plan(req: MealPlanRequest) -> dict:
    target_days = [req.day_index] if req.day_index is not None else list(range(7))

    # Stage 1 — LLM generation
    plan_data = _call_groq(_build_prompt(req, target_days))

    # Stage 2 — USDA validation (gracefully falls back per-ingredient)
    plan_data = _enrich_with_usda(plan_data)

    return plan_data
