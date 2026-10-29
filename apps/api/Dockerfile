FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra postgres --extra s3
COPY . .
RUN uv sync --frozen --no-dev --extra postgres --extra s3
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "sowa.main:app", "--host", "0.0.0.0", "--port", "8000"]
