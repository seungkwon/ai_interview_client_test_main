from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models import Answer, FeedbackReport, ProcessingJob
from app.models import InterviewSession as InterviewSessionModel
from app.models import JobCategory, Question
from app.models.user import User
from app.schemas.interview import (
    CurrentQuestionResponse,
    CreateInterviewRequest,
    InterviewQuestion,
    InterviewReportResponse,
    InterviewSessionResponse,
    NextQuestionResponse,
    StartInterviewResponse,
    SubmitAnswerResponse,
    SubmitTextAnswerRequest,
)
from app.services.processing_queue import enqueue_job


QUESTION_TEMPLATES = {
    "common": [
        "Please introduce yourself briefly.",
        "Tell us about a challenge you solved recently.",
        "What is one strength you rely on at work?",
        "Describe a time you collaborated across teams.",
        "Why do you want this role?",
    ],
    "it": [
        "Walk through a project where you improved a system or workflow.",
        "How do you approach debugging when the cause is unclear?",
        "Describe how you balance speed and code quality.",
        "Tell us about a time you handled production risk.",
        "What kind of engineering environment helps you do your best work?",
    ],
}


class InterviewService:
    def create_session(
        self,
        payload: CreateInterviewRequest,
        user_id: str,
        db: Session,
    ) -> InterviewSessionResponse:
        session_uuid = uuid4()
        questions = self._build_questions(payload.job_category_code, payload.question_count)
        interview_session = self._persist_created_session(session_uuid, payload, questions, user_id, db)
        return InterviewSessionResponse(**self._serialize_db_session(interview_session))

    def get_session(
        self,
        session_id: str,
        user_id: str,
        db: Session,
    ) -> InterviewSessionResponse:
        db_session = self._load_owned_session(session_id, user_id, db)
        return InterviewSessionResponse(**self._serialize_db_session(db_session))

    def start_session(
        self,
        session_id: str,
        user_id: str,
        db: Session,
    ) -> StartInterviewResponse:
        db_session = self._load_owned_session(session_id, user_id, db)
        self._mark_session_started(db_session, db)
        question = self._get_current_question_or_409(db_session, db)
        return StartInterviewResponse(
            session_id=session_id,
            status=db_session.status,
            question=self._build_question_response(question),
        )

    def get_current_question(
        self,
        session_id: str,
        user_id: str,
        db: Session,
    ) -> CurrentQuestionResponse:
        db_session = self._load_owned_session(session_id, user_id, db)
        question = self._get_current_question_or_409(db_session, db)
        return CurrentQuestionResponse(
            session_id=session_id,
            question=self._build_question_response(question),
        )

    def submit_text_answer(
        self,
        session_id: str,
        question_id: str,
        payload: SubmitTextAnswerRequest,
        user_id: str,
        db: Session,
    ) -> SubmitAnswerResponse:
        db_session = self._load_owned_session(session_id, user_id, db)
        self._validate_answer_submission(
            db_session=db_session,
            question_id=question_id,
            attempt_no=payload.attempt_no,
            db=db,
        )
        self._persist_answer(
            question_id=question_id,
            attempt_no=payload.attempt_no,
            is_final_attempt=payload.is_final_attempt,
            answer_type="text",
            answer_payload={"text": payload.text},
            db=db,
        )
        if payload.is_final_attempt:
            self._create_processing_job(
                db_session=db_session,
                job_type="answer_evaluation",
                current_stage="evaluation_queued",
                queue_name="interview-evaluation",
                metrics_json={
                    "question_id": question_id,
                    "attempt_no": payload.attempt_no,
                    "answer_type": "text",
                },
                complete_inline_if_unavailable=True,
                db=db,
            )
        return SubmitAnswerResponse(
            session_id=session_id,
            question_id=question_id,
            attempt_no=payload.attempt_no,
            accepted=True,
            queued_stt=False,
            queued_evaluation=payload.is_final_attempt,
            next_action="next_question" if payload.is_final_attempt else "retry_allowed",
        )

    def submit_audio_answer(
        self,
        session_id: str,
        question_id: str,
        filename: str,
        content_type: str,
        attempt_no: int,
        is_final_attempt: bool,
        duration_sec: int,
        user_id: str,
        db: Session,
    ) -> SubmitAnswerResponse:
        db_session = self._load_owned_session(session_id, user_id, db)
        self._validate_answer_submission(
            db_session=db_session,
            question_id=question_id,
            attempt_no=attempt_no,
            db=db,
        )
        self._persist_answer(
            question_id=question_id,
            attempt_no=attempt_no,
            is_final_attempt=is_final_attempt,
            answer_type="audio",
            answer_payload={
                "filename": filename,
                "content_type": content_type,
                "duration_sec": duration_sec,
            },
            db=db,
        )
        self._create_processing_job(
            db_session=db_session,
            job_type="speech_to_text",
            current_stage="stt_queued",
            queue_name="interview-stt",
            metrics_json={
                "question_id": question_id,
                "attempt_no": attempt_no,
                "answer_type": "audio",
                "duration_sec": duration_sec,
            },
            complete_inline_if_unavailable=True,
            db=db,
        )
        if is_final_attempt:
            self._create_processing_job(
                db_session=db_session,
                job_type="answer_evaluation",
                current_stage="evaluation_queued",
                queue_name="interview-evaluation",
                metrics_json={
                    "question_id": question_id,
                    "attempt_no": attempt_no,
                    "answer_type": "audio",
                },
                complete_inline_if_unavailable=True,
                db=db,
            )
        return SubmitAnswerResponse(
            session_id=session_id,
            question_id=question_id,
            attempt_no=attempt_no,
            accepted=True,
            queued_stt=True,
            queued_evaluation=is_final_attempt,
            next_action="next_question" if is_final_attempt else "retry_allowed",
        )

    def move_to_next_question(
        self,
        session_id: str,
        question_id: str,
        user_id: str,
        db: Session,
    ) -> NextQuestionResponse:
        db_session = self._load_owned_session(session_id, user_id, db)
        current_question = self._load_session_question(question_id, db_session.id, db)
        self._ensure_final_attempt_exists(question_id, db)

        next_question = db.scalar(
            select(Question)
            .where(
                Question.interview_session_id == db_session.id,
                Question.sequence_no > current_question.sequence_no,
            )
            .order_by(Question.sequence_no.asc())
            .limit(1)
        )
        if next_question is None:
            self._mark_session_completed(db_session, db)
            return NextQuestionResponse(
                session_id=session_id,
                status=db_session.status,
                report_ready=True,
            )

        return NextQuestionResponse(
            session_id=session_id,
            status=db_session.status,
            question=self._build_question_response(next_question),
            report_ready=False,
        )

    def get_report(
        self,
        session_id: str,
        user_id: str,
        db: Session,
    ) -> InterviewReportResponse:
        db_session = self._load_owned_session(session_id, user_id, db)
        if db_session.status != "completed":
            return InterviewReportResponse(session_id=session_id, status="not_ready", report=None)

        answered_question_count, submitted_answer_count = self._load_report_counts(db_session.id, db)
        report = {
            "overall_score": min(100, 60 + submitted_answer_count * 5),
            "summary": "Development report generated from the mocked interview flow.",
            "answered_question_count": answered_question_count,
            "submitted_answer_count": submitted_answer_count,
        }
        report_job = self._create_processing_job(
            db_session=db_session,
            job_type="report_generation",
            current_stage="report_building",
            queue_name="interview-report",
            metrics_json=report,
            complete_inline_if_unavailable=False,
            db=db,
        )
        self._persist_report(db_session, report, db)
        if not self._enqueue_processing_job(report_job, db):
            self._complete_processing_job(report_job.id, metrics_json=report, db=db)
        return InterviewReportResponse(session_id=session_id, status="ready", report=report)

    def _serialize_db_session(self, session: InterviewSessionModel) -> dict:
        return {
            "session_id": str(session.id),
            "status": session.status,
            "question_count": session.question_count,
            "answer_time_limit_sec": session.answer_time_limit_sec,
            "allow_retry": session.allow_retry,
        }

    def _build_questions(self, job_category_code: str, question_count: int) -> list[dict]:
        templates = QUESTION_TEMPLATES.get(job_category_code, QUESTION_TEMPLATES["common"])
        return [
            {
                "id": str(uuid4()),
                "sequence_no": index + 1,
                "question_text": templates[index % len(templates)],
            }
            for index in range(question_count)
        ]

    def _build_question_response(self, question: Question) -> InterviewQuestion:
        return InterviewQuestion(
            id=str(question.id),
            sequence_no=question.sequence_no,
            question_text=question.question_text,
        )

    def _load_session_question(
        self,
        question_id: str,
        session_id: UUID,
        db: Session,
    ) -> Question:
        try:
            question_uuid = UUID(question_id)
            question = db.get(Question, question_uuid)
        except (SQLAlchemyError, ValueError) as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview question not found.",
            ) from exc

        if question is None or question.interview_session_id != session_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview question not found.",
            )
        return question

    def _persist_created_session(
        self,
        session_uuid: UUID,
        payload: CreateInterviewRequest,
        questions: list[dict],
        user_id: str,
        db: Session,
    ) -> InterviewSessionModel:
        try:
            self._ensure_user(db, user_id)
            job_category = db.scalar(select(JobCategory).where(JobCategory.code == payload.job_category_code))
            if job_category is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job category not found.",
                )

            interview_session = InterviewSessionModel(
                id=session_uuid,
                user_id=UUID(user_id),
                job_category_id=job_category.id,
                mode=payload.mode,
                status="pending",
                question_count=payload.question_count,
                answer_time_limit_sec=payload.answer_time_limit_sec,
                allow_retry=payload.allow_retry,
            )
            db.add(interview_session)
            for item in questions:
                db.add(
                    Question(
                        id=UUID(item["id"]),
                        interview_session_id=session_uuid,
                        sequence_no=item["sequence_no"],
                        question_text=item["question_text"],
                    )
                )
            db.commit()
            db.refresh(interview_session)
            return interview_session
        except HTTPException:
            db.rollback()
            raise
        except (SQLAlchemyError, ValueError) as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to create interview session.",
            ) from exc

    def _ensure_user(self, db: Session, user_id: str) -> None:
        user_uuid = UUID(user_id)
        existing_user = db.get(User, user_uuid)
        if existing_user is not None:
            return

        db.add(
            User(
                id=user_uuid,
                email="admin@example.com",
                password_hash="dev-only",
                display_name="Developer",
                role="admin",
                is_active=True,
            )
        )
        db.flush()

    def _load_owned_session(
        self,
        session_id: str,
        user_id: str,
        db: Session,
    ) -> InterviewSessionModel:
        try:
            session_uuid = UUID(session_id)
            user_uuid = UUID(user_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview session not found.",
            ) from exc

        try:
            db_session = db.get(InterviewSessionModel, session_uuid)
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load interview session.",
            ) from exc

        if db_session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview session not found.",
            )
        if db_session.user_id != user_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this interview session.",
            )
        return db_session

    def _mark_session_started(self, db_session: InterviewSessionModel, db: Session) -> None:
        if db_session.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Interview session is already completed.",
            )
        if db_session.status != "in_progress":
            try:
                db_session.status = "in_progress"
                if db_session.started_at is None:
                    db_session.started_at = utc_now()
                db.commit()
                db.refresh(db_session)
            except SQLAlchemyError as exc:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Unable to start interview session.",
                ) from exc

    def _get_current_question_or_409(
        self,
        db_session: InterviewSessionModel,
        db: Session,
    ) -> Question:
        if db_session.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Interview session is already completed.",
            )

        try:
            questions = db.scalars(
                select(Question)
                .where(Question.interview_session_id == db_session.id)
                .order_by(Question.sequence_no.asc())
            ).all()
            final_answered_question_ids = {
                answer.question_id
                for answer in db.scalars(
                    select(Answer)
                    .join(Question, Question.id == Answer.question_id)
                    .where(
                        Question.interview_session_id == db_session.id,
                        Answer.is_final_attempt.is_(True),
                    )
                ).all()
            }
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load current interview question.",
            ) from exc

        for question in questions:
            if question.id not in final_answered_question_ids:
                return question

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active question is available for this session.",
        )

    def _validate_answer_submission(
        self,
        db_session: InterviewSessionModel,
        question_id: str,
        attempt_no: int,
        db: Session,
    ) -> None:
        if db_session.status != "in_progress":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Interview session must be in progress before submitting answers.",
            )

        current_question = self._get_current_question_or_409(db_session, db)
        if str(current_question.id) != question_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Question is not the current active question.",
            )
        if attempt_no > 1 and not db_session.allow_retry:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Retries are disabled for this session.",
            )

        try:
            question_uuid = UUID(question_id)
            existing = db.scalar(
                select(Answer).where(
                    Answer.question_id == question_uuid,
                    Answer.attempt_no == attempt_no,
                )
            )
        except (SQLAlchemyError, ValueError) as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to validate answer submission.",
            ) from exc

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Attempt number already submitted for this question.",
            )

    def _persist_answer(
        self,
        question_id: str,
        attempt_no: int,
        is_final_attempt: bool,
        answer_type: str,
        answer_payload: dict,
        db: Session,
    ) -> None:
        try:
            question_uuid = UUID(question_id)
            question = db.get(Question, question_uuid)
            if question is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Interview question not found.",
                )

            db.add(
                Answer(
                    question_id=question_uuid,
                    answer_type=answer_type,
                    attempt_no=attempt_no,
                    text_content=answer_payload.get("text"),
                    audio_file_path=answer_payload.get("filename"),
                    duration_sec=answer_payload.get("duration_sec"),
                    is_final_attempt=is_final_attempt,
                )
            )
            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except (SQLAlchemyError, ValueError) as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to persist interview answer.",
            ) from exc

    def _ensure_final_attempt_exists(self, question_id: str, db: Session) -> None:
        try:
            question_uuid = UUID(question_id)
            has_final_attempt = db.scalar(
                select(Answer.id)
                .where(
                    Answer.question_id == question_uuid,
                    Answer.is_final_attempt.is_(True),
                )
                .limit(1)
            )
        except (SQLAlchemyError, ValueError) as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to validate final interview answer.",
            ) from exc

        if has_final_attempt is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A final answer attempt is required before moving to the next question.",
            )

    def _mark_session_completed(self, db_session: InterviewSessionModel, db: Session) -> None:
        try:
            db_session.status = "completed"
            db_session.completed_at = utc_now()
            db_session.report_status = "ready"
            db.commit()
            db.refresh(db_session)
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to complete interview session.",
            ) from exc

    def _load_report_counts(self, session_id: UUID, db: Session) -> tuple[int, int]:
        try:
            answer_rows = db.scalars(
                select(Answer).join(Question, Question.id == Answer.question_id).where(
                    Question.interview_session_id == session_id
                )
            ).all()
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to build interview report.",
            ) from exc

        answered_question_count = len({answer.question_id for answer in answer_rows})
        return answered_question_count, len(answer_rows)

    def _persist_report(
        self,
        db_session: InterviewSessionModel,
        report: dict,
        db: Session,
    ) -> None:
        try:
            existing = db.scalar(
                select(FeedbackReport).where(FeedbackReport.interview_session_id == db_session.id)
            )
            summary = report["summary"]
            if existing is None:
                db.add(
                    FeedbackReport(
                        interview_session_id=db_session.id,
                        overall_score=report["overall_score"],
                        content_score=report["overall_score"],
                        speech_score=report["overall_score"],
                        posture_score=report["overall_score"],
                        strength_summary=summary,
                        improvement_summary=summary,
                        full_report_markdown=summary,
                    )
                )
            else:
                existing.overall_score = report["overall_score"]
                existing.content_score = report["overall_score"]
                existing.speech_score = report["overall_score"]
                existing.posture_score = report["overall_score"]
                existing.strength_summary = summary
                existing.improvement_summary = summary
                existing.full_report_markdown = summary

            db_session.final_score = report["overall_score"]
            db_session.report_status = "ready"
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to persist interview report.",
            ) from exc

    def _create_processing_job(
        self,
        db_session: InterviewSessionModel,
        job_type: str,
        current_stage: str,
        queue_name: str,
        metrics_json: dict,
        complete_inline_if_unavailable: bool,
        db: Session,
    ) -> ProcessingJob:
        try:
            job = ProcessingJob(
                user_id=db_session.user_id,
                interview_session_id=db_session.id,
                job_type=job_type,
                status="queued",
                current_stage=current_stage,
                queue_name=queue_name,
                metrics_json=metrics_json,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            if complete_inline_if_unavailable and not self._enqueue_processing_job(job, db):
                self._complete_processing_job(job.id, metrics_json=metrics_json, db=db)
            return job
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to queue processing job.",
            ) from exc

    def _enqueue_processing_job(self, job: ProcessingJob, db: Session) -> bool:
        queued = enqueue_job(job.queue_name, str(job.id))
        self._set_job_execution_mode(job.id, "queued" if queued else "inline", db)
        return queued

    def _complete_processing_job(
        self,
        job_id: UUID,
        metrics_json: dict,
        db: Session,
    ) -> None:
        try:
            job = db.get(ProcessingJob, job_id)
            if job is None:
                return
            job.status = "completed"
            job.current_stage = "completed"
            job.started_at = job.started_at or utc_now()
            job.completed_at = utc_now()
            job.metrics_json = metrics_json
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to complete processing job.",
            ) from exc

    def _set_job_execution_mode(self, job_id: UUID, execution_mode: str, db: Session) -> None:
        try:
            job = db.get(ProcessingJob, job_id)
            if job is None:
                return
            metrics = dict(job.metrics_json or {})
            metrics["execution_mode"] = execution_mode
            job.metrics_json = metrics
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to store processing job execution mode.",
            ) from exc
