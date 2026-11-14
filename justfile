set dotenv-load := true

# install everything (Python workspace + web)
bootstrap:
    uv sync --all-packages
    cd apps/web && pnpm install

# start Postgres
db:
    docker compose up -d postgres

migrate:
    uv run jobos migrate

# API + workers (DBOS) on :8000
server:
    uv run jobos serve --role all

web:
    cd apps/web && pnpm dev

# local runner (real Chrome)
runner:
    uv run jobos-runner run

test:
    uv run pytest -q

lint:
    uv run ruff check .
    cd apps/web && pnpm lint && pnpm typecheck
