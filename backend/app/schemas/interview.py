from typing import Any, Optional
from pydantic import BaseModel, Field


class CreateInterviewRequest(BaseModel):
    job_category_code: str
    mode: str = Field(pattern="^(live|recorded)$")
    question_count: int = Field(default=5, ge=1, le=5)
    answer_time_limit_sec: int = Field(default=60, ge=10, le=60)
    allow_retry: bool = True


class InterviewSessionResponse(BaseModel):
    session_id: str
    status: str
    question_count: int
    answer_time_limit_sec: int
    allow_retry: bool


class InterviewQuestion(BaseModel):
    id: str
    sequence_no: int
    question_text: str


class CurrentQuestionResponse(BaseModel):
    session_id: str
    question: InterviewQuestion


class StartInterviewResponse(BaseModel):
    session_id: str
    status: str
    question: InterviewQuestion


class SubmitTextAnswerRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    attempt_no: int = Field(ge=1, le=3)
    is_final_attempt: bool = True


class SubmitAnswerResponse(BaseModel):
    session_id: str
    question_id: str
    attempt_no: int
    accepted: bool
    queued_stt: bool
    queued_evaluation: bool
    next_action: str


class NextQuestionResponse(BaseModel):
    session_id: str
    status: str
    question: Optional[InterviewQuestion] = None
    report_ready: bool = False


class InterviewReportResponse(BaseModel):
    session_id: str
    status: str
    report: Optional[dict[str, Any]]
