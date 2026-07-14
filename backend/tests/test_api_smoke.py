from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.main import app
from app.models import (
    Answer,
    FeedbackReport,
    InterviewSession,
    PostureEvent,
    PostureMetric,
    ProcessingJob,
    Question,
    SpeechMetric,
)
from app.models.user import User
from app.schemas.posture import PostureEvent as PostureEventPayload
from app.services.processing_queue import is_queue_available
from app.workers.processing_worker import process_one


class ApiSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.created_session_ids: list[str] = []
        self.created_user_ids: list[UUID] = []

    def tearDown(self) -> None:
        with SessionLocal() as db:
            for session_id in self.created_session_ids:
                session_uuid = UUID(session_id)
                question_rows = db.scalars(
                    select(Question).where(Question.interview_session_id == session_uuid)
                ).all()
                question_ids = [question.id for question in question_rows]
                if question_ids:
                    db.execute(delete(PostureEvent).where(PostureEvent.question_id.in_(question_ids)))
                    db.execute(delete(PostureMetric).where(PostureMetric.question_id.in_(question_ids)))
                    answer_rows = db.scalars(select(Answer).where(Answer.question_id.in_(question_ids))).all()
                    answer_ids = [answer.id for answer in answer_rows]
                    if answer_ids:
                        db.execute(delete(SpeechMetric).where(SpeechMetric.answer_id.in_(answer_ids)))
                    db.execute(delete(Answer).where(Answer.question_id.in_(question_ids)))
                    db.execute(delete(ProcessingJob).where(ProcessingJob.interview_session_id == session_uuid))
                    db.execute(delete(FeedbackReport).where(FeedbackReport.interview_session_id == session_uuid))
                    db.execute(delete(Question).where(Question.id.in_(question_ids)))
                db.execute(delete(InterviewSession).where(InterviewSession.id == session_uuid))
            for user_id in self.created_user_ids:
                db.execute(delete(User).where(User.id == user_id))
            db.commit()

    def _login(
        self,
        *,
        email: str = "admin@example.com",
        password: str = "admin1234!",
    ) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_login_rejects_invalid_password(self) -> None:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 401, response.text)

    def test_cors_allows_null_origin_for_electron(self) -> None:
        response = self.client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "null",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "null")

    def test_auth_logout_invalidates_token(self) -> None:
        headers = self._login()

        me_response = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me_response.status_code, 200, me_response.text)

        logout_response = self.client.post("/api/v1/auth/logout", headers=headers)
        self.assertEqual(logout_response.status_code, 200, logout_response.text)

        me_after_logout = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me_after_logout.status_code, 401, me_after_logout.text)

    def test_standard_user_cannot_access_admin_routes(self) -> None:
        headers = self._login(email="user@example.com", password="user1234!")
        me_response = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me_response.status_code, 200, me_response.text)
        self.assertEqual(me_response.json()["role"], "user")

        admin_response = self.client.get("/api/v1/admin/overview", headers=headers)
        self.assertEqual(admin_response.status_code, 403, admin_response.text)

    def test_server_posture_fallback_persists_summary(self) -> None:
        headers = self._login()
        create_response = self.client.post(
            "/api/v1/interviews",
            json={
                "job_category_code": "it",
                "mode": "live",
                "question_count": 1,
                "answer_time_limit_sec": 60,
                "allow_retry": True,
            },
            headers=headers,
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        session_id = create_response.json()["session_id"]
        self.created_session_ids.append(session_id)

        start_response = self.client.post(f"/api/v1/interviews/{session_id}/start", headers=headers)
        self.assertEqual(start_response.status_code, 200, start_response.text)
        question_id = start_response.json()["question"]["id"]

        mocked_analysis = {
            "summary": {
                "shoulder_asymmetry_score": 0.2,
                "torso_tilt_score": 0.1,
                "gaze_away_ratio": 0.3,
                "hand_face_event_count": 1,
                "upper_body_motion_score": 0.25,
                "visibility_drop_ratio": 0.0,
            },
            "events": [
                PostureEventPayload(
                    event_type="hand_face_contact",
                    severity="medium",
                    started_at_ms=1000,
                    ended_at_ms=2000,
                )
            ],
            "evidence": {"frame_width": 640, "frame_height": 480},
            "runtime": "cpu",
        }

        with self.assertLogs("app.services.posture_service", level="INFO") as captured_logs:
            with patch(
                "app.services.posture_service.PostureService._analyze_server_frame",
                return_value=mocked_analysis,
            ):
                response = self.client.post(
                    "/api/v1/posture/fallback-samples",
                    json={
                        "session_id": session_id,
                        "question_id": question_id,
                        "sample_count": 5,
                        "source_mode": "server",
                        "frame_jpeg_base64": "ignored-in-mock",
                        "landmarks_summary": {},
                    },
                    headers=headers,
                )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "stored")
        self.assertEqual(response.json()["stored_event_count"], 1)
        joined_logs = "\n".join(captured_logs.output)
        self.assertIn("Received posture fallback sample", joined_logs)
        self.assertIn("Stored server posture analysis", joined_logs)

        with SessionLocal() as db:
            metric = db.scalars(
                select(PostureMetric).where(PostureMetric.interview_session_id == UUID(session_id))
            ).first()
            self.assertIsNotNone(metric)
            self.assertEqual(metric.source_mode, "server")
            event = db.scalars(
                select(PostureEvent).where(PostureEvent.interview_session_id == UUID(session_id))
            ).first()
            self.assertIsNotNone(event)
            self.assertEqual(event.event_type, "hand_face_contact")

    def test_interview_lifecycle_and_processing_jobs(self) -> None:
        headers = self._login()
        create_response = self.client.post(
            "/api/v1/interviews",
            json={
                "job_category_code": "it",
                "mode": "live",
                "question_count": 2,
                "answer_time_limit_sec": 60,
                "allow_retry": True,
            },
            headers=headers,
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        session_id = create_response.json()["session_id"]
        self.created_session_ids.append(session_id)

        start_response = self.client.post(f"/api/v1/interviews/{session_id}/start", headers=headers)
        self.assertEqual(start_response.status_code, 200, start_response.text)
        first_question = start_response.json()["question"]

        text_answer_response = self.client.post(
            f"/api/v1/interviews/{session_id}/questions/{first_question['id']}/answers/text",
            json={"text": "answer one", "attempt_no": 1, "is_final_attempt": True},
            headers=headers,
        )
        self.assertEqual(text_answer_response.status_code, 200, text_answer_response.text)

        next_question_response = self.client.post(
            f"/api/v1/interviews/{session_id}/questions/{first_question['id']}/next",
            headers=headers,
        )
        self.assertEqual(next_question_response.status_code, 200, next_question_response.text)
        second_question = next_question_response.json()["question"]

        audio_answer_response = self.client.post(
            f"/api/v1/interviews/{session_id}/questions/{second_question['id']}/answers/audio",
            headers=headers,
            files={"file": ("sample.wav", b"fake-audio", "audio/wav")},
            data={"attempt_no": "1", "is_final_attempt": "true", "duration_sec": "12"},
        )
        self.assertEqual(audio_answer_response.status_code, 200, audio_answer_response.text)

        finish_response = self.client.post(
            f"/api/v1/interviews/{session_id}/questions/{second_question['id']}/next",
            headers=headers,
        )
        self.assertEqual(finish_response.status_code, 200, finish_response.text)
        self.assertTrue(finish_response.json()["report_ready"])

        report_response = self.client.get(f"/api/v1/interviews/{session_id}/report", headers=headers)
        self.assertEqual(report_response.status_code, 200, report_response.text)
        self.assertEqual(report_response.json()["status"], "ready")

        if is_queue_available():
            for _ in range(4):
                process_one(timeout=1)

        with SessionLocal() as db:
            jobs = db.scalars(
                select(ProcessingJob)
                .where(ProcessingJob.interview_session_id == UUID(session_id))
                .order_by(ProcessingJob.created_at.asc())
            ).all()
            job_types = [job.job_type for job in jobs]
            self.assertIn("answer_evaluation", job_types)
            self.assertIn("speech_to_text", job_types)
            self.assertIn("report_generation", job_types)


if __name__ == "__main__":
    unittest.main()
