from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class MentalState(str, Enum):
    neutral = "Neutral"
    anxious = "Anxious"
    distressed = "Distressed"
    depressed = "Depressed"
    crisis = "Crisis"


class Modality(str, Enum):
    face = "face"
    speech = "speech"
    text = "text"


class EmotionLabel(str, Enum):
    neutral = "neutral"
    happy = "happy"
    anxious = "anxious"
    distressed = "distressed"
    depressed = "depressed"


class TherapyMessageInput(BaseModel):
    role: Literal["patient", "assistant"]
    content: str = Field(min_length=1, max_length=4000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    fusion_metadata: dict | None = None


class SessionStartRequest(BaseModel):
    patient_id: int = Field(gt=0)
    preferred_language: Literal["en", "fr", "ar", "darija", "mixed"] = "en"


class SessionStartResponse(BaseModel):
    session_id: str | None = None
    patient_id: int
    started_at: datetime | None = None
    memory_items_loaded: int = 0
    allowed: bool = True
    block_reason: str | None = None
    physician_review_required: bool = False


class MessageRequest(BaseModel):
    session_id: str
    patient_id: int = Field(gt=0)
    text: str = Field(default="", max_length=4000)
    face_frame_base64: str | None = None
    face_emotion: EmotionLabel | None = None
    face_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    speech_audio_base64: str | None = None
    speech_emotion: EmotionLabel | None = None
    speech_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    speech_transcript: str | None = None

    @model_validator(mode="before")
    @classmethod
    def merge_voice_transcript(cls, data: Any) -> Any:
        if isinstance(data, dict):
            t = (data.get("text") or "").strip()
            st = (data.get("speech_transcript") or "").strip()
            if not t and st:
                data = {**data, "text": st}
        return data

    @model_validator(mode="after")
    def require_text(self) -> MessageRequest:
        if not (self.text or "").strip():
            raise ValueError("text or speech_transcript is required")
        return self


class FusionOutput(BaseModel):
    label: EmotionLabel
    distress_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    stress_level: int = Field(ge=1, le=10)
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    modalities_used: list[Modality]


class MessageResponse(BaseModel):
    session_id: str
    reply: str
    emotion: EmotionLabel
    distress_score: float
    language_detected: Literal["en", "fr", "ar", "darija", "mixed"]
    technique_used: str
    recommendation: str | None
    crisis_detected: bool
    mental_state: MentalState
    fusion: FusionOutput
    physician_review_required: bool = False
    anomaly_flags: list[str] = []
    retrieval_quality: str = "ok"


class CrisisAckRequest(BaseModel):
    event_id: str
    patient_id: int | None = Field(default=None, gt=0)


class PhysicianClearGateRequest(BaseModel):
    patient_id: int = Field(gt=0)


class EmotionFrameRequest(BaseModel):
    patient_id: int = Field(gt=0)
    frame_base64: str = Field(min_length=20)


class EmotionFrameResponse(BaseModel):
    patient_id: int
    label: EmotionLabel
    confidence: float = Field(ge=0.0, le=1.0)
    distress_score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionSnapshotResponse(BaseModel):
    session_id: str
    patient_id: int
    started_at: datetime
    ended_at: datetime | None
    messages: list[TherapyMessageInput]
    last_state: MentalState | None


class TrendPoint(BaseModel):
    timestamp: datetime
    distress_score: float = Field(ge=0.0, le=1.0)
    state: MentalState


class TrendResponse(BaseModel):
    patient_id: int
    window_size: int = 7
    slope: float
    points: list[TrendPoint]


class CrisisEvent(BaseModel):
    id: str
    patient_id: int
    session_id: str
    probability: float = Field(ge=0.0, le=1.0)
    action_taken: str
    created_at: datetime
    acknowledged_at: datetime | None = None


class CrisisEventsResponse(BaseModel):
    items: list[CrisisEvent]


class VoiceTranscribeResponse(BaseModel):
    text: str
    language_guess: str | None = None


class VoiceSynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    language: Literal["en", "fr", "ar", "darija", "mixed"] = "en"


class SessionEndRequest(BaseModel):
    session_id: str
    patient_id: int = Field(gt=0)


class SessionEndResponse(BaseModel):
    session_id: str
    summary_stored: bool
    stored_memory_items: int


class SessionHistoryItem(BaseModel):
    session_id: str
    started_at: datetime
    ended_at: datetime
    preferred_language: str = "en"
    last_state: str | None = None
    excerpt: str = ""
    techniques: list[str] = Field(default_factory=list)
    has_risk_flags: bool = False


class SessionHistoryResponse(BaseModel):
    patient_id: int
    items: list[SessionHistoryItem]
