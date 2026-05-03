import asyncio
import json
import os
import shutil
from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException
from .pipeline_nutrition import PipelineNutrition
from .profil_schema import ProfilUtilisateur
from .meal_plan_schema import MealPlanRequest
from .meal_plan_pipeline import generate_meal_plan as _generate_meal_plan

router = APIRouter(prefix="/nutrition", tags=["nutrition"])

# Pipeline instance to be initialized at startup
pipeline: Optional[PipelineNutrition] = None

def get_pipeline():
    global pipeline
    if pipeline is None:
        # Fallback if lifespan didn't run (e.g. testing)
        pipeline = PipelineNutrition()
    return pipeline

@router.post("/analyse")
async def analyse_meal(
    image: UploadFile = File(...),
    profil: str = Form(...),
    _pipeline: PipelineNutrition = Depends(get_pipeline)
):
    """
    Analyzes a food photo and returns a personalized diabetes nutrition report.
    """
    # 1. Validate Profile
    try:
        profil_dict = json.loads(profil)
        profil_obj = ProfilUtilisateur(**profil_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid profile data: {str(e)}")

    # 2. Save temporary image
    temp_dir = "tmp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, image.filename)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    try:
        # 3. Run Pipeline
        rapport = _pipeline.analyser(temp_path, profil_obj.model_dump())
        return rapport
    except Exception as e:
        print(f"Pipeline error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Pipeline failure: {str(e)}")
    finally:
        # 4. Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.post("/meal-plan/generate")
async def generate_meal_plan(request: MealPlanRequest):
    """
    Groq LLM generates a 7-day (or single-day) meal plan with estimated macros.
    Called internally by Django — no user auth needed on this route.

    Runs in a thread pool so the blocking Groq HTTP call does not freeze
    the FastAPI event loop.
    """
    try:
        result = await asyncio.to_thread(_generate_meal_plan, request)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "pipeline_ready": pipeline is not None
    }
