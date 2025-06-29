FROM python:3.12-slim AS base

LABEL maintainer="Mehmet Baykar"
LABEL description="OpenAI-compatible API wrapper for POE"
LABEL version="0.5.0"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

ENV HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=1 \
    LOG_LEVEL=info \
    ENABLE_HEALTHCHECK=true

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    lsof \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

COPY docker/requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY docker/app/ ./app/
COPY docker/start.sh .

RUN chmod +x start.sh

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app \
    && mkdir -p /app/tmp /app/logs \
    && chown -R app:app /app

USER app

EXPOSE 8000

# Health check (optional - controlled by ENABLE_HEALTHCHECK env var)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD if [ "$ENABLE_HEALTHCHECK" = "true" ]; then \
          curl -f http://localhost:${PORT:-8000}/health || exit 1; \
        else \
          exit 0; \
        fi

CMD ["./start.sh"]
