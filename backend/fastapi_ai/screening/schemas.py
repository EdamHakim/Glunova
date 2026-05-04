from pydantic import BaseModel, Field


class TongueInferenceResponse(BaseModel):
    status: str = "ok"
    patient_id: int = Field(gt=0)
    model_name: str
    model_version: str
    threshold_used: float = Field(ge=0, le=1)
    logit: float
    probability: float = Field(ge=0, le=1)
    prediction_index: int
    prediction_label: str


class TongueModelHealthResponse(BaseModel):
    status: str
    model_file_exists: bool
    model_loaded: bool
    model_path: str


class TongueGradcamResponse(BaseModel):
    status: str = "ok"
    patient_id: int = Field(gt=0)
    heatmap_base64: str
    prediction_label: str
    probability: float = Field(ge=0, le=1)


class VoiceShapSegment(BaseModel):
    segment: int = Field(ge=1)
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    shap_value: float
    abs_shap: float = Field(ge=0)


class VoiceInferenceResponse(BaseModel):
    status: str = "ok"
    patient_id: int = Field(gt=0)
    model_name: str
    model_version: str
    threshold_used: float = Field(ge=0, le=1)
    probability: float = Field(ge=0, le=1)
    raw_probability: float = Field(ge=0, le=1)
    prediction_index: int
    prediction_label: str
    decision_score: float
    ood_mahal_score: float
    ood_flag: bool
    shap_ready: bool
    shap_message: str
    shap_base_value: float | None = None
    shap_segments: list[VoiceShapSegment] = Field(default_factory=list)
    shap_plot_base64: str | None = None


class VoiceModelHealthResponse(BaseModel):
    status: str
    model_file_exists: bool
    model_loaded: bool
    model_path: str
    byols_repo_exists: bool
    byols_checkpoint_exists: bool


# ─────────────────────────────────────────────────────────────
# CATARACT SCHEMAS
# ─────────────────────────────────────────────────────────────


class CataractInferenceResponse(BaseModel):
    status: str = "ok"
    patient_id: int = Field(gt=0)
    model_name: str
    model_version: str
    prediction_index: int = Field(ge=0, le=3)
    prediction_label: str
    confidence: float = Field(ge=0, le=1)
    p_cataract: float = Field(ge=0, le=1)
    probabilities: dict[str, float] = Field(description="Probabilities for each class")


class CataractModelHealthResponse(BaseModel):
    status: str
    model_file_exists: bool
    model_loaded: bool
    model_path: str


class CataractGradcamResponse(BaseModel):
    status: str = "ok"
    patient_id: int = Field(gt=0)
    heatmap_base64: str
    prediction_label: str
    confidence: float = Field(ge=0, le=1)
    p_cataract: float = Field(ge=0, le=1)
    probabilities: dict[str, float]
