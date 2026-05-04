from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class ProfilUtilisateur(BaseModel):
    age: int = Field(..., ge=1, le=120)
    weight_kg: float = Field(..., gt=0, le=500)
    height_cm: float = Field(..., gt=0, le=300)
    diabetes_type: Literal["Type 1", "Type 2", "Prediabetes"]
    medication: List[str] = []
    last_glucose: Optional[str] = None
    carb_limit_per_meal_g: int = Field(default=60, ge=0, le=500)
    allergies: List[str] = []
