# Progress Handoff

Last updated: 2026-07-09

## Current Repository State
- Backend: FastAPI with SQLAlchemy models, Alembic initial migration, JWT auth scaffold, and mixed DB-backed/mock fallback services.
- Frontend: React renderer wired to backend mock/API flow, Electron build pipeline working.
- Infra: Docker Compose for API/Postgres/Redis, with local default ports shifted to avoid conflicts.

## Recent Commits
- `69644b8` Extract shared time helper from dev store
- `72f2ce3` Record interview processing jobs
- `fae711c` Move interview flow to DB-only state
- `73f2354` Remove admin memory fallback
- `5ce4651` Validate JWT tokens against active login sessions
- `6a59a69` Remove posture memory fallback
- `1ce61a5` Remove recorded analysis memory fallback
- `7e4fb60` Persist recorded analysis ownership in processing jobs
- `6da0884` Enforce recorded analysis ownership and add handoff
- `ed0cef1` Enforce interview ownership for user-scoped routes
- `491c074` Require auth for interview and analysis endpoints
- `0cbec87` Add JWT auth and protect admin endpoints
- `cc521bb` Persist admin and analysis flows with database-backed services
- `898a1ec` Fix seeded dev user and verify DB-backed interview flow
- `8ae4f36` Change default local service ports
- `0814257` Add initial Alembic migration and seeded schema
- `5894838` Add database-backed interview persistence scaffolding
- `75e8818` Implement mocked interview flow and Electron build pipeline

## Verified Working
- Backend dependencies installed in `backend/.venv`.
- Frontend dependencies installed and `npm run build` passes.
- Electron renderer + main/preload build passes.
- Alembic `upgrade head` succeeded against project Postgres on local port `55432`.
- `job_categories` seed inserted successfully.
- Interview full-cycle DB persistence verified:
  - `interview_sessions` increases
  - `answers` increases
  - `feedback_reports` increases
- Posture and recorded-analysis endpoints now leave DB traces:
  - `posture_metrics`
  - `posture_events`
  - `processing_jobs`
- JWT auth behavior verified:
  - login returns token
  - `/auth/me` works with bearer token
  - `/admin/overview` returns `401` without token
- Protected route behavior verified:
  - `/interviews` returns `401` without token
  - authenticated interview/posture/recorded-analysis requests return `200`
- Interview ownership enforcement verified for user-scoped routes.
- Recorded-analysis DB ownership and status lookup verified after Alembic `20260709_0002`.
- Recorded-analysis service now runs DB-only without `dev_store.recorded_analyses` fallback.
- Posture service now validates sessions and persists summaries DB-only without `store.posture_summaries`.
- JWT bearer validation now checks active `login_sessions` rows, and logged-out tokens return `401`.
- Login now validates actual seeded users by email/password instead of issuing a shared dev-admin token.
- Test account passwords are now bcrypt-hashed, with current DBs updated through Alembic `20260709_0004`.
- Admin service now runs DB-only for overview, active sessions, and interview detail.
- Interview service now runs DB-only for session, question, answer, next, and report flow.
- Interview flow now creates `processing_jobs` rows for evaluation, STT, and report generation.
- Shared `utc_now()` helper moved out of `dev_store`; service-layer `store` usage has been eliminated.
- Legacy `backend/app/services/dev_store.py` has been removed entirely.
- Redis worker path verified: enqueue -> `app.workers.processing_worker` consume -> DB status completion.
- Redis-backed queue enqueue plus worker consumption path is now implemented and verified.
- `backend/tests/test_api_smoke.py` added for auth/logout and DB-backed interview smoke coverage.
- `python -m unittest tests.test_api_smoke` passes in `backend/.venv`.

## Handoff Snapshot
- This handoff is intended to be committed together with the recorded-analysis ownership update.
- After this commit, the expected next step is to restart from this file and continue DB-first cleanup work.

## Important Runtime Defaults
- PostgreSQL host/port for local runs: `localhost:55432`
- Redis host/port for local runs: `localhost:56379`
- API port: `8000`
- Test admin account: `admin@example.com` / `admin1234!`
- Test user account: `user@example.com` / `user1234!`
- Compose API container overrides internal service hosts:
  - `POSTGRES_HOST=postgres`
  - `POSTGRES_PORT=5432`
  - `REDIS_HOST=redis`
  - `REDIS_PORT=6379`

## Key Files
- Backend config: `backend/app/core/config.py`
- JWT/auth helpers: `backend/app/core/security.py`
- Alembic config: `backend/alembic.ini`
- Initial migration: `backend/alembic/versions/20260709_0001_initial_schema.py`
- Processing-job ownership migration: `backend/alembic/versions/20260709_0002_processing_job_user_id.py`
- Test account seed migration: `backend/alembic/versions/20260709_0003_seed_test_accounts.py`
- Bcrypt seed hash migration: `backend/alembic/versions/20260709_0004_bcrypt_seed_hashes.py`
- Interview service: `backend/app/services/interview/service.py`
- Auth service: `backend/app/services/auth/service.py`
- Admin service: `backend/app/services/admin/service.py`
- Posture service: `backend/app/services/posture_service.py`
- Recorded analysis service: `backend/app/services/recorded_analysis_service.py`
- Frontend app: `frontend/src/app/App.tsx`
- Frontend API client: `frontend/src/app/api.ts`

## Suggested Next Steps
1. Decide whether to keep the current Redis queue with inline fallback, or remove the fallback and require worker availability in all environments.
2. Expand automated tests beyond the current smoke coverage:
   - JWT protected routes
   - interview ownership checks
   - DB persistence for posture and recorded analysis
   - full DB-only interview lifecycle
   - interview `processing_jobs` generation
   - Redis worker dequeue and completion flow

## Recommended Restart Procedure
1. Open this file first: `docs/PROGRESS_HANDOFF.md`
2. Check working tree: `git status --short`
3. If continuing backend work, inspect:
   - `backend/app/services/recorded_analysis_service.py`
   - `backend/app/api/v1/endpoints/recorded_analysis.py`
   - `backend/alembic/versions/20260709_0002_processing_job_user_id.py`
4. Run targeted verification after changes:
   - auth login/me/admin protection
   - interview create/start/answer/report
   - posture local-summary persistence
   - recorded-analysis create/status ownership
