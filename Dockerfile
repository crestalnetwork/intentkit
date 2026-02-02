# Build stage
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies with app group (excludes dev-only tools like pytest, ruff)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --group app --no-install-project

# Copy the rest of the project
COPY . .

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --group app

# Runtime stage
FROM python:3.13-slim AS runtime

# Install runtime dependencies only
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --from=builder /app/intentkit /app/intentkit
COPY --from=builder /app/app /app/app
COPY --from=builder /app/scripts /app/scripts

ARG RELEASE
ENV RELEASE=$RELEASE
ENV PATH="/app/.venv/bin:$PATH"

# Command to run the application
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "80"]
