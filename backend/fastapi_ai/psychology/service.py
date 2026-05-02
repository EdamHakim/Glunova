from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import fmean
import base64
import binascii
from io import BytesIO
import json
import logging
import math
import tempfile
import uuid
from typing import Any

import numpy as np
from PIL import Image

from core.config import settings

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
from psychology.hf_emotion_inference import classify_audio, classify_image, classify_text
from psychology.kb_retrieval import resolve_kb_retrieval_limit
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
MIN_RETRIEVAL_SCORE = 0.16


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
        self._hf_face_bundle: tuple[Any, Any] | None = None
        self._emotion2vec_infer: Any | None = None
        self._hf_text_classifier: Any | None = None
        self._latest_face_by_patient: dict[int, tuple[EmotionLabel, float, datetime]] = {}
        self._face_distress_ema_by_patient: dict[int, float] = {}

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
        kb_limit = resolve_kb_retrieval_limit(payload.text, mental_state)
        kb_context = self._knowledge_base.search(payload.text, language=language_detected, limit=kb_limit)
        anomaly_flags: list[str] = []
        retrieval_quality = self._retrieval_quality(kb_context)
        if retrieval_quality != "ok":
            anomaly_flags.append(f"retrieval_{retrieval_quality}")
        memory_items = self._memories.top(payload.patient_id, 5)
        session_phase = self._session_phase(raw_session.messages)
        prior_techniques = self._extract_recent_techniques(raw_session.messages, limit=5)
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
            safety_mode = "crisis_guard"
        else:
            recommendation = self._recommendation(mental_state)
            base_technique = self._technique_for_state(mental_state)
            technique = self._progress_technique_for_state(mental_state, base_technique, prior_techniques)
            safety_tier = self._safety_tier(crisis_probability)
            reply, recommendation, technique, llm_anomalies, safety_mode = self._therapy_reply_multimodal(
                user_text=payload.text,
                mental_state=mental_state,
                language_detected=language_detected,
                recommendation=recommendation,
                technique=technique,
                kb_context=kb_context,
                memory_items=memory_items,
                health_context=health_context,
                fusion=fusion,
                retrieval_quality=retrieval_quality,
                safety_tier=safety_tier,
                session_phase=session_phase,
            )
            anomaly_flags.extend(llm_anomalies)
            if safety_tier == "elevated":
                anomaly_flags.append("safety_elevated")

        assistant_msg = TherapyMessageInput(
            role="assistant",
            content=reply,
            fusion_metadata={
                "technique_used": technique,
                "recommendation": recommendation,
                "session_phase": session_phase,
                "safety_mode": safety_mode,
                "continuity_memory_count": len(memory_items),
            },
        )
        session.messages.append(assistant_msg)
        session.messages[:] = session.messages[-MAX_SHORT_MEMORY:]

        point = TrendPoint(timestamp=datetime.utcnow(), distress_score=fusion.distress_score, state=mental_state)
        self._emotion_logs.append(payload.patient_id, point)
        jump = self._distress_jump_anomaly(raw_session.messages, fusion.distress_score)
        if jump:
            anomaly_flags.append("fusion_abrupt_jump")
        raw_session.messages = session.messages
        raw_session.last_state = session.last_state.value if session.last_state else None
        raw_session.ended_at = session.ended_at
        self._sessions.put_session(raw_session)

        physician_review_required = False
        if self._pool is not None:
            from psychology.repositories import get_physician_review_required

            physician_review_required = get_physician_review_required(self._pool, payload.patient_id)

        logger.info(
            "psychology.message.complete mental_state=%s distress=%.3f retrieval_quality=%s anomalies=%s",
            mental_state.value,
            fusion.distress_score,
            retrieval_quality,
            ",".join(anomaly_flags) if anomaly_flags else "none",
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
            anomaly_flags=anomaly_flags,
            retrieval_quality=retrieval_quality,
        )

    def detect_emotion_frame(self, patient_id: int, frame_base64: str) -> EmotionFrameResponse:
        face = self._infer_face_emotion_from_frame(frame_base64)
        if face is None:
            # If current frame failed, reuse the latest recent label to avoid hard-locking
            # neutral 35% for transient detector failures.
            cached = self._latest_face_by_patient.get(patient_id)
            if cached is not None:
                cached_label, cached_confidence, observed_at = cached
                age = (datetime.utcnow() - observed_at).total_seconds()
                if age <= 2.5:
                    decay = max(0.55, 1.0 - (age / 4.0))
                    label = cached_label
                    confidence = max(0.4, min(0.95, cached_confidence * decay))
                    score = self._label_to_distress(label)
                else:
                    label = EmotionLabel.neutral
                    confidence = 0.45
                    score = self._label_to_distress(label)
            else:
                label = EmotionLabel.neutral
                confidence = 0.45
                score = self._label_to_distress(label)
        else:
            label, confidence = face
            score = self._label_to_distress(label)
        prev_ema = self._face_distress_ema_by_patient.get(patient_id, score)
        ema = (0.65 * prev_ema) + (0.35 * score)
        self._face_distress_ema_by_patient[patient_id] = ema
        score = max(0.0, min(1.0, ema))
        label = self._score_to_label(score)
        self._latest_face_by_patient[patient_id] = (label, confidence, datetime.utcnow())
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
        memory_blob = self._json_for_longterm_memory(session, summary_dict)
        self._memories.append(patient_id, memory_blob)
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
            face_result = self._infer_face_emotion_from_frame(payload.face_frame_base64)
            if face_result is not None:
                self._latest_face_by_patient[payload.patient_id] = (
                    face_result[0],
                    face_result[1],
                    datetime.utcnow(),
                )
        if face_result is None and payload.face_emotion and payload.face_confidence is not None:
            face_result = (payload.face_emotion, payload.face_confidence)
            self._latest_face_by_patient[payload.patient_id] = (
                face_result[0],
                face_result[1],
                datetime.utcnow(),
            )
        if face_result is None:
            cached_face = self._latest_face_by_patient.get(payload.patient_id)
            if cached_face is not None:
                label, confidence, observed_at = cached_face
                # Reuse only recent camera evidence so stale frames do not bias chat.
                age_seconds = (datetime.utcnow() - observed_at).total_seconds()
                if age_seconds <= 6.0:
                    freshness_decay = max(0.55, 1.0 - (age_seconds / 10.0))
                    face_result = (label, max(0.4, min(0.95, confidence * freshness_decay)))
        if face_result is not None:
            entries.append((face_result[0], face_result[1], Modality.face))

        speech_result = None
        if payload.speech_audio_base64:
            speech_result = self._infer_speech_emotion_emotion2vec(payload.speech_audio_base64)
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

    def _run_text_emotion_hf(self) -> bool:
        """Use HF for text emotion if explicitly enabled, or when a remote inference token is configured (no local weights)."""
        if settings.psychology_text_emotion_use_hf:
            return True
        if self._emotion_inference_mode_norm() == "local":
            return False
        return bool((settings.psychology_hf_api_token or "").strip())

    def _text_emotion(self, text: str) -> tuple[EmotionLabel, float, float]:
        # Local transformers pipelines can multi‑GB download; Inference API path uses `PSYCHOLOGY_HF_API_TOKEN` / HF_TOKEN only.
        if self._run_text_emotion_hf():
            hf_text = self._infer_text_emotion_hf(text)
            if hf_text is not None:
                return hf_text
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
        language_detected: str,
        recommendation: str | None,
        technique: str,
        kb_context: list[dict[str, str]] | None,
        memory_items: list[str],
        health_context: dict[str, Any],
        fusion: FusionOutput,
        retrieval_quality: str,
        safety_tier: str,
        session_phase: str,
    ) -> tuple[str, str | None, str, list[str], str]:
        from psychology.llm_therapy import run_therapy_llm

        anomalies: list[str] = []
        if retrieval_quality != "ok":
            anomalies.append(f"retrieval_{retrieval_quality}")
        fusion_summary = (
            f"label={fusion.label.value}, distress={fusion.distress_score}, "
            f"stress={fusion.stress_level}, modalities={[m.value for m in fusion.modalities_used]}, "
            f"session_phase={session_phase}, safety_tier={safety_tier}"
        )
        llm = run_therapy_llm(
            user_text=user_text,
            mental_state=mental_state.value,
            detected_language=language_detected,
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
            if llm.get("safety_mode") == "crisis_guard":
                rec_out = "notify_clinician_immediately"
                anomalies.append("llm_crisis_guard_mode")
            if llm.get("safety_mode") == "elevated_guard":
                anomalies.append("llm_elevated_guard_mode")
            citations = llm.get("citations")
            if not isinstance(citations, list) or len(citations) == 0:
                anomalies.append("llm_missing_citations")
            return llm["reply"].strip(), rec_out, tech_out, anomalies, str(llm.get("safety_mode") or "normal")
        if retrieval_quality != "ok":
            reply = (
                "Thanks for sharing this. I want to support you carefully. "
                "Could you tell me what feels heaviest right now, and what helped even a little in the past?"
            )
            return reply, recommendation, "supportive_reflection", anomalies + ["llm_low_context_fallback"], "low_context"
        tpl = self._therapy_reply_template(user_text, mental_state, recommendation, kb_context)
        fallback_mode = "elevated_guard" if safety_tier == "elevated" else "normal"
        if safety_tier == "elevated":
            tpl = (
                "I can hear this is getting heavier. You're not alone in this moment. "
                + tpl
            )
        return tpl, recommendation, technique, ["llm_parse_fallback"], fallback_mode

    @staticmethod
    def _retrieval_quality(kb_context: list[dict[str, Any]]) -> str:
        if not kb_context:
            return "empty"
        scores = [float(item.get("relevance_score") or 0.0) for item in kb_context]
        best = max(scores) if scores else 0.0
        if best < MIN_RETRIEVAL_SCORE:
            return "low_score"
        return "ok"

    @staticmethod
    def _distress_jump_anomaly(messages: list[TherapyMessageInput], distress_now: float) -> bool:
        for msg in reversed(messages):
            if msg.role != "patient" or not isinstance(msg.fusion_metadata, dict):
                continue
            prev = msg.fusion_metadata.get("distress_score")
            if isinstance(prev, (float, int)):
                return abs(float(prev) - distress_now) >= 0.45
        return False

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

    def _memory_translation_hint(self, patient_blob: str, preferred_language: str) -> str | None:
        det = self._detect_language((patient_blob or "").strip())
        pref = (preferred_language or "en").strip().lower()
        for tag in ("fr", "ar", "darija", "mixed"):
            if tag in {pref, det}:
                return tag
        return None

    def _json_for_longterm_memory(self, session: SessionData | SessionRecord, summary_dict: dict[str, Any]) -> str:
        """Serialize session summary for embedding; translates patient text when session is FR/ar/darija/mixed."""
        preferred = getattr(session, "preferred_language", "en") or "en"
        patient_blob = " ".join(str(m.content) for m in session.messages if m.role == "patient")
        out_dict = summary_dict
        if settings.psychology_memory_translate_to_english:
            hint = self._memory_translation_hint(patient_blob, preferred)
            if hint:
                try:
                    from psychology.memory_translate import translate_summary_strings_for_embedding

                    out_dict = translate_summary_strings_for_embedding(summary_dict, hint=hint)
                except Exception:
                    logger.debug("memory translation failed; storing canonical summary blob", exc_info=True)
                    out_dict = summary_dict
        return json.dumps(out_dict, ensure_ascii=False)

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
            "techniques_used": [
                str((m.fusion_metadata or {}).get("technique_used"))
                for m in session.messages
                if m.role == "assistant"
                and isinstance(m.fusion_metadata, dict)
                and (m.fusion_metadata or {}).get("technique_used")
            ],
            "session_phases_seen": [
                str((m.fusion_metadata or {}).get("session_phase"))
                for m in session.messages
                if m.role == "assistant"
                and isinstance(m.fusion_metadata, dict)
                and (m.fusion_metadata or {}).get("session_phase")
            ],
        }

    @staticmethod
    def _session_phase(messages: list[TherapyMessageInput]) -> str:
        patient_turns = sum(1 for m in messages if m.role == "patient")
        if patient_turns <= 1:
            return "opening_checkin"
        if patient_turns <= 5:
            return "working_phase"
        return "closing_reflection"

    @staticmethod
    def _extract_recent_techniques(messages: list[TherapyMessageInput], limit: int = 5) -> list[str]:
        techniques: list[str] = []
        for msg in reversed(messages):
            if msg.role != "assistant" or not isinstance(msg.fusion_metadata, dict):
                continue
            tech = msg.fusion_metadata.get("technique_used")
            if isinstance(tech, str) and tech.strip():
                techniques.append(tech.strip())
            if len(techniques) >= limit:
                break
        return list(reversed(techniques))

    @staticmethod
    def _progress_technique_for_state(state: MentalState, base_technique: str, prior_techniques: list[str]) -> str:
        arc = {
            MentalState.anxious: ["supportive_reflection", "grounding", "cognitive_restructuring"],
            MentalState.distressed: ["grounding", "problem_solving", "cognitive_restructuring"],
            MentalState.depressed: ["supportive_reflection", "behavioral_activation", "values_microtask"],
            MentalState.neutral: ["supportive_reflection", "strengths_review"],
        }.get(state, [base_technique])
        if base_technique not in arc:
            arc = [base_technique] + arc
        if not prior_techniques:
            return arc[0]
        last = prior_techniques[-1]
        if last not in arc:
            return arc[0]
        idx = arc.index(last)
        return arc[min(idx + 1, len(arc) - 1)]

    @staticmethod
    def _safety_tier(crisis_probability: float) -> str:
        if crisis_probability >= CRISIS_THRESHOLD:
            return "crisis"
        if crisis_probability >= 0.60:
            return "elevated"
        return "normal"

    def _detect_language(self, text: str) -> str:
        lower = text.lower()
        darija_tokens = (
            "chnowa",
            "chnowa",
            "barsha",
            "barcha",
            "3andi",
            "3and",
            "mouch",
            "manich",
            "nheb",
            "naamel",
            "brabi",
            "sbeh",
            "labes",
            "wallahi",
            "yesser",
            "bezef",
            "fama",
            "maaneha",
        )
        if any(token in lower for token in darija_tokens):
            return "darija"
        if any(ch in text for ch in ("3", "5", "7", "9")) and any(token in lower for token in ("ani", "enti", "howa", "hiya", "nheb", "3andi", "mouch")):
            return "darija"
        if any(token in text for token in ("ال", "مرحبا", "أشعر", "انا", "أنت", "كيف")):
            return "ar"
        if any(token in lower for token in ("bonjour", "merci", "salut", "je ", "vous ", "ça", "s'il", "avec")):
            return "fr"
        if any(token in lower for token in ("bonjour", "hello", "مرحبا", "salam")):
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
        base = [0.2, 0.2, 0.2, 0.2, 0.2]
        idx = {
            EmotionLabel.neutral: 0,
            EmotionLabel.happy: 1,
            EmotionLabel.anxious: 2,
            EmotionLabel.distressed: 3,
            EmotionLabel.depressed: 4,
        }[label]
        base[idx] = min(0.9, max(0.35, confidence))
        rest = (1.0 - base[idx]) / 4.0
        for i in range(5):
            if i != idx:
                base[i] = rest
        return base

    @staticmethod
    def _label_to_distress(label: EmotionLabel) -> float:
        return {
            EmotionLabel.neutral: 0.2,
            EmotionLabel.happy: 0.08,
            EmotionLabel.anxious: 0.47,
            EmotionLabel.distressed: 0.7,
            EmotionLabel.depressed: 0.9,
        }[label]

    @staticmethod
    def _score_to_label(score: float) -> EmotionLabel:
        if score <= 0.17:
            return EmotionLabel.happy
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
            for backend in ("opencv", "retinaface", "mtcnn"):
                try:
                    analysis = DeepFace.analyze(
                        img_path=image,
                        actions=["emotion"],
                        enforce_detection=False,
                        detector_backend=backend,
                        silent=True,
                    )
                    if isinstance(analysis, list):
                        analysis = analysis[0]
                    emotion_scores = analysis.get("emotion", {})
                    if not emotion_scores:
                        continue
                    normalized = {
                        str(k).lower(): max(0.0, float(v))
                        for k, v in emotion_scores.items()
                    }
                    total = sum(normalized.values()) or 1.0
                    normalized = {k: v / total for k, v in normalized.items()}
                    grouped = {
                        EmotionLabel.happy: normalized.get("happy", 0.0),
                        EmotionLabel.neutral: normalized.get("neutral", 0.0),
                        EmotionLabel.anxious: normalized.get("fear", 0.0) + (0.55 * normalized.get("surprise", 0.0)),
                        EmotionLabel.distressed: normalized.get("angry", 0.0) + normalized.get("disgust", 0.0) + (0.45 * normalized.get("sad", 0.0)),
                        EmotionLabel.depressed: (0.55 * normalized.get("sad", 0.0)) + (0.25 * normalized.get("fear", 0.0)),
                    }
                    mapped = max(grouped, key=grouped.get)
                    conf = grouped[mapped]
                    return mapped, max(0.42, min(0.99, conf))
                except Exception:
                    continue
            return None
        except ImportError:
            self._deepface_available = False
            return None
        except Exception:
            # Keep detector available on transient frame/runtime errors.
            return None

    def _infer_face_emotion_from_frame(self, frame_base64: str) -> tuple[EmotionLabel, float] | None:
        return self._infer_face_emotion_vit(frame_base64)

    @staticmethod
    def _emotion_inference_mode_norm() -> str:
        m = (settings.psychology_emotion_inference_mode or "auto").strip().lower()
        return m if m in {"auto", "inference_api", "local"} else "auto"

    @classmethod
    def _allow_local_inference_fallback(cls) -> bool:
        return cls._emotion_inference_mode_norm() == "auto"

    def _infer_face_emotion_vit_hf_api(self, image_bytes: bytes) -> tuple[EmotionLabel, float] | None:
        token = (settings.psychology_hf_api_token or "").strip()
        model_id = (
            settings.psychology_face_emotion_model.strip()
            or "mo-thecreator/vit-Facial-Expression-Recognition"
        )
        out = classify_image(token, model_id, image_bytes, settings.psychology_hf_inference_timeout_s)
        if out is None:
            return None
        raw_label, score = out
        mapped = self._map_face_label_generic(raw_label)
        return mapped, max(0.4, min(0.99, float(score)))

    def _infer_face_emotion_vit_local(self, image_bytes: bytes) -> tuple[EmotionLabel, float] | None:
        try:
            from transformers import AutoImageProcessor, AutoModelForImageClassification
            import torch
        except Exception:
            return None
        try:
            if self._hf_face_bundle is None:
                model_id = (
                    settings.psychology_face_emotion_model.strip()
                    or "mo-thecreator/vit-Facial-Expression-Recognition"
                )
                processor = AutoImageProcessor.from_pretrained(model_id)
                model = AutoModelForImageClassification.from_pretrained(model_id)
                model.eval()
                self._hf_face_bundle = (processor, model)
            processor, model = self._hf_face_bundle
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            with torch.no_grad():
                inputs = processor(images=image, return_tensors="pt")
                logits = model(**inputs).logits
                probs = torch.nn.functional.softmax(logits, dim=-1)
                conf, idx = torch.max(probs, dim=-1)
            raw_label = str(model.config.id2label.get(int(idx.item()), "neutral"))
            mapped = self._map_face_label_generic(raw_label)
            confidence = float(conf.item())
            return mapped, max(0.4, min(0.99, confidence))
        except Exception:
            return None

    def _infer_face_emotion_vit(self, frame_base64: str) -> tuple[EmotionLabel, float] | None:
        image_bytes = self._safe_b64decode(frame_base64)
        if image_bytes is None:
            return None
        mode = self._emotion_inference_mode_norm()
        token = (settings.psychology_hf_api_token or "").strip()
        if mode == "inference_api" and not token:
            logger.warning("psychology face emotion: inference_api mode but HF token missing")
            return None
        if mode != "local" and token:
            api_out = self._infer_face_emotion_vit_hf_api(image_bytes)
            if api_out is not None:
                return api_out
            if mode == "inference_api":
                return None
        if mode == "local" or self._allow_local_inference_fallback():
            return self._infer_face_emotion_vit_local(image_bytes)
        return None

    def _infer_speech_emotion_hf_api(self, wav_bytes: bytes) -> tuple[EmotionLabel, float] | None:
        hf_audio_model = (settings.psychology_speech_emotion_hf_model or "").strip()
        if not hf_audio_model:
            return None
        token = (settings.psychology_hf_api_token or "").strip()
        out = classify_audio(token, hf_audio_model, wav_bytes, settings.psychology_hf_inference_timeout_s)
        if out is None:
            return None
        raw_label, confidence = out
        mapped = self._map_speech_label_generic(raw_label)
        return mapped, max(0.35, min(0.99, float(confidence)))

    def _infer_speech_emotion_emotion2vec_local(self, wav_bytes: bytes) -> tuple[EmotionLabel, float] | None:
        try:
            from modelscope.pipelines import pipeline as ms_pipeline
            from modelscope.utils.constant import Tasks
        except Exception:
            return None
        try:
            if self._emotion2vec_infer is None:
                model_id = settings.psychology_speech_emotion_model.strip() or "iic/emotion2vec_plus_large"
                self._emotion2vec_infer = ms_pipeline(task=Tasks.emotion_recognition, model=model_id)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                tmp.write(wav_bytes)
                tmp.flush()
                raw = self._emotion2vec_infer(tmp.name, granularity="utterance", extract_embedding=False)
            raw_label, confidence = self._extract_emotion2vec_result(raw)
            mapped = self._map_speech_label_generic(raw_label)
            return mapped, max(0.35, min(0.99, confidence))
        except Exception:
            return None

    def _infer_speech_emotion_emotion2vec(self, audio_base64: str) -> tuple[EmotionLabel, float] | None:
        wav_bytes = self._safe_b64decode(audio_base64)
        if wav_bytes is None:
            return None
        mode = self._emotion_inference_mode_norm()
        token = (settings.psychology_hf_api_token or "").strip()
        hf_audio_model = (settings.psychology_speech_emotion_hf_model or "").strip()
        if mode == "inference_api" and not token:
            logger.warning("psychology speech emotion: inference_api mode but HF token missing")
            return None
        if mode == "inference_api" and not hf_audio_model:
            logger.warning(
                "psychology speech emotion: inference_api mode requires PSYCHOLOGY_SPEECH_EMOTION_HF_MODEL "
                "(Inference API `audio_classification` repo id)"
            )
            return None
        if (
            mode != "local"
            and token
            and hf_audio_model
        ):
            api_out = self._infer_speech_emotion_hf_api(wav_bytes)
            if api_out is not None:
                return api_out
            if mode == "inference_api":
                return None
        if mode == "local" or self._allow_local_inference_fallback():
            local_out = self._infer_speech_emotion_emotion2vec_local(wav_bytes)
            if local_out is not None:
                return local_out
        return None

    def _infer_text_emotion_hf_api(self, text: str) -> tuple[EmotionLabel, float, float] | None:
        token = (settings.psychology_hf_api_token or "").strip()
        model_id = (
            settings.psychology_text_emotion_model.strip()
            or "j-hartmann/emotion-english-distilroberta-base"
        )
        out = classify_text(token, model_id, text, settings.psychology_hf_inference_timeout_s)
        if out is None:
            return None
        raw_label, score = out
        mapped = self._map_text_label_generic(raw_label)
        sentiment = {
            EmotionLabel.happy: 0.6,
            EmotionLabel.neutral: 0.2,
            EmotionLabel.anxious: -0.4,
            EmotionLabel.distressed: -0.55,
            EmotionLabel.depressed: -0.8,
        }[mapped]
        return mapped, max(0.35, min(0.99, float(score))), sentiment

    def _infer_text_emotion_hf_local(self, text: str) -> tuple[EmotionLabel, float, float] | None:
        try:
            from transformers import pipeline
        except Exception:
            return None
        try:
            if self._hf_text_classifier is None:
                model_id = (
                    settings.psychology_text_emotion_model.strip()
                    or "j-hartmann/emotion-english-distilroberta-base"
                )
                self._hf_text_classifier = pipeline(
                    "text-classification",
                    model=model_id,
                    tokenizer=model_id,
                    top_k=1,
                    truncation=True,
                )
            result = self._hf_text_classifier(text)
            if not result:
                return None
            first = result[0]
            if isinstance(first, list) and first:
                first = first[0]
            raw_label = str(first.get("label", "neutral"))
            score = float(first.get("score", 0.6))
            mapped = self._map_text_label_generic(raw_label)
            sentiment = {
                EmotionLabel.happy: 0.6,
                EmotionLabel.neutral: 0.2,
                EmotionLabel.anxious: -0.4,
                EmotionLabel.distressed: -0.55,
                EmotionLabel.depressed: -0.8,
            }[mapped]
            return mapped, max(0.35, min(0.99, score)), sentiment
        except Exception:
            return None

    def _infer_text_emotion_hf(self, text: str) -> tuple[EmotionLabel, float, float] | None:
        mode = self._emotion_inference_mode_norm()
        token = (settings.psychology_hf_api_token or "").strip()
        if mode == "inference_api" and not token:
            logger.warning("psychology text emotion: inference_api mode but HF token missing")
            return None
        if mode != "local" and token:
            api_out = self._infer_text_emotion_hf_api(text)
            if api_out is not None:
                return api_out
            if mode == "inference_api":
                return None
        if mode == "local" or self._allow_local_inference_fallback():
            return self._infer_text_emotion_hf_local(text)
        return None

    @staticmethod
    def _safe_b64decode(raw: str) -> bytes | None:
        try:
            payload = raw.split(",", 1)[1] if "," in raw else raw
            return base64.b64decode(payload, validate=False)
        except (ValueError, binascii.Error):
            return None

    @staticmethod
    def _extract_emotion2vec_result(raw: Any) -> tuple[str, float]:
        best_label = "neutral"
        best_score = 0.6

        def visit(node: Any) -> None:
            nonlocal best_label, best_score
            if isinstance(node, dict):
                lbl = node.get("label") or node.get("emotion") or node.get("text")
                scr = node.get("score") or node.get("confidence") or node.get("prob")
                if isinstance(lbl, str):
                    score_val = float(scr) if isinstance(scr, (int, float)) else 0.6
                    if score_val >= best_score:
                        best_label = lbl
                        best_score = score_val
                for v in node.values():
                    visit(v)
                return
            if isinstance(node, list):
                for item in node:
                    visit(item)

        visit(raw)
        return best_label, best_score

    @staticmethod
    def _map_face_label_generic(label: str) -> EmotionLabel:
        lower = label.lower()
        if "happy" in lower or "joy" in lower:
            return EmotionLabel.happy
        if "neutral" in lower or "calm" in lower:
            return EmotionLabel.neutral
        if "sad" in lower or "depress" in lower:
            return EmotionLabel.depressed
        if "fear" in lower or "anx" in lower or "surprise" in lower:
            return EmotionLabel.anxious
        if "ang" in lower or "disgust" in lower or "frustrat" in lower:
            return EmotionLabel.distressed
        return EmotionLabel.neutral

    @staticmethod
    def _map_speech_label_generic(label: str) -> EmotionLabel:
        lower = label.lower()
        if "happy" in lower or "joy" in lower or "excit" in lower:
            return EmotionLabel.happy
        if "neutral" in lower or "calm" in lower:
            return EmotionLabel.neutral
        if "sad" in lower or "depress" in lower:
            return EmotionLabel.depressed
        if "fear" in lower or "anx" in lower:
            return EmotionLabel.anxious
        if "ang" in lower or "frustrat" in lower or "disgust" in lower:
            return EmotionLabel.distressed
        return EmotionLabel.anxious

    @staticmethod
    def _map_text_label_generic(label: str) -> EmotionLabel:
        lower = label.lower()
        if "joy" in lower or "happy" in lower or "optim" in lower:
            return EmotionLabel.happy
        if "neutral" in lower:
            return EmotionLabel.neutral
        if "sad" in lower or "depress" in lower:
            return EmotionLabel.depressed
        if "fear" in lower or "worry" in lower or "anx" in lower:
            return EmotionLabel.anxious
        if "anger" in lower or "angry" in lower or "stress" in lower or "distress" in lower:
            return EmotionLabel.distressed
        return EmotionLabel.neutral

    def warm_heavy_psychology_caches(self) -> None:
        """Load local text-emotion transformers before the first chat when that path may run."""
        mode = self._emotion_inference_mode_norm()
        token = bool((settings.psychology_hf_api_token or "").strip())
        if mode == "inference_api":
            return
        if mode == "auto" and not token and not settings.psychology_text_emotion_use_hf:
            return
        if mode == "local" and not settings.psychology_text_emotion_use_hf:
            return
        try:
            self._infer_text_emotion_hf_local("warmup.")
        except Exception:
            logger.debug("psychology local text classifier warm skipped", exc_info=True)


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
