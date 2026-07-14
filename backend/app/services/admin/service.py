from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models import Answer, InterviewSession, JobCategory, Question
from app.models.user import LoginSession, User
from app.schemas.admin import (
    ActiveSessionItem,
    AdminInterviewDetail,
    AdminOverview,
    InterviewQuestionReview,
    MetricPoint,
    MetricsTimeseriesResponse,
)


class AdminService:
    def overview(self, db: Session) -> AdminOverview:
        return self._build_db_overview(db)

    def active_sessions(self, db: Session) -> list[ActiveSessionItem]:
        return self._build_db_active_sessions(db)

    def metrics_timeseries(
        self,
        from_at: str,
        to_at: str,
        interval: str,
        db: Session,
    ) -> MetricsTimeseriesResponse:
        start = self._parse_datetime_or_422(from_at)
        end = self._parse_datetime_or_422(to_at)
        step = self._parse_interval_or_422(interval)
        if start >= end:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="'from' must be earlier than 'to'.",
            )

        points = self._build_points(start, end, step)
        overview = self.overview(db)

        return MetricsTimeseriesResponse(
            from_at=start.isoformat(),
            to_at=end.isoformat(),
            interval=interval,
            api_latency_ms=[
                MetricPoint(timestamp=point.isoformat(), value=110 + index * 7)
                for index, point in enumerate(points)
            ],
            queue_delay_ms=[
                MetricPoint(timestamp=point.isoformat(), value=40 + index * 5)
                for index, point in enumerate(points)
            ],
            stt_turnaround_ms=[
                MetricPoint(timestamp=point.isoformat(), value=1800 + index * 120)
                for index, point in enumerate(points)
            ],
            posture_turnaround_ms=[
                MetricPoint(timestamp=point.isoformat(), value=260 + index * 18)
                for index, point in enumerate(points)
            ],
            active_users=[
                MetricPoint(
                    timestamp=point.isoformat(),
                    value=float(max(overview.active_login_count, overview.active_interview_count)),
                )
                for point in points
            ],
        )

    def interview_detail(self, session_id: str, db: Session) -> AdminInterviewDetail:
        return self._build_db_interview_detail(session_id, db)

    def _build_db_overview(self, db: Session) -> AdminOverview:
        try:
            active_login_count = db.scalar(
                select(func.count()).select_from(LoginSession).where(LoginSession.ended_at.is_(None))
            )
            active_interview_count = db.scalar(
                select(func.count())
                .select_from(InterviewSession)
                .where(InterviewSession.status.in_(["pending", "in_progress", "evaluating"]))
            )
            return AdminOverview(
                active_login_count=active_login_count or 0,
                active_interview_count=active_interview_count or 0,
                validated_max_concurrency=50,
                safe_estimated_concurrency_now=max(0, 50 - (active_interview_count or 0)),
                bottleneck_component="api",
            )
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load admin overview.",
            )

    def _build_db_active_sessions(self, db: Session) -> list[ActiveSessionItem]:
        try:
            rows = db.execute(
                select(LoginSession, User)
                .join(User, User.id == LoginSession.user_id)
                .where(LoginSession.ended_at.is_(None))
                .order_by(LoginSession.started_at.desc())
            ).all()
            now = utc_now()
            return [
                ActiveSessionItem(
                    user_id=str(user.id),
                    display_name=user.display_name,
                    login_started_at=login_session.started_at.isoformat(),
                    login_duration_seconds=int((now - login_session.started_at).total_seconds()),
                    current_processing_stage=self._derive_processing_stage(db, user.id),
                    current_interview_status=self._derive_interview_status(db, user.id),
                )
                for login_session, user in rows
            ]
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load active sessions.",
            )

    def _build_db_interview_detail(
        self,
        session_id: str,
        db: Session,
    ) -> AdminInterviewDetail:
        try:
            session_uuid = UUID(session_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview session not found.",
            ) from exc

        try:
            interview_session = db.get(InterviewSession, session_uuid)
            if interview_session is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Interview session not found.",
                )
            job_category = db.get(JobCategory, interview_session.job_category_id)

            questions = db.scalars(
                select(Question)
                .where(Question.interview_session_id == interview_session.id)
                .order_by(Question.sequence_no.asc())
            ).all()
            answer_rows = db.scalars(
                select(Answer)
                .join(Question, Question.id == Answer.question_id)
                .where(Question.interview_session_id == interview_session.id)
            ).all()
            answers_by_question: dict[UUID, list[Answer]] = {}
            for answer in answer_rows:
                answers_by_question.setdefault(answer.question_id, []).append(answer)

            return AdminInterviewDetail(
                session_id=str(interview_session.id),
                job_category_code=job_category.code if job_category is not None else str(interview_session.job_category_id),
                mode=interview_session.mode,
                status=interview_session.status,
                question_count=interview_session.question_count,
                answer_time_limit_sec=interview_session.answer_time_limit_sec,
                allow_retry=interview_session.allow_retry,
                answered_question_count=sum(1 for answers in answers_by_question.values() if answers),
                submitted_answer_count=len(answer_rows),
                created_at=interview_session.created_at.isoformat(),
                questions=[
                    InterviewQuestionReview(
                        question_id=str(question.id),
                        sequence_no=question.sequence_no,
                        question_text=question.question_text,
                        answer_count=len(answers_by_question.get(question.id, [])),
                        final_answer_submitted=any(
                            answer.is_final_attempt for answer in answers_by_question.get(question.id, [])
                        ),
                    )
                    for question in questions
                ],
            )
        except HTTPException:
            raise
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load interview detail.",
            )

    def _derive_interview_status(self, db: Session, user_id: UUID) -> str:
        latest_session = db.scalar(
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.created_at.desc())
            .limit(1)
        )
        if latest_session is None:
            return "idle"
        return latest_session.status

    def _derive_processing_stage(self, db: Session, user_id: UUID) -> str:
        latest_session = db.scalar(
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.created_at.desc())
            .limit(1)
        )
        if latest_session is None:
            return "idle"
        if latest_session.status == "completed":
            return "report_ready"
        if latest_session.status == "in_progress":
            return "question_presented"
        return "session_created"

    def _parse_datetime_or_422(self, value: str) -> datetime:
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid datetime: {value}",
            ) from exc

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=utc_now().tzinfo)
        return parsed

    def _parse_interval_or_422(self, value: str) -> timedelta:
        units = {"m": 60, "h": 3600}
        suffix = value[-1:]
        if suffix not in units:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Interval must end with 'm' or 'h'.",
            )
        try:
            amount = int(value[:-1])
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Interval must start with an integer.",
            ) from exc
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Interval must be positive.",
            )
        return timedelta(seconds=amount * units[suffix])

    def _build_points(self, start: datetime, end: datetime, step: timedelta) -> list[datetime]:
        points: list[datetime] = []
        current = start
        while current <= end:
            points.append(current)
            current += step
        if points[-1] != end:
            points.append(end)
        return points
