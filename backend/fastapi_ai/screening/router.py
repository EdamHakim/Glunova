import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from core.rbac import require_roles
from monitoring.services.triggers import record_screening_and_refresh
from screening.schemas import (
    TongueGradcamResponse,
    TongueInferenceResponse,
    TongueModelHealthResponse,
    VoiceInferenceResponse,
    VoiceModelHealthResponse,
)
from screening.services.tongue_pt_service import TonguePtService
from screening.services.voice_svm_service import VoiceSvmService

router = APIRouter(prefix="/screening", tags=["screening"])
logger = logging.getLogger(__name__)
_tongue_service = TonguePtService()
_voice_service = VoiceSvmService()


def _patient_id_from_claims(claims: dict) -> int:
    raw = claims.get("user_id")
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user identity",
        )
    try:
        patient_id = int(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity in token",
        ) from exc
    if patient_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity in token",
        )
    return patient_id


@router.post(
    "/tongue/infer",
    response_model=TongueInferenceResponse,
    summary="Tongue diabetes PyTorch inference",
)
async def infer_tongue_diabetes(
    image: UploadFile = File(...),
    claims: dict = Depends(require_roles("patient")),
) -> TongueInferenceResponse:
    patient_id = _patient_id_from_claims(claims)
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

    record_screening_and_refresh(
        user_id=patient_id,
        modality="tongue",
        score=float(prediction.probability),
        risk_label=prediction.prediction_label,
        model_version=f"{prediction.model_name}@{prediction.model_version}",
        metadata={
            "logit": float(prediction.logit),
            "prediction_index": int(prediction.prediction_index),
            "threshold_used": float(prediction.threshold_used),
        },
    )

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
    _claims: dict = Depends(require_roles("patient")),
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
    image: UploadFile = File(...),
    claims: dict = Depends(require_roles("patient")),
) -> TongueGradcamResponse:
    patient_id = _patient_id_from_claims(claims)
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


@router.post(
    "/voice/infer",
    response_model=VoiceInferenceResponse,
    summary="Voice diabetes BYOL-S + SVM inference with SHAP segments",
)
async def infer_voice_diabetes(
    audio: UploadFile = File(...),
    claims: dict = Depends(require_roles("patient")),
) -> VoiceInferenceResponse:
    patient_id = _patient_id_from_claims(claims)
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be an audio clip.",
        )

    raw_bytes = await audio.read()
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio is empty.",
        )

    try:
        prediction = _voice_service.predict(raw_bytes)
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
        logger.exception("Voice inference failed unexpectedly")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Voice inference failed unexpectedly.",
        ) from exc

    record_screening_and_refresh(
        user_id=patient_id,
        modality="voice",
        score=float(prediction.probability),
        risk_label=prediction.prediction_label,
        model_version=f"{prediction.model_name}@{prediction.model_version}",
        metadata={
            "prediction_index": int(prediction.prediction_index),
            "threshold_used": float(prediction.threshold_used),
            "raw_probability": float(prediction.raw_probability),
            "decision_score": float(prediction.decision_score),
            "ood_mahal_score": float(prediction.ood_mahal_score),
            "ood_flag": bool(prediction.ood_flag),
            "shap_ready": bool(prediction.shap_ready),
        },
    )

    return VoiceInferenceResponse(
        patient_id=patient_id,
        model_name=prediction.model_name,
        model_version=prediction.model_version,
        threshold_used=prediction.threshold_used,
        probability=prediction.probability,
        raw_probability=prediction.raw_probability,
        prediction_index=prediction.prediction_index,
        prediction_label=prediction.prediction_label,
        decision_score=prediction.decision_score,
        ood_mahal_score=prediction.ood_mahal_score,
        ood_flag=prediction.ood_flag,
        shap_ready=prediction.shap_ready,
        shap_message=prediction.shap_message,
        shap_base_value=prediction.shap_base_value,
        shap_segments=prediction.shap_segments,
        shap_plot_base64=prediction.shap_plot_base64,
    )


@router.get("/voice/health", response_model=VoiceModelHealthResponse)
def voice_model_health(
    _claims: dict = Depends(require_roles("patient")),
) -> VoiceModelHealthResponse:
    model_exists = _voice_service.model_path.exists()
    byols_repo_exists = _voice_service.byols_repo.exists()
    byols_checkpoint_exists = _voice_service.byols_checkpoint.exists()
    return VoiceModelHealthResponse(
        status="ok" if model_exists and byols_repo_exists and byols_checkpoint_exists else "missing_model",
        model_file_exists=model_exists,
        model_loaded=_voice_service.is_loaded,
        model_path=_voice_service.model_path.as_posix(),
        byols_repo_exists=byols_repo_exists,
        byols_checkpoint_exists=byols_checkpoint_exists,
    )
