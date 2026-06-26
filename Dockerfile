FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml README.md ./
COPY src ./src

RUN uv sync --no-dev --production

# ── runtime ───────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app
COPY config ./config

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -sf http://localhost:9091/health || exit 1

EXPOSE 9090 9091 9092

CMD ["kater", "serve", "--host", "0.0.0.0"]
