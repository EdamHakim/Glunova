"""Monitoring router — internal endpoint that triggers v11 fusion + persistence.

NOT user-facing. Called by:
- Django register view after a patient signup (tabular-only fusion)
- FastAPI inference routes after persisting a new screening score (full fusion)

The route is currently open (no auth). For production, protect with a shared
X-Internal-Key header or restrict to localhost via reverse proxy.
"""
from __future__ import annotations

import asyncio
import logging
import threading

from fastapi import APIRouter, HTTPException, status

from monitoring.services.fusion_service import get_fusion_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def _fire_coordination_agent(patient_id: int) -> None:
    """Run the async care coordination agent in a daemon thread (fire-and-forget)."""
    try:
        from agent.orchestrator import run_coordination
        asyncio.run(run_coordination(patient_id, "alert"))
        logger.info("[monitoring.router] Agent coordination completed for patient %s", patient_id)
    except Exception as exc:
        logger.warning("[monitoring.router] Agent coordination failed for patient %s: %s", patient_id, exc)


@router.post(
    "/internal/refresh-tier/{patient_id}",
    summary="Run fusion v11 + persist RiskAssessment + HealthAlert (internal)",
)
def refresh_tier_for_patient(patient_id: int) -> dict:
    if patient_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="patient_id must be a positive integer",
        )
    service = get_fusion_service()
    try:
        result = service.refresh_tier_for_patient(patient_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Fusion refresh failed for patient %s", patient_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fusion refresh failed: {exc}",
        ) from exc

    # Trigger care coordination agent for HIGH or CRITICAL tier (new alert not required).
    if result.get("tier", "").upper() in ("HIGH", "CRITICAL"):
        threading.Thread(
            target=_fire_coordination_agent,
            args=(patient_id,),
            daemon=True,
        ).start()
        logger.info("[monitoring.router] Spawned agent thread for %s patient %s", result.get("tier"), patient_id)

    return result


@router.get(
    "/internal/preview-tier/{patient_id}",
    summary="Run fusion v11 WITHOUT persisting (for debugging)",
)
def preview_tier_for_patient(patient_id: int) -> dict:
    if patient_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="patient_id must be a positive integer",
        )
    service = get_fusion_service()
    try:
        result = service.predict_for_patient(patient_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Fusion preview failed for patient %s", patient_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fusion preview failed: {exc}",
        ) from exc
    return result
