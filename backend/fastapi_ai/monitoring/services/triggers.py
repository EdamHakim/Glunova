"""Glue for inference routes: persist a screening result then refresh the tier.

Each inference route (DR, Thermal, Tongue) calls record_screening_and_refresh()
right before returning the response. Both steps are wrapped in try/except so
the caller's response is never blocked by DB or fusion failures.
"""
from __future__ import annotations

import logging

from monitoring.services.fusion_service import get_fusion_service
from monitoring.services.persistence import persist_screening_result

logger = logging.getLogger(__name__)


def record_screening_and_refresh(
    user_id: int,
    modality: str,
    score: float,
    risk_label: str,
    model_version: str,
    metadata: dict | None = None,
) -> None:
    try:
        sr_id = persist_screening_result(
            user_id=user_id,
            modality=modality,
            score=score,
            risk_label=risk_label,
            model_version=model_version,
            metadata=metadata,
        )
    except Exception:
        logger.exception("persist_screening_result failed for patient %s (%s)", user_id, modality)
        return

    if sr_id is None:
        logger.warning(
            "ScreeningResult not persisted for patient %s (%s) — DB pool unavailable",
            user_id, modality,
        )
        return

    try:
        get_fusion_service().refresh_tier_for_patient(user_id)
    except Exception:
        logger.exception("Fusion refresh after %s persist failed for patient %s", modality, user_id)
