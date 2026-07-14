from pydantic import BaseModel


class AdminOverview(BaseModel):
    active_login_count: int
    active_interview_count: int
    validated_max_concurrency: int
    safe_estimated_concurrency_now: int
    bottleneck_component: str


class ActiveSessionItem(BaseModel):
    user_id: str
    display_name: str
    login_started_at: str
    login_duration_seconds: int
    current_processing_stage: str
    current_interview_status: str


class MetricPoint(BaseModel):
    timestamp: str
    value: float


class MetricsTimeseriesResponse(BaseModel):
    from_at: str
    to_at: str
    interval: str
    api_latency_ms: list[MetricPoint]
    queue_delay_ms: list[MetricPoint]
    stt_turnaround_ms: list[MetricPoint]
    posture_turnaround_ms: list[MetricPoint]
    active_users: list[MetricPoint]


class InterviewQuestionReview(BaseModel):
    question_id: str
    sequence_no: int
    question_text: str
    answer_count: int
    final_answer_submitted: bool


class AdminInterviewDetail(BaseModel):
    session_id: str
    job_category_code: str
    mode: str
    status: str
    question_count: int
    answer_time_limit_sec: int
    allow_retry: bool
    answered_question_count: int
    submitted_answer_count: int
    created_at: str
    questions: list[InterviewQuestionReview]
