from fastapi import FastAPI

from clinic.router import router as clinic_router
from kids.router import router as kids_router
from nutrition.router import router as nutrition_router
from psychology.router import router as psychology_router
from screening.router import router as screening_router

app = FastAPI(title="Glunova AI Engine")

app.include_router(screening_router)
app.include_router(clinic_router)
app.include_router(psychology_router)
app.include_router(nutrition_router)
app.include_router(kids_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "fastapi_ai"}
