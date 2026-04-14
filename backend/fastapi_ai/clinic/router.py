from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.rbac import require_roles

router = APIRouter(prefix="/clinic", tags=["clinic"])


class CaseReviewRequest(BaseModel):
    patient_id: int = Field(gt=0)
    include_imaging: bool = False


@router.post("/priority-review")
def priority_review(
    payload: CaseReviewRequest,
    _claims: dict = Depends(require_roles("doctor")),
) -> dict:
    return {"patient_id": payload.patient_id, "priority": "high" if payload.include_imaging else "moderate"}
