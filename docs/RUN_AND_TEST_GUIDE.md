# Run And Test Guide

## Overview
This guide covers:
- Docker services start/stop
- test account information
- backend start/stop
- frontend start/stop
- worker start/stop
- basic verification commands

## Test Accounts
- Admin
  - email: `admin@example.com`
  - password: `admin1234!`
- User
  - email: `user@example.com`
  - password: `user1234!`

## Default Local Ports
- Backend API: `8000`
- PostgreSQL: `55432`
- Redis: `56379`
- Frontend Vite dev server: usually `5173`

## Prerequisites
- Python virtual environment created at `backend/.venv`
- Backend dependencies installed from `backend/requirements/base.txt`
- Frontend dependencies installed with `npm install`
- Project root `.env` file present if you want Docker `api` service to read env values

## Docker Start
Start PostgreSQL and Redis only:

```powershell
docker compose -f infra/compose/docker-compose.yml up -d postgres redis
```

Start PostgreSQL, Redis, and API container together:

```powershell
docker compose -f infra/compose/docker-compose.yml up -d postgres redis
```

Check status:

```powershell
docker compose -f infra/compose/docker-compose.yml ps
```

View logs:

```powershell
docker compose -f infra/compose/docker-compose.yml logs -f postgres redis
```

## Docker Stop
Stop containers but keep volumes:

```powershell
docker compose -f infra/compose/docker-compose.yml down
```

Stop containers and remove Postgres volume data too:

```powershell
docker compose -f infra/compose/docker-compose.yml down -v
```

## Backend Start
Move to backend:

```powershell
cd backend
```

Apply migrations:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Run API locally:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Backend health check:

```powershell
curl http://localhost:8000/health
```

## Backend Stop
- If running in the terminal directly, press `Ctrl+C`
- If running in Docker, use:

```powershell
Docker API container is no longer used. Run the backend locally with `uvicorn` instead.
```

## Frontend Start
Move to frontend:

```powershell
cd frontend
```

Run Vite dev server:

```powershell
npm run dev
```

Optional production-style Electron run:

```powershell
npm run electron:prod
```

## Frontend Stop
- If running in the terminal directly, press `Ctrl+C`

## Worker Start
Make sure Redis is running first.

Run one worker pass:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.workers.processing_worker --once
```

Run the worker continuously:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.workers.processing_worker
```

## Worker Stop
- If running in the terminal directly, press `Ctrl+C`

## Basic Test Flow
1. Start `postgres` and `redis`
2. Run Alembic migrations
3. Start backend
4. Start worker
5. Start frontend
6. Login with one of the test accounts

## Smoke Tests
Run backend smoke tests:

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest tests.test_api_smoke
```

## Useful Manual Checks
Admin login and profile:

```powershell
curl -X POST http://localhost:8000/api/v1/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"admin@example.com\",\"password\":\"admin1234!\"}"
```

User login:

```powershell
curl -X POST http://localhost:8000/api/v1/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"user@example.com\",\"password\":\"user1234!\"}"
```

## Notes
- Current queue behavior supports Redis-backed worker processing with inline fallback if Redis is unavailable.
- Current password hashing uses `bcrypt`.
- Current backend smoke test file is `backend/tests/test_api_smoke.py`.
