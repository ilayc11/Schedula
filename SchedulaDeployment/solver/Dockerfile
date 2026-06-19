FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy dependency definition
COPY pyproject.toml ./

# Install dependencies (including optional 'test' group for testing)
# We use --system to install into the container's system python
RUN uv pip install --system --no-cache -r pyproject.toml
RUN uv pip install --system --no-cache ".[test]"

# Copy source code and tests
COPY src/ ./src/

# Run the solver
CMD ["python", "-m", "src.main"]
