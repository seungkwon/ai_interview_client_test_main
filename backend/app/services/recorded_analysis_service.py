from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models import ProcessingJob
from app.schemas.recorded_analysis import (
    RecordedAnalysisCreateResponse,
    RecordedAnalysisStatusResponse,
)
from app.services.processing_queue import enqueue_job


class RecordedAnalysisService:
    SUPPORTED_CONTENT_TYPES = {
        "video/mp4",
        "video/x-msvideo",
    }
    SUPPORTED_EXTENSIONS = {".mp4", ".avi"}
    MAX_DURATION_SEC = 600

    def create_analysis(
        self,
        filename: str,
        content_type: str,
        duration_sec: int,
        user_id: str,
        db: Session,
    ) -> RecordedAnalysisCreateResponse:
        self._validate_upload(filename, content_type, duration_sec)
        session_id = str(uuid4())
        job_id = str(uuid4())
        self._persist_processing_job(
            job_id=job_id,
            session_id=session_id,
            filename=filename,
            content_type=content_type,
            duration_sec=duration_sec,
            user_id=user_id,
            db=db,
        )
        if not enqueue_job("recorded-analysis", job_id):
            self._persist_execution_mode(job_id, "inline", db)
            self._persist_processing_status(job_id, "processing", db)
        return RecordedAnalysisCreateResponse(
            session_id=session_id,
            job_id=job_id,
            status="queued",
        )

    def get_analysis(
        self,
        session_id: str,
        user_id: str,
        db: Session,
    ) -> RecordedAnalysisStatusResponse:
        db_response = self._get_analysis_from_db(session_id, user_id, db)
        if db_response is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recorded analysis session not found.",
            )
        return db_response

    def _validate_upload(
        self,
        filename: str,
        content_type: str,
        duration_sec: int,
    ) -> None:
        extension = ""
        if "." in filename:
            extension = filename[filename.rfind(".") :].lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only mp4 and avi uploads are supported.",
            )
        if content_type not in self.SUPPORTED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported recorded analysis content type.",
            )
        if duration_sec > self.MAX_DURATION_SEC:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recorded analysis uploads must be 10 minutes or shorter.",
            )

    def _persist_processing_job(
        self,
        job_id: str,
        session_id: str,
        filename: str,
        content_type: str,
        duration_sec: int,
        user_id: str,
        db: Session,
    ) -> None:
        try:
            db.add(
                ProcessingJob(
                    id=UUID(job_id),
                    user_id=UUID(user_id),
                    interview_session_id=None,
                    job_type="recorded_analysis",
                    status="queued",
                    current_stage="upload_received",
                    queue_name="recorded-analysis",
                    metrics_json={
                        "session_id": session_id,
                        "progress": 0,
                        "file_name": filename,
                        "duration_sec": duration_sec,
                        "content_type": content_type,
                        "execution_mode": "queued",
                    },
                )
            )
            db.commit()
        except (SQLAlchemyError, ValueError):
            db.rollback()

    def _persist_processing_status(self, job_id: str, status_value: str, db: Session) -> None:
        try:
            job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == UUID(job_id)))
            if job is None:
                return
            job.status = status_value
            job.current_stage = "completed" if status_value == "completed" else "processing"
            metrics = dict(job.metrics_json or {})
            metrics["progress"] = 100 if status_value == "completed" else 35
            job.metrics_json = metrics
            if status_value == "processing" and job.started_at is None:
                job.started_at = utc_now()
            if status_value == "completed":
                job.completed_at = utc_now()
            db.commit()
        except SQLAlchemyError:
            db.rollback()

    def _persist_execution_mode(self, job_id: str, execution_mode: str, db: Session) -> None:
        try:
            job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == UUID(job_id)))
            if job is None:
                return
            metrics = dict(job.metrics_json or {})
            metrics["execution_mode"] = execution_mode
            job.metrics_json = metrics
            db.commit()
        except SQLAlchemyError:
            db.rollback()

    def _get_analysis_from_db(
        self,
        session_id: str,
        user_id: str,
        db: Session,
    ) -> RecordedAnalysisStatusResponse | None:
        try:
            job = db.scalar(
                select(ProcessingJob).where(
                    ProcessingJob.job_type == "recorded_analysis",
                    ProcessingJob.metrics_json["session_id"].as_string() == session_id,
                )
            )
        except (SQLAlchemyError, ValueError):
            db.rollback()
            return None

        if job is None:
            return None
        if job.user_id is not None and str(job.user_id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this recorded analysis session.",
            )

        execution_mode = (job.metrics_json or {}).get("execution_mode", "inline")
        next_status = self._advance_status(job.status, execution_mode)
        if next_status != job.status:
            self._persist_processing_status(str(job.id), next_status, db)
            db.refresh(job)

        return self._build_status_response(
            {
                "session_id": session_id,
                "job_id": str(job.id),
                "status": job.status,
                "progress": int((job.metrics_json or {}).get("progress", 0)),
                "file_name": (job.metrics_json or {}).get("file_name", "recorded.bin"),
                "duration_sec": int((job.metrics_json or {}).get("duration_sec", 0)),
                "content_type": (job.metrics_json or {}).get(
                    "content_type", "application/octet-stream"
                ),
            }
        )

    def _advance_status(self, current_status: str, execution_mode: str) -> str:
        if execution_mode == "queued":
            return current_status
        if current_status == "queued":
            return "processing"
        if current_status == "processing":
            return "completed"
        return current_status

    def _build_status_response(self, payload: dict) -> RecordedAnalysisStatusResponse:
        return RecordedAnalysisStatusResponse(
            session_id=payload["session_id"],
            job_id=payload["job_id"],
            status=payload["status"],
            progress=int(payload["progress"]),
            file_name=payload["file_name"],
            duration_sec=int(payload["duration_sec"]),
            content_type=payload["content_type"],
        )
