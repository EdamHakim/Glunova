from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from core.rbac import require_roles
from psychology.schemas import (
    CrisisEventsResponse,
    EmotionFrameRequest,
    EmotionFrameResponse,
    MessageRequest,
    MessageResponse,
    SessionEndRequest,
    SessionEndResponse,
    SessionSnapshotResponse,
    SessionStartRequest,
    SessionStartResponse,
    TrendResponse,
)
from psychology.knowledge_ingestion import build_ingestion_manifest
from psychology.service import PsychologyService

router = APIRouter(prefix="/psychology", tags=["psychology"])
service = PsychologyService()


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
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            frame = data.get("frame_base64", "")
            inferred = service.detect_emotion_frame(patient_id, frame)
            await websocket.send_json(
                {
                    "patient_id": patient_id,
                    "label": inferred.label,
                    "confidence": inferred.confidence,
                    "distress_score": inferred.distress_score,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            await asyncio.sleep(0.5)  # 2 fps server-side cadence.
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
    _claims: dict = Depends(require_roles("patient", "doctor")),
) -> SessionEndResponse:
    try:
        return service.end_session(payload.session_id, payload.patient_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.get("/knowledge/sources")
def knowledge_sources(
    _claims: dict = Depends(require_roles("doctor")),
) -> dict:
    return {"items": build_ingestion_manifest()}
