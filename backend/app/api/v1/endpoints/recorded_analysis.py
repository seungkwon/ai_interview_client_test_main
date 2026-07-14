from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.deps import get_db
from app.schemas.auth import UserProfile
from app.schemas.recorded_analysis import (
    RecordedAnalysisCreateResponse,
    RecordedAnalysisStatusResponse,
)
from app.services.recorded_analysis_service import RecordedAnalysisService

router = APIRouter()
recorded_analysis_service = RecordedAnalysisService()


@router.post("", response_model=RecordedAnalysisCreateResponse)
async def create_recorded_analysis(
    file: UploadFile = File(...),
    duration_sec: int = Form(...),
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecordedAnalysisCreateResponse:
    return recorded_analysis_service.create_analysis(
        filename=file.filename or "recorded.bin",
        content_type=file.content_type or "application/octet-stream",
        duration_sec=duration_sec,
        user_id=current_user.id,
        db=db,
    )


@router.get("/{session_id}", response_model=RecordedAnalysisStatusResponse)
async def get_recorded_analysis(
    session_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecordedAnalysisStatusResponse:
    return recorded_analysis_service.get_analysis(session_id, current_user.id, db)
