from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobCategory(Base):
    __tablename__ = "job_categories"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name_ko: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    job_category_id: Mapped[int] = mapped_column(ForeignKey("job_categories.id"))
    mode: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    question_count: Mapped[int] = mapped_column(SmallInteger, default=5)
    answer_time_limit_sec: Mapped[int] = mapped_column(Integer, default=60)
    allow_retry: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    final_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    report_status: Mapped[str] = mapped_column(String(32), default="not_ready")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    interview_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id"), index=True
    )
    sequence_no: Mapped[int] = mapped_column(SmallInteger)
    question_text: Mapped[str] = mapped_column(Text)
    llm_prompt_version: Mapped[str] = mapped_column(String(50), default="v1")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id"), index=True)
    answer_type: Mapped[str] = mapped_column(String(32))
    attempt_no: Mapped[int] = mapped_column(SmallInteger)
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audio_file_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    duration_sec: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_final_attempt: Mapped[bool] = mapped_column(Boolean, default=True)


class SpeechMetric(Base):
    __tablename__ = "speech_metrics"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    answer_id: Mapped[UUID] = mapped_column(ForeignKey("answers.id"), unique=True, index=True)
    stt_model: Mapped[str] = mapped_column(String(64))
    stt_latency_ms: Mapped[int] = mapped_column(Integer)
    transcript_confidence_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    speaking_rate_wpm: Mapped[float] = mapped_column(Numeric(8, 2))
    pause_count: Mapped[int] = mapped_column(Integer, default=0)
    pause_ratio: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    filler_count: Mapped[int] = mapped_column(Integer, default=0)
    repetition_score: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PostureMetric(Base):
    __tablename__ = "posture_metrics"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    interview_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id"),
        index=True,
    )
    question_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("questions.id"), nullable=True)
    source_mode: Mapped[str] = mapped_column(String(32))
    sample_fps: Mapped[float] = mapped_column(Numeric(4, 2), default=5)
    shoulder_asymmetry_score: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    torso_tilt_score: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    gaze_away_ratio: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    hand_face_event_count: Mapped[int] = mapped_column(Integer, default=0)
    upper_body_motion_score: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    visibility_drop_ratio: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PostureEvent(Base):
    __tablename__ = "posture_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    interview_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id"),
        index=True,
    )
    question_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("questions.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    started_at_ms: Mapped[int] = mapped_column(Integer)
    ended_at_ms: Mapped[int] = mapped_column(Integer)
    evidence_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FeedbackReport(Base):
    __tablename__ = "feedback_reports"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    interview_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id"),
        unique=True,
        index=True,
    )
    overall_score: Mapped[float] = mapped_column(Numeric(5, 2))
    content_score: Mapped[float] = mapped_column(Numeric(5, 2))
    speech_score: Mapped[float] = mapped_column(Numeric(5, 2))
    posture_score: Mapped[float] = mapped_column(Numeric(5, 2))
    strength_summary: Mapped[str] = mapped_column(Text)
    improvement_summary: Mapped[str] = mapped_column(Text)
    full_report_markdown: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    interview_session_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("interview_sessions.id"),
        nullable=True,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    current_stage: Mapped[str] = mapped_column(String(64))
    queue_name: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metrics_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    active_login_count: Mapped[int] = mapped_column(Integer, default=0)
    active_interview_count: Mapped[int] = mapped_column(Integer, default=0)
    api_p95_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    queue_wait_p95_ms: Mapped[int] = mapped_column(Integer, default=0)
    stt_avg_turnaround_ms: Mapped[int] = mapped_column(Integer, default=0)
    posture_avg_turnaround_ms: Mapped[int] = mapped_column(Integer, default=0)
    validated_max_concurrency: Mapped[int] = mapped_column(Integer, default=0)
    safe_estimated_concurrency_now: Mapped[int] = mapped_column(Integer, default=0)
    bottleneck_component: Mapped[str] = mapped_column(String(32))
