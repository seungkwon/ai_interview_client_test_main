from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260709_0001"
down_revision = None
branch_labels = None
depends_on = None


JOB_CATEGORY_ROWS = [
    {"id": 1, "code": "management_hr", "name_ko": "경영/인사", "sort_order": 1, "is_active": True},
    {"id": 2, "code": "accounting", "name_ko": "회계", "sort_order": 2, "is_active": True},
    {"id": 3, "code": "it", "name_ko": "IT", "sort_order": 3, "is_active": True},
    {"id": 4, "code": "rnd", "name_ko": "R&D", "sort_order": 4, "is_active": True},
    {"id": 5, "code": "manufacturing", "name_ko": "제조", "sort_order": 5, "is_active": True},
    {"id": 6, "code": "distribution", "name_ko": "유통", "sort_order": 6, "is_active": True},
    {"id": 7, "code": "public", "name_ko": "공공", "sort_order": 7, "is_active": True},
    {"id": 8, "code": "general_office", "name_ko": "일반 사무", "sort_order": 8, "is_active": True},
]

DEV_USER_ROW = {
    "id": "00000000-0000-0000-0000-000000000001",
    "email": "admin@example.com",
    "password_hash": "dev-only",
    "display_name": "Developer",
    "role": "admin",
    "is_active": True,
}


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "job_categories",
        sa.Column("id", sa.SmallInteger(), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name_ko", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_job_categories_code", "job_categories", ["code"], unique=True)

    op.create_table(
        "login_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_token_jti", sa.String(length=255), nullable=False),
        sa.Column("client_type", sa.String(length=32), nullable=False, server_default="electron"),
        sa.Column("client_version", sa.String(length=32), nullable=False, server_default="0.1.0"),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_label", sa.String(length=100), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("access_token_jti"),
    )
    op.create_index("ix_login_sessions_user_id", "login_sessions", ["user_id"], unique=False)

    op.create_table(
        "interview_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_category_id", sa.SmallInteger(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("question_count", sa.SmallInteger(), nullable=False, server_default="5"),
        sa.Column("answer_time_limit_sec", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("allow_retry", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("report_status", sa.String(length=32), nullable=False, server_default="not_ready"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["job_category_id"], ["job_categories.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_interview_sessions_user_id", "interview_sessions", ["user_id"], unique=False)

    op.create_table(
        "questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("interview_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_no", sa.SmallInteger(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("llm_prompt_version", sa.String(length=50), nullable=False, server_default="v1"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["interview_session_id"], ["interview_sessions.id"]),
    )
    op.create_index("ix_questions_interview_session_id", "questions", ["interview_session_id"], unique=False)

    op.create_table(
        "answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_type", sa.String(length=32), nullable=False),
        sa.Column("attempt_no", sa.SmallInteger(), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("audio_file_path", sa.String(length=255), nullable=True),
        sa.Column("duration_sec", sa.Numeric(8, 2), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_final_attempt", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
    )
    op.create_index("ix_answers_question_id", "answers", ["question_id"], unique=False)

    op.create_table(
        "speech_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("answer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stt_model", sa.String(length=64), nullable=False),
        sa.Column("stt_latency_ms", sa.Integer(), nullable=False),
        sa.Column("transcript_confidence_note", sa.String(length=255), nullable=True),
        sa.Column("speaking_rate_wpm", sa.Numeric(8, 2), nullable=False),
        sa.Column("pause_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pause_ratio", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("filler_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repetition_score", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.id"]),
        sa.UniqueConstraint("answer_id"),
    )
    op.create_index("ix_speech_metrics_answer_id", "speech_metrics", ["answer_id"], unique=True)

    op.create_table(
        "posture_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("interview_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_mode", sa.String(length=32), nullable=False),
        sa.Column("sample_fps", sa.Numeric(4, 2), nullable=False, server_default="5"),
        sa.Column("shoulder_asymmetry_score", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("torso_tilt_score", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("gaze_away_ratio", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("hand_face_event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("upper_body_motion_score", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("visibility_drop_ratio", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["interview_session_id"], ["interview_sessions.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
    )
    op.create_index("ix_posture_metrics_interview_session_id", "posture_metrics", ["interview_session_id"], unique=False)

    op.create_table(
        "posture_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("interview_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("started_at_ms", sa.Integer(), nullable=False),
        sa.Column("ended_at_ms", sa.Integer(), nullable=False),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["interview_session_id"], ["interview_sessions.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
    )
    op.create_index("ix_posture_events_interview_session_id", "posture_events", ["interview_session_id"], unique=False)

    op.create_table(
        "feedback_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("interview_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("content_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("speech_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("posture_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("strength_summary", sa.Text(), nullable=False),
        sa.Column("improvement_summary", sa.Text(), nullable=False),
        sa.Column("full_report_markdown", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["interview_session_id"], ["interview_sessions.id"]),
        sa.UniqueConstraint("interview_session_id"),
    )
    op.create_index("ix_feedback_reports_interview_session_id", "feedback_reports", ["interview_session_id"], unique=True)

    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("interview_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("current_stage", sa.String(length=64), nullable=False),
        sa.Column("queue_name", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["interview_session_id"], ["interview_sessions.id"]),
    )
    op.create_index("ix_processing_jobs_interview_session_id", "processing_jobs", ["interview_session_id"], unique=False)

    op.create_table(
        "system_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("active_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_interview_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("api_p95_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queue_wait_p95_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stt_avg_turnaround_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("posture_avg_turnaround_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("validated_max_concurrency", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("safe_estimated_concurrency_now", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bottleneck_component", sa.String(length=32), nullable=False),
    )

    users = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("email", sa.String(length=255)),
        sa.column("password_hash", sa.String(length=255)),
        sa.column("display_name", sa.String(length=100)),
        sa.column("role", sa.String(length=32)),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(users, [DEV_USER_ROW])

    job_categories = sa.table(
        "job_categories",
        sa.column("id", sa.SmallInteger()),
        sa.column("code", sa.String(length=50)),
        sa.column("name_ko", sa.String(length=100)),
        sa.column("sort_order", sa.SmallInteger()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(job_categories, JOB_CATEGORY_ROWS)


def downgrade() -> None:
    op.drop_table("system_metrics")
    op.drop_index("ix_processing_jobs_interview_session_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")
    op.drop_index("ix_feedback_reports_interview_session_id", table_name="feedback_reports")
    op.drop_table("feedback_reports")
    op.drop_index("ix_posture_events_interview_session_id", table_name="posture_events")
    op.drop_table("posture_events")
    op.drop_index("ix_posture_metrics_interview_session_id", table_name="posture_metrics")
    op.drop_table("posture_metrics")
    op.drop_index("ix_speech_metrics_answer_id", table_name="speech_metrics")
    op.drop_table("speech_metrics")
    op.drop_index("ix_answers_question_id", table_name="answers")
    op.drop_table("answers")
    op.drop_index("ix_questions_interview_session_id", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_interview_sessions_user_id", table_name="interview_sessions")
    op.drop_table("interview_sessions")
    op.drop_index("ix_login_sessions_user_id", table_name="login_sessions")
    op.drop_table("login_sessions")
    op.drop_index("ix_job_categories_code", table_name="job_categories")
    op.drop_table("job_categories")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
