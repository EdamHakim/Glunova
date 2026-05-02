import os
import json
import shutil
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, File, UploadFile, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from .pipeline_nutrition import PipelineNutrition
from .profil_schema import ProfilUtilisateur

# Initialize Pipeline
pipeline = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    pipeline = PipelineNutrition()
    yield
    # Cleanup if needed
    pipeline = None

app = FastAPI(title="Glunova Nutrition AI API", lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/analyse")
async def analyse_meal(
    image: UploadFile = File(...),
    profil: str = Form(...)
):
    """
    POST /analyse
    - Accepts: multipart/form-data with `image` (file) + `profil` (JSON string)
    - Returns: the rapport_final dict as JSON
    """
    if not pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    # 1. Validate profil fields
    try:
        profil_dict = json.loads(profil)
        ProfilUtilisateur(**profil_dict) # Validation check
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid profil data: {str(e)}")

    # 2. Save temporary image
    temp_dir = "tmp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, image.filename)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    try:
        # 3. Call the pipeline
        rapport = pipeline.analyser(temp_path, profil_dict)
        return rapport
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")
    finally:
        # 4. Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.get("/health")
def health():
    return {"status": "ok", "pipeline_ready": pipeline is not None}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
