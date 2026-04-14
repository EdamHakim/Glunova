from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from clinic.router import router as clinic_router
from kids.router import router as kids_router
from nutrition.router import router as nutrition_router
from psychology.router import router as psychology_router
from screening.router import router as screening_router

app = FastAPI(title="Glunova AI Engine")

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
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
