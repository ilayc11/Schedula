# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install locked runtime dependencies only (no dev deps).
# Copy lock metadata separately so this layer remains cacheable when source changes.
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

ENV PATH="/app/.venv/bin:${PATH}"

# Copy application source after dependency install to maximize layer cache hits.
COPY src/ ./src/

EXPOSE 8000

ENV PYTHONUNBUFFERED=1


# Run the backend
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
