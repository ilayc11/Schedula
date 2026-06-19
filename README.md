# Schedula

Schedula is a course scheduling system organized into three main repositories:

- [SchedulaBackend](SchedulaBackend/README.md): FastAPI backend for authentication, APIs, PostgreSQL access, RabbitMQ messaging, LLM-based constraint processing, WebSocket progress updates, and scheduled automation.
- [SchedulaDeployment](SchedulaDeployment/README.md): Docker Compose orchestration, solver service, notification service, and end-to-end integration tests.
- [SchedulaFrontend](SchedulaFrontend/README.md): React + Vite frontend for lecturer and secretary workflows.

This repository is the umbrella home for the full Schedula workspace. It mirrors the three component repositories above and serves as the top-level entry point for the stack.

## Project Overview

- Backend handles authentication, APIs, persistence, solver requests, notification events, and scheduler jobs.
- Deployment wires together PostgreSQL, RabbitMQ, backend, solver, notification service, frontend, and optional GPU/runtime services.
- Frontend provides the lecturer and secretary user interface for login, constraint management, schedule views, and breaking-constraints dashboards.

## Repository Layout

```text
Schedula/
	README.md
	SchedulaBackend/
	SchedulaDeployment/
	SchedulaFrontend/
```

## Common Development Flow

1. Use SchedulaBackend for API, database, and backend logic.
2. Use SchedulaDeployment for orchestration, solver, notification service, and integration testing.
3. Use SchedulaFrontend for UI work and client-side behavior.

## Documentation

- Backend details: [SchedulaBackend/README.md](SchedulaBackend/README.md)
- Deployment and orchestration: [SchedulaDeployment/README.md](SchedulaDeployment/README.md)
- Frontend details: [SchedulaFrontend/README.md](SchedulaFrontend/README.md)
- Solver documentation: [SchedulaDeployment/SOLVER_DOCUMENTATION.md](SchedulaDeployment/SOLVER_DOCUMENTATION.md)

## Notes

- The backend uses JWT-based role control for lecturer and secretary routes.
- The deployment stack includes PostgreSQL, RabbitMQ, solver, notification service, and frontend services.
- The frontend supports lecturer and secretary routes, schedule views, constraint workflows, and breaking-constraints dashboards.

## Getting Started

For day-to-day development, work in the repository that matches the area you need to change:

- API and backend logic: SchedulaBackend
- Infrastructure and service orchestration: SchedulaDeployment
- UI and client behavior: SchedulaFrontend
