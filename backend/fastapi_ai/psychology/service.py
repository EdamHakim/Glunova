from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import fmean
import base64
import binascii
import json
import logging
import math
import tempfile
import uuid
from typing import Any

import numpy as np

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
from psychology.knowledge_ingestion import get_knowledge_base
from psychology.storage import (
    CrisisStore,
    InMemoryCrisisStore,
    InMemoryMemoryStore,
    InMemorySessionStore,
    InMemoryTrendStore,
    MemoryStore,
    SessionRecord,
    SessionStore,
    TrendStore,
)

logger = logging.getLogger(__name__)


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
    def __init__(
        self,
        pool: Any | None = None,
        sessions: SessionStore | None = None,
        crisis_events: CrisisStore | None = None,
        emotion_logs: TrendStore | None = None,
        memories: MemoryStore | None = None,
    ) -> None:
        self._pool = pool
        self._sessions = sessions or InMemorySessionStore()
        self._crisis_events = crisis_events or InMemoryCrisisStore()
        self._emotion_logs = emotion_logs or InMemoryTrendStore()
        self._memories = memories or InMemoryMemoryStore()
        self._knowledge_base = get_knowledge_base()
        self._deepface_available = None
        self._speechbrain_available = None

    def start_session(self, patient_id: int, preferred_language: str) -> SessionStartResponse:
        started = datetime.utcnow()
        if self._pool is not None:
            from psychology.repositories import get_physician_review_required

            if get_physician_review_required(self._pool, patient_id):
                return SessionStartResponse(
                    patient_id=patient_id,
                    started_at=started,
                    allowed=False,
                    block_reason="Physician review is required before starting another AI session.",
                    physician_review_required=True,
                    memory_items_loaded=0,
                )
        session_id = str(uuid.uuid4())
        self._sessions.create_session(
            SessionRecord(
                session_id=session_id,
                patient_id=patient_id,
                preferred_language=preferred_language,
                started_at=started,
            )
        )
        memories = self._memories.top(patient_id, 3)
        logger.info("psychology.session.start patient_id=%s session_id=%s", patient_id, session_id)
        return SessionStartResponse(
            session_id=session_id,
            patient_id=patient_id,
            started_at=started,
            memory_items_loaded=min(3, len(memories)),
            allowed=True,
            physician_review_required=False,
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
        language_detected = self._detect_language(payload.text)
        crisis_probability = self._crisis_probability(payload.text)
        hist = list(raw_session.crisis_score_history)
        hist.append(crisis_probability)
        hist = hist[-8:]
        raw_session.crisis_score_history = hist
        crisis_detected = self._crisis_trigger(crisis_probability, hist)
        logger.info(
            "psychology.message crisis_prob=%.3f crisis=%s session_id=%s",
            crisis_probability,
            crisis_detected,
            payload.session_id,
        )
        fusion = self._fusion(payload)
        trend_slope = self._trend_slope(payload.patient_id)
        mental_state = self._classify_mental_state(fusion.distress_score, crisis_detected, trend_slope)
        kb_context = self._knowledge_base.search(payload.text, language=language_detected, limit=3)
        memory_items = self._memories.top(payload.patient_id, 3)
        health_context: dict[str, Any] = {}
        if self._pool is not None:
            from psychology.repositories import get_patient_health_context

            health_context = get_patient_health_context(self._pool, payload.patient_id)
        session.last_state = mental_state

        fusion_meta = json.loads(fusion.model_dump_json())
        fusion_meta["crisis_probability"] = crisis_probability
        fusion_meta["language_detected"] = language_detected
        patient_msg = TherapyMessageInput(
            role="patient",
            content=payload.text,
            fusion_metadata=fusion_meta,
        )
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
            reply, recommendation, technique = self._therapy_reply_multimodal(
                user_text=payload.text,
                mental_state=mental_state,
                recommendation=recommendation,
                technique=technique,
                kb_context=kb_context,
                memory_items=memory_items,
                health_context=health_context,
                fusion=fusion,
            )

        assistant_msg = TherapyMessageInput(role="assistant", content=reply)
        session.messages.append(assistant_msg)
        session.messages[:] = session.messages[-MAX_SHORT_MEMORY:]

        point = TrendPoint(timestamp=datetime.utcnow(), distress_score=fusion.distress_score, state=mental_state)
        self._emotion_logs.append(payload.patient_id, point)
        raw_session.messages = session.messages
        raw_session.last_state = session.last_state.value if session.last_state else None
        raw_session.ended_at = session.ended_at
        self._sessions.put_session(raw_session)

        physician_review_required = False
        if self._pool is not None:
            from psychology.repositories import get_physician_review_required

            physician_review_required = get_physician_review_required(self._pool, payload.patient_id)

        logger.info(
            "psychology.message.complete mental_state=%s distress=%.3f",
            mental_state.value,
            fusion.distress_score,
        )
        return MessageResponse(
            session_id=payload.session_id,
            reply=reply,
            emotion=fusion.label,
            distress_score=fusion.distress_score,
            language_detected=language_detected,
            technique_used=technique,
            recommendation=recommendation,
            crisis_detected=crisis_detected,
            mental_state=mental_state,
            fusion=fusion,
            physician_review_required=physician_review_required,
        )

    def detect_emotion_frame(self, patient_id: int, frame_base64: str) -> EmotionFrameResponse:
        face = self._infer_face_emotion_deepface(frame_base64)
        if face is None:
            # Deterministic fallback keeps endpoint stable if DeepFace is unavailable.
            score = min(1.0, max(0.0, (len(frame_base64) % 100) / 100))
            if score >= 0.8:
                label = EmotionLabel.depressed
            elif score >= 0.6:
                label = EmotionLabel.distressed
            elif score >= 0.35:
                label = EmotionLabel.anxious
            else:
                label = EmotionLabel.neutral
            confidence = max(0.55, min(0.95, score + 0.2))
        else:
            label, confidence = face
            score = self._label_to_distress(label)
        ms = self._classify_mental_state(score, crisis_detected=False, trend_slope=0.0)
        self._emotion_logs.append(
            patient_id,
            TrendPoint(timestamp=datetime.utcnow(), distress_score=score, state=ms),
        )
        return EmotionFrameResponse(
            patient_id=patient_id,
            label=label,
            confidence=confidence,
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

    def acknowledge_crisis(self, event_id: str, patient_id: int | None) -> bool:
        if self._pool is None:
            return False
        from psychology.repositories import acknowledge_crisis_event

        return acknowledge_crisis_event(self._pool, event_id, patient_id)

    def clear_physician_gate(self, patient_id: int) -> None:
        if self._pool is None:
            return
        from psychology.repositories import clear_physician_review_required

        clear_physician_review_required(self._pool, patient_id)

    def end_session(self, session_id: str, patient_id: int) -> SessionEndResponse:
        session = self._sessions.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        session.ended_at = datetime.utcnow()
        summary_dict = self._build_summary_dict(session)
        session.session_summary_json = summary_dict
        self._memories.append(patient_id, json.dumps(summary_dict, ensure_ascii=False))
        self._sessions.put_session(session)
        logger.info("psychology.session.end session_id=%s patient_id=%s", session_id, patient_id)
        return SessionEndResponse(
            session_id=session_id,
            summary_stored=True,
            stored_memory_items=len(self._memories.top(patient_id, 3)),
        )

    def _fusion(self, payload: MessageRequest) -> FusionOutput:
        entries: list[tuple[EmotionLabel, float, Modality]] = []
        text_label, text_confidence, text_sentiment = self._text_emotion(payload.text)
        entries.append((text_label, text_confidence, Modality.text))

        face_result = None
        if payload.face_frame_base64:
            face_result = self._infer_face_emotion_deepface(payload.face_frame_base64)
        if face_result is None and payload.face_emotion and payload.face_confidence is not None:
            face_result = (payload.face_emotion, payload.face_confidence)
        if face_result is not None:
            entries.append((face_result[0], face_result[1], Modality.face))

        speech_result = None
        if payload.speech_audio_base64:
            speech_result = self._infer_speech_emotion_speechbrain(payload.speech_audio_base64)
        if speech_result is None and payload.speech_emotion and payload.speech_confidence is not None:
            speech_result = (payload.speech_emotion, payload.speech_confidence)
        if speech_result is not None:
            entries.append((speech_result[0], speech_result[1], Modality.speech))

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
                action_taken="Safe response returned + physician review gate raised",
                created_at=datetime.utcnow(),
            )
        )
        if self._pool is not None:
            from psychology.repositories import set_physician_review_required

            set_physician_review_required(self._pool, patient_id, True)
        logger.warning("psychology.crisis.trigger patient_id=%s session_id=%s prob=%.3f", patient_id, session_id, probability)

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

    @staticmethod
    def _crisis_trigger(probability: float, history: list[float]) -> bool:
        if probability >= CRISIS_THRESHOLD:
            return True
        tail = history[-3:]
        if len(tail) < 3:
            return False
        return (sum(tail) / 3.0) >= 0.65 and probability >= 0.60

    def _therapy_reply_multimodal(
        self,
        user_text: str,
        mental_state: MentalState,
        recommendation: str | None,
        technique: str,
        kb_context: list[dict[str, str]] | None,
        memory_items: list[str],
        health_context: dict[str, Any],
        fusion: FusionOutput,
    ) -> tuple[str, str | None, str]:
        from psychology.llm_therapy import run_therapy_llm

        fusion_summary = (
            f"label={fusion.label.value}, distress={fusion.distress_score}, "
            f"stress={fusion.stress_level}, modalities={[m.value for m in fusion.modalities_used]}"
        )
        llm = run_therapy_llm(
            user_text=user_text,
            mental_state=mental_state.value,
            kb_snippets=kb_context or [],
            memory_items=memory_items,
            health_context=health_context,
            fusion_summary=fusion_summary,
        )
        if llm and isinstance(llm.get("reply"), str) and llm["reply"].strip():
            rec = llm.get("recommendation")
            if isinstance(rec, str):
                rec_out: str | None = rec.strip() or recommendation
            else:
                rec_out = recommendation
            tech = llm.get("technique")
            tech_out = tech.strip() if isinstance(tech, str) and tech.strip() else technique
            return llm["reply"].strip(), rec_out, tech_out
        tpl = self._therapy_reply_template(user_text, mental_state, recommendation, kb_context)
        return tpl, recommendation, technique

    def _therapy_reply_template(
        self,
        user_text: str,
        state: MentalState,
        recommendation: str | None,
        kb_context: list[dict[str, str]] | None = None,
    ) -> str:
        kb_hint = ""
        if kb_context:
            first = kb_context[0].get("text", "").strip()
            if first:
                kb_hint = f" CBT hint: {first[:140]}"
        if state == MentalState.neutral:
            return f"Thank you for sharing. What felt most manageable for you today?{kb_hint}"
        if state == MentalState.anxious:
            return (
                "I hear that this feels heavy. Let's slow down together: inhale for 4, hold 7, exhale 8. "
                f"After one round, tell me one thought that is driving this stress.{kb_hint}"
            )
        if state == MentalState.distressed:
            return (
                "You're carrying a lot right now. Let's ground first: name 5 things you can see, "
                f"4 you can feel, and 3 you can hear. Then we can break this into one small next step.{kb_hint}"
            )
        if state == MentalState.depressed:
            return (
                "Thank you for saying this out loud. We can keep this very small: pick one tiny action "
                f"for the next 10 minutes, like drinking water or opening a window.{kb_hint}"
            )
        return SAFE_CRISIS_REPLY

    def _build_summary_dict(self, session: SessionData | SessionRecord) -> dict[str, Any]:
        patient_msgs = [msg.content for msg in session.messages if msg.role == "patient"]
        last_user = patient_msgs[-1:] or [""]
        risk_flags: list[str] = []
        joined = " ".join(patient_msgs).lower()
        for token in ("suicide", "hurt myself", "hopeless", "worthless"):
            if token in joined:
                risk_flags.append(token)
        last_state = session.last_state
        if isinstance(last_state, MentalState):
            ls = last_state.value
        elif isinstance(last_state, str):
            ls = last_state
        else:
            ls = MentalState.neutral.value
        return {
            "session_id": session.session_id,
            "last_state": ls,
            "last_patient_message_excerpt": last_user[0][:200],
            "risk_flags": risk_flags,
            "breakthroughs": [],
            "triggers": [],
            "emotions_trail": [
                (m.fusion_metadata or {}).get("label")
                for m in session.messages
                if isinstance(m.fusion_metadata, dict)
            ],
        }

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

    def _infer_face_emotion_deepface(self, frame_base64: str) -> tuple[EmotionLabel, float] | None:
        if self._deepface_available is False:
            return None
        try:
            from deepface import DeepFace  # type: ignore
            import cv2  # type: ignore

            self._deepface_available = True
            image_bytes = self._safe_b64decode(frame_base64)
            if image_bytes is None:
                return None
            image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                return None
            analysis = DeepFace.analyze(
                img_path=image,
                actions=["emotion"],
                enforce_detection=False,
                detector_backend="opencv",
                silent=True,
            )
            if isinstance(analysis, list):
                analysis = analysis[0]
            emotion_scores = analysis.get("emotion", {})
            if not emotion_scores:
                return None
            top_label = max(emotion_scores, key=emotion_scores.get).lower()
            conf = float(emotion_scores[top_label]) / 100.0
            mapped = self._map_deepface_label(top_label)
            return mapped, max(0.45, min(0.99, conf))
        except Exception:
            self._deepface_available = False
            return None

    def _infer_speech_emotion_speechbrain(self, audio_base64: str) -> tuple[EmotionLabel, float] | None:
        if self._speechbrain_available is False:
            return None
        try:
            from speechbrain.inference.classifiers import EncoderClassifier  # type: ignore

            self._speechbrain_available = True
            wav_bytes = self._safe_b64decode(audio_base64)
            if wav_bytes is None:
                return None
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                tmp.write(wav_bytes)
                tmp.flush()
                classifier = EncoderClassifier.from_hparams(
                    source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
                    savedir="pretrained_models/speechbrain_emotion",
                )
                _, _, _, text_lab = classifier.classify_file(tmp.name)
            label_raw = text_lab[0].strip().lower() if text_lab else "neu"
            mapped = self._map_speechbrain_label(label_raw)
            confidence = 0.7
            return mapped, confidence
        except Exception:
            self._speechbrain_available = False
            return None

    @staticmethod
    def _safe_b64decode(raw: str) -> bytes | None:
        try:
            payload = raw.split(",", 1)[1] if "," in raw else raw
            return base64.b64decode(payload, validate=False)
        except (ValueError, binascii.Error):
            return None

    @staticmethod
    def _map_deepface_label(label: str) -> EmotionLabel:
        if label in {"sad", "fear", "angry", "disgust"}:
            return EmotionLabel.distressed
        if label in {"surprise"}:
            return EmotionLabel.anxious
        if label in {"happy"}:
            return EmotionLabel.neutral
        if label in {"neutral"}:
            return EmotionLabel.neutral
        return EmotionLabel.anxious

    @staticmethod
    def _map_speechbrain_label(label: str) -> EmotionLabel:
        if label in {"sad", "sadness"}:
            return EmotionLabel.depressed
        if label in {"ang", "angry", "fru", "frustrated"}:
            return EmotionLabel.distressed
        if label in {"hap", "exc", "happy", "excited"}:
            return EmotionLabel.neutral
        if label in {"neu", "neutral"}:
            return EmotionLabel.neutral
        return EmotionLabel.anxious


def create_psychology_service() -> PsychologyService:
    from psychology.db import get_connection_pool
    from psychology.patient_memory import build_memory_store
    from psychology.repositories import PsqlCrisisStore, PsqlSessionStore, PsqlTrendStore

    memories = build_memory_store()
    pool = get_connection_pool()
    if pool is not None:
        return PsychologyService(
            pool=pool,
            sessions=PsqlSessionStore(pool),
            crisis_events=PsqlCrisisStore(pool),
            emotion_logs=PsqlTrendStore(pool),
            memories=memories,
        )
    return PsychologyService(memories=memories)
