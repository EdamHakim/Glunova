from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from core.rbac import require_roles
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
    SessionSnapshotResponse,
    SessionStartRequest,
    SessionStartResponse,
    TrendResponse,
)
from psychology.knowledge_ingestion import build_ingestion_manifest, get_knowledge_base
from psychology.service import create_psychology_service

router = APIRouter(prefix="/psychology", tags=["psychology"])
service = create_psychology_service()
knowledge_base = get_knowledge_base()


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


@router.post("/knowledge/reindex")
def knowledge_reindex(
    _claims: dict = Depends(require_roles("doctor")),
) -> dict:
    count = knowledge_base.reindex_sources()
    return {"indexed_chunks": count, "qdrant_enabled": knowledge_base.enabled}


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


@router.get("/knowledge/search")
def knowledge_search(
    q: str = Query(min_length=2),
    language: str | None = Query(default=None),
    limit: int = Query(default=3, ge=1, le=10),
    _claims: dict = Depends(require_roles("doctor")),
) -> dict:
    items = knowledge_base.search(q, language=language, limit=limit)
    return {"items": items, "qdrant_enabled": knowledge_base.enabled}
