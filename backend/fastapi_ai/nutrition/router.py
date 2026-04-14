from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.rbac import require_roles

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


class MealLogRequest(BaseModel):
    patient_id: int = Field(gt=0)
    description: str = Field(min_length=2)
    estimated_carbs_g: float = Field(ge=0)


@router.post("/analyze-meal")
def analyze_meal(
    payload: MealLogRequest,
    _claims: dict = Depends(require_roles("patient", "doctor")),
) -> dict:
    gi_band = "high" if payload.estimated_carbs_g > 75 else "moderate"
    return {"patient_id": payload.patient_id, "gi_band": gi_band}
