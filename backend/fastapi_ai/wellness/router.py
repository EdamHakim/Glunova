from __future__ import annotations

import asyncio
from functools import partial

from fastapi import APIRouter, HTTPException

from .weekly_wellness_pipeline import generate_weekly_wellness_plan
from .weekly_wellness_schema import WeeklyWellnessPlanRequest

router = APIRouter(prefix="/wellness", tags=["wellness"])


@router.post("/weekly-plan/generate")
async def generate_plan(req: WeeklyWellnessPlanRequest) -> dict:
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, partial(generate_weekly_wellness_plan, req))
        return result
    except EnvironmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {exc}")


@router.get("/health")
def health() -> dict:
    import os
    return {
        "status": "ok",
        "openai_key_set": bool(os.environ.get("OPENAI_API_KEY")),
    }
