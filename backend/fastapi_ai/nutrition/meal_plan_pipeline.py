"""
Weekly Meal Plan pipeline — LLM via api.navy (OpenAI-compatible).

Generates the plan structure: meal names, descriptions, ingredients with
quantities, GI/GL assessment, diabetes rationale, and model-estimated macros.
"""
import json
import os
import re
from typing import Optional

from openai import OpenAI

from .meal_plan_schema import MealPlanRequest
from .pipeline_nutrition import call_with_retry   # reuse existing retry helper

NAVY_BASE_URL = "https://api.navy/v1"
NAVY_MODEL    = os.environ.get("OPENAI_MODEL", "gpt-4o")

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


def _call_navy(prompt: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key, base_url=NAVY_BASE_URL)

    def _api_call():
        return client.chat.completions.create(
            model=NAVY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=6000,
        )

    resp = call_with_retry(_api_call)
    raw  = resp.choices[0].message.content.strip()
    raw  = re.sub(r"```json\s*|```\s*", "", raw).strip()
    return json.loads(raw)


def generate_meal_plan(req: MealPlanRequest) -> dict:
    target_days = [req.day_index] if req.day_index is not None else list(range(7))
    return _call_navy(_build_prompt(req, target_days))
