from pathlib import Path

from dotenv import load_dotenv

# Same file as Django: backend/.env (Docker Compose also passes it via env_file).
_backend_root = Path(__file__).resolve().parent.parent
load_dotenv(_backend_root / ".env", override=True)

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from clinic.router import router as clinic_router
from kids.router import router as kids_router
from nutrition.router import router as nutrition_router
from psychology.router import router as psychology_router
from screening.router import router as screening_router
from extraction.router import router as extraction_router

app = FastAPI(title="Glunova AI Engine")

raw_origins = os.getenv("FRONTEND_ORIGINS", "")
frontend_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
legacy_origin = os.getenv("FRONTEND_ORIGIN", "").strip()
if legacy_origin:
    frontend_origins.append(legacy_origin)
if not frontend_origins:
    frontend_origins = ["http://localhost:3000", "http://172.19.32.1:3000"]
frontend_origins = list(dict.fromkeys(frontend_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(screening_router)
app.include_router(extraction_router)
app.include_router(clinic_router)
app.include_router(psychology_router)
app.include_router(nutrition_router)
app.include_router(kids_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "fastapi_ai"}
