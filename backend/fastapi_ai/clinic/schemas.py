from typing import Literal

from pydantic import BaseModel, Field

DFUSeverityLevel = Literal["none", "mild", "moderate", "severe", "critical"]


class ThermalFootInferenceResponse(BaseModel):
    status: str = "ok"
    patient_id: int = Field(gt=0)
    reviewed_by_user_id: int = Field(gt=0)
    model_name: str
    model_version: str
    threshold_used: float = Field(ge=0, le=1)
    logit: float
    probability: float = Field(ge=0, le=1)
    prediction_index: int
    prediction_label: str


class ThermalFootModelHealthResponse(BaseModel):
    status: str
    model_file_exists: bool
    model_loaded: bool
    model_path: str
    detail: str | None = None


class ThermalFootGradcamResponse(BaseModel):
    status: str = "ok"
    patient_id: int = Field(gt=0)
    reviewed_by_user_id: int = Field(gt=0)
    heatmap_base64: str
    prediction_label: str
    probability: float = Field(ge=0, le=1)


class DFUSegmentationInferenceResponse(BaseModel):
    status: str = "ok"
    patient_id: int = Field(gt=0)
    reviewed_by_user_id: int = Field(gt=0)
    model_name: str
    model_version: str
    threshold_used: float = Field(ge=0, le=1)
    ulcer_detected: bool
    ulcer_severity: DFUSeverityLevel = Field(
        description="Heuristic triage tier from ulcer area in mm² (none|mild|moderate|severe|critical).",
    )
    ulcer_area_ratio: float = Field(ge=0, le=1)
    ulcer_area_px: int = Field(ge=0)
    bbox_x: int = Field(ge=0)
    bbox_y: int = Field(ge=0)
    bbox_width_px: int = Field(ge=0)
    bbox_height_px: int = Field(ge=0)
    mm_per_pixel: float = Field(gt=0)
    ulcer_area_mm2: float = Field(ge=0)
    bbox_width_mm: float = Field(ge=0)
    bbox_height_mm: float = Field(ge=0)
    mask_base64: str
    overlay_base64: str


class DFUSegmentationModelHealthResponse(BaseModel):
    status: str
    model_file_exists: bool
    model_loaded: bool
    model_path: str
    detail: str | None = None


class DFUSegmentationXAIResponse(BaseModel):
    status: str = "ok"
    patient_id: int = Field(gt=0)
    reviewed_by_user_id: int = Field(gt=0)
    xai_overlay_base64: str
    mask_base64: str
    ulcer_detected: bool


# ─── Retinopathy (DR cascade V5.1 → V8) ──────────────────────────────


class RetinopathyV51Detail(BaseModel):
    dr_detected: bool
    dr_probability: float = Field(ge=0, le=1)
    no_dr_probability: float = Field(ge=0, le=1)
    threshold_used: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    model_name: str
    model_version: str


class RetinopathyV8Detail(BaseModel):
    grade_idx: int = Field(ge=0, le=3)
    grade_label: str
    confidence: float = Field(ge=0, le=1)
    probabilities: dict[str, float]
    model_name: str
    model_version: str


class RetinopathyInferenceResponse(BaseModel):
    status: str = "ok"
    patient_id: int = Field(gt=0)
    reviewed_by_user_id: int = Field(gt=0)
    clinical_grade: int = Field(ge=0, le=4)
    clinical_grade_label: str
    v51: RetinopathyV51Detail
    v8: RetinopathyV8Detail | None = None


class RetinopathyGradcamResponse(BaseModel):
    status: str = "ok"
    patient_id: int = Field(gt=0)
    reviewed_by_user_id: int = Field(gt=0)
    method: str
    heatmap_base64: str
    grade_label: str
    confidence: float = Field(ge=0, le=1)
    attention_area: float = Field(ge=0, le=1)


class RetinopathyModelHealthResponse(BaseModel):
    status: str
    v51_file_exists: bool
    v51_loaded: bool
    v51_path: str
    v8_file_exists: bool
    v8_loaded: bool
    v8_path: str
    detail: str | None = None
