# AI Interview v2 API and WebSocket Draft

## 1. API Conventions
- Base path: `/api/v1`
- Auth: bearer token
- Response format: JSON
- Uploads: multipart for audio/video files

## 2. Auth APIs

### `POST /auth/login`
- request
```json
{
  "email": "admin@example.com",
  "password": "secret"
}
```
- response
```json
{
  "access_token": "jwt",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "display_name": "Admin",
    "role": "admin"
  }
}
```

### `POST /auth/logout`
- marks login session closed

### `GET /auth/me`
- returns current user profile and role

## 3. Job Category APIs

### `GET /job-categories`
- returns 8 interview categories

## 4. Interview Session APIs

### `POST /interviews`
- create a session
- request
```json
{
  "job_category_code": "it",
  "mode": "live",
  "question_count": 5,
  "answer_time_limit_sec": 60,
  "allow_retry": true
}
```

### `GET /interviews/{session_id}`
- session summary and current status

### `POST /interviews/{session_id}/start`
- marks session started and generates first question

### `GET /interviews/{session_id}/questions/current`
- returns current question

### `POST /interviews/{session_id}/questions/{question_id}/next`
- completes current question and generates next question

### `GET /interviews/{session_id}/report`
- final feedback report

## 5. Answer APIs

### `POST /interviews/{session_id}/questions/{question_id}/answers/text`
- request
```json
{
  "text": "지원 동기를 말씀드리겠습니다.",
  "attempt_no": 1,
  "is_final_attempt": true
}
```

### `POST /interviews/{session_id}/questions/{question_id}/answers/audio`
- multipart upload
- fields
  - `file`
  - `attempt_no`
  - `is_final_attempt`
  - `duration_sec`
- behavior
  - stores file
  - queues STT
  - queues speech metric extraction

## 6. Recorded Video APIs

### `POST /recorded-analysis`
- multipart upload
- validation rules
  - max 10 minutes
  - max 500 MB
  - formats: `mp4`, `avi`
- response
```json
{
  "session_id": "uuid",
  "job_id": "uuid",
  "status": "queued"
}
```

### `GET /recorded-analysis/{session_id}`
- recorded analysis status and progress

## 7. Posture APIs

### `POST /posture/local-summary`
- for local analysis summary upload per question or time window
- request
```json
{
  "session_id": "uuid",
  "question_id": "uuid",
  "source_mode": "local",
  "sample_fps": 5,
  "summary": {
    "shoulder_asymmetry_score": 0.14,
    "gaze_away_ratio": 0.18,
    "hand_face_event_count": 3,
    "upper_body_motion_score": 0.31
  },
  "events": [
    {
      "event_type": "gaze_away",
      "severity": "medium",
      "started_at_ms": 12000,
      "ended_at_ms": 13600
    }
  ]
}
```

### `POST /posture/fallback-samples`
- for server fallback path
- request may contain sampled frames metadata or extracted landmark summaries

## 8. Admin APIs

### `GET /admin/overview`
- returns cards for:
  - active login count
  - active interview count
  - validated max concurrency
  - safe estimated concurrency now
  - current bottleneck component

### `GET /admin/metrics/timeseries`
- query params
  - `from`
  - `to`
  - `interval`
- returns chart series:
  - api latency
  - queue delay
  - STT turnaround
  - posture turnaround
  - active users

### `GET /admin/sessions/active`
- returns active users with:
  - user identity
  - login started time
  - session duration
  - current processing stage
  - current interview status

### `GET /admin/interviews/{session_id}`
- detailed session review

## 9. WebSocket Events

### Endpoint
- `/ws/interviews/{session_id}`

### Client -> Server
- `session.subscribe`
- `posture.status`
- `heartbeat`

### Server -> Client
- `question.generated`
- `timer.started`
- `stt.queued`
- `stt.completed`
- `evaluation.started`
- `evaluation.completed`
- `report.ready`
- `recorded.progress`
- `error`

### Example Server Event
```json
{
  "type": "stt.completed",
  "session_id": "uuid",
  "question_id": "uuid",
  "payload": {
    "transcript_ready": true,
    "stt_latency_ms": 4210
  }
}
```

## 10. Suggested Error Codes
- `AUTH_INVALID_CREDENTIALS`
- `AUTH_FORBIDDEN`
- `INTERVIEW_NOT_FOUND`
- `QUESTION_NOT_ACTIVE`
- `ANSWER_TIME_EXCEEDED`
- `UPLOAD_FORMAT_NOT_SUPPORTED`
- `UPLOAD_FILE_TOO_LARGE`
- `UPLOAD_DURATION_EXCEEDED`
- `STT_PROCESSING_FAILED`
- `POSTURE_PROCESSING_FAILED`
- `REPORT_NOT_READY`

## 11. First Implementation Priority
1. `POST /auth/login`
2. `GET /job-categories`
3. `POST /interviews`
4. `POST /interviews/{session_id}/start`
5. `POST /interviews/{session_id}/questions/{question_id}/answers/text`
6. `POST /interviews/{session_id}/questions/{question_id}/answers/audio`
7. `GET /interviews/{session_id}/report`
8. `GET /admin/overview`
