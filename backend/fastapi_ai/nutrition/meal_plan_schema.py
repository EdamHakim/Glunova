from pydantic import BaseModel
from typing import List, Optional


class MealPlanRequest(BaseModel):
    patient_id: int
    age: int
    weight_kg: float
    height_cm: float
    bmi: float
    diabetes_type: str            # "Type 1" | "Type 2" | "Gestational" | "Prediabetes"
    hba1c: Optional[float] = None        # percent
    last_glucose: Optional[float] = None # mg/dL
    medications: List[str] = []
    allergies: List[str] = []
    carb_limit_per_meal_g: int = 60
    target_calories_kcal: Optional[float] = None
    target_carbs_g: Optional[float] = None
    target_protein_g: Optional[float] = None
    target_fat_g: Optional[float] = None
    cuisine: str = "mediterranean"   # "mediterranean"|"maghreb"|"middle_eastern"|"western"
    week_start: str = ""             # ISO date "YYYY-MM-DD"
    day_index: Optional[int] = None  # None=full week; 0–6=single day regen
