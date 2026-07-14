from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    interviews,
    job_categories,
    posture,
    recorded_analysis,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(job_categories.router, prefix="/job-categories", tags=["job-categories"])
api_router.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(posture.router, prefix="/posture", tags=["posture"])
api_router.include_router(
    recorded_analysis.router,
    prefix="/recorded-analysis",
    tags=["recorded-analysis"],
)
