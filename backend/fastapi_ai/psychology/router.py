from __future__ import annotations

import asyncio
from datetime import datetime
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Response, UploadFile, WebSocket, WebSocketDisconnect

from core.config import settings
from core.rbac import require_roles
from core.security import decode_access_token
from psychology.schemas import (
    CrisisAckRequest,
    CrisisEventsResponse,
    EmotionFrameRequest,
    EmotionFrameResponse,
    MessageRequest,
    MessageResponse,
    PhysicianClearGateRequest,
    SessionEndRequest,
    SessionEndResponse,
    SessionHistoryResponse,
    SessionSnapshotResponse,
    SessionStartRequest,
    SessionStartResponse,
    TrendResponse,
    VoiceSynthesizeRequest,
    VoiceTranscribeResponse,
)
from psychology.knowledge_ingestion import build_ingestion_manifest, get_knowledge_base
from psychology.voice_service import (
    ElevenLabsSpeechError,
    GroqSpeechError,
    VoiceConfigurationError,
    synthesize_speech_mp3,
    transcribe_audio_bytes,
)
from psychology.service import create_psychology_service

router = APIRouter(prefix="/psychology", tags=["psychology"])
service = create_psychology_service()
knowledge_base = get_knowledge_base()
logger = logging.getLogger(__name__)


def _assert_session_history_access(claims: dict, patient_id: int) -> None:
    role = str(claims.get("role") or "")
    if role in {"doctor", "caregiver"}:
        return
    if role == "patient":
        try:
            claim_uid = int(claims.get("user_id") or claims.get("sub") or 0)
        except (TypeError, ValueError):
            claim_uid = 0
        if claim_uid != patient_id:
            raise HTTPException(status_code=403, detail="Patients may only view their own session history")
        return
    raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.post("/session/start", response_model=SessionStartResponse)
def start_session(
    payload: SessionStartRequest,
    _claims: dict = Depends(require_roles("patient", "doctor", "caregiver")),
) -> SessionStartResponse:
    return service.start_session(payload.patient_id, payload.preferred_language)


@router.post("/message", response_model=MessageResponse)
def message(
    payload: MessageRequest,
    _claims: dict = Depends(require_roles("patient", "doctor")),
) -> MessageResponse:
    try:
        return service.handle_message(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.post("/emotion/frame", response_model=EmotionFrameResponse)
def emotion_frame(
    payload: EmotionFrameRequest,
    _claims: dict = Depends(require_roles("patient", "doctor")),
) -> EmotionFrameResponse:
    return service.detect_emotion_frame(payload.patient_id, payload.frame_base64)


@router.websocket("/ws/emotion/{patient_id}")
async def emotion_stream(websocket: WebSocket, patient_id: int) -> None:
    token = websocket.query_params.get("token") or websocket.cookies.get("access_token")
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return
    try:
        claims = decode_access_token(token)
    except HTTPException:
        await websocket.close(code=1008, reason="Invalid token")
        return
    role = str(claims.get("role") or "")
    if role not in {"patient", "doctor"}:
        await websocket.close(code=1008, reason="Insufficient role permissions")
        return
    if role == "patient":
        try:
            claim_user_id = int(claims.get("user_id") or claims.get("sub") or 0)
        except (TypeError, ValueError):
            claim_user_id = 0
        if claim_user_id != patient_id:
            await websocket.close(code=1008, reason="Patient stream access denied")
            return
    await websocket.accept()
    try:
        while True:
            try:
                data = await websocket.receive_json()
                frame = data.get("frame_base64", "")
                # Run frame inference off the event loop and bound latency so
                # model cold-start/download does not freeze websocket updates.
                inferred = await asyncio.wait_for(
                    asyncio.to_thread(service.detect_emotion_frame, patient_id, frame),
                    timeout=2.5,
                )
                await websocket.send_json(
                    {
                        "patient_id": patient_id,
                        "label": inferred.label,
                        "confidence": inferred.confidence,
                        "distress_score": inferred.distress_score,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
            except (asyncio.TimeoutError, TimeoutError):
                try:
                    await websocket.send_json(
                        {
                            "patient_id": patient_id,
                            "label": "neutral",
                            "confidence": 0.0,
                            "distress_score": 0.2,
                            "timestamp": datetime.utcnow().isoformat(),
                            "error": "model_loading",
                        }
                    )
                except Exception:
                    break
            except WebSocketDisconnect:
                break
            except Exception as exc:
                # Keep stream alive on per-frame inference or serialization failures.
                logger.warning("emotion_stream frame handling failed for patient_id=%s: %s", patient_id, exc)
                try:
                    await websocket.send_json(
                        {
                            "patient_id": patient_id,
                            "label": "neutral",
                            "confidence": 0.35,
                            "distress_score": 0.2,
                            "timestamp": datetime.utcnow().isoformat(),
                            "error": "frame_processing_failed",
                        }
                    )
                except Exception:
                    break
            await asyncio.sleep(0.25)  # 4 fps server-side cadence.
    except WebSocketDisconnect:
        return


@router.get("/session/{session_id}", response_model=SessionSnapshotResponse)
def get_session(
    session_id: str,
    _claims: dict = Depends(require_roles("patient", "doctor", "caregiver")),
) -> SessionSnapshotResponse:
    try:
        return service.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.get("/sessions/history/{patient_id}", response_model=SessionHistoryResponse)
def session_history(
    patient_id: int,
    limit: int = Query(25, ge=1, le=60),
    claims: dict = Depends(require_roles("patient", "doctor", "caregiver")),
) -> SessionHistoryResponse:
    _assert_session_history_access(claims, patient_id)
    return service.list_session_history(patient_id, limit)


@router.get("/trends/{patient_id}", response_model=TrendResponse)
def trends(
    patient_id: int,
    _claims: dict = Depends(require_roles("patient", "doctor", "caregiver")),
) -> TrendResponse:
    return service.get_trends(patient_id)


@router.get("/crisis/events", response_model=CrisisEventsResponse)
def crisis_events(
    patient_id: int | None = Query(default=None, gt=0),
    _claims: dict = Depends(require_roles("doctor", "caregiver")),
) -> CrisisEventsResponse:
    items = service.list_crisis_events()
    if patient_id is not None:
        items = [item for item in items if item.patient_id == patient_id]
    return CrisisEventsResponse(items=items)


@router.post("/session/end", response_model=SessionEndResponse)
def end_session(
    payload: SessionEndRequest,
    background_tasks: BackgroundTasks,
    _claims: dict = Depends(require_roles("patient", "doctor")),
) -> SessionEndResponse:
    try:
        return service.end_session(payload.session_id, payload.patient_id, background_tasks=background_tasks)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.get("/knowledge/sources")
def knowledge_sources(
    _claims: dict = Depends(require_roles("doctor")),
) -> dict:
    return {"items": build_ingestion_manifest()}


@router.post("/knowledge/reindex")
def knowledge_reindex(
    _claims: dict = Depends(require_roles("doctor")),
) -> dict:
    stats = knowledge_base.reindex_sources()
    return {"qdrant_enabled": knowledge_base.enabled, **stats}


@router.post("/crisis/ack")
def crisis_acknowledge(
    payload: CrisisAckRequest,
    claims: dict = Depends(require_roles("doctor", "caregiver")),
) -> dict:
    patient_filter: int | None = payload.patient_id
    if claims.get("role") == "caregiver" and patient_filter is None:
        raise HTTPException(status_code=400, detail="patient_id required for caregiver acknowledgement")
    ok = service.acknowledge_crisis(payload.event_id, patient_filter)
    if not ok:
        raise HTTPException(status_code=404, detail="Crisis event not found or already acknowledged")
    return {"ok": True}


@router.post("/physician/clear-gate")
def physician_clear_gate(
    payload: PhysicianClearGateRequest,
    _claims: dict = Depends(require_roles("doctor")),
) -> dict:
    service.clear_physician_gate(payload.patient_id)
    return {"ok": True}


@router.post("/voice/transcribe", response_model=VoiceTranscribeResponse)
async def voice_transcribe(
    audio: UploadFile = File(...),
    language_hint: str | None = Form(default=None),
    _claims: dict = Depends(require_roles("patient", "doctor")),
) -> VoiceTranscribeResponse:
    """Groq Whisper STT for Sanadi voice mode (multipart `audio`)."""
    data = await audio.read()
    max_b = settings.psychology_voice_max_upload_bytes
    if len(data) > max_b:
        raise HTTPException(status_code=413, detail=f"audio exceeds maximum size ({max_b} bytes)")
    if not data:
        raise HTTPException(status_code=400, detail="empty audio file")
    name = audio.filename or "recording.webm"
    try:
        text, guessed = transcribe_audio_bytes(data, filename=name, language_hint=language_hint)
    except VoiceConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("voice_transcribe failed: %s", exc)
        raise HTTPException(status_code=502, detail="transcription upstream failed") from exc
    if not text.strip():
        raise HTTPException(status_code=422, detail="no speech detected in audio")
    return VoiceTranscribeResponse(text=text, language_guess=guessed)


@router.post("/voice/synthesize")
def voice_synthesize(
    payload: VoiceSynthesizeRequest,
    _claims: dict = Depends(require_roles("patient", "doctor")),
) -> Response:
    """TTS (ElevenLabs or Groq) for Sanadi replies."""
    try:
        blob, ctype = synthesize_speech_mp3(payload.text, language=payload.language)
    except VoiceConfigurationError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ElevenLabsSpeechError, GroqSpeechError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("voice_synthesize failed: %s", exc)
        raise HTTPException(status_code=502, detail="speech synthesis upstream failed") from exc
    return Response(content=blob, media_type=ctype)


@router.get("/knowledge/search")
def knowledge_search(
    q: str = Query(min_length=2),
    language: str | None = Query(default=None),
    limit: int = Query(default=3, ge=1, le=15),
    source_version: str | None = Query(
        default=None,
        description="When set, only chunks with this payload `source_version` (requires Qdrant payload index).",
    ),
    min_ingested_at: str | None = Query(
        default=None,
        description="ISO-8601 lower bound on `ingested_at` (requires payload index on `ingested_at`).",
    ),
    _claims: dict = Depends(require_roles("doctor")),
) -> dict:
    items = knowledge_base.search(
        q,
        language=language,
        limit=limit,
        source_version=source_version,
        min_ingested_at_iso=min_ingested_at,
    )
    return {"items": items, "qdrant_enabled": knowledge_base.enabled}


@router.get("/rag/health")
def rag_health(
    _claims: dict = Depends(require_roles("doctor")),
) -> dict:
    return knowledge_base.health_status()
