FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    DAGSTER_HOME=/app/.dagster_home

# Install dependencies first for layer caching, then the project itself.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev && mkdir -p /app/.dagster_home /app/data

EXPOSE 3000
CMD ["uv", "run", "dagster", "dev", "-h", "0.0.0.0", "-p", "3000"]
