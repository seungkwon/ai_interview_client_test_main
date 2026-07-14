from typing import Optional

from pydantic import BaseModel, Field


class PostureEvent(BaseModel):
    event_type: str
    severity: str = Field(pattern="^(low|medium|high)$")
    started_at_ms: int = Field(ge=0)
    ended_at_ms: int = Field(ge=0)


class PostureSummaryPayload(BaseModel):
    shoulder_asymmetry_score: float = Field(ge=0, le=1)
    gaze_away_ratio: float = Field(ge=0, le=1)
    hand_face_event_count: int = Field(ge=0)
    upper_body_motion_score: float = Field(ge=0, le=1)


class PostureLocalSummaryRequest(BaseModel):
    session_id: str
    question_id: str
    source_mode: str = Field(pattern="^(local|server)$")
    sample_fps: int = Field(ge=1, le=30)
    mediapipe_delegate_preference: Optional[str] = Field(default=None, pattern="^(auto|cpu|gpu)$")
    summary: PostureSummaryPayload
    events: list[PostureEvent] = Field(default_factory=list)


class PostureFallbackSampleRequest(BaseModel):
    session_id: str
    question_id: str
    sample_count: int = Field(ge=1)
    source_mode: str = Field(pattern="^(fallback|server)$")
    mediapipe_delegate_preference: Optional[str] = Field(default=None, pattern="^(auto|cpu|gpu)$")
    landmarks_summary: dict = Field(default_factory=dict)
    frame_jpeg_base64: Optional[str] = None


class PostureSubmissionResponse(BaseModel):
    session_id: str
    question_id: str
    status: str
    stored_event_count: int
    mediapipe_runtime: Optional[str] = None
