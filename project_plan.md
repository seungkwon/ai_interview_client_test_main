# AI Interview v2 Project Plan

## 1. Goal
- Build an Electron-only desktop app with React UI and FastAPI backend for interview practice.
- Analyze posture from live or recorded video and analyze answers from voice/text.
- Use LangGraph with `gpt-5-nano` for question generation, answer scoring, and feedback.
- Prefer low-latency client-side inference first, with automatic fallback to server-side processing.

## 2. Core Requirements

### User Features
- Login/logout
- Choose target job category
- Receive interview questions based on selected category
- Answer by voice or text
- Support both live interview mode and recorded video analysis mode
- Analyze posture during answers
- Analyze speech during answers
- Show final feedback and scoring after the full interview session
- Optional client-side overlay showing posture keypoints and posture judgment state

### Admin/Operations Features
- Latency and processing-time monitoring UI
- Queue/work distribution visibility
- User session lookup and review
- Concurrent user capacity measurement dashboard
- Show both validated benchmark capacity and real-time estimated safe capacity
- Show which users are currently active
- Show what processing step each active user is currently in
- Show login session duration per active user
- Use `.env`-based configuration

## 3. Suggested Architecture

### Frontend
- Electron shell for desktop packaging
- React app for the main UI
- WebSocket client for streaming state, analysis events, and progress
- MediaPipe-based local posture analysis path
- Canvas overlay renderer for posture keypoints, skeleton lines, and judgment badges
- Local performance probe to decide when to keep analysis on the client or switch to the server

### Backend
- FastAPI API service
- Separate API and worker responsibilities for scalability
- Redis queue for async processing
- PostgreSQL for users, sessions, answers, scores, and metrics
- LangGraph pipeline for:
  - question generation
  - answer evaluation
  - feedback generation
- OpenAI STT integration with `gpt-4o-transcribe`

### Deployment
- Single `docker-compose` stack for:
  - `api`
  - `worker`
  - `postgres`
  - `redis`

## 4. Data Model Draft
- `users`
- `job_categories`
- `interview_sessions`
- `questions`
- `answers`
- `posture_events`
- `speech_metrics`
- `feedback_reports`
- `system_metrics`
- `active_runtime_sessions`

## 5. Delivery Phases

### Phase 1. Foundation
- Initialize project structure with `frontend` and `backend`
- Set up Electron + React app structure
- Set up FastAPI project structure
- Add Docker Compose for PostgreSQL and Redis
- Add SQLAlchemy, Pydantic, and Alembic baseline
- Add `.env.example`

### Phase 2. Authentication and Basic UI
- Implement local account-based login/logout
- Build responsive layout:
  - status panel
  - menu
  - main content area
- Add job-category selection flow

### Phase 3. Interview Session Flow
- Create session lifecycle:
  - create session
  - generate question
  - collect answer
  - store result
- Add text-answer flow first
- Connect LangGraph question/feedback pipeline
- Show final combined feedback after session completion
- Default interview rule:
  - 5 questions per session
  - 1 minute answer time per question
  - re-answer allowed

### Phase 4. Voice Analysis
- Add microphone capture
- Convert Korean speech to text with `gpt-4o-transcribe`
- Upload audio to STT per question/answer segment
- Measure speaking speed, filler/repetition, and pauses
- Merge speech metrics into answer evaluation

### Phase 5. Video/Posture Analysis
- Add webcam and recorded-video input in MVP
- Implement local performance probe
- Add local MediaPipe posture analysis
- Add backend fallback analysis channel
- Add optional overlay for:
  - body keypoints
  - skeleton connections
  - real-time posture judgment labels
- Add user control to toggle overlay visibility on/off
- Overlay default state: OFF on first launch
- Define posture issue taxonomy:
  - shoulder asymmetry
  - unstable hand movement
  - shaking
  - gaze/head instability

### Phase 6. Realtime Transport and Queueing
- Add WebSocket streaming
- Introduce Redis-backed job queue
- Split API and worker responsibilities
- Implement progress/status events for frontend

### Phase 7. Monitoring and Admin Tools
- Track request latency, inference time, queue delay, and worker throughput
- Expose admin-only monitoring screen
- Add session list/detail view for admin users
- Show active concurrent sessions and estimated safe concurrent capacity
- Show benchmark-based maximum validated concurrent users alongside current real-time estimate
- Show per-user active state, current processing stage, and login session duration
- Use mixed cards + charts layout
- Add structured logs

### Phase 8. Stabilization
- E2E tests for interview flow
- Failure handling for camera, mic, network, and model timeouts
- Packaging and release workflow

## 6. Recommended Build Order
1. Backend foundation and DB
2. Frontend shell and responsive UI
3. Text-based interview flow with LLM
4. Voice capture and speech metrics
5. Video/posture analysis
6. WebSocket + queue scaling
7. Admin monitoring
8. QA and packaging

## 7. MVP Definition
- Login/logout with local accounts
- 8 job categories:
  - 경영/인사
  - 회계
  - IT
  - R&D
  - 제조
  - 유통
  - 공공
  - 일반 사무
- Text answer + voice answer support
- LLM question generation and answer feedback
- OpenAI-based Korean STT + basic speech metrics
- STT request pattern: per-question audio upload
- Live webcam posture analysis with local-first / server-fallback switch
- Recorded-video analysis support
- Recorded-video constraints:
  - max duration: 10 minutes
  - max size: 500 MB
  - supported formats: MP4, AVI
- Interview defaults:
  - 5 questions per session
  - 1 minute per answer
  - re-answer allowed
- On-screen posture keypoint/judgment overlay with user on/off toggle
- Overlay default state: OFF on first launch
- Session history persisted in PostgreSQL
- Final feedback report shown after interview completion
- Admin session lookup
- Admin dashboard for active concurrent users and capacity estimate
- Dashboard shows both tested maximum concurrency and current estimated safe concurrency
- Admin session detail shows active users, current task/processing status, and login session duration

## 8. Main Risks
- Real-time latency may vary significantly by user machine
- Local posture analysis quality may differ across cameras and lighting
- Queue/worker architecture adds complexity early
- Speech analysis quality depends on STT quality and noisy audio conditions
- Electron packaging and media permissions may require platform-specific handling

## 9. Confirmed Product Decisions
- Platform: Electron-only desktop app
- Language support at launch: Korean only
- Authentication: local account system only
- MVP includes recorded-video upload/analysis
- Recorded-video constraints: up to 10 minutes, 500 MB, MP4/AVI
- Feedback timing: show once after the interview session ends
- Speech-to-text: OpenAI-based Korean STT
- STT model: `gpt-4o-transcribe`
- STT request mode: upload per question/answer unit, not continuous realtime streaming
- Interview defaults: 5 questions, 1 minute per answer, re-answer allowed
- Admin scope: metrics visibility + user session lookup + concurrent user/capacity dashboard, without reprocessing controls
- Admin detail scope: active users, current processing status, login session duration
- Admin UI style: mixed cards + charts
- Capacity display policy: show both fixed benchmark maximum and real-time estimated safe capacity
- Real-time capacity formula: bottleneck-based `min(api_capacity, worker_capacity, stt_capacity, posture_capacity)`
- Overlay default policy: OFF at first launch
- Posture overlay scope: upper-body core keypoints only
- Local-to-server switching policy: use the recommended multi-signal threshold rule

## 10. Recommended Choices To Confirm

### A. Concurrent Capacity Formula
- Confirmed: use both fixed benchmark maximum and real-time estimated safe capacity
- Recommended real-time formula:
  - `safe_estimated_concurrency_now = min(api_capacity, worker_capacity, stt_capacity, posture_capacity)`
- Each capacity should be derived from the current bottleneck:
  - `api_capacity`: based on API p95 latency staying within target
  - `worker_capacity`: based on queue wait p95 staying within target
  - `stt_capacity`: based on average STT turnaround per answer unit
  - `posture_capacity`: based on average posture analysis turnaround per sampled batch
- Recommended thresholds:
  - API p95 latency <= 1500 ms
  - queue wait p95 <= 3000 ms
  - STT average turnaround <= 8000 ms
  - posture analysis average turnaround <= 1000 ms

### B. Posture Overlay Display Scope
- Confirmed: start with upper-body core only
- Default points:
  - nose
  - left/right ear
  - left/right shoulder
  - left/right elbow
  - left/right wrist
- Optional expansion later:
  - minimal hand fingertip points
  - minimal face direction points
- Recommendation: do not draw full face mesh by default

### C. Local-To-Server Switching Rule
- Confirmed: switch to server processing if any condition is met for 3 consecutive checks:
  - local posture inference time > 200 ms
  - effective local analysis FPS < 4
  - renderer + analysis combined main-thread busy ratio > 70%
  - landmark detection confidence remains low for more than 2 seconds
- Confirmed: return to local processing only after recovery margin is satisfied for 5 consecutive checks:
  - local posture inference time < 140 ms
  - effective local analysis FPS >= 5
  - main-thread busy ratio < 55%
