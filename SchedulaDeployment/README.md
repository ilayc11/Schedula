# Schedula Deployment

Deployment and orchestration repository for the Schedula microservices stack.

This repository contains:

- Docker Compose orchestration for backend, solver, notification service, database, RabbitMQ, frontend, and optional GPU LLM runtime.
- Service-specific subprojects (`solver/`, `notification_service/`).
- End-to-end integration tests (`tests/`) for the full scheduling pipeline.

## Services

`docker-compose.yml` defines the following services:

- `postgres` - primary relational database.
- `rabbitmq` - async messaging broker between services.
- `backend` - FastAPI backend (CPU profile).
- `backend-gpu` - FastAPI backend (GPU profile, uses Ollama).
- `solver` - OR-Tools CP-SAT scheduling solver.
- `notification` - notification delivery and Telegram linking/webhook handler.
- `frontend` - React app (CPU profile).
- `frontend-gpu` - React app wired to `backend-gpu`.
- `ollama-gpu` - optional local LLM runtime for GPU profile.
- `cloudflared-backend` - optional tunnel for exposing backend webhook endpoint.

## Profiles

- CPU stack:

```powershell
docker compose --profile cpu up --build
```

- GPU stack:

```powershell
docker compose --profile gpu up --build
```

The profile controls which backend/frontend variant is started.

## Typical Local Workflow

1. Start the stack (CPU or GPU profile).
2. Initialize backend schema once:

```powershell
curl -X POST http://localhost:8000/db/init
```

3. Open:
	- Frontend: `http://localhost:5173`
	- Backend docs: `http://localhost:8000/docs`
	- Notification health: `http://localhost:8001/health`

## Key Environment Variables

See `.env.example` for defaults/overrides.

- `NOTIFICATION_SERVICE_BASE_URL`
- `NOTIFICATION_QUEUE_NAME`
- `TELEGRAM_BOT_NAME`
- `TELEGRAM_LINK_TOKEN_TTL_SECONDS`
- `APPRISE_URLS`
- `CLOUDFLARED_TUNNEL_TOKEN`
- `RABBITMQ_URL`
- `DATABASE_URL`

## Integration Tests

The integration suite lives in `tests/` and validates end-to-end flow:

`Backend API -> RabbitMQ -> Solver -> Database`

Run tests:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pytest tests/ -v -s
```

For full scenario details, see `tests/README.md`.

## Solver and Notification Service Docs

- Solver details: `solver/README.md` and `SOLVER_DOCUMENTATION.md`
- Notification + Telegram linking/webhook flows: `notification_service/README.md`

## Security Note

Do not commit real credentials or tokens in compose/environment files. Keep secrets in local `.env` or a secret manager.
