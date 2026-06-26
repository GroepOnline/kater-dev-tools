FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.7.8 /uv /usr/local/bin/uv
COPY pyproject.toml README.md ./
COPY src ./src

RUN uv sync --no-dev --production

# ── runtime ───────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -u 10001 kater

COPY --from=builder /app /app
COPY config ./config

USER kater

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -sf http://localhost:9091/health || exit 1

EXPOSE 9090 9091 9092

CMD ["kater", "serve", "--host", "0.0.0.0"]
