from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from core.rbac import require_roles
from clinic.schemas import (
    ThermalFootGradcamResponse,
    ThermalFootInferenceResponse,
    ThermalFootModelHealthResponse,
)
from clinic.services.thermal_foot_pt_service import ThermalFootPtService

router = APIRouter(prefix="/clinic", tags=["clinic"])
_thermal_foot_service = ThermalFootPtService()


class CaseReviewRequest(BaseModel):
    patient_id: int = Field(gt=0)
    include_imaging: bool = False


@router.post("/priority-review")
def priority_review(
    payload: CaseReviewRequest,
    _claims: dict = Depends(require_roles("doctor")),
) -> dict:
    return {"patient_id": payload.patient_id, "priority": "high" if payload.include_imaging else "moderate"}


def _user_id_from_claims(claims: dict) -> int:
    raw = claims.get("user_id")
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user identity",
        )
    try:
        uid = int(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity in token",
        ) from exc
    if uid <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity in token",
        )
    return uid


@router.post(
    "/thermal-foot/infer",
    response_model=ThermalFootInferenceResponse,
    summary="Thermal foot IR diabetes screening (doctor)",
)
async def infer_thermal_foot_diabetes(
    patient_id: int = Form(..., description="Patient record id this image belongs to"),
    image: UploadFile = File(...),
    claims: dict = Depends(require_roles("doctor")),
) -> ThermalFootInferenceResponse:
    doctor_id = _user_id_from_claims(claims)
    if patient_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="patient_id must be a positive integer.",
        )
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be an image.",
        )

    raw_bytes = await image.read()
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty.",
        )

    try:
        prediction = _thermal_foot_service.predict(raw_bytes)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Thermal foot checkpoint could not be loaded: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Thermal foot inference failed unexpectedly.",
        )

    return ThermalFootInferenceResponse(
        patient_id=patient_id,
        reviewed_by_user_id=doctor_id,
        model_name=prediction.model_name,
        model_version=prediction.model_version,
        threshold_used=prediction.threshold_used,
        logit=prediction.logit,
        probability=prediction.probability,
        prediction_index=prediction.prediction_index,
        prediction_label=prediction.prediction_label,
    )


@router.get("/thermal-foot/health", response_model=ThermalFootModelHealthResponse)
def thermal_foot_model_health(
    _claims: dict = Depends(require_roles("doctor")),
) -> ThermalFootModelHealthResponse:
    path = _thermal_foot_service.model_path
    model_exists = path.exists()
    detail: str | None = None
    if model_exists:
        try:
            _thermal_foot_service.ensure_loaded()
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            detail = str(exc)
    status = "missing_model"
    if model_exists and detail is None:
        status = "ok"
    elif model_exists and detail is not None:
        status = "load_failed"
    return ThermalFootModelHealthResponse(
        status=status,
        model_file_exists=model_exists,
        model_loaded=_thermal_foot_service.is_loaded,
        model_path=path.as_posix(),
        detail=detail,
    )


@router.post(
    "/thermal-foot/gradcam",
    response_model=ThermalFootGradcamResponse,
    summary="Thermal foot Grad-CAM explanation (doctor)",
)
async def thermal_foot_gradcam(
    patient_id: int = Form(..., description="Patient record id this image belongs to"),
    image: UploadFile = File(...),
    claims: dict = Depends(require_roles("doctor")),
) -> ThermalFootGradcamResponse:
    doctor_id = _user_id_from_claims(claims)
    if patient_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="patient_id must be a positive integer.",
        )
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be an image.",
        )
    raw_bytes = await image.read()
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty.",
        )

    try:
        data = _thermal_foot_service.generate_gradcam(raw_bytes)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Thermal foot checkpoint could not be loaded: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Grad-CAM generation failed unexpectedly.",
        )

    return ThermalFootGradcamResponse(
        patient_id=patient_id,
        reviewed_by_user_id=doctor_id,
        heatmap_base64=data["heatmap_base64"],
        prediction_label=data["prediction_label"],
        probability=data["probability"],
    )
