# Dockerfile for vibes-api server
# Multi-stage build for smaller image

FROM python:3.12-slim AS base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY pyproject.toml requirements-server.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir -r requirements-server.txt

# Copy application code
COPY vibes_api/ ./vibes_api/
COPY server/ ./server/

# Create a non-root user
RUN useradd -m -u 1000 vibes && chown -R vibes:vibes /app
USER vibes

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Run the server
CMD ["python", "-m", "server"]
