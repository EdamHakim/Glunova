from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from core.rbac import require_roles
from screening.schemas import TongueGradcamResponse, TongueInferenceResponse, TongueModelHealthResponse
from screening.services.tongue_pt_service import TonguePtService

router = APIRouter(prefix="/screening", tags=["screening"])
_tongue_service = TonguePtService()

@router.post(
    "/tongue/infer",
    response_model=TongueInferenceResponse,
    summary="Tongue diabetes PyTorch inference",
)
async def infer_tongue_diabetes(
    patient_id: int = Form(..., gt=0),
    image: UploadFile = File(...),
    _claims: dict = Depends(require_roles("patient", "doctor")),
) -> TongueInferenceResponse:
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
        prediction = _tongue_service.predict(raw_bytes)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tongue inference failed unexpectedly.",
        ) from exc

    return TongueInferenceResponse(
        patient_id=patient_id,
        model_name=prediction.model_name,
        model_version=prediction.model_version,
        threshold_used=prediction.threshold_used,
        logit=prediction.logit,
        probability=prediction.probability,
        prediction_index=prediction.prediction_index,
        prediction_label=prediction.prediction_label,
    )


@router.get("/tongue/health", response_model=TongueModelHealthResponse)
def tongue_model_health(
    _claims: dict = Depends(require_roles("doctor")),
) -> TongueModelHealthResponse:
    model_exists = _tongue_service.model_path.exists()
    return TongueModelHealthResponse(
        status="ok" if model_exists else "missing_model",
        model_file_exists=model_exists,
        model_loaded=_tongue_service.is_loaded,
        model_path=_tongue_service.model_path.as_posix(),
    )


@router.post(
    "/tongue/gradcam",
    response_model=TongueGradcamResponse,
    summary="Generate tongue Grad-CAM heatmap",
)
async def tongue_gradcam(
    patient_id: int = Form(..., gt=0),
    image: UploadFile = File(...),
    _claims: dict = Depends(require_roles("patient", "doctor")),
) -> TongueGradcamResponse:
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
        data = _tongue_service.generate_gradcam(raw_bytes)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Grad-CAM generation failed unexpectedly.",
        ) from exc

    return TongueGradcamResponse(
        patient_id=patient_id,
        heatmap_base64=data["heatmap_base64"],
        prediction_label=data["prediction_label"],
        probability=data["probability"],
    )
