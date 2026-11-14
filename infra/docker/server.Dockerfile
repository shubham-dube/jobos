FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps/server ./apps/server
COPY apps/runner/pyproject.toml ./apps/runner/pyproject.toml
COPY apps/runner/src ./apps/runner/src
RUN uv sync --frozen --no-dev --package jobos
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["jobos", "serve", "--host", "0.0.0.0", "--port", "8000"]
