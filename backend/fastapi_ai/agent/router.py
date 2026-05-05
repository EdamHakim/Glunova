from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from agent.orchestrator import run_coordination
from agent.schemas import (
    CoordinateAllRequest,
    CoordinateAllResponse,
    CoordinateRequest,
    CoordinateResponse,
)
from core.db import get_connection_pool

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/coordinate", response_model=CoordinateResponse)
async def coordinate_patient(req: CoordinateRequest) -> CoordinateResponse:
    """Run the care coordination agent for a single patient."""
    try:
        return await run_coordination(req.patient_id, req.trigger)
    except Exception as exc:
        logger.error("[AgentRouter] patient=%s error=%s", req.patient_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/coordinate/all", response_model=CoordinateAllResponse)
async def coordinate_all(req: CoordinateAllRequest) -> CoordinateAllResponse:
    """Run coordination for all patients with active alerts in the last 24 hours (nightly batch)."""
    pool = get_connection_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database pool unavailable")

    patient_ids: list[int] = []
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT patient_id
                    FROM monitoring_healthalert
                    WHERE status = 'active'
                      AND triggered_at >= NOW() - INTERVAL '24 hours'
                    ORDER BY patient_id
                    """
                )
                patient_ids = [row[0] for row in cur.fetchall()]
    except Exception as exc:
        logger.error("[AgentRouter/all] DB query failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    total_dispatched = 0
    errors: list[str] = []

    for pid in patient_ids:
        try:
            result = await run_coordination(pid, req.trigger)
            total_dispatched += result.messages_dispatched
        except Exception as exc:
            msg = f"patient={pid}: {exc}"
            logger.error("[AgentRouter/all] %s", msg)
            errors.append(msg)

    return CoordinateAllResponse(
        patients_processed=len(patient_ids),
        messages_dispatched=total_dispatched,
        errors=errors,
    )
