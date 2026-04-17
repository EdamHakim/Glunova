import logging
import os

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

from screening.model_bootstrap import ensure_tongue_checkpoint

# Run before screening (and config) imports resolve PT_MODEL_PATH.
ensure_tongue_checkpoint()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from clinic.router import router as clinic_router
from kids.router import router as kids_router
from nutrition.router import router as nutrition_router
from psychology.router import router as psychology_router
from screening.router import router as screening_router

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
app.include_router(clinic_router)
app.include_router(psychology_router)
app.include_router(nutrition_router)
app.include_router(kids_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "fastapi_ai"}
