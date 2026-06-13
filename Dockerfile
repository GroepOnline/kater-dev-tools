FROM python:3.12-slim

ENV UV_LINK_MODE=copy
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml README.md ./
COPY src ./src

RUN uv sync --no-dev

EXPOSE 9090
CMD ["uv", "run", "kater", "mcp", "serve"]
