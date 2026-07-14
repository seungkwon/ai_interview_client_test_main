from __future__ import annotations

import base64
import logging
from io import BytesIO
from pathlib import Path
from threading import Lock
from urllib.request import urlretrieve
from uuid import UUID

import mediapipe as mp
import numpy as np
from fastapi import HTTPException, status
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision
from PIL import Image
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import InterviewSession, PostureEvent as PostureEventModel, PostureMetric, Question
from app.schemas.posture import (
    PostureEvent,
    PostureFallbackSampleRequest,
    PostureLocalSummaryRequest,
    PostureSubmissionResponse,
)

logger = logging.getLogger(__name__)
TRACE_LOG_PATH = Path(__file__).resolve().parents[3] / "posture_trace.log"
POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)
POSE_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "pose_landmarker_lite.task"


def emit_posture_trace(message: str) -> None:
    logger.info(message)
    print(message, flush=True)
    try:
        with TRACE_LOG_PATH.open("a", encoding="utf-8") as trace_file:
            trace_file.write(f"{message}\n")
    except OSError:
        pass


class PostureService:
    _pose_lock = Lock()
    _pose_analyzers: dict[BaseOptions.Delegate, vision.PoseLandmarker] = {}

    def submit_local_summary(
        self,
        payload: PostureLocalSummaryRequest,
        user_id: str,
        db: Session,
    ) -> PostureSubmissionResponse:
        self._ensure_session_exists(payload.session_id, user_id, db)
        self._persist_local_summary(payload, db)
        return PostureSubmissionResponse(
            session_id=payload.session_id,
            question_id=payload.question_id,
            status="stored",
            stored_event_count=len(payload.events),
            mediapipe_runtime=payload.mediapipe_delegate_preference,
        )

    def submit_fallback_samples(
        self,
        payload: PostureFallbackSampleRequest,
        user_id: str,
        db: Session,
    ) -> PostureSubmissionResponse:
        self._ensure_session_exists(payload.session_id, user_id, db)
        emit_posture_trace(
            "Received posture fallback sample "
            f"session_id={payload.session_id} "
            f"question_id={payload.question_id} "
            f"source_mode={payload.source_mode} "
            f"sample_count={payload.sample_count}"
        )
        analysis = self._analyze_server_frame(payload) if payload.source_mode == "server" else None
        if analysis is not None:
            self._persist_server_summary(payload, analysis, db)
            emit_posture_trace(
                "Stored server posture analysis "
                f"session_id={payload.session_id} "
                f"question_id={payload.question_id} "
                f"events={len(analysis['events'])}"
            )
        else:
            self._persist_fallback_summary(payload, db)
            emit_posture_trace(
                "Queued fallback posture sample "
                f"session_id={payload.session_id} "
                f"question_id={payload.question_id} "
                f"source_mode={payload.source_mode}"
            )
        return PostureSubmissionResponse(
            session_id=payload.session_id,
            question_id=payload.question_id,
            status="stored" if analysis is not None else "queued",
            stored_event_count=len(analysis["events"]) if analysis is not None else 0,
            mediapipe_runtime=analysis["runtime"] if analysis is not None else None,
        )

    def _ensure_session_exists(self, session_id: str, user_id: str, db: Session) -> None:
        try:
            session_uuid = UUID(session_id)
            interview_session = db.get(InterviewSession, session_uuid)
        except ValueError:
            interview_session = None
        except SQLAlchemyError:
            db.rollback()
            interview_session = None

        if interview_session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview session not found.",
            )
        if str(interview_session.user_id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this interview session.",
            )

    def _persist_local_summary(
        self,
        payload: PostureLocalSummaryRequest,
        db: Session,
    ) -> None:
        try:
            session_uuid = UUID(payload.session_id)
            question_uuid = UUID(payload.question_id)
        except ValueError:
            return

        try:
            if db.get(Question, question_uuid) is None:
                return
            db.add(
                PostureMetric(
                    interview_session_id=session_uuid,
                    question_id=question_uuid,
                    source_mode=payload.source_mode,
                    sample_fps=payload.sample_fps,
                    shoulder_asymmetry_score=payload.summary.shoulder_asymmetry_score,
                    gaze_away_ratio=payload.summary.gaze_away_ratio,
                    hand_face_event_count=payload.summary.hand_face_event_count,
                    upper_body_motion_score=payload.summary.upper_body_motion_score,
                )
            )
            for event in payload.events:
                db.add(
                    PostureEventModel(
                        interview_session_id=session_uuid,
                        question_id=question_uuid,
                        event_type=event.event_type,
                        severity=event.severity,
                        started_at_ms=event.started_at_ms,
                        ended_at_ms=event.ended_at_ms,
                        evidence_json=None,
                    )
                )
            db.commit()
        except SQLAlchemyError:
            db.rollback()

    def _persist_fallback_summary(
        self,
        payload: PostureFallbackSampleRequest,
        db: Session,
    ) -> None:
        try:
            session_uuid = UUID(payload.session_id)
            question_uuid = UUID(payload.question_id)
        except ValueError:
            return

        try:
            if db.get(Question, question_uuid) is None:
                return
            db.add(
                PostureMetric(
                    interview_session_id=session_uuid,
                    question_id=question_uuid,
                    source_mode=payload.source_mode,
                    sample_fps=payload.sample_count,
                )
            )
            db.commit()
        except SQLAlchemyError:
            db.rollback()

    def _persist_server_summary(
        self,
        payload: PostureFallbackSampleRequest,
        analysis: dict,
        db: Session,
    ) -> None:
        try:
            session_uuid = UUID(payload.session_id)
            question_uuid = UUID(payload.question_id)
        except ValueError:
            return

        try:
            if db.get(Question, question_uuid) is None:
                return
            summary = analysis["summary"]
            db.add(
                PostureMetric(
                    interview_session_id=session_uuid,
                    question_id=question_uuid,
                    source_mode="server",
                    sample_fps=payload.sample_count,
                    shoulder_asymmetry_score=summary["shoulder_asymmetry_score"],
                    gaze_away_ratio=summary["gaze_away_ratio"],
                    hand_face_event_count=summary["hand_face_event_count"],
                    upper_body_motion_score=summary["upper_body_motion_score"],
                    visibility_drop_ratio=summary["visibility_drop_ratio"],
                    torso_tilt_score=summary["torso_tilt_score"],
                )
            )
            for event in analysis["events"]:
                db.add(
                    PostureEventModel(
                        interview_session_id=session_uuid,
                        question_id=question_uuid,
                        event_type=event.event_type,
                        severity=event.severity,
                        started_at_ms=event.started_at_ms,
                        ended_at_ms=event.ended_at_ms,
                        evidence_json=analysis["evidence"],
                    )
                )
            db.commit()
        except SQLAlchemyError:
            db.rollback()

    def _analyze_server_frame(self, payload: PostureFallbackSampleRequest) -> dict | None:
        if not payload.frame_jpeg_base64:
            emit_posture_trace(
                "Server posture analysis skipped because frame payload is missing "
                f"session_id={payload.session_id} question_id={payload.question_id}"
            )
            return None

        image = self._decode_frame(payload.frame_jpeg_base64)
        if image is None:
            emit_posture_trace(
                "Server posture analysis skipped because frame decoding failed "
                f"session_id={payload.session_id} question_id={payload.question_id}"
            )
            return None

        emit_posture_trace(
            "Starting server posture analysis "
            f"session_id={payload.session_id} "
            f"question_id={payload.question_id} "
            f"frame={int(image.shape[1])}x{int(image.shape[0])} "
            f"delegate={payload.mediapipe_delegate_preference or 'cpu'}"
        )
        pose, runtime = self._get_pose_analyzer(payload.mediapipe_delegate_preference or "cpu")
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        with self._pose_lock:
            result = pose.detect(mp_image)

        landmarks = result.pose_landmarks[0] if result.pose_landmarks else None
        if not landmarks:
            emit_posture_trace(
                "Server posture analysis completed without landmarks "
                f"session_id={payload.session_id} question_id={payload.question_id}"
            )
            return None

        summary = self._build_summary(landmarks)
        events = self._build_events(summary, payload.sample_count)
        evidence = {
            "frame_width": int(image.shape[1]),
            "frame_height": int(image.shape[0]),
            "landmark_count": len(landmarks),
        }
        emit_posture_trace(
            "Server posture analysis completed "
            f"session_id={payload.session_id} "
            f"question_id={payload.question_id} "
            f"landmarks={len(landmarks)} "
            f"events={len(events)} "
            f"delegate={runtime}"
        )
        return {"summary": summary, "events": events, "evidence": evidence, "runtime": runtime}

    def _get_pose_analyzer(self, delegate_preference: str) -> tuple[vision.PoseLandmarker, str]:
        preferred_delegate = (
            BaseOptions.Delegate.GPU
            if delegate_preference == "gpu"
            else BaseOptions.Delegate.CPU
        )
        delegates = (
            [BaseOptions.Delegate.GPU, BaseOptions.Delegate.CPU]
            if delegate_preference == "auto"
            else [preferred_delegate]
        )

        last_error: Exception | None = None
        model_path = self._ensure_pose_model()
        for delegate in delegates:
            analyzer = self._pose_analyzers.get(delegate)
            if analyzer is not None:
                return analyzer, "gpu" if delegate == BaseOptions.Delegate.GPU else "cpu"

            try:
                options = vision.PoseLandmarkerOptions(
                    base_options=BaseOptions(
                        model_asset_path=str(model_path),
                        delegate=delegate,
                    ),
                    running_mode=vision.RunningMode.IMAGE,
                    num_poses=1,
                    min_pose_detection_confidence=0.5,
                    min_pose_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                analyzer = vision.PoseLandmarker.create_from_options(options)
                self._pose_analyzers[delegate] = analyzer
                runtime = "gpu" if delegate == BaseOptions.Delegate.GPU else "cpu"
                emit_posture_trace(f"Initialized server MediaPipe analyzer delegate={runtime}")
                return analyzer, runtime
            except Exception as exc:
                last_error = exc
                emit_posture_trace(
                    "Server MediaPipe analyzer initialization failed "
                    f"delegate={'gpu' if delegate == BaseOptions.Delegate.GPU else 'cpu'} "
                    f"error={exc}"
                )

        if last_error is not None:
            raise last_error
        raise RuntimeError("Unable to initialize server MediaPipe analyzer.")

    def _ensure_pose_model(self) -> Path:
        if POSE_MODEL_PATH.exists():
            return POSE_MODEL_PATH

        POSE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        emit_posture_trace(f"Downloading MediaPipe pose model to {POSE_MODEL_PATH}")
        urlretrieve(POSE_MODEL_URL, POSE_MODEL_PATH)
        return POSE_MODEL_PATH

    def _decode_frame(self, encoded_frame: str) -> np.ndarray | None:
        try:
            frame_bytes = base64.b64decode(encoded_frame)
            image = Image.open(BytesIO(frame_bytes)).convert("RGB")
        except Exception:
            return None
        return np.asarray(image)

    def _build_summary(self, landmarks: list) -> dict[str, float | int]:
        nose = landmarks[0]
        left_shoulder = landmarks[11]
        right_shoulder = landmarks[12]
        left_wrist = landmarks[15]
        right_wrist = landmarks[16]
        left_hip = landmarks[23]
        right_hip = landmarks[24]

        shoulder_center_x = (left_shoulder.x + right_shoulder.x) / 2
        shoulder_center_y = (left_shoulder.y + right_shoulder.y) / 2
        hip_center_x = (left_hip.x + right_hip.x) / 2
        hip_center_y = (left_hip.y + right_hip.y) / 2

        shoulder_asymmetry_score = self._clamp01(abs(left_shoulder.y - right_shoulder.y) * 3.2)
        torso_tilt_score = self._clamp01(abs(shoulder_center_x - hip_center_x) * 4)
        gaze_away_ratio = self._clamp01(abs(nose.x - shoulder_center_x) * 3.5)
        hand_face_event_count = int(
            self._distance(left_wrist.x, left_wrist.y, nose.x, nose.y) < 0.12
            or self._distance(right_wrist.x, right_wrist.y, nose.x, nose.y) < 0.12
        )
        upper_body_motion_score = self._clamp01(
            self._distance(shoulder_center_x, shoulder_center_y, hip_center_x, hip_center_y) * 0.4
        )
        visible_landmarks = sum(1 for landmark in landmarks if getattr(landmark, "visibility", 1) > 0.35)
        visibility_drop_ratio = self._clamp01(1 - (visible_landmarks / max(1, len(landmarks))))

        return {
            "shoulder_asymmetry_score": shoulder_asymmetry_score,
            "torso_tilt_score": torso_tilt_score,
            "gaze_away_ratio": gaze_away_ratio,
            "hand_face_event_count": hand_face_event_count,
            "upper_body_motion_score": upper_body_motion_score,
            "visibility_drop_ratio": visibility_drop_ratio,
        }

    def _build_events(self, summary: dict[str, float | int], sample_count: int) -> list[PostureEvent]:
        timestamp_ms = sample_count * 1000
        events: list[PostureEvent] = []

        if float(summary["gaze_away_ratio"]) > 0.35:
            events.append(
                PostureEvent(
                    event_type="gaze_away",
                    severity="high" if float(summary["gaze_away_ratio"]) > 0.6 else "medium",
                    started_at_ms=max(0, timestamp_ms - 1000),
                    ended_at_ms=timestamp_ms,
                )
            )
        if int(summary["hand_face_event_count"]) > 0:
            events.append(
                PostureEvent(
                    event_type="hand_face_contact",
                    severity="medium",
                    started_at_ms=max(0, timestamp_ms - 1000),
                    ended_at_ms=timestamp_ms,
                )
            )
        if float(summary["torso_tilt_score"]) > 0.35:
            events.append(
                PostureEvent(
                    event_type="torso_tilt",
                    severity="high" if float(summary["torso_tilt_score"]) > 0.6 else "low",
                    started_at_ms=max(0, timestamp_ms - 1000),
                    ended_at_ms=timestamp_ms,
                )
            )

        return events

    def _distance(self, ax: float, ay: float, bx: float, by: float) -> float:
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    def _clamp01(self, value: float) -> float:
        return max(0.0, min(1.0, value))
