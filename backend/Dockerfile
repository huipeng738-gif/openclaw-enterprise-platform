FROM ghcr.io/astral-sh/uv:0.12.17 AS uv
FROM python:3.12-slim
WORKDIR /srv
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
ENV UV_PYTHON_DOWNLOADS=never UV_NO_DEV=1
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
ENV PATH="/srv/.venv/bin:$PATH"
CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8100"]
