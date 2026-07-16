FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements-server.txt ./
RUN pip install --no-cache-dir -e . && pip install --no-cache-dir -r requirements-server.txt

COPY vibes_api/ ./vibes_api/
COPY server/ ./server/

RUN useradd -m -u 1000 vibes && chown -R vibes:vibes /app
USER vibes

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

CMD ["python", "-m", "server"]
