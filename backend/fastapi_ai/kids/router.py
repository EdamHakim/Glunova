from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.rbac import require_roles

router = APIRouter(prefix="/kids", tags=["kids"])


class StoryRequest(BaseModel):
    patient_id: int = Field(gt=0)
    prompt: str = Field(min_length=5, max_length=300)


@router.post("/story")
def build_story(
    payload: StoryRequest,
    _claims: dict = Depends(require_roles("patient")),
) -> dict:
    return {"patient_id": payload.patient_id, "title": "Glucose Heroes", "prompt_used": payload.prompt}
