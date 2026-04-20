from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import fmean
import math
import uuid

from psychology.schemas import (
    CrisisEvent,
    EmotionFrameResponse,
    EmotionLabel,
    FusionOutput,
    MentalState,
    MessageRequest,
    MessageResponse,
    Modality,
    SessionEndResponse,
    SessionSnapshotResponse,
    SessionStartResponse,
    TherapyMessageInput,
    TrendPoint,
    TrendResponse,
)
from psychology.storage import (
    InMemoryCrisisStore,
    InMemoryMemoryStore,
    InMemorySessionStore,
    InMemoryTrendStore,
    SessionRecord,
)


DISTRESS_THRESHOLDS: dict[MentalState, tuple[float, float]] = {
    MentalState.neutral: (0.0, 0.34),
    MentalState.anxious: (0.35, 0.59),
    MentalState.distressed: (0.60, 0.79),
    MentalState.depressed: (0.80, 0.99),
}
CRISIS_THRESHOLD = 0.75
MAX_SHORT_MEMORY = 10
SAFE_CRISIS_REPLY = (
    "I am concerned about your safety. I am alerting your care team now. "
    "Please stay where you are and reach out to emergency services if you are in immediate danger."
)


@dataclass
class SessionData:
    session_id: str
    patient_id: int
    started_at: datetime
    preferred_language: str
    messages: list[TherapyMessageInput] = field(default_factory=list)
    ended_at: datetime | None = None
    last_state: MentalState | None = None


class PsychologyService:
    def __init__(self) -> None:
        self._sessions = InMemorySessionStore()
        self._crisis_events = InMemoryCrisisStore()
        self._emotion_logs = InMemoryTrendStore()
        self._memories = InMemoryMemoryStore()

    def start_session(self, patient_id: int, preferred_language: str) -> SessionStartResponse:
        session_id = str(uuid.uuid4())
        started = datetime.utcnow()
        self._sessions.create_session(
            SessionRecord(
                session_id=session_id,
                patient_id=patient_id,
                preferred_language=preferred_language,
                started_at=started,
            )
        )
        memories = self._memories.top(patient_id, 3)
        return SessionStartResponse(
            session_id=session_id,
            patient_id=patient_id,
            started_at=started,
            memory_items_loaded=min(3, len(memories)),
        )

    def handle_message(self, payload: MessageRequest) -> MessageResponse:
        raw_session = self._sessions.get_session(payload.session_id)
        if raw_session is None:
            raise KeyError(payload.session_id)
        session = SessionData(
            session_id=raw_session.session_id,
            patient_id=raw_session.patient_id,
            started_at=raw_session.started_at,
            preferred_language=raw_session.preferred_language,
            messages=raw_session.messages,
            ended_at=raw_session.ended_at,
            last_state=MentalState(raw_session.last_state) if raw_session.last_state else None,
        )
        crisis_probability = self._crisis_probability(payload.text)
        crisis_detected = crisis_probability >= CRISIS_THRESHOLD
        fusion = self._fusion(payload)
        trend_slope = self._trend_slope(payload.patient_id)
        mental_state = self._classify_mental_state(fusion.distress_score, crisis_detected, trend_slope)
        session.last_state = mental_state

        patient_msg = TherapyMessageInput(role="patient", content=payload.text)
        session.messages.append(patient_msg)
        session.messages[:] = session.messages[-MAX_SHORT_MEMORY:]

        if crisis_detected:
            self._record_crisis(payload.patient_id, payload.session_id, crisis_probability)
            reply = SAFE_CRISIS_REPLY
            recommendation = "notify_clinician_immediately"
            technique = "safety_protocol"
        else:
            recommendation = self._recommendation(mental_state)
            technique = self._technique_for_state(mental_state)
            reply = self._therapy_reply(payload.text, mental_state, recommendation)

        assistant_msg = TherapyMessageInput(role="assistant", content=reply)
        session.messages.append(assistant_msg)
        session.messages[:] = session.messages[-MAX_SHORT_MEMORY:]

        point = TrendPoint(timestamp=datetime.utcnow(), distress_score=fusion.distress_score, state=mental_state)
        self._emotion_logs.append(payload.patient_id, point)
        raw_session.messages = session.messages
        raw_session.last_state = session.last_state.value if session.last_state else None
        raw_session.ended_at = session.ended_at
        self._sessions.put_session(raw_session)

        return MessageResponse(
            session_id=payload.session_id,
            reply=reply,
            emotion=fusion.label,
            distress_score=fusion.distress_score,
            language_detected=self._detect_language(payload.text),
            technique_used=technique,
            recommendation=recommendation,
            crisis_detected=crisis_detected,
            mental_state=mental_state,
            fusion=fusion,
        )

    def detect_emotion_frame(self, patient_id: int, frame_base64: str) -> EmotionFrameResponse:
        # Deterministic pseudo-scoring keeps this endpoint stable for 2fps streams.
        score = min(1.0, max(0.0, (len(frame_base64) % 100) / 100))
        if score >= 0.8:
            label = EmotionLabel.depressed
        elif score >= 0.6:
            label = EmotionLabel.distressed
        elif score >= 0.35:
            label = EmotionLabel.anxious
        else:
            label = EmotionLabel.neutral
        return EmotionFrameResponse(
            patient_id=patient_id,
            label=label,
            confidence=max(0.55, min(0.95, score + 0.2)),
            distress_score=score,
        )

    def get_session(self, session_id: str) -> SessionSnapshotResponse:
        session = self._sessions.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        return SessionSnapshotResponse(
            session_id=session.session_id,
            patient_id=session.patient_id,
            started_at=session.started_at,
            ended_at=session.ended_at,
            messages=session.messages,
            last_state=MentalState(session.last_state) if session.last_state else None,
        )

    def get_trends(self, patient_id: int) -> TrendResponse:
        points = self._emotion_logs.recent(patient_id, 7)
        return TrendResponse(
            patient_id=patient_id,
            window_size=7,
            slope=self._trend_slope(patient_id),
            points=points,
        )

    def list_crisis_events(self) -> list[CrisisEvent]:
        return self._crisis_events.list()

    def end_session(self, session_id: str, patient_id: int) -> SessionEndResponse:
        session = self._sessions.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        session.ended_at = datetime.utcnow()
        summary = self._build_summary(session)
        self._memories.append(patient_id, summary)
        self._sessions.put_session(session)
        return SessionEndResponse(
            session_id=session_id,
            summary_stored=True,
            stored_memory_items=len(self._memories.top(patient_id, 3)),
        )

    def _fusion(self, payload: MessageRequest) -> FusionOutput:
        entries: list[tuple[EmotionLabel, float, Modality]] = []
        text_label, text_confidence, text_sentiment = self._text_emotion(payload.text)
        entries.append((text_label, text_confidence, Modality.text))
        if payload.face_emotion and payload.face_confidence is not None:
            entries.append((payload.face_emotion, payload.face_confidence, Modality.face))
        if payload.speech_emotion and payload.speech_confidence is not None:
            entries.append((payload.speech_emotion, payload.speech_confidence, Modality.speech))

        if not entries:
            entries = [(EmotionLabel.neutral, 0.5, Modality.text)]

        weighted = 0.0
        weights = 0.0
        modalities: list[Modality] = []
        for label, conf, modality in entries:
            probabilities = self._emotion_distribution(label, conf)
            entropy = -sum(p * math.log(max(p, 1e-8)) for p in probabilities) / math.log(len(probabilities))
            gate_weight = max(0.05, 1.0 - entropy)
            distress_value = self._label_to_distress(label)
            weighted += distress_value * gate_weight
            weights += gate_weight
            modalities.append(modality)

        distress_score = weighted / max(weights, 1e-8)
        output_label = self._score_to_label(distress_score)
        confidence = max(0.5, min(0.98, fmean([entry[1] for entry in entries])))
        stress_level = min(10, max(1, int(round(distress_score * 10))))
        return FusionOutput(
            label=output_label,
            distress_score=round(distress_score, 4),
            confidence=round(confidence, 4),
            stress_level=stress_level,
            sentiment_score=round(text_sentiment, 4),
            modalities_used=modalities,
        )

    def _classify_mental_state(self, distress_score: float, crisis_detected: bool, trend_slope: float) -> MentalState:
        if crisis_detected:
            return MentalState.crisis
        adjusted = min(1.0, max(0.0, distress_score + max(0.0, trend_slope) * 0.03))
        if adjusted >= 0.8:
            return MentalState.depressed
        if adjusted >= 0.6:
            return MentalState.distressed
        if adjusted >= 0.35:
            return MentalState.anxious
        return MentalState.neutral

    def _trend_slope(self, patient_id: int) -> float:
        points = self._emotion_logs.recent(patient_id, 7)
        if len(points) < 2:
            return 0.0
        x_mean = (len(points) - 1) / 2
        y_mean = fmean(p.distress_score for p in points)
        numerator = sum((idx - x_mean) * (point.distress_score - y_mean) for idx, point in enumerate(points))
        denominator = sum((idx - x_mean) ** 2 for idx in range(len(points)))
        return 0.0 if denominator == 0 else numerator / denominator

    def _record_crisis(self, patient_id: int, session_id: str, probability: float) -> None:
        self._crisis_events.add(
            CrisisEvent(
                id=str(uuid.uuid4()),
                patient_id=patient_id,
                session_id=session_id,
                probability=probability,
                action_taken="Safe response returned + immediate doctor alert",
                created_at=datetime.utcnow(),
            )
        )

    def _text_emotion(self, text: str) -> tuple[EmotionLabel, float, float]:
        lower = text.lower()
        if any(token in lower for token in ("suicide", "kill myself", "can't continue", "end it")):
            return EmotionLabel.depressed, 0.95, -0.95
        if any(token in lower for token in ("hopeless", "empty", "worthless", "depressed")):
            return EmotionLabel.depressed, 0.85, -0.8
        if any(token in lower for token in ("panic", "anxious", "stressed", "overwhelmed")):
            return EmotionLabel.anxious, 0.8, -0.5
        if any(token in lower for token in ("tired", "angry", "cry", "pressure")):
            return EmotionLabel.distressed, 0.72, -0.45
        return EmotionLabel.neutral, 0.7, 0.2

    def _recommendation(self, state: MentalState) -> str | None:
        if state == MentalState.anxious:
            return "breathing_478"
        if state == MentalState.distressed:
            return "grounding_54321"
        if state == MentalState.depressed:
            return "behavioral_activation_microtask"
        return None

    def _technique_for_state(self, state: MentalState) -> str:
        if state == MentalState.anxious:
            return "cognitive_restructuring"
        if state == MentalState.distressed:
            return "grounding"
        if state == MentalState.depressed:
            return "behavioral_activation"
        return "supportive_reflection"

    def _therapy_reply(self, user_text: str, state: MentalState, recommendation: str | None) -> str:
        if state == MentalState.neutral:
            return "Thank you for sharing. What felt most manageable for you today?"
        if state == MentalState.anxious:
            return (
                "I hear that this feels heavy. Let's slow down together: inhale for 4, hold 7, exhale 8. "
                "After one round, tell me one thought that is driving this stress."
            )
        if state == MentalState.distressed:
            return (
                "You're carrying a lot right now. Let's ground first: name 5 things you can see, "
                "4 you can feel, and 3 you can hear. Then we can break this into one small next step."
            )
        if state == MentalState.depressed:
            return (
                "Thank you for saying this out loud. We can keep this very small: pick one tiny action "
                "for the next 10 minutes, like drinking water or opening a window."
            )
        return SAFE_CRISIS_REPLY

    def _build_summary(self, session: SessionData | SessionRecord) -> str:
        last_user = [msg.content for msg in session.messages if msg.role == "patient"][-1:] or [""]
        return (
            f"Session {session.session_id} summary: last_state={session.last_state or MentalState.neutral}, "
            f"last_patient_message={last_user[0][:160]}"
        )

    def _detect_language(self, text: str) -> str:
        lower = text.lower()
        if any(token in lower for token in ("le", "la", "bonjour", "merci", "je ", "vous ")):
            return "fr"
        if any(token in text for token in ("ال", "مرحبا", "أشعر")):
            return "ar"
        if any(token in lower for token in ("chnowa", "barsha", "barcha", "3andi", "mouch")):
            return "darija"
        if any(token in lower for token in ("bonjour", "hello", "مرحبا")):
            return "mixed"
        return "en"

    def _crisis_probability(self, text: str) -> float:
        lower = text.lower()
        hot_words = ("suicide", "kill myself", "end my life", "can't go on", "hurt myself")
        medium_words = ("hopeless", "no point", "worthless", "give up")
        if any(token in lower for token in hot_words):
            return 0.91
        if any(token in lower for token in medium_words):
            return 0.66
        return 0.12

    @staticmethod
    def _emotion_distribution(label: EmotionLabel, confidence: float) -> list[float]:
        base = [0.25, 0.25, 0.25, 0.25]
        idx = {
            EmotionLabel.neutral: 0,
            EmotionLabel.anxious: 1,
            EmotionLabel.distressed: 2,
            EmotionLabel.depressed: 3,
        }[label]
        base[idx] = min(0.9, max(0.35, confidence))
        rest = (1.0 - base[idx]) / 3.0
        for i in range(4):
            if i != idx:
                base[i] = rest
        return base

    @staticmethod
    def _label_to_distress(label: EmotionLabel) -> float:
        return {
            EmotionLabel.neutral: 0.2,
            EmotionLabel.anxious: 0.47,
            EmotionLabel.distressed: 0.7,
            EmotionLabel.depressed: 0.9,
        }[label]

    @staticmethod
    def _score_to_label(score: float) -> EmotionLabel:
        if score >= 0.8:
            return EmotionLabel.depressed
        if score >= 0.6:
            return EmotionLabel.distressed
        if score >= 0.35:
            return EmotionLabel.anxious
        return EmotionLabel.neutral
