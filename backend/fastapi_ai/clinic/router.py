import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

from core.rbac import require_roles
from clinic.schemas import (
    DFUSegmentationInferenceResponse,
    DFUSegmentationModelHealthResponse,
    DFUSegmentationXAIResponse,
    ThermalFootGradcamResponse,
    ThermalFootInferenceResponse,
    ThermalFootModelHealthResponse,
)
from clinic.models.DFUSegmentation import DFUSegmenter
from clinic.services.thermal_foot_pt_service import ThermalFootPtService

router = APIRouter(prefix="/clinic", tags=["clinic"])
_thermal_foot_service = ThermalFootPtService()
_dfu_segmentation_service = DFUSegmenter()


def _lesion_metrics(prediction, mm_per_pixel: float) -> dict:
    return {
        "mm_per_pixel": mm_per_pixel,
        "ulcer_area_mm2": float(prediction.ulcer_area_px) * (mm_per_pixel**2),
        "bbox_width_mm": float(prediction.bbox_width_px) * mm_per_pixel,
        "bbox_height_mm": float(prediction.bbox_height_px) * mm_per_pixel,
    }


def _simple_pdf_report(lines: list[str]) -> bytes:
    escaped_lines = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    content_lines = ["BT", "/F1 11 Tf", "50 780 Td", "14 TL"]
    for idx, line in enumerate(escaped_lines):
        if idx == 0:
            content_lines.append(f"({line}) Tj")
        else:
            content_lines.append(f"T* ({line}) Tj")
    content_lines.append("ET")
    stream_text = "\n".join(content_lines)
    stream_bytes = stream_text.encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj")
    objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj")
    objects.append(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj"
    )
    objects.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")
    objects.append(
        f"5 0 obj << /Length {len(stream_bytes)} >> stream\n".encode("ascii")
        + stream_bytes
        + b"\nendstream endobj"
    )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
        pdf.extend(b"\n")
    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)


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
    threshold: float = Form(0.5, description="Mask threshold in [0, 1]"),
    mm_per_pixel: float = Form(0.5, description="Physical scaling factor in millimeters per pixel"),
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

    try:
        prediction = _dfu_segmentation_service.predict(raw_bytes, threshold=threshold)
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
    metrics = _lesion_metrics(prediction, mm_per_pixel)

    return DFUSegmentationInferenceResponse(
        patient_id=patient_id,
        reviewed_by_user_id=doctor_id,
        model_name="resnet34_unet_dfu",
        model_version="pth-v1",
        threshold_used=prediction.threshold_used,
        ulcer_detected=prediction.ulcer_detected,
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
    threshold: float = Form(0.5, description="Mask threshold in [0, 1]"),
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

    try:
        prediction = _dfu_segmentation_service.predict(raw_bytes, threshold=threshold)
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
    "/dfu-segmentation/report.pdf",
    summary="DFU segmentation PDF report (doctor)",
)
async def dfu_segmentation_report_pdf(
    patient_id: int = Form(..., description="Patient record id this image belongs to"),
    image: UploadFile = File(...),
    threshold: float = Form(0.5, description="Mask threshold in [0, 1]"),
    mm_per_pixel: float = Form(0.5, description="Physical scaling factor in millimeters per pixel"),
    claims: dict = Depends(require_roles("doctor")),
) -> Response:
    doctor_id = _user_id_from_claims(claims)
    if patient_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="patient_id must be positive.")
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must be an image.")
    raw_bytes = await image.read()
    if not raw_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded image is empty.")

    try:
        prediction = _dfu_segmentation_service.predict(raw_bytes, threshold=threshold)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DFU report generation failed unexpectedly.",
        )

    metrics = _lesion_metrics(prediction, mm_per_pixel)
    report_lines = [
        "Glunova Clinical Decision Support - DFU Segmentation Report",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Doctor ID: {doctor_id}",
        f"Patient ID: {patient_id}",
        "",
        f"Model: resnet34_unet_dfu (pth-v1), threshold={prediction.threshold_used:.2f}",
        f"Ulcer detected: {'yes' if prediction.ulcer_detected else 'no'}",
        f"Ulcer area: {prediction.ulcer_area_px} px ({metrics['ulcer_area_mm2']:.2f} mm^2)",
        (
            "Bounding box: "
            f"x={prediction.bbox_x}, y={prediction.bbox_y}, "
            f"w={prediction.bbox_width_px}px ({metrics['bbox_width_mm']:.2f}mm), "
            f"h={prediction.bbox_height_px}px ({metrics['bbox_height_mm']:.2f}mm)"
        ),
        "",
        "Clinical note: AI output supports decision making and does not replace diagnosis.",
    ]
    pdf_bytes = _simple_pdf_report(report_lines)
    filename = f"dfu_report_patient_{patient_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
