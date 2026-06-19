# Schedula Backend

FastAPI backend for Schedula. It manages authentication, lecturer/secretary APIs, database access, RabbitMQ messaging, LLM-powered constraint processing, WebSocket progress updates, and scheduler-driven automation.

## What This Service Does

- Serves external REST APIs for lecturer and secretary workflows.
- Persists data in PostgreSQL via async `asyncpg` repositories (no ORM).
- Publishes solver requests to RabbitMQ and consumes solver responses.
- Publishes notification events for the notification service.
- Runs scheduled jobs (nightly solver run + semester period transition checks).
- Proxies Telegram webhook requests to the notification service.
- Provides development-only CRUD and helper routes under `/dev`.

## Tech Stack

- Python 3.12+
- FastAPI + Uvicorn
- asyncpg
- aio-pika (RabbitMQ)
- Pydantic v2 + pydantic-settings
- APScheduler
- python-jose + passlib (JWT auth)
- httpx (Telegram webhook proxy + outbound HTTP)
- websockets (constraint pipeline progress)

## Repository Layout

```text
SchedulaBackend/
  pyproject.toml
  uv.lock
  README.md
  .env.example
  Dockerfile
  src/
    main.py
    config.py
    scheduler.py
    database/
      database.py
      init_db.sql
    middleware/
      auth.py
      logging.py
    rabbitmq/
      rabbitmq.py
      consumer.py
    notifications/
      ...
    websocket/
      ...
    llm_pipeline/
      ...
    routes/
      db.py
      rabbitmq.py
      webhooks.py
      ws.py
      external/
        auth.py
        lecturer/
        secretary/
      dev_routes/
        README.md
        ...
    repositories/
      ...
    models/
      ...
    input_convertor/
      ...
    utils/
      ...
    validators/
      ...
  tests/
    ...
```

## Runtime Architecture

- On startup (`src/main.py`):
  - Connects to PostgreSQL.
  - Connects to RabbitMQ.
  - Starts solver response consumer (`constraints_response_queue`).
  - Starts APScheduler jobs.
- On shutdown: cancels consumer, stops scheduler, disconnects RabbitMQ and DB.

### Scheduler Jobs

- `nightly_solver_run`: daily at 02:00, creates solver runs for active semesters (`SUB`, `REV`, `CHA`) and publishes to `constraints_request_queue`.
- `period_transition_check`: every 30 minutes (UTC), checks semester period/status transitions and emits notification events.

## Configuration

Settings are loaded from environment variables (case-insensitive) and may be placed in `.env` (see `.env.example`).

Important variables:

- `DATABASE_URL`
- `DATABASE_POOL_MIN_SIZE`
- `DATABASE_POOL_MAX_SIZE`
- `RABBITMQ_URL`
- `NOTIFICATION_QUEUE_NAME`
- `NOTIFICATION_SERVICE_BASE_URL`
- `LLM_PROVIDER` (`ollama`, `groq`, or `university`)
- `OLLAMA_URL`
- `OLLAMA_MODEL`
- `GROQ_API_KEY`
- `GROQ_MODEL`
- `UNIVERSITY_URL` (used when `LLM_PROVIDER=university`)
- `UNIVERSITY_VERIFY_SSL` (defaults to `false` for the campus self-signed cert)
- `FRONTEND_BASE_URL` (used in lecturer notification deep links)
- `APP_NAME`, `DEBUG`
- `ENABLE_DEV_ROUTES`
- `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`

Security note:

- Replace default JWT settings in non-development environments.

## Local Development

### 1) Install dependencies

```powershell
# from SchedulaBackend/
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### 2) Start required infrastructure

This backend requires PostgreSQL, RabbitMQ, solver, and notification service. The recommended way is to run the full stack from the sibling deployment repo:

```powershell
cd ..\SchedulaDeployment
docker compose up --build
```

### 3) Run backend directly (optional, for backend-only iteration)

```powershell
cd ..\SchedulaBackend
python src/main.py
```

or

```powershell
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Bootstrap and Health

Initialize schema:

```powershell
curl -X POST http://localhost:8000/db/init
```

Health checks:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/db/health
curl http://localhost:8000/rabbitmq/health
```

## API Surface

Docs:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

Public route groups (no JWT enforcement):

- `/auth/*`
- `/dev/*` (when enabled)
- `/docs`, `/redoc`, `/openapi.json`
- `/ws/*`
- `/webhooks/*`
- `/health`
- `/db/*` (includes destructive `POST /db/init` and `DELETE /db/clear`)
- `/rabbitmq/*`

Protected route groups (JWT + role-based middleware):

- `/lecturer/*` requires role `L`
- `/secretary/*` requires role `S`

The `AuthenticationMiddleware` only enforces JWT on prefixes listed in `PROTECTED_PREFIXES` (`/lecturer`, `/secretary`); everything else passes through. Network-level controls should be used to restrict access to `/db/*` and `/rabbitmq/*` in non-development environments.

High-level route groups:

- `/auth` login/logout
- `/lecturer/constraints`, `/lecturer/schedules`, `/lecturer/dashboard`, `/lecturer/notifications`
- `/secretary/setup`, `/secretary/semesters`, `/secretary/schedules`, `/secretary/dashboard`, `/secretary/breaking-constraints`, `/secretary/manage-constraints`, `/secretary/fairness`
- `/db` database admin endpoints (init/clear/health)
- `/rabbitmq` publish/debug endpoints
- `/ws` realtime pipeline progress
- `/webhooks/telegram` Telegram webhook proxy

## Notifications and Webhooks

The backend publishes notification events to RabbitMQ (`notification_queue_name`, default `notifications_queue`) which the notification service consumes. There are two producer modules:

- `src/notifications/period_events.py` - period and semester-status transitions.
  - Emitted from the `period_transition_check` scheduler job and from immediate checks triggered when a secretary updates a semester (`POST/PUT /secretary/semesters`).
  - Message types include `period_transition` and semester `status` change events.
- `src/notifications/lecturer_events.py` - lecturer-targeted events (schema v2.0 envelopes):
  - `lecturer_constraint_saved` - emitted from `routes/external/lecturer/constraints.py` when a lecturer saves their constraints.
  - `lecturer_constraint_edited_by_secretary` - emitted from `routes/external/secretary/manage_constraints.py`.
  - `schedule_published` - emitted from `routes/external/secretary/schedules.py`, fan-out to all lecturers assigned to offerings in the published schedule.
  - Deep-link URLs are built from `FRONTEND_BASE_URL`.

Solver responses (`constraints_response_queue`) are consumed by `src/rabbitmq/consumer.py` and only update the `solver_runs` row in the database. They no longer publish notification events directly; notifications related to schedule outcomes are produced explicitly by the routes that publish a schedule (see `schedule_published` above). This is regression-tested in `tests/notifications/test_solver_result_removed.py`.

Telegram webhook updates are accepted on `POST /webhooks/telegram` and forwarded as-is to `${NOTIFICATION_SERVICE_BASE_URL}/webhooks/telegram` by `src/routes/webhooks.py`.

## Development Routes

When `ENABLE_DEV_ROUTES=true`, backend mounts `/dev/*` CRUD/helper endpoints for development and integration testing.

See: `src/routes/dev_routes/README.md`

## Testing

```powershell
pytest tests/
```

## Related Repositories

- `SchedulaDeployment`: docker-compose orchestration, solver service, notification service.
- `SchedulaFrontend`: React frontend that consumes backend APIs.



