from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from core.rbac import require_roles
from clinic.schemas import (
    DFUSegmentationInferenceResponse,
    DFUSegmentationModelHealthResponse,
    DFUSegmentationXAIResponse,
    RetinopathyGradcamResponse,
    RetinopathyInferenceResponse,
    RetinopathyModelHealthResponse,
    ThermalFootGradcamResponse,
    ThermalFootInferenceResponse,
    ThermalFootModelHealthResponse,
)
from clinic.DFUSegmentation import DFUSegmenter, estimate_mm_per_pixel_assumed_foot_span
from clinic.dfu_severity import classify_dfu_severity
from monitoring.services.triggers import record_screening_and_refresh
from clinic.services.retinopathy_service import RetinopathyService
from clinic.services.thermal_foot_pt_service import ThermalFootPtService

router = APIRouter(prefix="/clinic", tags=["clinic"])
_thermal_foot_service = ThermalFootPtService()
_dfu_segmentation_service = DFUSegmenter()
_retinopathy_service = RetinopathyService()


def _lesion_metrics(prediction, mm_per_pixel: float) -> dict:
    return {
        "mm_per_pixel": mm_per_pixel,
        "ulcer_area_mm2": float(prediction.ulcer_area_px) * (mm_per_pixel**2),
        "bbox_width_mm": float(prediction.bbox_width_px) * mm_per_pixel,
        "bbox_height_mm": float(prediction.bbox_height_px) * mm_per_pixel,
    }


def _resolve_dfu_mm_per_pixel(
    raw_bytes: bytes,
    *,
    mm_per_pixel_auto: bool,
    mm_per_pixel: float,
) -> float:
    if mm_per_pixel_auto:
        try:
            return estimate_mm_per_pixel_assumed_foot_span(raw_bytes)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
    if mm_per_pixel <= 0 or not float(mm_per_pixel).isfinite():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mm_per_pixel must be a positive finite number when not using auto.",
        )
    return float(mm_per_pixel)


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
    "/dfu-segmentation/infer",
    response_model=DFUSegmentationInferenceResponse,
    summary="Diabetic foot ulcer detection and segmentation (doctor)",
)
async def infer_dfu_segmentation(
    patient_id: int = Form(..., description="Patient record id this image belongs to"),
    image: UploadFile = File(...),
    threshold_auto: bool = Form(
        False,
        description="If true, choose mask threshold from the model probability map (ignore manual threshold).",
    ),
    threshold: float = Form(0.5, description="Mask threshold in [0, 1] when threshold_auto is false"),
    mm_per_pixel_auto: bool = Form(
        False,
        description="If true, estimate mm/pixel from image size (~24 cm along longest edge; rough prior).",
    ),
    mm_per_pixel: float = Form(
        0.5,
        description="Millimeters per pixel when mm_per_pixel_auto is false",
    ),
    claims: dict = Depends(require_roles("doctor")),
) -> DFUSegmentationInferenceResponse:
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

    eff_threshold: float | None = None if threshold_auto else threshold
    if not threshold_auto and not (0.0 <= threshold <= 1.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="threshold must be between 0 and 1 when threshold_auto is false.",
        )

    try:
        prediction = _dfu_segmentation_service.predict(raw_bytes, threshold=eff_threshold)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"DFU segmentation checkpoint could not be loaded: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DFU segmentation inference failed unexpectedly.",
        )
    mm_px = _resolve_dfu_mm_per_pixel(
        raw_bytes,
        mm_per_pixel_auto=mm_per_pixel_auto,
        mm_per_pixel=mm_per_pixel,
    )
    metrics = _lesion_metrics(prediction, mm_px)
    ratio = float(prediction.ulcer_area_ratio)
    ulcer_severity = classify_dfu_severity(
        ulcer_detected=prediction.ulcer_detected,
        area_mm2=float(metrics["ulcer_area_mm2"]),
    )

    # Fusion-friendly score: mirrors glunova_predictor.DFUSegmentationPredictor.
    # Any detected ulcer (>=0.1% area) starts at 0.5 and scales up with coverage.
    # Sub-threshold detections fall to 0 so the asymmetric filter drops them.
    if ratio >= 0.001:
        fusion_score = min(0.5 + ratio * 20.0, 1.0)
    else:
        fusion_score = 0.0
    record_screening_and_refresh(
        user_id=patient_id,
        modality="foot_ulcer",
        score=fusion_score,
        risk_label=(
            f"Ulcer ({ulcer_severity})" if prediction.ulcer_detected else "No ulcer"
        ),
        model_version="resnet34_unet_dfu@pth-v1",
        metadata={
            "threshold_used": float(prediction.threshold_used),
            "threshold_auto": threshold_auto,
            "mm_per_pixel_auto": mm_per_pixel_auto,
            "ulcer_area_ratio": ratio,
            "ulcer_area_px": int(prediction.ulcer_area_px),
            "ulcer_area_mm2": float(metrics["ulcer_area_mm2"]),
            "ulcer_severity": ulcer_severity,
            "bbox_width_mm": float(metrics["bbox_width_mm"]),
            "bbox_height_mm": float(metrics["bbox_height_mm"]),
        },
    )

    return DFUSegmentationInferenceResponse(
        patient_id=patient_id,
        reviewed_by_user_id=doctor_id,
        model_name="resnet34_unet_dfu",
        model_version="pth-v1",
        threshold_used=prediction.threshold_used,
        ulcer_detected=prediction.ulcer_detected,
        ulcer_severity=ulcer_severity,
        ulcer_area_ratio=prediction.ulcer_area_ratio,
        ulcer_area_px=prediction.ulcer_area_px,
        bbox_x=prediction.bbox_x,
        bbox_y=prediction.bbox_y,
        bbox_width_px=prediction.bbox_width_px,
        bbox_height_px=prediction.bbox_height_px,
        mm_per_pixel=metrics["mm_per_pixel"],
        ulcer_area_mm2=metrics["ulcer_area_mm2"],
        bbox_width_mm=metrics["bbox_width_mm"],
        bbox_height_mm=metrics["bbox_height_mm"],
        mask_base64=prediction.mask_base64,
        overlay_base64=prediction.overlay_base64,
    )


@router.get("/dfu-segmentation/health", response_model=DFUSegmentationModelHealthResponse)
def dfu_segmentation_model_health(
    _claims: dict = Depends(require_roles("doctor")),
) -> DFUSegmentationModelHealthResponse:
    path = _dfu_segmentation_service.checkpoint_path
    model_exists = path.exists()
    detail: str | None = None
    if model_exists:
        try:
            _dfu_segmentation_service.ensure_loaded()
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            detail = str(exc)

    status_text = "missing_model"
    if model_exists and detail is None:
        status_text = "ok"
    elif model_exists and detail is not None:
        status_text = "load_failed"

    return DFUSegmentationModelHealthResponse(
        status=status_text,
        model_file_exists=model_exists,
        model_loaded=_dfu_segmentation_service.is_loaded,
        model_path=path.as_posix(),
        detail=detail,
    )


@router.post(
    "/dfu-segmentation/xai",
    response_model=DFUSegmentationXAIResponse,
    summary="DFU segmentation explainability overlay (doctor)",
)
async def dfu_segmentation_xai(
    patient_id: int = Form(..., description="Patient record id this image belongs to"),
    image: UploadFile = File(...),
    threshold_auto: bool = Form(False, description="Auto mask threshold from probability map"),
    threshold: float = Form(0.5, description="Mask threshold in [0, 1] when threshold_auto is false"),
    claims: dict = Depends(require_roles("doctor")),
) -> DFUSegmentationXAIResponse:
    doctor_id = _user_id_from_claims(claims)
    if patient_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="patient_id must be positive.")
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must be an image.")
    raw_bytes = await image.read()
    if not raw_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded image is empty.")

    eff_threshold: float | None = None if threshold_auto else threshold
    if not threshold_auto and not (0.0 <= threshold <= 1.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="threshold must be between 0 and 1 when threshold_auto is false.",
        )

    try:
        prediction = _dfu_segmentation_service.predict(raw_bytes, threshold=eff_threshold)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DFU XAI generation failed unexpectedly.",
        )

    return DFUSegmentationXAIResponse(
        patient_id=patient_id,
        reviewed_by_user_id=doctor_id,
        xai_overlay_base64=prediction.overlay_base64,
        mask_base64=prediction.mask_base64,
        ulcer_detected=prediction.ulcer_detected,
    )


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

    record_screening_and_refresh(
        user_id=patient_id,
        modality="infrared",
        score=float(prediction.probability),
        risk_label=prediction.prediction_label,
        model_version=f"{prediction.model_name}@{prediction.model_version}",
        metadata={
            "logit": float(prediction.logit),
            "prediction_index": int(prediction.prediction_index),
            "threshold_used": float(prediction.threshold_used),
        },
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


# ─── Retinopathy (DR cascade V5.1 → V8) ──────────────────────────────


@router.post(
    "/retinopathy/infer",
    response_model=RetinopathyInferenceResponse,
    summary="Diabetic retinopathy cascade V5.1 → V8 (doctor)",
)
async def infer_retinopathy(
    patient_id: int = Form(..., description="Patient record id this image belongs to"),
    image: UploadFile = File(...),
    claims: dict = Depends(require_roles("doctor")),
) -> RetinopathyInferenceResponse:
    doctor_id = _user_id_from_claims(claims)
    if patient_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="patient_id must be a positive integer.")
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must be an image.")

    raw_bytes = await image.read()
    if not raw_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded image is empty.")

    try:
        result = _retinopathy_service.predict_cascade(raw_bytes)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Retinopathy checkpoint could not be loaded: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Retinopathy inference failed unexpectedly.",
        )

    v51 = result.binary
    v51_payload = {
        "dr_detected": v51.dr_detected,
        "dr_probability": v51.dr_probability,
        "no_dr_probability": v51.no_dr_probability,
        "threshold_used": v51.threshold_used,
        "confidence": v51.confidence,
        "model_name": v51.model_name,
        "model_version": v51.model_version,
    }
    v8_payload = None
    if result.severity is not None:
        v8 = result.severity
        v8_payload = {
            "grade_idx": v8.grade_idx,
            "grade_label": v8.grade_label,
            "confidence": v8.confidence,
            "probabilities": v8.probabilities,
            "model_name": v8.model_name,
            "model_version": v8.model_version,
        }

    record_screening_and_refresh(
        user_id=patient_id,
        modality="retinopathy",
        score=float(v51.dr_probability),
        risk_label=result.clinical_grade_label,
        model_version=f"{v51.model_name}@{v51.model_version}+v8",
        metadata={
            "clinical_grade": int(result.clinical_grade),
            "v51_threshold_used": float(v51.threshold_used),
            "v51_dr_detected": bool(v51.dr_detected),
            "dr_v8_grade": int(result.severity.grade_idx) if result.severity else 0,
            "dr_v8_confidence": float(result.severity.confidence) if result.severity else 0.0,
            "dr_v8_probabilities": result.severity.probabilities if result.severity else None,
        },
    )

    return RetinopathyInferenceResponse(
        patient_id=patient_id,
        reviewed_by_user_id=doctor_id,
        clinical_grade=result.clinical_grade,
        clinical_grade_label=result.clinical_grade_label,
        v51=v51_payload,
        v8=v8_payload,
    )


@router.post(
    "/retinopathy/gradcam",
    response_model=RetinopathyGradcamResponse,
    summary="Retinopathy explainability heatmap (doctor)",
)
async def retinopathy_gradcam(
    patient_id: int = Form(..., description="Patient record id this image belongs to"),
    image: UploadFile = File(...),
    claims: dict = Depends(require_roles("doctor")),
) -> RetinopathyGradcamResponse:
    doctor_id = _user_id_from_claims(claims)
    if patient_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="patient_id must be a positive integer.")
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must be an image.")

    raw_bytes = await image.read()
    if not raw_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded image is empty.")

    try:
        cascade = _retinopathy_service.predict_cascade(raw_bytes)
        # Choose explainer based on cascade verdict: EigenCAM for No DR (gentle global view),
        # multi-scale HiResCAM for any DR class (lesion-focused).
        if cascade.severity is None:
            data = _retinopathy_service.binary.generate_eigencam(raw_bytes)
            method = "EigenCAM"
            grade_label = cascade.clinical_grade_label
            confidence = cascade.binary.confidence
            attention_area = float(data["attention_area"])
            heatmap_b64 = data["heatmap_base64"]
        else:
            data = _retinopathy_service.severity.generate_hires_cam(
                raw_bytes, target_class=cascade.severity.grade_idx,
            )
            method = "HiResCAM-MultiScale"
            grade_label = cascade.clinical_grade_label
            confidence = cascade.severity.confidence
            attention_area = float(data["attention_area"])
            heatmap_b64 = data["heatmap_base64"]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Retinopathy checkpoint could not be loaded: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Retinopathy heatmap generation failed unexpectedly.",
        )

    return RetinopathyGradcamResponse(
        patient_id=patient_id,
        reviewed_by_user_id=doctor_id,
        method=method,
        heatmap_base64=heatmap_b64,
        grade_label=grade_label,
        confidence=confidence,
        attention_area=attention_area,
    )


@router.get("/retinopathy/health", response_model=RetinopathyModelHealthResponse)
def retinopathy_model_health(
    _claims: dict = Depends(require_roles("doctor")),
) -> RetinopathyModelHealthResponse:
    v51 = _retinopathy_service.binary
    v8 = _retinopathy_service.severity
    v51_path = v51.model_path
    v8_path = v8.model_path
    v51_exists = v51_path.exists()
    v8_exists = v8_path.exists()

    detail: str | None = None
    if v51_exists:
        try:
            v51.ensure_loaded()
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            detail = f"V5.1 load error: {exc}"
    if v8_exists and detail is None:
        try:
            v8.ensure_loaded()
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            detail = f"V8 load error: {exc}"

    if not v51_exists or not v8_exists:
        status_text = "missing_model"
    elif detail is not None:
        status_text = "load_failed"
    elif v51.is_loaded and v8.is_loaded:
        status_text = "ok"
    else:
        status_text = "partial"

    return RetinopathyModelHealthResponse(
        status=status_text,
        v51_file_exists=v51_exists,
        v51_loaded=v51.is_loaded,
        v51_path=v51_path.as_posix(),
        v8_file_exists=v8_exists,
        v8_loaded=v8.is_loaded,
        v8_path=v8_path.as_posix(),
        detail=detail,
    )
