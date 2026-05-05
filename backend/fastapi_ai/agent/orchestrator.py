"""Orchestrator — pure Python A2A coordinator.

Sequence:
  1. Open one MCP session (stdio subprocess of mcp_server.py).
  2. ContextAgent  — fan-out MCP tool calls → PatientContext.
  3. RiskReasonerAgent — Groq LLM reasoning → ReasoningOutput.
  4. DispatchAgent — Groq LLM + MCP dispatch → DispatchResult.
  5. Close MCP session.

Cooldown: skip if the patient's wellness plan was stamped by the agent
within the last 30 minutes (prevents burst alert duplicates).
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent.agents import context_agent, dispatch_agent, risk_reasoner_agent
from agent.schemas import CoordinateResponse

logger = logging.getLogger(__name__)

_MCP_SERVER = Path(__file__).parent / "mcp_server.py"
_COOLDOWN_MINUTES = 30


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=[str(_MCP_SERVER)],
    )


def _is_cooled_down(context) -> tuple[bool, str]:
    """Return (should_run, skip_reason). Checks last_agent_run in wellness plan snapshot."""
    try:
        plan = (context.nutrition or {}).get("plan") or {}
        last_run_str = plan.get("last_agent_run")
        if not last_run_str:
            return True, ""
        last_run = datetime.fromisoformat(last_run_str)
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last_run < timedelta(minutes=_COOLDOWN_MINUTES):
            return False, f"cooldown: last run {last_run_str}"
    except Exception:
        pass
    return True, ""


async def run_coordination(patient_id: int, trigger: str) -> CoordinateResponse:
    logger.info("[Orchestrator] START patient=%s trigger=%s", patient_id, trigger)

    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ── Step 1: gather context ────────────────────────────────────────
            ctx = await context_agent.run(patient_id, session)

            # ── Step 2: cooldown guard ────────────────────────────────────────
            # CRITICAL alerts always bypass the cooldown.
            risk_tier = (ctx.monitoring.get("risk") or {}).get("tier", "LOW")
            if trigger != "alert" or risk_tier != "CRITICAL":
                should_run, reason = _is_cooled_down(ctx)
                if not should_run:
                    logger.info("[Orchestrator] SKIPPED patient=%s reason=%s", patient_id, reason)
                    return CoordinateResponse(
                        status="skipped",
                        patient_id=patient_id,
                        messages_dispatched=0,
                        trigger=trigger,
                        risk_tier=risk_tier,
                        skipped_reason=reason,
                    )

            # ── Step 3: reason ────────────────────────────────────────────────
            reasoning = await risk_reasoner_agent.run(ctx)

            # Clinical triggers (manual, nutrition_skip, crisis) always dispatch.
            _force_dispatch = {"manual", "nutrition_skip", "crisis"}
            if not reasoning.should_dispatch and trigger not in _force_dispatch:
                logger.info(
                    "[Orchestrator] NO DISPATCH patient=%s tier=%s",
                    patient_id, reasoning.risk_tier,
                )
                return CoordinateResponse(
                    status="ok",
                    patient_id=patient_id,
                    messages_dispatched=0,
                    trigger=trigger,
                    risk_tier=reasoning.risk_tier,
                    skipped_reason="signals within normal range",
                )

            # ── Step 4: dispatch ──────────────────────────────────────────────
            result = await dispatch_agent.run(reasoning, ctx.care_team, session)

    logger.info(
        "[Orchestrator] DONE patient=%s dispatched=%s recipients=%s",
        patient_id, result.messages_dispatched, result.recipients,
    )
    return CoordinateResponse(
        status="ok",
        patient_id=patient_id,
        messages_dispatched=result.messages_dispatched,
        trigger=trigger,
        risk_tier=reasoning.risk_tier,
    )
