from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.rbac import require_roles

router = APIRouter(prefix="/psychology", tags=["psychology"])


class EmotionRequest(BaseModel):
    patient_id: int = Field(gt=0)
    transcript: str = Field(min_length=3)


@router.post("/emotion-detect")
def emotion_detect(
    payload: EmotionRequest,
    _claims: dict = Depends(require_roles("patient")),
) -> dict:
    return {"patient_id": payload.patient_id, "emotion": "neutral", "support_needed": False}
