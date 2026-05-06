"""ContextAgent — pure Python + MCP.

Calls nutrition, psychology, and care-team MCP tools in parallel and aggregates
results into a PatientContext ready for RiskReasonerAgent (no screening / risk-assessment feeds).
"""

from __future__ import annotations

import asyncio
import json
import logging

from mcp import ClientSession

from agent.schemas import PatientContext

logger = logging.getLogger(__name__)


async def run(patient_id: int, session: ClientSession) -> PatientContext:
    """Fan-out MCP data tools (nutrition, psychology, care team), return PatientContext."""

    nutrition_task, psychology_task, care_team_task = await asyncio.gather(
        session.call_tool("get_nutrition_summary", {"patient_id": patient_id}),
        session.call_tool("get_psychology_state", {"patient_id": patient_id}),
        session.call_tool("get_care_team", {"patient_id": patient_id}),
    )

    def _parse(result) -> dict:
        try:
            text = result.content[0].text if result.content else "{}"
            return json.loads(text)
        except Exception:
            return {}

    nutrition = _parse(nutrition_task)
    psychology = _parse(psychology_task)
    care_team = _parse(care_team_task)

    logger.info(
        "[ContextAgent] patient=%s sessions_7d=%s skipped_sessions=%s",
        patient_id,
        psychology.get("sessions_7d", "?"),
        nutrition.get("skipped_sessions", "?"),
    )

    return PatientContext(
        patient_id=patient_id,
        nutrition=nutrition,
        psychology=psychology,
        care_team=care_team,
    )
