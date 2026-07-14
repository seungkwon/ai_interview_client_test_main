from __future__ import annotations

import argparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.time import utc_now
from app.db.session import SessionLocal
from app.models import Answer, ProcessingJob, SpeechMetric
from app.services.processing_queue import dequeue_job


KNOWN_QUEUES = [
    "recorded-analysis",
    "interview-stt",
    "interview-evaluation",
    "interview-report",
]


def process_job(job_id: str) -> bool:
    with SessionLocal() as db:
        try:
            job = db.get(ProcessingJob, UUID(job_id))
            if job is None:
                return False

            job.status = "processing"
            job.current_stage = _processing_stage_for(job.job_type)
            job.started_at = job.started_at or utc_now()
            db.commit()

            _run_job(job, db)

            job.status = "completed"
            job.current_stage = "completed"
            job.completed_at = utc_now()
            db.commit()
            return True
        except (SQLAlchemyError, ValueError):
            db.rollback()
            return False


def process_one(timeout: int = 1) -> bool:
    item = dequeue_job(KNOWN_QUEUES, timeout=timeout)
    if item is None:
        return False
    _, job_id = item
    return process_job(job_id)


def run_forever(timeout: int = 5) -> None:
    while True:
        process_one(timeout=timeout)


def _processing_stage_for(job_type: str) -> str:
    if job_type == "recorded_analysis":
        return "processing"
    if job_type == "speech_to_text":
        return "transcribing"
    if job_type == "answer_evaluation":
        return "evaluating"
    if job_type == "report_generation":
        return "building_report"
    return "processing"


def _run_job(job: ProcessingJob, db) -> None:
    metrics = dict(job.metrics_json or {})
    if job.job_type == "recorded_analysis":
        metrics["progress"] = 100
        job.metrics_json = metrics
        return

    if job.job_type == "speech_to_text":
        _create_speech_metric(job, metrics, db)
        return

    job.metrics_json = metrics


def _create_speech_metric(job: ProcessingJob, metrics: dict, db) -> None:
    question_id = metrics.get("question_id")
    attempt_no = metrics.get("attempt_no")
    if not question_id or attempt_no is None:
        return

    answer = db.scalar(
        select(Answer).where(
            Answer.question_id == UUID(question_id),
            Answer.attempt_no == int(attempt_no),
        )
    )
    if answer is None:
        return

    existing = db.scalar(select(SpeechMetric).where(SpeechMetric.answer_id == answer.id))
    if existing is not None:
        return

    db.add(
        SpeechMetric(
            answer_id=answer.id,
            stt_model="mock-worker",
            stt_latency_ms=850,
            transcript_confidence_note="worker-generated placeholder metric",
            speaking_rate_wpm=132,
            pause_count=3,
            pause_ratio=0.08,
            filler_count=1,
            repetition_score=0.12,
        )
    )
    db.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--timeout", type=int, default=5)
    args = parser.parse_args()

    if args.once:
        process_one(timeout=args.timeout)
        return
    run_forever(timeout=args.timeout)


if __name__ == "__main__":
    main()
