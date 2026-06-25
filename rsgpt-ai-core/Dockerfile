# Simple Dockerfile for ECR deployment
FROM python:3.13-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==1.8.3

# Configure Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=1

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --only=main --no-root

# Copy application code
COPY . .

# Expose port
EXPOSE 8090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:8090/health || exit 1

# Default: single worker (safe for WebSockets)
# Override with: docker run -e UVICORN_WORKERS=4 ...
ENV UVICORN_WORKERS=1

# Start the application
# For production with multiple workers, set UVICORN_WORKERS environment variable
# Note: With multiple workers, WebSockets require ALB sticky sessions
CMD ["poetry", "run", "start"]
