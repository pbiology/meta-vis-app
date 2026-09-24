FROM python:3.14-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv

# The venv lives at /opt/venv, NOT uv's default /app/.venv: docker-compose
# bind-mounts ./backend over /app, which would hide a venv stored there.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_CACHE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-build --no-install-project --extra dev

COPY app ./app
COPY load_taxonomy.py ./
COPY mongo-init.js ./
COPY outbreak_configs.json ./
COPY controls_taxa.json ./

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]