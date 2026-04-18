from pydantic import BaseModel, Field


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


class ThermalFootGradcamResponse(BaseModel):
    status: str = "ok"
    patient_id: int = Field(gt=0)
    reviewed_by_user_id: int = Field(gt=0)
    heatmap_base64: str
    prediction_label: str
    probability: float = Field(ge=0, le=1)
