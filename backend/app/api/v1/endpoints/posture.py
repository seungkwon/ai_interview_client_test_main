from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.deps import get_db
from app.schemas.auth import UserProfile
from app.schemas.posture import (
    PostureFallbackSampleRequest,
    PostureLocalSummaryRequest,
    PostureSubmissionResponse,
)
from app.services.posture_service import PostureService

router = APIRouter()
posture_service = PostureService()


@router.post("/local-summary", response_model=PostureSubmissionResponse)
async def submit_local_summary(
    payload: PostureLocalSummaryRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostureSubmissionResponse:
    return posture_service.submit_local_summary(payload, current_user.id, db)


@router.post("/fallback-samples", response_model=PostureSubmissionResponse)
async def submit_fallback_samples(
    payload: PostureFallbackSampleRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostureSubmissionResponse:
    return posture_service.submit_fallback_samples(payload, current_user.id, db)
