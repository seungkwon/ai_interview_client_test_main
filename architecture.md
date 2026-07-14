# AI Interview v2 Architecture

## 1. Repository Structure

```text
ai_interview_new/
  frontend/
    electron/
      main/
      preload/
    src/
      app/
      pages/
      features/
        auth/
        interview/
        posture/
        speech/
        admin/
      components/
      hooks/
      services/
      workers/
      styles/
      types/
    public/
    package.json
    vite.config.ts
  backend/
    app/
      api/
        v1/
          endpoints/
      core/
      db/
      models/
      schemas/
      services/
        auth/
        interview/
        posture/
        speech/
        admin/
        llm/
        queue/
      workers/
      websocket/
      tests/
    alembic/
    requirements/
    Dockerfile
  infra/
    docker/
      postgres/
      redis/
    compose/
      docker-compose.yml
  docs/
    architecture.md
    db_schema.md
    api_spec.md
  .env.example
  plan.md
  project_plan.md
```

## 2. Frontend Responsibility Split

### Electron Main
- app lifecycle
- secure window creation
- file dialog for recorded video selection
- native permission handling when needed

### Electron Preload
- expose safe IPC bridge
- file selection
- app version/system info
- optional local media capability checks

### React Renderer
- login flow
- job-category selection
- interview session UI
- live video stage
- recorded video analysis flow
- admin dashboard

### Web Worker
- posture feature post-processing
- event scoring
- overlay preparation payloads

## 3. Frontend Feature Modules

### `features/auth`
- login form
- logout action
- auth token/session storage

### `features/interview`
- session creation
- question display
- timer handling
- answer submit/re-answer
- final report UI

### `features/posture`
- MediaPipe integration
- 5 FPS sampling
- local/server switching
- canvas overlay rendering
- posture event aggregation

### `features/speech`
- mic capture
- answer-segment audio buffering
- upload to backend STT endpoint
- speaking speed / filler / pause metrics display

### `features/admin`
- active user cards
- concurrency/capacity charts
- latency charts
- session detail table

## 4. Backend Responsibility Split

### API Service
- authentication
- session CRUD
- question generation trigger
- answer submit
- final report retrieval
- admin metrics/session views
- upload endpoints
- websocket session state broadcast

### Worker Service
- STT request handling
- posture fallback processing
- LangGraph evaluation jobs
- report generation jobs
- metrics aggregation jobs

## 5. Processing Flow

### Live Interview Flow
1. User logs in.
2. User selects a job category.
3. Frontend creates interview session.
4. Backend creates first question through LangGraph.
5. User answers with text or voice while posture analysis runs.
6. Frontend stores local posture events and sends summaries or fallback frames/events to backend.
7. Voice answer is uploaded per question to backend.
8. Backend runs STT, merges speech metrics, and queues evaluation.
9. Repeat for 5 questions.
10. Backend builds final report and frontend renders it.

### Recorded Video Flow
1. User uploads/selects recorded file.
2. Frontend validates size, duration, and format.
3. Frontend uploads metadata and file.
4. Backend queues posture/speech analysis.
5. Frontend receives progress via WebSocket.
6. Final report is shown when job completes.

## 6. Posture Analysis Runtime

### Local Path
- input video remains smooth at display FPS
- analysis samples at 5 FPS
- MediaPipe extracts core upper-body keypoints
- worker computes posture features and events
- canvas overlay draws only when enabled

### Server Fallback Path
- activated by multi-signal threshold rule
- send sampled frames or extracted landmarks/events
- backend worker performs posture scoring
- backend streams progress and results back

## 7. Security and Session Notes
- local account auth only
- admin role flag required for admin dashboard routes
- avoid exposing raw OpenAI key to frontend
- frontend should upload answer audio/video only to backend
- websocket auth should use short-lived session token or bearer token validation

## 8. Initial Milestone Output
- working auth shell
- session create/question flow
- per-question answer upload
- local posture analysis skeleton
- admin active session dashboard
