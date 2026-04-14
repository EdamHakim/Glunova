from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.rbac import require_roles

router = APIRouter(prefix="/screening", tags=["screening"])


class ScreeningInferenceRequest(BaseModel):
    patient_id: int = Field(gt=0)
    voice_embedding: list[float] = Field(default_factory=list)
    tongue_image_url: str | None = None


@router.post("/infer")
def infer_screening(
    payload: ScreeningInferenceRequest,
    _claims: dict = Depends(require_roles("patient", "doctor")),
) -> dict:
    risk_score = 0.5 if payload.voice_embedding else 0.3
    return {"patient_id": payload.patient_id, "risk_score": risk_score}
