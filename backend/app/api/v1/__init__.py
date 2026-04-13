from fastapi import APIRouter

from app.api.v1 import (
    appointments,
    auth,
    caregivers,
    doctors,
    medical,
    monitoring,
    patients,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(patients.router, prefix="/patients", tags=["patients"])
api_router.include_router(doctors.router, prefix="/doctors", tags=["doctors"])
api_router.include_router(caregivers.router, prefix="/caregivers", tags=["caregivers"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
api_router.include_router(medical.router, prefix="/medical", tags=["medical"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
