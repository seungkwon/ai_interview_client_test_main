# AI Interview v2

Electron + React frontend and FastAPI backend for AI-powered interview practice.

## Structure
- `frontend`: Electron shell and React renderer
- `backend`: FastAPI API, worker-ready service layout
- `infra/compose`: Docker Compose for PostgreSQL and Redis
- `docs`: copied design docs and future documentation

## Current Status
- backend API flows are DB-backed for auth, interview, posture, recorded analysis, and admin
- JWT tokens are validated against active login sessions
- test account passwords are stored with bcrypt hashing
- Redis-backed processing queue and worker path are implemented with inline fallback
- frontend React dashboard and Electron build pipeline are wired and build successfully

## Environment
Copy `.env.example` to `.env` and fill in secrets before running services.
Default local ports are `55432` for PostgreSQL, `56379` for Redis, and `8000` for the API.
For local runs, use `POSTGRES_HOST=localhost` and `REDIS_HOST=localhost`. Docker Compose is used only for `postgres` and `redis`, while the API runs locally with `uvicorn`.

## Test Accounts
- Admin: `admin@example.com` / `admin1234!`
- User: `user@example.com` / `user1234!`

## Backend Setup
1. `cd backend`
2. `python -m venv .venv`
3. `.\\.venv\\Scripts\\python -m pip install -r requirements\\base.txt`
4. `.\\.venv\\Scripts\\python -m uvicorn app.main:app --reload`

## Worker Setup
1. Start Redis first. For local Docker Compose: `docker compose -f infra/compose/docker-compose.yml up -d redis`
2. `cd backend`
3. Run one job-processing pass: `.\\.venv\\Scripts\\python -m app.workers.processing_worker --once`
4. Run the worker loop continuously: `.\\.venv\\Scripts\\python -m app.workers.processing_worker`

## Backend Tests
1. `cd backend`
2. Run smoke tests: `.\\.venv\\Scripts\\python -m unittest tests.test_api_smoke`

## Frontend Setup
1. `cd frontend`
2. `npm install`
3. `npm run dev`

## Electron Build
1. `cd frontend`
2. `npm run build`
3. `npm run electron:prod`

## Next Work
1. decide whether to keep inline queue fallback or require worker availability in every environment
2. expand automated test coverage beyond smoke tests
3. integrate real STT, LLM evaluation, and posture pipelines
4. connect richer real-time interview events if needed
