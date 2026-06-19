# Schedula AI Coding Instructions

## Project Overview

Schedula is a microservices-based course scheduling system.

- **Backend:** FastAPI (Python) handling API, DB, and LLM processing.
- **Solver:** Python service using Google OR-Tools CP-SAT to solve scheduling constraints via CSP (Constraint Satisfaction Programming).
- **Notification Service:** Python service using Apprise for notifications.
- **Infrastructure:** Docker Compose, PostgreSQL, RabbitMQ, Ollama/Groq.

## Architecture & Data Flow

- **Communication:** Services communicate asynchronously via RabbitMQ (`aio_pika`).
  - **Solver:** Polls `constraints_request_queue`, publishes to `constraints_response_queue`.
  - **Backend Consumer:** Listens on `constraints_response_queue` to process solver results.
  - **Notifications:** Listens on `notifications_queue`.
- **Database:** PostgreSQL accessed via `asyncpg` with connection pooling.
- **LLM:** Backend integrates with Ollama (local) or Groq (cloud) via `src/llm_pipeline` for constraint processing.
- **Scheduler:** APScheduler runs automated tasks (nightly solver runs at 2:00 AM for active semesters).

## Backend Development (`SchedulaBackend`)

- **Framework:** FastAPI with Pydantic v2.
- **Database:** Raw SQL with `asyncpg`. No ORM. Use `src/database/database.py` for connection.
- **Authentication:** JWT-based with role-based access control (RBAC).
  - Middleware: `src/middleware/auth.py` automatically validates tokens and enforces role-based access.
  - Roles: "L" (Lecturer), "S" (Secretary).
  - Protected routes: `/lecturer/*` (requires "L"), `/secretary/*` (requires "S").
  - Public routes: `/auth/*`, `/dev/*`, `/docs`, `/openapi.json`, `/redoc`.
  - Auth utilities: `src/utils/auth.py` for token encoding/decoding.
- **Dev Routes:** `src/routes/dev_routes` contains CRUD endpoints for testing. Enabled via `enable_dev_routes` setting.
- **Configuration:** `src/config.py` uses `pydantic-settings`.
  - Supports multiple LLM providers: `ollama` (local) or `groq` (cloud API).
  - JWT settings: `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`.
- **Logging:** Custom `LoggingMiddleware` in `src/middleware/logging.py`.
- **Scheduler:** `src/scheduler.py` uses APScheduler for automated nightly solver runs (2:00 AM) for active semesters (SUB/REV/CHA status).
- **RabbitMQ Consumer:** `src/rabbitmq/consumer.py` listens on `constraints_response_queue` and persists solver results to database.

## Deployment & Services (`SchedulaDeployment`)

- **Orchestration:** `docker-compose.yml` defines all services.
- **Profiles:** Backend has `cpu` and `gpu` profiles for different Ollama models.
- **Solver:** Located in `solver/`. Uses Google OR-Tools CP-SAT solver for constraint satisfaction programming.
  - Implements intelligent batching logic (waits for more messages before solving).
  - Detects conflicts and returns minimal unsatisfiable subsets (MUS) when scheduling fails.
  - See `SOLVER_DOCUMENTATION.md` for complete technical details.
- **Notification:** Located in `notification_service/`. Uses Apprise.

## Critical Workflows

- **Run Local:** `docker-compose up --build`
- **Run Backend Dev:** `python src/main.py` (ensure Postgres/RabbitMQ are running).
- **Testing:**
  - Backend: `pytest tests/`
  - Solver: `pytest tests/` (inside `solver` directory in SchedulaDeployment)
  - Integration Tests: `pytest tests/test_happy_path.py`, `test_failure_path.py`, etc.

## Key Features

### Breaking Constraints

- System tracks constraints that cannot be satisfied together during scheduling.
- Solver identifies minimal unsatisfiable subsets (MUS) when scheduling fails.
- Breaking constraints stored in `breaking_constraints` table with grouping by `constraints_id`.
- Secretary can view and mark breaking constraints as seen.
- API endpoints: `/secretary/breaking-constraints` (list, mark as seen).

### Fairness Reports

- Track fairness metrics for generated schedules.
- Stored in `fairness_reports` table linked to schedules.
- Dev routes available for CRUD operations.

### Dashboard

- Lecturer dashboard shows courses, schedules, and constraints.
- Secretary dashboard shows semester stats, solver runs, and breaking constraints.
- Endpoints: `/lecturer/dashboard`, `/secretary/dashboard`.

### LLM Pipeline

- Multi-stage constraint processing pipeline (Stages 0-9).
- Stage 0: Input validation and clarification.
- Stages 1-9: Full constraint parsing and extraction.
- WRAP Stage: Conflict resolution for contradictory constraints.
- Supports both Ollama (local) and Groq (cloud) providers.

## Conventions

- **Async/Await:** Use `async` for all I/O (DB, RabbitMQ, HTTP).
- **Type Hinting:** Strict type hints required.
- **Error Handling:** Use `HTTPException` in routes. Log errors before raising.
- **RabbitMQ:** Use the global `rabbitmq` instance in `src/rabbitmq/rabbitmq.py`.
- **Environment:** Use `.env` files or environment variables for config.

## Coding Standards

For detailed implementation patterns, conventions, and best practices, refer to [`STANDARDS.md`](../../STANDARDS.md) in the project root. It covers:

- **Pydantic Models:** Base class, validators, and field validation
- **Repositories:** CRUD patterns, return types, and helper functions
- **Routes:** API response patterns, error handling, and status codes
- **Type Hints:** Complete type annotations requirements
- **Testing:** Unit and integration test patterns

## Key Files

- `SchedulaBackend/src/main.py`: App entry point, lifespan manager.
- `SchedulaBackend/src/scheduler.py`: APScheduler for automated nightly solver runs.
- `SchedulaBackend/src/rabbitmq/rabbitmq.py`: RabbitMQ connection manager.
- `SchedulaBackend/src/rabbitmq/consumer.py`: Consumer for solver response queue.
- `SchedulaBackend/src/middleware/auth.py`: JWT authentication and RBAC middleware.
- `SchedulaBackend/src/config.py`: Application configuration with LLM provider settings.
- `SchedulaBackend/src/llm_pipeline/`: Logic for LLM constraint processing.
- `SchedulaBackend/src/routes/external/lecturer/`: Lecturer-specific API endpoints.
- `SchedulaBackend/src/routes/external/secretary/`: Secretary-specific API endpoints.
- `SchedulaBackend/STANDARDS.md`: Detailed coding standards and patterns.
- `SchedulaDeployment/docker-compose.yml`: Service definitions.
- `SchedulaDeployment/SOLVER_DOCUMENTATION.md`: Complete solver technical documentation.
- `SchedulaDeployment/solver/src/solver.py`: OR-Tools CP-SAT solver implementation.
