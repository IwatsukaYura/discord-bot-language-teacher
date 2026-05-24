FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/

RUN useradd -m -u 1000 bot && \
    mkdir -p /app/data && \
    chown -R bot:bot /app

USER bot

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV PATH=/app/.venv/bin:$PATH

CMD ["python", "src/main.py"]
