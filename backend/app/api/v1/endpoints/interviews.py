from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.deps import get_db
from app.schemas.auth import UserProfile
from app.schemas.interview import (
    CurrentQuestionResponse,
    CreateInterviewRequest,
    InterviewReportResponse,
    InterviewSessionResponse,
    NextQuestionResponse,
    StartInterviewResponse,
    SubmitAnswerResponse,
    SubmitTextAnswerRequest,
)
from app.services.interview.service import InterviewService

router = APIRouter()
interview_service = InterviewService()


@router.post("", response_model=InterviewSessionResponse)
async def create_interview(
    payload: CreateInterviewRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InterviewSessionResponse:
    return interview_service.create_session(payload, current_user.id, db)


@router.get("/{session_id}", response_model=InterviewSessionResponse)
async def get_interview(
    session_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InterviewSessionResponse:
    return interview_service.get_session(session_id, current_user.id, db)


@router.post("/{session_id}/start", response_model=StartInterviewResponse)
async def start_interview(
    session_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StartInterviewResponse:
    return interview_service.start_session(session_id, current_user.id, db)


@router.get("/{session_id}/questions/current", response_model=CurrentQuestionResponse)
async def get_current_question(
    session_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentQuestionResponse:
    return interview_service.get_current_question(session_id, current_user.id, db)


@router.post(
    "/{session_id}/questions/{question_id}/answers/text",
    response_model=SubmitAnswerResponse,
)
async def submit_text_answer(
    session_id: str,
    question_id: str,
    payload: SubmitTextAnswerRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubmitAnswerResponse:
    return interview_service.submit_text_answer(session_id, question_id, payload, current_user.id, db)


@router.post(
    "/{session_id}/questions/{question_id}/answers/audio",
    response_model=SubmitAnswerResponse,
)
async def submit_audio_answer(
    session_id: str,
    question_id: str,
    file: UploadFile = File(...),
    attempt_no: int = Form(...),
    is_final_attempt: bool = Form(...),
    duration_sec: int = Form(...),
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubmitAnswerResponse:
    return interview_service.submit_audio_answer(
        session_id=session_id,
        question_id=question_id,
        filename=file.filename or "audio.bin",
        content_type=file.content_type or "application/octet-stream",
        attempt_no=attempt_no,
        is_final_attempt=is_final_attempt,
        duration_sec=duration_sec,
        user_id=current_user.id,
        db=db,
    )


@router.post(
    "/{session_id}/questions/{question_id}/next",
    response_model=NextQuestionResponse,
)
async def next_question(
    session_id: str,
    question_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NextQuestionResponse:
    return interview_service.move_to_next_question(session_id, question_id, current_user.id, db)


@router.get("/{session_id}/report", response_model=InterviewReportResponse)
async def get_report(
    session_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InterviewReportResponse:
    return interview_service.get_report(session_id, current_user.id, db)
